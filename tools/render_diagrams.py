"""Render every .mmd diagram in a folder to PNG.

Usage:
    venv\\Scripts\\python.exe tools\\render_diagrams.py docs\\final-project\\diagrams

Why this exists instead of `npx @mermaid-js/mermaid-cli`:
  * it renders offline (mermaid.min.js is vendored in tools/vendor/), which
    matters when the presentation laptop has no internet in the room;
  * it reuses the Playwright Chromium the project already installed, so there is
    no Node install or 300 MB Puppeteer download involved;
  * it renders each diagram at 3x, so the PNG stays sharp when it is dropped
    into the 2-4 page Summary document or zoomed on a projector.

The .mmd files stay the source of truth: edit the text, re-run this script.
"""

from __future__ import annotations

import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

MERMAID_JS = pathlib.Path(__file__).with_name("vendor") / "mermaid.min.js"
SCALE = 3
PAD = 24

PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  html, body { margin:0; padding:0; background:#ffffff; }
  #out { display:inline-block; }
  #out svg { display:block; }
</style>
<script>__MERMAID__</script>
</head><body><div id="out"></div></body></html>
"""

RENDER = """
async (source) => {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'base',
    themeVariables: {
      fontFamily: 'Segoe UI, Arial, Helvetica, sans-serif',
      fontSize: '14px',
      primaryColor: '#ffffff',
      primaryTextColor: '#3a2a20',
      primaryBorderColor: '#c1592a',
      lineColor: '#8c4a2f',
      tertiaryColor: '#eef2f7'
    },
    flowchart: { htmlLabels: true, useMaxWidth: false, curve: 'basis' },
    er: { useMaxWidth: false }
  });
  const id = 'diagram-' + Math.random().toString(36).slice(2);
  const { svg } = await mermaid.render(id, source);
  const out = document.getElementById('out');
  out.innerHTML = svg;
  const el = out.querySelector('svg');
  el.removeAttribute('width');
  el.removeAttribute('height');
  el.removeAttribute('style');
  const box = el.viewBox.baseVal;
  el.setAttribute('width', box.width);
  el.setAttribute('height', box.height);
  return { width: box.width, height: box.height };
}
"""


def render_all(folder: pathlib.Path) -> int:
    files = sorted(folder.glob("*.mmd"))
    if not files:
        print(f"no .mmd files in {folder}")
        return 1
    if not MERMAID_JS.exists():
        print(f"missing {MERMAID_JS} - the vendored Mermaid build is required")
        return 1

    page_html = PAGE.replace("__MERMAID__", MERMAID_JS.read_text(encoding="utf-8"))
    failures = 0

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=SCALE)

        for source_file in files:
            target = source_file.with_suffix(".png")
            try:
                page.set_viewport_size({"width": 2400, "height": 1800})
                page.set_content(page_html, wait_until="load")
                size = page.evaluate(RENDER, json.loads(json.dumps(source_file.read_text(encoding="utf-8"))))
                width = int(size["width"]) + PAD * 2
                height = int(size["height"]) + PAD * 2
                page.set_viewport_size({"width": max(width, 400), "height": max(height, 300)})
                page.locator("#out svg").screenshot(path=str(target))
                print(f"  {source_file.name}  ->  {target.name}  ({width}x{height} @{SCALE}x)")
            except Exception as exc:  # keep going: one bad diagram must not hide the others
                failures += 1
                print(f"  FAILED {source_file.name}: {type(exc).__name__}: {exc}")

        browser.close()

    print(f"{len(files) - failures}/{len(files)} diagrams rendered into {folder}")
    return 1 if failures else 0


if __name__ == "__main__":
    target_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("docs/final-project/diagrams")
    if not target_dir.is_dir():
        print(f"not a folder: {target_dir}")
        raise SystemExit(1)
    raise SystemExit(render_all(target_dir))

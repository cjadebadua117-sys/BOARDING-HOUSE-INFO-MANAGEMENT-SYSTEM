"""Targeted cascade + contrast checker for a single selector.

Answers two questions the bulk audit cannot answer on its own:

1. *Which* rule wins? The five stacked stylesheets fight each other with
   `!important` and load order, so a failing chip is usually a specificity
   problem, not a colour problem. This enumerates every rule in
   `document.styleSheets` that sets `color` / `background*` on the selector
   and reports selector text, specificity, source sheet and importance.
2. What is the *real* background? Computed styles cannot see a photograph,
   gradient or a fixed scene layer, so the element's own box is screenshotted
   and the dominant pixel colour behind the glyphs is sampled with PIL.

Usage:
    ./venv/Scripts/python.exe tools/ui_check.py \
        --base-url http://127.0.0.1:8020 --theme dark \
        --page /search/ --selector "span.badge-bhims-verified"
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter

from PIL import Image
from playwright.sync_api import sync_playwright

DEFAULT_CREDS = {"student": "UiAudit2026!", "landlord": "UiAudit2026!", "root": "UiAudit2026!"}

RULE_JS = r"""
(selector) => {
  const propRe = /^(color|background|background-color|background-image)$/;
  // Specificity of a selector *list* is the max over its compounds — counting
  // every class in the whole rule would inflate `.a, .b, .c` into (0,3,0).
  const one = sel => {
    let ids = 0, cls = 0, typ = 0;
    (sel.match(/#[\w-]+/g) || []).forEach(() => ids++);
    (sel.match(/\.[\w-]+/g) || []).forEach(() => cls++);
    (sel.match(/\[[^\]]+\]/g) || []).forEach(() => cls++);
    (sel.match(/:(?!:)[\w-]+/g) || []).forEach(() => cls++);
    (sel.match(/(^|[\s>+~])([a-zA-Z][\w-]*)/g) || []).forEach(() => typ++);
    return [ids, cls, typ];
  };
  const spec = sel => sel.split(',').map(one).reduce(
    (best, s) => (s[0] > best[0] || (s[0] === best[0] && s[1] > best[1]) ||
                  (s[0] === best[0] && s[1] === best[1] && s[2] > best[2])) ? s : best,
    [0, 0, 0]);
  const out = [];
  let order = 0;
  const walk = (rules, sheetName) => {
    for (const rule of rules) {
      order++;
      // Style rules expose an empty `cssRules` (CSS nesting), so check for a
      // selector first and only descend into real group rules (@media etc.).
      if (!rule.selectorText) {
        if (rule.cssRules && rule.cssRules.length) walk(rule.cssRules, sheetName);
        continue;
      }
      if (!rule.style) continue;
      if (!rule.selectorText.includes(selector.split('.').pop())) continue;
      for (const prop of Array.from(rule.style)) {
        if (!propRe.test(prop)) continue;
        out.push({
          sheet: sheetName, selector: rule.selectorText, prop,
          value: rule.style.getPropertyValue(prop),
          important: rule.style.getPropertyPriority(prop) === 'important',
          spec: spec(rule.selectorText), order
        });
      }
    }
  };
  for (const sheet of document.styleSheets) {
    let name = (sheet.href || 'inline').split('/').pop();
    if (name.includes('?')) name = name.split('?')[0];
    try { walk(sheet.cssRules, name); } catch (e) { /* cross-origin */ }
  }
  return out;
}
"""

COMPUTED_JS = r"""
(selector) => {
  const el = document.querySelector(selector);
  if (!el) return null;
  const cs = getComputedStyle(el);
  const r = el.getBoundingClientRect();
  return {
    tag: el.tagName.toLowerCase(),
    text: (el.textContent || '').trim().slice(0, 60),
    color: cs.color, background: cs.backgroundColor, image: cs.backgroundImage,
    fontSize: parseFloat(cs.fontSize), weight: parseInt(cs.fontWeight, 10) || 400,
    ratioDeclared: cs.getPropertyValue('--ce-ok-ink').trim() || null,
    rect: { x: r.x, y: r.y, w: r.width, h: r.height }
  };
}
"""


def parse_rgb(value: str):
    m = re.match(r"rgba?\(([^)]+)\)", value or "")
    if not m:
        return None
    parts = [float(v.strip()) for v in m.group(1).replace("/", " ").split(",")]
    a = parts[3] if len(parts) > 3 else 1.0
    return parts[0], parts[1], parts[2], a


def channel(v: float) -> float:
    v /= 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    return 0.2126 * channel(rgb[0]) + 0.7152 * channel(rgb[1]) + 0.0722 * channel(rgb[2])


def ratio(a, b) -> float:
    l1, l2 = luminance(a), luminance(b)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def dominant(png: bytes):
    """Most common colour in a box.

    Sampling a box that still contains glyphs mostly measures antialiasing, so
    the caller hides the ink before shooting; what is left is the backdrop.
    """
    img = Image.open(io.BytesIO(png)).convert("RGB")
    counts = Counter(img.getdata())
    return counts.most_common(1)[0][0] if counts else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8020")
    ap.add_argument("--page", required=True)
    ap.add_argument("--selector", required=True)
    ap.add_argument("--theme", default="dark", choices=["dark", "light"])
    ap.add_argument("--user", default=None, choices=["student", "landlord", "root"])
    ap.add_argument("--viewport", default="1280x900")
    ap.add_argument("--channel", default="msedge")
    args = ap.parse_args()

    width, height = (int(v) for v in args.viewport.lower().split("x"))
    base = args.base_url.rstrip("/")
    # Git-Bash rewrites a leading "/" argument into a Windows path, so accept
    # "search/" as well as "/search/" and rebuild the URL ourselves.
    path = args.page
    if ":" in path:  # Git-Bash already rewrote it, or a full URL was passed
        raise SystemExit(f"path looks rewritten by Git-Bash: {path!r} — set MSYS_NO_PATHCONV=1")
    if not path.startswith("/"):
        path = "/" + path

    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.channel, headless=True)
        ctx = browser.new_context(viewport={"width": width, "height": height})
        page = ctx.new_page()
        if args.user:
            creds = DEFAULT_CREDS[args.user]
            page.goto(f"{base}/accounts/login/", wait_until="networkidle")
            page.fill("input[name='username']", args.user)
            page.fill("input[name='password']", creds)
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle")
        page.goto(base + path, wait_until="networkidle")
        if args.theme == "dark":
            page.evaluate(
                "() => { document.documentElement.setAttribute('data-theme','dark');"
                " document.documentElement.classList.remove('light');"
                " document.documentElement.classList.add('dark'); }"
            )
            page.wait_for_timeout(400)
        computed = page.evaluate(COMPUTED_JS, args.selector)
        if not computed:
            print(json.dumps({"error": f"no element for {args.selector}"}, indent=2))
            return 1
        rules = page.evaluate(RULE_JS, args.selector)
        handle = page.query_selector(args.selector)
        if handle:
            # Hiding the glyph ink leaves the box's true backdrop: this is the
            # only way to see a photograph, gradient or fixed scene layer that
            # computed styles cannot report.
            handle.evaluate(
                "el => { el.style.setProperty('color','transparent','important');"
                " el.style.setProperty('text-shadow','none','important');"
                " el.querySelectorAll('i,svg,path').forEach(k => k.style.setProperty('color','transparent','important')); }"
            )
            png = handle.screenshot()
            handle.evaluate(
                "el => { el.style.removeProperty('color'); el.style.removeProperty('text-shadow');"
                " el.querySelectorAll('i,svg,path').forEach(k => { k.style.removeProperty('color'); }); }"
            )
        else:
            png = None

    # Rules that can actually win: important beats non-important, then
    # specificity, then document order (later sheet = later).
    def key(rule):
        return (1 if rule["important"] else 0, tuple(rule["spec"]), rule["order"])

    rules.sort(key=key)
    # Sorted ascending, so the *last* writer per property is the effective one.
    winners = {prop: None for prop in ("color", "background-color")}
    for rule in rules:
        target = "color" if rule["prop"] == "color" else "background-color"
        winners[target] = rule

    ink = parse_rgb(computed["color"])
    bg = dominant(png) if png else None
    result = {
        "page": path,
        "theme": args.theme,
        "selector": args.selector,
        "element": computed,
        "pixelBackground": f"rgb{bg}" if bg else None,
        "pixelRatio": round(ratio(ink[:3], bg), 2) if (bg and ink) else None,
        "rulesFound": len(rules),
        "winner": winners,
        "allRules": rules[-6:],
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())

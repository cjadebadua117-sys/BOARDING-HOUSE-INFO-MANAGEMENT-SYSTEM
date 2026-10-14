"""Find pages that render their data as bare text instead of visualising it.

`ui_audit.py` asks "is this page accessible?". This asks a different question:
does the page *show* anything? A page whose whole content is a run of plain
labels and values scores badly here even when every contrast ratio passes,
because the reader has to read and mentally pair every field themselves.

Signals measured in the live DOM:

  * ratio of text to visual elements (icons, images, avatars, badges)
  * how much of the content area is painted (backgrounds, borders, radius,
    shadows) versus bare text
  * rows that carry an image/avatar vs rows that are text only
  * unstyled leftovers: default-styled buttons, links the same colour as body
    copy, tables with no card/row treatment

Usage (dev server must already be running):

    ./venv/Scripts/python.exe tools/explore_visual.py --base-url http://127.0.0.1:8021
    ./venv/Scripts/python.exe tools/explore_visual.py --theme dark --shots .audit/shots
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

DESKTOP = {"width": 1440, "height": 900}

PAGES = [
    ("public", None, "/"),
    ("public", None, "/listings/"),
    ("public", None, "/listings/26/"),
    ("public", None, "/listings/32/"),
    ("public", None, "/search/?q=room"),
    ("public", None, "/users/6/"),
    ("student", "demo_student01", "/students/dashboard/"),
    ("student", "demo_student01", "/students/inquiries/"),
    ("student", "demo_student01", "/students/inquiries/1/"),
    ("student", "demo_student01", "/students/bookings/"),
    ("student", "demo_student01", "/profile/"),
    ("student", "demo_student01", "/profile/edit/"),
    ("landlord", "demo_landlord", "/landlords/dashboard/"),
    ("landlord", "demo_landlord", "/landlords/inquiries/"),
    ("landlord", "demo_landlord", "/landlords/inquiries/1/"),
    ("landlord", "demo_landlord", "/landlords/bookings/"),
    ("landlord", "demo_landlord", "/landlords/ratings/"),
    ("landlord", "demo_landlord", "/landlords/boarding-houses/"),
    ("landlord", "demo_landlord", "/landlords/boarding-houses/26/"),
    ("landlord", "demo_landlord", "/landlords/boarding-houses/26/rooms/add/"),
    ("admin", "root", "/admin/dashboard/"),
    ("admin", "root", "/admin/analytics/"),
    ("admin", "root", "/admin/landlords/"),
    ("admin", "root", "/admin/landlords/6/"),
    ("admin", "root", "/admin/students/"),
    ("admin", "root", "/admin/ratings/"),
    ("admin", "root", "/admin/reports/"),
    ("admin", "root", "/admin/settings/"),
    ("admin", "root", "/admin/barangays/"),
    ("admin", "root", "/admin/listings/pending/"),
]

SCORE_JS = r"""
() => {
  // Scope to the page's own content. `main` still contains the app shell's
  // nav in some templates, and the sidebar alone contributes ~6,000
  // characters of boilerplate -- which flattered every page equally and hid
  // exactly the differences this tool exists to find.
  const main = document.querySelector('.app-content')
           || document.querySelector('main')
           || document.querySelector('#main-content')
           || document.body;
  const vis = el => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.15) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };

  const icons = main.querySelectorAll('i[class*="bi-"], svg, .icon, [class*="icon"]').length;
  const images = main.querySelectorAll('img').length;
  const avatars = main.querySelectorAll('[class*="avatar"], img.rounded-circle, img[class*="profile"]').length;

  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'HEAD']);

  // Text nodes with real words in them -- the mass the reader has to digest.
  // Style/script bodies are text nodes too, and several templates embed a
  // whole stylesheet or script inside the content block; counting those made
  // /profile/ look like it had 23,000 characters of prose when it has ~290.
  let textNodes = 0, textChars = 0;
  const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT, {
    acceptNode: node => SKIP.has(node.parentElement && node.parentElement.tagName)
      ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
  });
  let n;
  while ((n = walker.nextNode())) {
    const t = (n.textContent || '').trim();
    if (t.length > 2) { textNodes++; textChars += t.length; }
  }

  // Elements that carry any visible paint of their own.
  const all = Array.from(main.querySelectorAll('*')).filter(
    el => vis(el) && !SKIP.has(el.tagName));
  const painted = all.filter(el => {
    const cs = getComputedStyle(el);
    return (cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)')
        || cs.backgroundImage !== 'none'
        || (cs.borderTopWidth !== '0px' && cs.borderTopStyle !== 'none')
        || (cs.boxShadow && cs.boxShadow !== 'none');
  }).length;

  // Repeated content rows: how many of them carry a picture?
  const rowSel = 'tbody tr, .card, article, .list-group-item, .booking-item, .message-row, .stat-card';
  const rows = Array.from(main.querySelectorAll(rowSel)).filter(vis);
  const rowsWithMedia = rows.filter(r =>
    r.querySelector('img, svg, [class*="avatar"]')).length;

  // Links that are visually indistinguishable from surrounding body text.
  const bodyColour = getComputedStyle(main).color;
  const plainLinks = Array.from(main.querySelectorAll('a[href]')).filter(vis).filter(a => {
    const cs = getComputedStyle(a);
    return cs.color === bodyColour && cs.textDecorationLine === 'none';
  }).length;
  const links = Array.from(main.querySelectorAll('a[href]')).filter(vis).length;

  // Font variety: one font family across the page means unstyled fallback.
  const families = new Set(all.map(el => getComputedStyle(el).fontFamily.split(',')[0].trim()));

  return {
    textNodes, textChars, icons, images, avatars, elements: all.length,
    painted, rows: rows.length, rowsWithMedia, links, plainLinks,
    families: Array.from(families),
    h1: (document.querySelector('h1') || {}).textContent || '',
  };
}
"""


def score(d: dict) -> tuple[float, list[str]]:
    """0 = nothing visual at all, 100 = richly visualised."""
    reasons: list[str] = []
    if d["textChars"] == 0:
        return 100.0, ["page has no text at all"]

    # Visual mass per 1000 characters of text.
    per_1k = 1000.0 / max(d["textChars"], 1)
    visual = d["icons"] + d["images"] * 2 + d["avatars"] * 2
    visual_density = visual * per_1k
    painted_density = d["painted"] * per_1k

    s = 0.0
    s += min(40.0, visual_density * 12)
    s += min(30.0, painted_density * 1.4)

    if d["rows"]:
        media_ratio = d["rowsWithMedia"] / d["rows"]
        s += media_ratio * 20
        if media_ratio == 0:
            reasons.append(f"none of {d['rows']} repeated rows carries an image or avatar")
    else:
        s += 8  # no repeated rows to visualise

    if d["links"]:
        plain_ratio = d["plainLinks"] / d["links"]
        s += (1 - plain_ratio) * 10
        if plain_ratio > 0.5:
            reasons.append(f"{d['plainLinks']}/{d['links']} links look like plain body text")

    if len(d["families"]) <= 1:
        s -= 10
        reasons.append("a single font family across the whole page")

    if d["textChars"] > 2500 and (d["icons"] + d["images"]) < 4:
        reasons.append(f"{d['textChars']} characters with only "
                       f"{d['icons'] + d['images']} visual elements")

    return max(0.0, min(100.0, s)), reasons


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="http://127.0.0.1:8021")
    ap.add_argument("--theme", choices=["light", "dark"], default="light")
    ap.add_argument("--shots")
    ap.add_argument("--channel", default="msedge")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    from explore_flows import django_ready, make_sessions

    base = args.base_url.rstrip("/")
    django_ready()
    sessions = make_sessions(["demo_student01", "demo_landlord", "root"], base)
    rows = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=args.channel, headless=True)
        for _label, who, path in PAGES:
            ctx = browser.new_context(viewport=DESKTOP, color_scheme="light", reduced_motion="reduce")
            ctx.add_init_script(
                "try { localStorage.setItem('bhims-theme', '%s');"
                " localStorage.setItem('bhims-theme-version', 'teal-v2'); } catch (e) {}" % args.theme
            )
            if who:
                if who not in sessions:
                    print(f"!! no session for {who!r}", file=sys.stderr)
                    ctx.close()
                    continue
                ctx.add_cookies([sessions[who]])
            page = ctx.new_page()
            try:
                page.goto(base + path, wait_until="load", timeout=25000)
                page.wait_for_timeout(700)
                d = page.evaluate(SCORE_JS)
                s, reasons = score(d)
                rows.append({"path": path, "role": who or "anon", "score": round(s, 1), **d})
                if args.shots:
                    os.makedirs(args.shots, exist_ok=True)
                    safe = path.strip("/").replace("/", "_").replace("?", "-") or "home"
                    page.screenshot(path=f"{args.shots}/{args.theme}-{safe}.png", full_page=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {path}: {type(exc).__name__}: {exc}", file=sys.stderr)
            ctx.close()
        browser.close()

    rows.sort(key=lambda r: r["score"])
    print(f"\n{'score':>6}  {'path':46s} text  icon img rows+media plainLinks")
    for r in rows:
        print(f"{r['score']:6.1f}  {r['path'][:46]:46s} {r['textChars']:5d} "
              f"{r['icons']:4d} {r['images']:3d} {r['rowsWithMedia']:3d}/{r['rows']:<3d} "
              f"{r['plainLinks']:3d}/{r['links']:<3d}")
    print()
    for r in rows[:6]:
        d, _ = score(r)
        print(f"  {r['score']:5.1f}  {r['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
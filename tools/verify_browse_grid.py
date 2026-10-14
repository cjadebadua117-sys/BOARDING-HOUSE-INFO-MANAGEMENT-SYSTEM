"""Verify the browse results grid survives the thing that broke it.

The regression this guards: the AJAX swap target (.browse-results > div) and the
fragment that fills it both carried .listing-grid, so the results header and the
cards grid became two items of the *same* grid — a half-width column of cards
with an empty third column beside them. The swap target is a plain container
now, and the fragment owns the only .listing-grid.

Checks, in a browser: exactly one cards grid, no grid nested in a grid, no
duplicate ids, the header spanning the results column, filter fields wide enough
to type in, and the same again after an AJAX filter change and for the empty
state — plus a phone, where the layout is one column.

The filter panel is checked in the same pass. It is <details open> (desktop and
no-JS keep the whole panel) that collapses to a single tappable row on small
screens, where an always-open panel is a full screen of fields with no boarding
house in sight. On desktop it is a bar spanning the results column above the
grid — as a 320px sidebar it was taller than the viewport and hid its own Apply
button below the fold.

Usage:
    ./venv/Scripts/python.exe tools/verify_browse_grid.py --base http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import sys

from playwright.sync_api import sync_playwright

PROBE = """
() => {
  const frag = document.getElementById('listingFragment');
  const cards = document.querySelector('#listingGrid');
  const header = document.querySelector('.results-header');
  const ids = [...document.querySelectorAll('[id]')].map((e) => e.id);
  const field = document.querySelector('#filterForm .col-6 input, #filterForm .col-12 input');
  return {
    hasFragment: !!frag,
    fragmentIsGrid: frag ? getComputedStyle(frag).display === 'grid' : null,
    fragmentChildren: frag ? [...frag.children].map((el) => el.className || el.tagName) : [],
    grids: [...document.querySelectorAll('.listing-grid')]
      .filter((g) => g.id !== 'listingSkeleton')
      .map((g) => ({ id: g.id, x: Math.round(g.getBoundingClientRect().x), w: Math.round(g.getBoundingClientRect().width) })),
    nested: document.querySelectorAll('.listing-grid .listing-grid').length,
    dupIds: ids.filter((v, i) => ids.indexOf(v) !== i),
    header: header ? Math.round(header.getBoundingClientRect().width) : null,
    resultsWidth: (() => { const r = document.querySelector('.browse-results'); return r ? Math.round(r.getBoundingClientRect().width) : null; })(),
    cards: cards ? cards.querySelectorAll('.result-card:not(.skeleton-card)').length : 0,
    empty: (() => { const e = document.querySelector('.results-empty'); return e ? Math.round(e.getBoundingClientRect().width) : null; })(),
    fieldWidth: field ? Math.round(field.getBoundingClientRect().width) : null,
    url: location.search,
    panel: (() => {
      const el = document.getElementById('filterPanel');
      if (!el) return null;
      const form = document.getElementById('filterForm');
      const card = document.querySelector('.listing-card');
      const res = document.querySelector('.browse-results');
      const chev = el.querySelector('.filter-card-chevron');
      return {
        tag: el.tagName,
        open: el.open === true,
        firstChild: el.firstElementChild ? el.firstElementChild.tagName : null,
        h: Math.round(el.getBoundingClientRect().height),
        x: Math.round(el.getBoundingClientRect().x),
        w: Math.round(el.getBoundingClientRect().width),
        bottom: Math.round(el.getBoundingClientRect().bottom),
        resultsX: res ? Math.round(res.getBoundingClientRect().x) : null,
        resultsW: res ? Math.round(res.getBoundingClientRect().width) : null,
        resultsTop: res ? Math.round(res.getBoundingClientRect().top) : null,
        applyBottom: (() => {
          const b = document.querySelector('#filterForm button[type="submit"]');
          return b ? Math.round(b.getBoundingClientRect().bottom) : null;
        })(),
        formH: form ? Math.round(form.getBoundingClientRect().height) : null,
        chevron: chev ? getComputedStyle(chev).display : null,
        firstCardTop: card ? Math.round(card.getBoundingClientRect().top) : null,
        viewportH: window.innerHeight,
        missingIds: ['filterForm', 'listingFragment', 'listingSkeleton', 'filterStatus']
          .filter((id) => !document.getElementById(id)),
        scrolls: document.documentElement.scrollWidth > window.innerWidth + 1,
      };
    })(),
  };
}
"""

checks: list[tuple[bool, str]] = []


def check(ok, label: str) -> None:
    checks.append((bool(ok), label))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


def one_grid(snap, where: str, cards_grid: bool = True) -> None:
    """The results column holds at most one cards grid, never a grid in a grid.

    `cards_grid=False` is the empty state, which correctly has none — only the
    empty panel, which must still span the column.
    """
    expect = 1 if cards_grid else 0
    check(len(snap["grids"]) == expect, f"{where}: {expect} cards grid ({len(snap['grids'])})")
    check(snap["nested"] == 0, f"{where}: no grid nested inside a grid ({snap['nested']})")
    check(not snap["dupIds"], f"{where}: no duplicate ids ({(snap['dupIds'] or ['none'])[:3]})")
    check(snap["fragmentIsGrid"] is False, f"{where}: the swap target is a plain container, not a grid")
    if snap["grids"]:
        g = snap["grids"][0]
        check(g["id"] == "listingGrid", f"{where}: the grid is the fragment's own (#{g['id']})")
        check(snap["resultsWidth"] and abs(g["w"] - snap["resultsWidth"]) <= 2,
              f"{where}: the cards grid spans the results column ({g['w']}px of {snap['resultsWidth']}px)")
        if snap["header"] is not None:
            check(abs(snap["header"] - g["w"]) <= 2,
                  f"{where}: the header spans it too ({snap['header']}px vs {g['w']}px)")


def panel_placement(snap, where: str, collapsed: bool) -> None:
    """The filter panel must not own the first screen, and must not vanish.

    Open is the markup's own default, so a visitor without JavaScript — and
    every desktop screen — keeps the whole panel; on one column it collapses to
    a single tappable row instead of a screenful of fields above the listings.
    """
    p = snap["panel"]
    check(bool(p), f"{where}: the filter panel is on the page")
    if not p:
        return
    check(p["tag"] == "DETAILS", f"{where}: the panel is a disclosure (got <{p['tag']}>)")
    check(p["firstChild"] == "SUMMARY", f"{where}: its first child is the summary row")
    check(not p["missingIds"], f"{where}: the ids the browse script grabs still exist (missing {p['missingIds']})")
    check(p["scrolls"] is False, f"{where}: the page does not scroll sideways")
    if collapsed:
        check(p["open"] is False, f"{where}: it starts collapsed")
        check(p["h"] <= 90, f"{where}: collapsed it is one row ({p['h']}px)")
        check(p["chevron"] != "none", f"{where}: the chevron that says it opens is shown")
        check(p["firstCardTop"] is not None and p["firstCardTop"] < p["viewportH"],
              f"{where}: a listing is visible without scrolling (card at {p['firstCardTop']}px of {p['viewportH']}px)")
    else:
        check(p["open"] is True, f"{where}: it is open")
        check(p["formH"] and p["formH"] > 100, f"{where}: the fields are laid out ({p['formH']}px)")
        check(p["chevron"] == "none", f"{where}: no collapse chevron on desktop")
        # The bar owns the top of the results column, not a 320px column beside
        # it, and every control on it — including Apply — stays on screen. As a
        # sidebar it was 638px tall in a 768px viewport: its own Apply button sat
        # below the fold while every card was squeezed to 283px.
        check(p["w"] and p["resultsW"] and abs(p["w"] - p["resultsW"]) <= 2,
              f"{where}: the bar spans the results width ({p['w']}px of {p['resultsW']}px)")
        check(p["bottom"] is not None and p["resultsTop"] is not None and p["bottom"] <= p["resultsTop"] + 2,
              f"{where}: it sits above the listing grid (bar ends {p['bottom']}px, grid column starts {p['resultsTop']}px)")
        check(p["h"] < p["viewportH"] * 0.5,
              f"{where}: it is a bar, not a column ({p['h']}px of {p['viewportH']}px)")
        check(p["applyBottom"] is not None and p["applyBottom"] < p["viewportH"],
              f"{where}: its Apply button is on screen without scrolling (bottom {p['applyBottom']}px of {p['viewportH']}px)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1366, "height": 768})
        page = ctx.new_page()

        print("\n== the server-rendered page ==")
        page.goto(f"{base}/listings/", wait_until="load")
        page.wait_for_timeout(500)
        start = page.evaluate(PROBE)
        one_grid(start, "first paint")
        check(start["cards"] > 1, f"first paint: real cards are rendered ({start['cards']})")
        check(start["fieldWidth"] and start["fieldWidth"] >= 110,
              f"first paint: a filter field is wide enough to type in ({start['fieldWidth']}px)")
        panel_placement(start, "first paint", collapsed=False)

        print("\n== a filter change (the AJAX swap) ==")
        page.fill("#id_price_max", "900")
        page.wait_for_timeout(1200)
        filtered = page.evaluate(PROBE)
        one_grid(filtered, "after filtering")
        check(filtered["url"] == "?price_max=900", f"after filtering: the URL tracks it ({filtered['url']!r})")
        check(filtered["cards"] and filtered["cards"] < start["cards"],
              f"after filtering: fewer houses are shown ({start['cards']} -> {filtered['cards']})")
        check(any("active-filters" in c for c in filtered["fragmentChildren"]),
              "after filtering: the applied filter arrives as a chip")
        panel_placement(filtered, "after filtering", collapsed=False)

        print("\n== the empty state ==")
        page.fill("#id_price_max", "1")
        page.wait_for_timeout(1200)
        empty = page.evaluate(PROBE)
        one_grid(empty, "empty state", cards_grid=False)
        check(empty["empty"] and empty["resultsWidth"]
              and abs(empty["empty"] - empty["resultsWidth"]) <= 2,
              f"empty state: it spans the results column ({empty['empty']}px)")
        check(empty["fragmentChildren"] == ["results-empty results-empty-filters"],
              f"empty state: it replaces the whole fragment ({empty['fragmentChildren']})")

        print("\n== a phone ==")
        ctx2 = browser.new_context(viewport={"width": 390, "height": 844})
        phone = ctx2.new_page()
        phone.goto(f"{base}/listings/", wait_until="load")
        phone.wait_for_timeout(500)
        small = phone.evaluate(PROBE)
        one_grid(small, "phone")
        check(small["grids"] and small["grids"][0]["x"] < 40,
              f"phone: the grid starts at the page edge (x={small['grids'][0]['x'] if small['grids'] else None})")
        panel_placement(small, "phone", collapsed=True)
        phone.click("#filterPanel > summary")
        phone.wait_for_timeout(250)
        opened = phone.evaluate(PROBE)
        check(opened["panel"]["open"] is True, "phone: tapping the row opens the panel")
        check(opened["panel"]["h"] > 200, f"phone: and the fields are laid out ({opened['panel']['h']}px)")
        ctx2.close()
        ctx.close()
        browser.close()

    failed = [m for ok, m in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    for m in failed:
        print("  FAILED:", m)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

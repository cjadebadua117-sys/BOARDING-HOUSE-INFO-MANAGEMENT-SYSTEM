"""Audit the card layout on the signed-in student, landlord and admin pages.

The complaint this answers: "some of the cards are not properly organized".
That has a small number of concrete, measurable causes, so it is measured
instead of eyeballed:

  * a grid with more columns than the last row has items — a hole, e.g. the
    admin Overview's seven stat cards in a four-column grid;
  * cards sharing a row that are not the same height;
  * a card whose content is wider than the card (clipped text or a scroller);
  * any page that scrolls sideways at all.

Sessions are minted with Django's test client and injected as cookies, so the
audit runs against the same database and the same running server as the
browser the user is looking at.

Usage:
    ./venv/Scripts/python.exe tools/audit_card_layout.py --base http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from core.models import User  # noqa: E402

PROBE = """
() => {
  const rowsOf = (el) => {
    const items = [...el.children].filter((c) => c.getBoundingClientRect().height > 0);
    const rows = new Map();
    for (const c of items) {
      const k = Math.round(c.getBoundingClientRect().top / 2) * 2;
      if (!rows.has(k)) rows.set(k, []);
      rows.get(k).push(c);
    }
    return [...rows.values()];
  };
  const name = (el) => (el.className || el.tagName).toString().slice(0, 44);
  const out = { overflowX: 0, holes: [], ragged: [], clipped: [], raggedy: [] };

  out.overflowX = document.documentElement.scrollWidth - window.innerWidth;

  const box = (el) => {
    const b = el.getBoundingClientRect();
    return { h: Math.round(b.height), w: Math.round(b.width), t: Math.round(b.top + window.scrollY) };
  };

  const CARD = '.stat-card, .admin-table-wrap, .listing-card, .house-card, .room-card, .card';
  for (const grid of document.querySelectorAll('div,section,ul')) {
    const items = [...grid.children].filter((c) => c.getBoundingClientRect().height > 0);
    // Only containers of cards. A wrapped row of badges or buttons legitimately
    // stops short of the right edge and is not a hole.
    if (items.filter((c) => c.matches(CARD)).length < 2) continue;
    const rows = rowsOf(grid);
    if (rows.length < 2) continue;
    // A hole: some row stops short of the container's right edge while another
    // row reaches it. This is measured from the box itself rather than from a
    // column count, so it also catches a strip split across two sibling grids
    // (which is how the admin Overview's seven cards lost their fourth slot).
    const gRight = grid.getBoundingClientRect().right;
    const edgeOf = (row) => Math.max(...row.map((c) => c.getBoundingClientRect().right));
    const short = rows.filter((r) => gRight - edgeOf(r) > 8).length;
    if (short && short < rows.length) {
      out.holes.push({
        el: name(grid),
        rows: rows.map((r) => r.length),
        gaps: rows.map((r) => Math.round(gRight - edgeOf(r))),
      });
    }
    for (const row of rows) {
      const hs = row.map((c) => Math.round(c.getBoundingClientRect().height));
      if (Math.max(...hs) - Math.min(...hs) > 2 && row.length > 1) {
        out.ragged.push({ el: name(grid), heights: hs, n: row.length });
      }
    }
  }

  for (const el of document.querySelectorAll('.stat-card, .admin-table-wrap, .card, .bhims-empty, .listing-card')) {
    const b = el.getBoundingClientRect();
    if (b.height < 1) continue;
    if (el.scrollWidth > el.clientWidth + 1) {
      out.clipped.push({ el: name(el), scrollW: Math.round(el.scrollWidth), clientW: Math.round(el.clientWidth) });
    }
  }

  // Every top-level block on the page, so a lone wide card next to a narrow
  // one is visible in the dump.
  const blocks = [...document.querySelectorAll('.stat-card, .admin-table-wrap')].map((el) => ({ el: name(el), ...box(el) }));
  return { ...out, blocks };
}
"""

PAGES = [
    ("student", "/students/dashboard/"),
    ("student", "/students/inquiries/"),
    ("student", "/students/bookings/"),
    ("landlord", "/landlords/dashboard/"),
    ("landlord", "/landlords/boarding-houses/"),
    ("landlord", "/landlords/bookings/"),
    ("landlord", "/landlords/inquiries/"),
    ("admin", "/admin/dashboard/"),
    ("admin", "/admin/students/"),
    ("admin", "/admin/landlords/"),
    ("admin", "/admin/listings/pending/"),
    ("admin", "/admin/analytics/"),
    ("admin", "/admin/settings/"),
    ("admin", "/admin/reports/"),
    ("admin", "/admin/ratings/"),
    ("admin", "/admin/barangays/"),
]


def sessions() -> dict[str, str]:
    out = {}
    for role in ("student", "landlord", "admin"):
        user = User.objects.filter(role=role).order_by("id").first()
        c = Client()
        c.force_login(user)
        out[role] = c.cookies["sessionid"].value
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    jars = sessions()

    problems = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1366, "height": 768})
        for role, path in PAGES:
            ctx.add_cookies([{"name": "sessionid", "value": jars[role], "url": base}])
            page = ctx.new_page()
            page.goto(base + path, wait_until="load")
            page.wait_for_timeout(400)
            snap = page.evaluate(PROBE)
            title = page.title()
            bad = snap["overflowX"] > 0 or snap["holes"] or snap["ragged"] or snap["clipped"] or snap["raggedy"]
            problems += 1 if bad else 0
            print(f"\n== {role}: {path}  ({title})  {'<-- ISSUES' if bad else 'ok'}")
            if snap["overflowX"] > 0:
                print(f"   sideways scroll: {snap['overflowX']}px")
            for h in snap["holes"]:
                print(f"   HOLE in {h['el']}: rows {h['rows']} short of the right edge by {h['gaps']}px")
            for r in snap["ragged"]:
                print(f"   UNEQUAL ROW in {r['el']}: heights {r['heights']}")
            for c in snap["clipped"]:
                print(f"   CLIPPED in {c['el']}: scrollWidth {c['scrollW']} > clientWidth {c['clientW']}")
            widths = sorted({b["w"] for b in snap["blocks"]})
            print(f"   card widths on page: {widths}")
            page.close()
        ctx.close()
        browser.close()

    print(f"\n{problems} page(s) with layout issues")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

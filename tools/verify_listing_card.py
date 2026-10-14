"""Verify the browse card's three hard-won invariants.

Each of these was a real, visible defect, and each is the kind of thing a later
stylesheet tweak silently undoes:

1. The description is cut ON A WORD BOUNDARY, once, and the card shows exactly
   two lines. It used to be cut twice: server-side by truncatechars:140 (which
   lands mid-word —"…laundry is ₱150 a …") and then again by CSS, with no
   ellipsis, at whatever height flex left over.
2. The ₱ price is legible over the landlord's photo. It was cream text straight
   onto the photograph with only a soft shadow: measured 1.38–2.95:1 against
   the pixels behind it, so on a pale wall the number simply disappeared. It
   also borrowed --ce-on-accent, which inverts with the theme while the photo
   cannot, so dark mode painted it near-black.
3. The results count is not welded to the first card row (the two boxes met at
   exactly 0px, so the label looked cut off by the card's photo).

The pixel-level halves (two rendered lines, contrast over real photos) are
checked in a browser; this guards the declarations they depend on.

Usage:
    ./venv/Scripts/python.exe tools/verify_listing_card.py
"""
from __future__ import annotations

import os
import re
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

from django.test import Client  # noqa: E402

fails: list[str] = []


def check(ok, label: str) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        fails.append(label)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(ROOT, "core", "static", "core", "css", "pages", "browse_content.css")
CARD = os.path.join(ROOT, "core", "templates", "core", "includes", "listing_card.html")
BROWSE = os.path.join(ROOT, "core", "templates", "core", "includes", "browse_content.html")

css = open(CSS, encoding="utf-8").read()
card = open(CARD, encoding="utf-8").read()
browse = open(BROWSE, encoding="utf-8").read()


def block(selector: str) -> str:
    """The declaration body of one rule, or '' when the rule is gone."""
    m = re.search(r"(?m)^\s*" + re.escape(selector) + r"\s*\{(.*?)\}", css, re.S)
    return m.group(1) if m else ""


print("\n== the description is a real two-line slot ==")
desc = block(".result-description")
check(bool(desc), "browse_content.css: .result-description still exists")
check("max-height: 3em" in desc,
      "browse_content.css: .result-description is capped at exactly two lines (max-height 3em)")
check("overflow: hidden" in desc, "browse_content.css: and clips what does not fit")
check(not re.search(r"flex:\s*1", desc),
      "browse_content.css: it no longer eats the card's leftover space (flex:1 was why the cut moved per card)")

print("\n== the price sits on its own dark bed ==")
scrim = block(".result-image::after")
check(bool(scrim), "browse_content.css: .result-image::after scrim still exists")
check("linear-gradient" in scrim and "rgba(8, 18, 13" in scrim,
      "browse_content.css: the scrim is a dark gradient over the photo's bottom band")
check("pointer-events: none" in scrim, "browse_content.css: the scrim does not swallow clicks")
plate = block(".result-price")
check("background: rgba(8, 18, 13" in plate,
      "browse_content.css: .result-price carries its own plate")
ink = block(".result-price-value")
check("color: #fffdf7" in ink, "browse_content.css: the price ink is a fixed cream")
# Check the *declaration*, not the word: the rule's comment explains why the
# token is wrong here, and a substring test would flag its own explanation.
check(
    re.search(r"color:\s*var\(--ce-on-accent", ink) is None,
    "browse_content.css: the price ink no longer borrows --ce-on-accent "
    "(that token inverts with the theme while the photo cannot)",
)

print("\n== the count row is not welded to the cards ==")
header = block(".results-header")
m = re.search(r"margin-bottom:\s*([0-9.]+)(rem|px|em)", header)
check(bool(m), "browse_content.css: .results-header still declares a bottom margin")
if m:
    value, unit = float(m.group(1)), m.group(2)
    check(value > 0, f"browse_content.css: and it is not zero ({value}{unit})")

print("\n== the copy is cut once, on a word boundary ==")
# The filter usage (|truncatechars), not the word: the new comment above the
# copy names the filter it replaced.
check("|truncatechars" not in card,
      "listing_card.html: no truncatechars filter on the card copy (it cut words in half)")
check(card.count("|truncatewords:") == 2,
      f"listing_card.html: both card variants truncate by words ({card.count('|truncatewords:')} found)")
check('browse_content.css\' %}?v=' in browse,
      "browse_content.html: the stylesheet carries a ?v= so a fix actually reaches the browser")

print("\n== what the server actually renders ==")
DESC = re.compile(r'class="(?:result|card)-description">([^<]*)<')


def page(path: str, label: str) -> str:
    r = Client().get(path)
    html = r.content.decode("utf-8", "replace")
    check(r.status_code == 200, f"{label}: responds 200 (got {r.status_code})")
    return html


for path, label in [("/listings/", "the browse board"), ("/", "the landing page")]:
    html = page(path, label)
    texts = DESC.findall(html)
    check(bool(texts), f"{label}: the cards still render a description ({len(texts)} found)")
    # truncatewords appends " …" after a whole word; truncatechars appends "…"
    # straight onto whatever character it hit.
    blunt = [t.strip()[-24:] for t in texts if not t.rstrip().endswith(" \u2026") and "\u2026" in t]
    check(not blunt, f"{label}: every ellipsis follows a whole word (saw {blunt[:2]})")
    clean = all(t.rstrip().endswith(" \u2026") for t in texts)
    check(clean, f"{label}: every description is cut at a word boundary")

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILED'}")
for f in fails:
    print("  FAILED:", f)
sys.exit(1 if fails else 0)

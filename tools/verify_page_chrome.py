"""Verify the page band and the webfont ranges.

Two rules, both about what a page ships and what it looks like:

1. No page renders the "Home / <page>" breadcrumb strip. It used to be
   base.html's default, so every default-layout page wore a second navigation
   under the navbar that read as raw HTML next to the real page heading. The
   band is now opt-in, and the pages that asked for crumb items no longer do.

2. Every @font-face declares a unicode-range. Without one, a face matches any
   character, so the browser downloads BOTH the latin and the latin-ext file
   for a weight the moment the family is used -- ~48 KB of latin-ext per weight
   for text that is pure ASCII. The layout files already had ranges; the Inter
   and Urbanist faces had been stripped of theirs.

Usage:
    ./venv/Scripts/python.exe tools/verify_page_chrome.py
"""
from __future__ import annotations

import os
import re
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import transaction  # noqa: E402
from django.template.loader import render_to_string  # noqa: E402
from django.test import Client, RequestFactory  # noqa: E402

fails: list[str] = []


def check(ok, label: str) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        fails.append(label)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_CSS = os.path.join(ROOT, "core", "static", "vendor", "fonts.css")

# The band is recognisable by its wrapper, its landmark label, and the
# Bootstrap list it renders. Any of the three means it is back.
BAND = (
    re.compile(r'class="[^"]*\bbreadcrumb-nav\b'),
    re.compile(r'aria-label="Breadcrumb"'),
    re.compile(r'<ol[^>]*class="[^"]*\bbreadcrumb\b'),
)


def bands(html: str) -> int:
    """How many pieces of breadcrumb band markup a page carries."""
    return sum(len(p.findall(html)) for p in BAND)


def get(path: str):
    r = Client().get(path)
    return r.status_code, r.content.decode("utf-8", "replace")


def no_band(path: str, label: str, expect: int = 200) -> str:
    status, html = get(path)
    check(status == expect, f"{label}: responds {expect} (got {status})")
    check(bands(html) == 0, f"{label}: no breadcrumb band ({bands(html)} pieces)")
    return html


print("\n== the page that used to wear it first ==")
html = no_band("/listings/", "/listings/ (the browse board)")
check("browse-layout" in html, "/listings/: still the real browse page")
check("Boarding houses near NLUC" in html, "/listings/: the page heading is what greets you")

print("\n== a house page ==")
from core.views import visible_listings  # noqa: E402

listing = visible_listings().order_by("-id").first()
if listing is None:
    print("  [SKIP] a house page: no visible listing in this database")
else:
    detail = no_band(f"/listings/{listing.pk}/", "a house page")
    check(listing.name in detail, "a house page: still the real detail page")

print("\n== the landing page (never had one) ==")
status, html = get("/")
check(status == 200, f"/: responds 200 (got {status})")
check("landing-hero" in html, "/: it really is the landing page")
check(bands(html) == 0, f"/: no breadcrumb band ({bands(html)} pieces)")

print("\n== every sign-in surface and utility page ==")
for path, label, expect in [
    ("/students/login/", "the student portal deck", 200),
    ("/students/register/", "the student registration half", 200),
    ("/landlords/login/", "the landlord portal deck", 200),
    ("/accounts/login/", "the login endpoint", 200),
    ("/admin/login/", "the administrator sign-in", 200),
    ("/password-reset/", "the password reset", 200),
    ("/admin/", "the admin honeypot", 200),
    ("/no-such-page-chrome/", "the 404 page", 404),
]:
    no_band(path, label, expect=expect)

from core.views import handler500  # noqa: E402

resp = handler500(RequestFactory().get("/boom/"))
body = resp.content.decode("utf-8", "replace")
check(resp.status_code == 500, f"the 500 page: responds 500 (got {resp.status_code})")
check(bands(body) == 0, f"the 500 page: no breadcrumb band ({bands(body)} pieces)")

print("\n== the templates that used to declare crumb items ==")
# These four asked for crumb items; the band no longer exists to render them,
# so the declarations must be gone rather than left dangling.
for name, label in [
    ("core/boardings_list.html", "the browse template"),
    ("core/boarding_detail.html", "the detail template"),
    ("core/edit_profile.html", "the profile-edit template"),
    ("core/change_password.html", "the password-change template"),
]:
    src = open(os.path.join(ROOT, "core", "templates", name), encoding="utf-8").read()
    check("breadcrumb" not in src, f"{label}: no crumb declaration left behind")

for name, label in [
    ("core/landlord_confirmation.html", "the landlord confirmation screen"),
]:
    html = render_to_string(
        name,
        {
            "landlord_name": "Probe Landlord",
            "landlord_email": "probe@example.invalid",
            "landlord_password": "Probe-Pass-123",
            "landlord_id": "LL-0001",
            "credentials": [("Login Email", "probe@example.invalid")],
        },
        request=RequestFactory().get("/admin/landlords/add/"),
    )
    check(bands(html) == 0, f"{label}: no breadcrumb band ({bands(html)} pieces)")

print("\n== the app shell, signed in ==")


class Rollback(Exception):
    """Leave the database exactly as we found it."""


try:
    with transaction.atomic():
        probe = get_user_model().objects.create_user(
            username=f"page-chrome-{os.urandom(4).hex()}",
            email="page-chrome@example.invalid",
            password="Probe-Pass-123",
            role=get_user_model().Role.STUDENT,
            full_name="Page Chrome Probe",
        )
        c = Client()
        c.force_login(probe)

        for path, label in [
            ("/listings/", "the signed-in browse board"),
            ("/students/dashboard/", "the student dashboard"),
            ("/profile/edit/", "the profile-edit page"),
            ("/profile/change-password/", "the password-change page"),
        ]:
            r = c.get(path)
            html = r.content.decode("utf-8", "replace")
            check(r.status_code == 200, f"{label}: responds 200 (got {r.status_code})")
            check("app-shell" in html, f"{label}: renders the app shell")
            check(bands(html) == 0, f"{label}: no breadcrumb band ({bands(html)} pieces)")

        raise Rollback
except Rollback:
    pass

print("\n== every webfont face is ranged ==")
css = open(FONTS_CSS, encoding="utf-8").read()
faces = re.findall(r"@font-face\s*\{(.*?)\}", css, re.S)
check(len(faces) >= 29, f"fonts.css: the layout faces are still there ({len(faces)} faces)")

BARE = re.compile(r"[^;{}]*\.woff2")
uranged = [f for f in faces if "unicode-range" not in f]
check(
    not uranged,
    "fonts.css: every face declares a unicode-range "
    f"({len(uranged)} without: {[m.group(0).strip() for m in (BARE.search(f) for f in uranged) if m][:3]})",
)

# The split that saves the bytes: the latin-ext file must not be able to claim
# basic Latin, or it downloads for every page alongside the latin file.
LATIN_EXT_ONLY = [
    f for f in faces if "-latin-ext.woff2" in f and re.search(r"unicode-range:\s*U\+0000-00FF", f)
]
check(
    not LATIN_EXT_ONLY,
    f"fonts.css: no *-latin-ext face claims U+0000-00FF ({len(LATIN_EXT_ONLY)} do)",
)

basic = [f for f in faces if re.search(r"src:\s*url\(fonts/[^)]*-latin\.woff2", f)]
uncovered = [f for f in basic if not re.search(r"unicode-range:\s*U\+0000-00FF", f)]
check(
    not uncovered,
    f"fonts.css: every *-latin face covers U+0000-00FF ({len(uncovered)} do not)",
)

print("\n== nothing else claims to be the band ==")
for name in ["core/includes/navbar.html", "core/includes/footer.html"]:
    src = open(os.path.join(ROOT, "core", "templates", name), encoding="utf-8").read()
    check("breadcrumb" not in src, f"{name}: does not revive the band")

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILED'}")
for f in fails:
    print("  FAILED:", f)
sys.exit(1 if fails else 0)

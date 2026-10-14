"""Verify the big site footer is landing-only.

The rule this guards: the landing page — the one page a signed-out visitor
arrives on cold — wears the dark bhims-footer. Every other page ends where its
content ends. The footer used to be base.html's default, so it appeared under
the browse board, every house page, the auth portals, the 404 and the honeypot.

Usage:
    ./venv/Scripts/python.exe tools/verify_footer_scope.py
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
from django.test import Client, RequestFactory  # noqa: E402

fails: list[str] = []


def check(ok, label: str) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        fails.append(label)


FOOTER = re.compile(r'<footer[^>]*class="[^"]*\bbhims-footer\b')


def footers(html: str) -> int:
    """How many times the big site footer is rendered on a page."""
    return len(FOOTER.findall(html))


def get(path: str):
    r = Client().get(path)
    return r.status_code, r.content.decode("utf-8", "replace")


def no_footer(path: str, label: str, expect: int = 200) -> str:
    status, html = get(path)
    check(status == expect, f"{label}: responds {expect} (got {status})")
    check(footers(html) == 0, f"{label}: no big site footer ({footers(html)})")
    return html


print("\n== the landing page keeps it ==")
status, html = get("/")
check(status == 200, f"/: responds 200 (got {status})")
check("landing-hero" in html, "/: it really is the landing page")
check(footers(html) == 1, f"/: wears the footer exactly once ({footers(html)})")
check("bhims-footer-brand" in html and "Student portal" in html,
      "/: the footer renders whole (brand block + platform links)")
check("bhims-footer-inner" in html, "/: with its inner layout")

print("\n== browse and a house page ==")
html = no_footer("/listings/", "/listings/ (the browse board)")
check("browse-layout" in html, "/listings/: still the real browse page")

from core.views import visible_listings  # noqa: E402

listing = visible_listings().order_by("-id").first()
if listing is None:
    print("  [SKIP] a house page: no visible listing in this database")
else:
    detail = no_footer(f"/listings/{listing.pk}/", "a house page")
    check("boarding" in detail.lower(), "a house page: still the real detail page")

print("\n== every sign-in surface ==")
# "No footer" means the big site footer is gone, not that the page lost its own
# sign-off line: the decks carry one in the sheet (.auth-deck-foot), the
# default auth layout carries one under the card (.auth-foot).
for path, label, signoff in [
    ("/students/login/", "the student portal deck", "auth-deck-foot"),
    ("/students/register/", "the student registration half", "auth-deck-foot"),
    ("/landlords/login/", "the landlord portal deck", "auth-deck-foot"),
    ("/accounts/login/", "the login endpoint", "auth-deck-foot"),
    ("/admin/login/", "the administrator sign-in", "auth-foot"),
    ("/password-reset/", "the password reset", "auth-foot"),
]:
    html = no_footer(path, label)
    check(signoff in html, f"{label}: keeps its own small sign-off (.{signoff})")

print("\n== the pages nobody navigates to on purpose ==")
html = no_footer("/admin/", "the admin honeypot")
check("admin_honeypot" in html or "Sign in" in html, "the admin honeypot: still the fake form")

no_footer("/no-such-page-footer-scope/", "the 404 page", expect=404)

from core.views import handler500  # noqa: E402

resp = handler500(RequestFactory().get("/boom/"))
body = resp.content.decode("utf-8", "replace")
check(resp.status_code == 500, f"the 500 page: responds 500 (got {resp.status_code})")
check(footers(body) == 0, f"the 500 page: no big site footer ({footers(body)})")

# The administrator's "landlord account created" screen: only reachable by
# POSTing a new landlord, so it is rendered the way the view renders it.
from django.template.loader import render_to_string  # noqa: E402

confirmation = render_to_string(
    "core/landlord_confirmation.html",
    {
        "landlord_name": "Probe Landlord",
        "landlord_email": "probe@example.invalid",
        "landlord_password": "Probe-Pass-123",
        "landlord_id": "LL-0001",
        "credentials": [("Login Email", "probe@example.invalid")],
    },
    request=RequestFactory().get("/admin/landlords/add/"),
)
check("Landlord account created" in confirmation,
      "the landlord confirmation screen: still the real screen")
check(footers(confirmation) == 0,
      f"the landlord confirmation screen: no big site footer ({footers(confirmation)})")

print("\n== the app shell, signed in ==")


class Rollback(Exception):
    """Leave the database exactly as we found it."""


try:
    with transaction.atomic():
        probe = get_user_model().objects.create_user(
            username=f"footer-scope-{os.urandom(4).hex()}",
            email="footer-scope@example.invalid",
            password="Probe-Pass-123",
            role=get_user_model().Role.STUDENT,
            full_name="Footer Scope Probe",
        )
        c = Client()
        c.force_login(probe)

        for path, label in [
            ("/listings/", "the signed-in browse board"),
            ("/students/dashboard/", "the student dashboard"),
        ]:
            r = c.get(path)
            html = r.content.decode("utf-8", "replace")
            check(r.status_code == 200, f"{label}: responds 200 (got {r.status_code})")
            check("app-shell" in html, f"{label}: renders the app shell")
            check(footers(html) == 0, f"{label}: no big site footer ({footers(html)})")

        raise Rollback
except Rollback:
    pass

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILED'}")
for f in fails:
    print("  FAILED:", f)
sys.exit(1 if fails else 0)

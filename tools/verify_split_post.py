"""Verify the failed-POST paths of the student sign-in / create-account deck.

The test suite covers the views; this checks the thing the two-sheet layout
could have broken quietly: that a rejected POST reopens the sheet the visitor
was actually using, that the server's error markup still lands on that sheet,
and that the ?next= the view computed is still carried into both forms.

The deck itself (the sweep, the parked half, the accessibility pairing) is
checked in the browser by tools/verify_split_login.py.

Usage:
    ./venv/Scripts/python.exe tools/verify_split_post.py
"""
import os
import re
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

from django.test import Client  # noqa: E402

fails = []


def check(ok, label):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        fails.append(label)


def sheet_tag(html, name):
    """The opening tag of one sheet — hidden or not is read from the tag."""
    return re.search(r'<section[^>]*data-sheet="%s"[^>]*>' % name, html)


def probe(name, post, url, expect_mode, expect_marker):
    print(f"\n== {name} ==")
    c = Client()
    r = c.post(url, post)
    html = r.content.decode("utf-8", "replace")
    check(r.status_code == 200, f"{name}: responds 200 (got {r.status_code})")

    mode = re.search(r'data-mode="(\w+)"', html)
    mode = mode.group(1) if mode else None
    check(mode == expect_mode, f"{name}: reopens the {expect_mode} half (got {mode})")

    # Exactly one sheet is live, and it is the one the mode names.
    live, parked = ("signup", "signin") if expect_mode == "signup" else ("signin", "signup")
    live_tag = sheet_tag(html, live)
    parked_tag = sheet_tag(html, parked)
    check(live_tag is not None and "hidden" not in live_tag.group(0),
          f"{name}: the {live} sheet is the one rendered open")
    check(parked_tag is not None and "hidden" in parked_tag.group(0),
          f"{name}: the {parked} sheet is rendered hidden")

    check(expect_marker in html, f"{name}: server error markup still rendered ({expect_marker!r})")
    return html


# A registration POST missing required fields: the view sets initial_mode from
# the presence of password1, so this must come back on the registration sheet.
html = probe(
    "failed registration",
    {"username": "", "email": "", "password1": "abc", "password2": "xyz"},
    "/students/register/",
    expect_mode="signup",
    expect_marker="auth-summary",
)

print("\n== failed registration keeps what was typed ==")
c = Client()
r = c.post("/students/register/", {
    "username": "kept-username",
    "email": "kept@example.com",
    "full_name": "Kept Name",
    "student_id": "123",
    "program": "CE",
    "password1": "Str0ng-Pass!23",
    "password2": "Str0ng-Pass!23",
})
html = r.content.decode("utf-8", "replace")
check('value="kept-username"' in html, "username survives the round trip")
check('value="Kept Name"' in html, "full name survives the round trip")
check("Student ID must be in the format 241-0273-1." in html, "the bad student ID's own message is shown")

# A bad sign-in: stays on the sign-in sheet.
probe(
    "failed sign-in",
    {"username": "nobody-here", "password": "wrong-password"},
    "/students/login/",
    expect_mode="signin",
    expect_marker="auth-alert",
)

print("\n== ?next= is carried into both forms ==")
c = Client()
r = c.get("/students/login/?next=/browse/")
html = r.content.decode("utf-8", "replace")
check(html.count('name="next" value="/browse/"') == 2,
      f"both forms post the computed next target (found {html.count('name=\"next\" value=\"/browse/\"')})")

print("\n== both forms still post to their own view ==")
check('action="/students/register/"' in html, "registration sheet posts to student_register")
check('action="/accounts/login/"' in html or 'action="/students/login/"' in html,
      "sign-in sheet posts to the login view")

print("\n== the invitations are links, so they work without a script ==")
CTA = re.compile(r'<a class="auth-deck-cta"\s+href="([^"]+)"\s+data-goto="(\w+)"')
links = dict((m.group(2), m.group(1)) for m in CTA.finditer(html))
check(links.get("signup", "").endswith("/students/register/"),
      f"the create-account CTA links to the registration page (got {links.get('signup')!r})")
check(links.get("signin", "").endswith("/students/login/"),
      f"the sign-in CTA links to the sign-in page (got {links.get('signin')!r})")

print("\n== the parked half is inert in the markup, before any script runs ==")
signin_page = Client().get("/students/login/").content.decode("utf-8", "replace")
signup_page = Client().get("/students/login/?mode=signup").content.decode("utf-8", "replace")
check(re.search(r'data-invite="signin"\s+aria-hidden="true" inert', signin_page) is not None,
      "sign in: the parked sign-in invitation is aria-hidden and inert")
check(re.search(r'data-invite="signup"\s+aria-hidden="true" inert', signup_page) is not None,
      "create account: the parked registration invitation is aria-hidden and inert")
check(re.search(r'data-invite="signup"\s+aria-hidden="false"', signin_page) is not None,
      "sign in: the live invitation is exposed")

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILED'}")
for f in fails:
    print("  FAILED:", f)
sys.exit(1 if fails else 0)

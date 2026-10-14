"""BHIMS exhaustive page crawl: every URL x every role x every theme.

`ui_audit.py` checks a curated list of pages for contrast / tap size / overflow.
This goes wider and hunts a different class of defect: pages that are *broken*
rather than merely ugly.

  * HTTP >= 500, or Django's exception page
  * a JS error that kills the page's own behaviour
  * a subresource that 404s or fails to load
  * a redirect that lands somewhere the visitor did not ask for
  * a page whose body is suspiciously thin (empty states, "coming soon",
    unstyled fallbacks)

Usage (dev server must already be running):

    ./venv/Scripts/python.exe tools/explore_crawl.py --base-url http://127.0.0.1:8020
    ./venv/Scripts/python.exe tools/explore_crawl.py --role admin --theme dark
    ./venv/Scripts/python.exe tools/explore_crawl.py --json .audit/crawl.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

DESKTOP = {"width": 1440, "height": 900}

# Signs of a page that failed rather than a page that is merely plain.
TRACES = [
    ("django-exception", re.compile(r"Traceback \(most recent call last\)")),
    ("debug-toolbar-500", re.compile(r"Server Error \(500\)")),
    ("template-syntax", re.compile(r"TemplateSyntaxError|Invalid filter")),
    ("coming-soon", re.compile(r"coming soon|under construction|lorem ipsum", re.I)),
]

# A page that renders the shell but almost nothing else is the classic
# "not visualised" failure: the user lands, sees a header, and learns nothing.
THIN_BODY_CHARS = 400


@dataclass
class Row:
    role: str
    theme: str
    path: str
    status: int | None = None
    landed: str = ""
    title: str = ""
    h1: str = ""
    text_chars: int = 0
    cards: int = 0
    images: int = 0
    broken_images: int = 0
    console_errors: list[str] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    failed_requests: list[str] = field(default_factory=list)
    bad_responses: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    note: str = ""


def page_signals(page) -> dict:
    return page.evaluate(
        """() => {
      const main = document.querySelector('main') || document.body;
      const text = (main.innerText || '').replace(/\\s+/g, ' ').trim();
      return {
        title: document.title || '',
        h1: Array.from(document.querySelectorAll('h1')).map(h => h.innerText.trim())[0] || '',
        textChars: text.length,
        cards: document.querySelectorAll('.card, article, .listing-card, .stat-card, '
            + 'table tbody tr, .list-group-item, .message, .inquiry-item, .booking-item').length,
        images: document.querySelectorAll('img').length,
        brokenImages: Array.from(document.images)
            .filter(i => i.complete && i.naturalWidth === 0).map(i => i.getAttribute('src')),
        stylesheets: document.styleSheets.length,
      };
    }"""
    )


def build_page_list(base: str) -> dict[str, list[tuple[str, str]]]:
    """Every URL the site exposes, with real primary keys taken from the database.

    Hard-coding pk 1 everywhere hides the fact that pk 1 is a junk fixture row
    (`name='cjade'`, 81 rooms); some templates only misbehave on real records.
    """
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
    import django

    django.setup()
    from django.contrib.auth import get_user_model
    from core import models as m

    users = get_user_model().objects.all()
    first_landlord = users.filter(role="landlord").order_by("pk").first()
    second_landlord = users.filter(role="landlord").order_by("pk")[1:2].first()
    first_student = users.filter(role="student").order_by("pk").first()
    second_student = users.filter(role="student").order_by("pk")[1:2].first()
    admin = users.filter(role="admin").order_by("pk").first()

    # Prefer a house with photos and several rooms over the fixture row.
    house = m.BoardingHouse.objects.filter(owner=first_landlord, rooms__isnull=False) \
        .distinct().order_by("-pk").first() or m.BoardingHouse.objects.order_by("pk").first()
    other_house = m.BoardingHouse.objects.exclude(pk=house.pk).order_by("pk").first()
    room = house.rooms.order_by("pk").first() if house else None
    photo_room = None
    for r in (house.rooms.all() if house else []):
        if r.photos.exists():
            photo_room = r
            break
    inquiry = m.Inquiry.objects.order_by("pk").first()
    booking = m.Booking.objects.order_by("pk").first()
    report = m.UserReport.objects.order_by("pk").first()

    hp = house.pk if house else 1
    rp = room.pk if room else 1
    ohp = other_house.pk if other_house else hp
    ip = inquiry.pk if inquiry else 1
    bp = booking.pk if booking else 1
    up = first_landlord.pk if first_landlord else 1
    lp2 = second_landlord.pk if second_landlord else up
    sp = first_student.pk if first_student else 1
    sp2 = second_student.pk if second_student else sp
    ap = admin.pk if admin else 1

    anon = [
        ("landing", "/"),
        ("browse", "/listings/"),
        ("listing-detail", f"/listings/{hp}/"),
        ("listing-alias", f"/listing/{hp}/"),
        ("listing-detail-photo-room", f"/listings/{house.pk}/") if photo_room else ("browse-2", "/listings/?page=2"),
        ("search", "/search/?q=room"),
        ("search-empty", "/search/?q=zzzznomatch"),
        ("search-empty-q", "/search/"),
        ("browse-page2", "/listings/?page=2"),
        ("browse-filter", "/listings/?gender=female"),
        ("browse-sort", "/listings/?sort=price_low"),
        ("browse-barangay", "/listings/?barangay=1"),
        ("browse-page-oob", "/listings/?page=99"),
        ("login-student", "/students/login/"),
        ("login-landlord", "/landlords/login/"),
        ("login-admin", "/admin/login/"),
        ("login-accounts", "/accounts/login/"),
        ("login-typo-redirect", "/landlord/login/"),
        ("register-student", "/students/register/"),
        ("register-landlord-redirect", "/landlords/register/"),
        ("password-reset", "/password-reset/"),
        ("password-reset-done", "/password-reset/done/"),
        ("health", "/health/"),
        ("chat-redirect", "/chat/"),
        ("404", "/definitely-not-a-page/"),
    ]

    student = [
        ("student-dashboard", "/students/dashboard/"),
        ("student-inquiries", "/students/inquiries/"),
        ("student-inquiries-empty", "/students/inquiries/?status=replied"),
        ("student-thread", f"/students/inquiries/{ip}/"),
        ("student-bookings", "/students/bookings/"),
        ("student-bookings-filter", "/students/bookings/?status=pending"),
        ("profile", "/profile/"),
        ("profile-edit", "/profile/edit/"),
        ("profile-change-password", "/profile/change-password/"),
        ("profile-avatar", "/profile/avatar/"),
        ("browse-favourited", f"/listings/?landlord={up}"),
        ("user-profile-landlord", f"/users/{up}/"),
        ("rate-landlord", f"/users/{up}/rate/"),
        ("report-user", f"/users/{up}/report/"),
        ("rate-other-student", f"/users/{sp2}/rate/"),
    ]

    landlord = [
        ("landlord-dashboard", "/landlords/dashboard/"),
        ("landlord-inquiries", "/landlords/inquiries/"),
        ("landlord-inquiries-filter", "/landlords/inquiries/?status=pending"),
        ("landlord-thread", f"/landlords/inquiries/{ip}/"),
        ("landlord-bookings", "/landlords/bookings/"),
        ("landlord-ratings", "/landlords/ratings/"),
        ("landlord-houses", "/landlords/boarding-houses/"),
        ("landlord-house-detail", f"/landlords/boarding-houses/{hp}/"),
        ("landlord-house-other", f"/landlords/boarding-houses/{ohp}/"),
        ("landlord-house-edit", f"/landlords/boarding-houses/{hp}/edit/"),
        ("landlord-house-add", "/landlords/boarding-houses/add/"),
        ("landlord-room-add", f"/landlords/boarding-houses/{hp}/rooms/add/"),
        ("landlord-room-edit", f"/landlords/rooms/{rp}/edit/"),
        ("student-dashboard-as-landlord", "/students/dashboard/"),
        ("student-inquiries-as-landlord", "/students/inquiries/"),
        ("student-bookings-as-landlord", "/students/bookings/"),
        ("admin-dashboard-as-landlord", "/admin/dashboard/"),
        ("profile", "/profile/"),
        ("profile-edit", "/profile/edit/"),
        ("profile-change-password", "/profile/change-password/"),
    ]

    admin = [
        ("admin-dashboard", "/admin/dashboard/"),
        ("admin-analytics", "/admin/analytics/"),
        ("admin-pending", "/admin/listings/pending/"),
        ("admin-landlords", "/admin/landlords/"),
        ("admin-landlord-add", "/admin/landlords/add/"),
        ("admin-landlord-detail", f"/admin/landlords/{up}/"),
        ("admin-landlord-edit", f"/admin/landlords/{up}/edit/"),
        ("admin-landlord-edit-other", f"/admin/landlords/{lp2}/edit/"),
        ("admin-students", "/admin/students/"),
        ("admin-students-page2", "/admin/students/?page=2"),
        ("admin-barangays", "/admin/barangays/"),
        ("admin-ratings", "/admin/ratings/"),
        ("admin-reports", "/admin/reports/"),
        ("admin-report-detail", f"/admin/reports/{report.pk}/") if report else ("admin-reports-2", "/admin/reports/"),
        ("admin-settings", "/admin/settings/"),
        ("landing-as-admin", "/"),
        ("student-dashboard-as-admin", "/students/dashboard/"),
        ("landlord-dashboard-as-admin", "/landlords/dashboard/"),
        ("profile", "/profile/"),
        ("profile-edit", "/profile/edit/"),
        ("profile-change-password", "/profile/change-password/"),
        ("user-profile-student", f"/users/{sp}/"),
    ]

    return {"anon": anon, "student": student, "landlord": landlord, "admin": admin}


def crawl(ctx, base: str, role: str, theme: str, pages, only: str | None) -> list[Row]:
    rows: list[Row] = []
    page = ctx.new_page()
    page.set_viewport_size(DESKTOP)
    for name, path in pages:
        if only and only != name:
            continue
        console: list[str] = []
        perrors: list[str] = []
        failed: list[str] = []
        bad: list[str] = []
        # Listeners are attached ONCE per page and write into these bags, which
        # are reset between navigations. Re-registering per page cannot be undone
        # later -- Playwright re-wraps the handler on both add and remove, so
        # remove_listener raises KeyError -- and a left-over handler would report
        # one page's console errors against every page after it.
        page.on("console", lambda m: console.append(f"{m.type}: {m.text[:180]}") if m.type == "error" else None)
        page.on("pageerror", lambda e: perrors.append(str(e)[:180]))
        page.on("requestfailed", lambda r: failed.append(f"{r.failure} {r.url[:110]}") if r.failure else None)
        page.on("response", lambda r: bad.append(f"HTTP {r.status} {r.url[:110]}") if r.status >= 400 else None)

        row = Row(role=role, theme=theme, path=path)

        try:
            resp = page.goto(base + path, wait_until="load", timeout=25000)
            row.status = resp.status if resp else None
            page.wait_for_timeout(600)
            html = page.content()
            sig = page_signals(page)
            row.landed = page.url.replace(base, "") or "/"
            row.title = sig["title"]
            row.h1 = sig["h1"]
            row.text_chars = sig["textChars"]
            row.cards = sig["cards"]
            row.images = sig["images"]
            row.broken_images = len(sig["brokenImages"])

            for label, pattern in TRACES:
                if pattern.search(html):
                    row.flags.append(label)
            if row.status and row.status >= 500:
                row.flags.append(f"http-{row.status}")
            if row.status and row.status in (403, 401):
                row.flags.append(f"http-{row.status}")
            if row.broken_images:
                row.flags.append("broken-images")
            if perrors:
                row.flags.append("js-exception")
            if failed:
                row.flags.append("request-failed")
            if bad:
                row.flags.append("http-error-subresource")
            if console:
                row.flags.append("console-error")
            if row.landed.rstrip("/") != path.split("?")[0].rstrip("/") and row.status == 200:
                row.flags.append(f"redirected->{row.landed}")
            if row.text_chars < THIN_BODY_CHARS and not row.flags:
                row.flags.append("thin-body")
            if sig["stylesheets"] == 0:
                row.flags.append("no-stylesheets")
        except Exception as exc:
            row.note = f"{type(exc).__name__}: {exc}"[:200]
            row.flags.append("navigation-failed")
        row.console_errors = list(console)
        row.page_errors = list(perrors)
        row.failed_requests = list(failed)
        row.bad_responses = list(bad)
        rows.append(row)
        console.clear()
        perrors.clear()
        failed.clear()
        bad.clear()
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="http://127.0.0.1:8021")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--role", choices=["anon", "student", "landlord", "admin"])
    ap.add_argument("--theme", choices=["light", "dark"])
    ap.add_argument("--only", help="crawl a single named page")
    ap.add_argument("--channel", default="msedge")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    from ui_screenshots import session_cookies

    base = args.base_url.rstrip("/")
    sessions = session_cookies(base)
    pages = build_page_list(base)
    roles = [args.role] if args.role else ["anon", "student", "landlord", "admin"]
    themes = [args.theme] if args.theme else ["light", "dark"]
    account = {"anon": None, "student": "student", "landlord": "landlord", "admin": "root"}

    rows: list[Row] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=args.channel, headless=True)
        for theme in themes:
            for role in roles:
                acc = account[role]
                if acc and acc not in sessions:
                    print(f"!! no session for {acc!r} — skipping role {role}", file=sys.stderr)
                    continue
                ctx = browser.new_context(viewport=DESKTOP, color_scheme="light", reduced_motion="reduce")
                ctx.add_init_script(
                    "try { localStorage.setItem('bhims-theme', '%s');"
                    " localStorage.setItem('bhims-theme-version', 'teal-v2'); } catch (e) {}" % theme
                )
                if acc:
                    ctx.add_cookies([sessions[acc]])
                rows += crawl(ctx, base, role, theme, pages[role], args.only)
                ctx.close()
        browser.close()

    clean = 0
    for r in rows:
        # A deliberate 404 probe and cross-role denials are expected, not defects.
        expected = ("404" in r.path) or "http-403" in r.flags or "http-401" in r.flags
        bad = [f for f in r.flags if not f.startswith("redirected->")]
        marker = "~" if expected else ("!!" if bad else "  ")
        if not bad:
            clean += 1
        print(f"{marker} {r.role:9s} {r.theme:5s} {r.path:52s} -> {r.status} "
              f"{r.landed:38s} h1={r.h1[:26]!r} txt={r.text_chars} cards={r.cards} "
              f"img={r.images}/{r.broken_images} " + ("FLAGS=" + ",".join(bad) if bad else ""))
        for detail in (r.console_errors[:2] + r.page_errors[:2] + r.bad_responses[:3] + r.failed_requests[:2]):
            print(f"       | {detail}")
        if r.note:
            print(f"       ! {r.note}")

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump([r.__dict__ for r in rows], fh, indent=2)
        print(f"\nwrote {args.json_out}")

    flagged = [r for r in rows
               if [f for f in r.flags if not f.startswith("redirected->")]
               and not ("404" in r.path or "http-403" in r.flags or "http-401" in r.flags)]
    print(f"\n{len(rows)} renders ({len(roles)} role(s) x {len(themes)} theme(s)); "
          f"{clean} clean, {len(flagged)} flagged")
    for r in flagged:
        print(f"   {r.role}/{r.theme} {r.path}: {','.join(r.flags)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
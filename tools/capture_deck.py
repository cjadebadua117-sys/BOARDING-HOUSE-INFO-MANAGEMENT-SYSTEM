"""Capture the 8 system screenshots the final report needs.

4 light + 4 dark, focused on the system's main use (search -> view -> inquire)
plus the student, landlord and admin dashboards with the sidebar OPEN.

The sidebar and theme are both localStorage-driven, and the real app starts the
sidebar collapsed on every first visit (`readStored()` returns true when the key
is absent). So both are seeded through `add_init_script`, which runs before the
page's own scripts -- setting the key after load would be too late.

Usage:
    ./venv/Scripts/python.exe tools/capture_deck.py --base-url http://127.0.0.1:8021
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from ui_screenshots import DESKTOP, SETTLE_JS  # noqa: E402


def sessions_for(base: str, usernames: tuple[str, ...]) -> dict[str, dict]:
    """One real Django session per account, as ui_screenshots.session_cookies does.

    That helper is hard-wired to student/landlord/root, but the accounts holding
    the realistic demo content are demo_student01 and demo_landlord, so this
    makes the same session rows for whichever accounts are asked for.
    """
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
    import django

    django.setup()
    from django.conf import settings as dj
    from django.contrib.auth import (
        BACKEND_SESSION_KEY,
        HASH_SESSION_KEY,
        SESSION_KEY,
        get_user_model,
    )
    from django.contrib.sessions.backends.db import SessionStore

    backends = list(getattr(dj, "AUTHENTICATION_BACKENDS", []) or [])
    backend = backends[0] if backends else "django.contrib.auth.backends.ModelBackend"
    user_model = get_user_model()

    out: dict[str, dict] = {}
    for username in usernames:
        user = user_model.objects.filter(username=username).first()
        if not user:
            print(f"  ! no account {username!r}", file=sys.stderr)
            continue
        store = SessionStore()
        store[SESSION_KEY] = str(user.pk)
        store[BACKEND_SESSION_KEY] = backend
        store[HASH_SESSION_KEY] = user.get_session_auth_hash()
        store.create()
        out[username] = {
            "name": dj.SESSION_COOKIE_NAME,
            "value": store.session_key,
            "url": base,
        }
    return out


def init_script(theme: str) -> str:
    # bhims-theme-version must match the app's, or base.html resets the theme.
    return (
        "try {"
        " localStorage.setItem('bhims-theme', '%s');"
        " localStorage.setItem('bhims-theme-version', 'teal-v2');"
        " localStorage.setItem('bhims_sidebar_collapsed', '0');"  # 0 => sidebar open
        " } catch (e) {}" % theme
    )


# The listing the report uses for "view a house" and "send an inquiry".
# pk 26 is Villa Elena Boarding House -- a realistic listing with 3 rooms,
# photos and a settled inquiry thread, so the screenshots show real content.
HOUSE = "/listings/26/"

# role, theme, filename, fixed path (None => follow the first link on `list_from`)
SHOTS = [
    ("demo_student01", "light", "light-01-student-dashboard.png",
     "/students/dashboard/", None),
    ("public", "light", "light-02-browse-listings.png", "/listings/", None),
    ("public", "light", "light-03-listing-detail.png", HOUSE, None),
    # The inquiry form is its own page (core/send_inquiry.html), reached from the
    # listing. Room 62 ("Single Room") is used because this student already has a
    # conversation on room 63 -- the view reuses it and redirects to the thread,
    # so the form only renders for a room with no existing conversation.
    ("demo_student01", "light", "light-04-send-inquiry.png",
     "/inquiries/send/62/", None),
    ("demo_landlord", "dark", "dark-01-landlord-dashboard.png",
     "/landlords/dashboard/", None),
    ("root", "dark", "dark-02-admin-dashboard.png", "/admin/dashboard/", None),
    ("demo_landlord", "dark", "dark-03-landlord-inquiries.png",
     "/landlords/inquiries/", None),
    ("demo_student01", "dark", "dark-04-student-thread.png", "/students/inquiries/15/", None),
]


def first_link(page, pattern: str) -> str | None:
    import re
    rx = re.compile(pattern)
    for a in page.query_selector_all("a[href]"):
        href = a.get_attribute("href") or ""
        if rx.fullmatch(href):
            return href
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="http://127.0.0.1:8021")
    ap.add_argument("--out", default=".audit/deck-shots")
    ap.add_argument("--channel", default="msedge")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cookies = sessions_for(base, ("demo_student01", "demo_landlord", "root"))
    print("sessions:", ", ".join(sorted(cookies)) or "none")

    ok, failed = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.channel)
        for role, theme, fname, path, follow in SHOTS:
            ctx = browser.new_context(
                viewport=DESKTOP,
                color_scheme=theme,
                reduced_motion="reduce",
                device_scale_factor=2,
            )
            ctx.add_init_script(init_script(theme))
            if role != "public":
                key = role
                if key not in cookies:
                    print(f"  ! no session for {role}; skipping {fname}")
                    ctx.close()
                    failed.append(fname)
                    continue
                ctx.add_cookies([cookies[key]])
            page = ctx.new_page()
            try:
                if path is None:
                    page.goto(f"{base}{follow[0]}", wait_until="load")
                    target = first_link(page, follow[1])
                    if not target:
                        raise RuntimeError(f"no link matching {follow[1]} on {follow[0]}")
                    page.goto(f"{base}{target}", wait_until="load")
                else:
                    page.goto(f"{base}{path}", wait_until="load")
                # Confirm before trusting the shot. A page that quietly bounced
                # to a login or an error page would otherwise be captured as if
                # it were the real screen.
                page.evaluate(SETTLE_JS)
                page.wait_for_timeout(350)
                landed = page.url.rstrip("/")
                want = (base + path if path else "").rstrip("/")
                if want and landed != want:
                    raise RuntimeError(f"redirected away from {want} to {landed}")
                body = page.inner_text("body")[:4000]
                for bad in ("Sign In", "Page not found", "Not Found",
                            "Server Error", "Traceback"):
                    if bad in body and path not in ("", None):
                        if bad == "Sign In" and "/signin" not in landed:
                            continue
                        raise RuntimeError(f"page looks wrong: contains {bad!r}")
                dom_theme = page.evaluate(
                    "document.documentElement.getAttribute('data-theme')")
                shell = page.evaluate(
                    "(() => { const s=document.getElementById('appShell');"
                    " return s ? !s.classList.contains('sidebar-collapsed') : null; })()")
                page.screenshot(path=str(out_dir / fname), full_page=False)
                print(f"  OK  {fname}  theme={dom_theme}  sidebar_open={shell}  url={page.url}")
                if dom_theme != theme:
                    failed.append(f"{fname} (theme={dom_theme}, wanted {theme})")
                elif shell is False:
                    failed.append(f"{fname} (sidebar collapsed)")
                else:
                    ok.append(fname)
            except Exception as exc:  # noqa: BLE001
                print(f"  FAIL {fname}: {exc}")
                failed.append(fname)
            finally:
                ctx.close()
        browser.close()

    print(f"\n{len(ok)} captured, {len(failed)} problem(s)")
    for f in failed:
        print("  !", f)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

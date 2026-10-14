"""Screenshot every page of BHIMS into docs/screenshots.

Three things make this fast and accurate:

* **No login round-trips.** Instead of filling the login form for each role, a
  real Django session row is created and its `sessionid` cookie is injected
  into the browser context. Same auth path the app uses, zero form traffic, and
  no temporary passwords in the database.
* **Reveal animations are forced open.** `Scroll Reveal.js` adds `.revealed`
  only to elements that intersect the viewport, so a full-page capture of a
  long page would show blank sections. Every `[data-reveal]` node is revealed
  before the shot.
* **One context per role/theme**, pages visited in one pass with the lightest
  wait that still renders correctly (document load + fonts + lazy images).

Usage:
    ./venv/Scripts/python.exe tools/ui_screenshots.py                    # light desktop
    ./venv/Scripts/python.exe tools/ui_screenshots.py --theme both --viewport both
    ./venv/Scripts/python.exe tools/ui_screenshots.py --only landlord --theme dark
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Reuse the audited page lists so the two tools cannot drift apart.
from ui_audit import ADMIN_PAGES, DESKTOP, LANDLORD_PAGES, MOBILE, PUBLIC_PAGES, STUDENT_PAGES  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

# Pages the audit never needed but that are worth documenting. Anything that
# redirects or errors is still captured and flagged in INDEX.md, so the set can
# stay generous without hiding a broken page.
# /landlords/register/ is deliberately absent: it redirects to the landlord
# login, so it would just be a second copy of that shot.
EXTRA_PUBLIC: list[tuple[str, str]] = []
EXTRA_STUDENT = [
    ("student-change-password", "/profile/change-password/"),
    # Needs a session, so it belongs to a signed-in role rather than "public".
    ("student-view-landlord-profile", "/users/1/"),
]
EXTRA_LANDLORD = [
    ("landlord-house-add", "/landlords/boarding-houses/add/"),
    ("landlord-house-edit", "/landlords/boarding-houses/1/edit/"),
    ("landlord-room-add", "/landlords/boarding-houses/1/rooms/add/"),
]
EXTRA_ADMIN = [
    ("admin-landlord-add", "/admin/landlords/add/"),
    ("admin-landlord-edit", "/admin/landlords/1/edit/"),
]

ROLES = {
    "public": (PUBLIC_PAGES + EXTRA_PUBLIC, None),
    "student": (STUDENT_PAGES + EXTRA_STUDENT, "student"),
    "landlord": (LANDLORD_PAGES + EXTRA_LANDLORD, "landlord"),
    "admin": (ADMIN_PAGES + EXTRA_ADMIN, "root"),
}

SETTLE_JS = """async () => {
  // Reveal-on-scroll never fires below the fold, so un-hide it explicitly for
  // the `[data-reveal]` mechanism. The landing page instead hides content with
  // `html.fx .reveal { opacity: 0 }`, which is what left 2,200px of the mobile
  // landing blank in earlier captures: the observer only fires for elements
  // that were scrolled into view. The context is created with
  // prefers-reduced-motion, so the page's own settled-state rules
  // (`.reveal { opacity: 1; transform: none; transition: none }`) apply here
  // and nothing below the fold is captured mid-animation.
  document.querySelectorAll('[data-reveal]').forEach(el => el.classList.add('revealed'));
  // `in-view` is the landing page's own class for a revealed element (its
  // observer adds exactly this). Applying it here captures the settled state
  // instead of racing an IntersectionObserver that fires while scrolling.
  document.querySelectorAll('.reveal').forEach(el => el.classList.add('in-view'));
  // Lazy images would otherwise render as gaps in a full-page capture. Forcing
  // the attribute only *starts* the fetch, so the wait below is the part that
  // matters: shooting 180ms after this point captured the landing page with its
  // hero photo half-decoded and the sign-in buttons genuinely absent from the
  // image — a defect that existed only in the screenshot.
  document.querySelectorAll('img[loading="lazy"]').forEach(img => { img.loading = 'eager'; });
  // A scroll pass starts anything still waiting on an intersection observer.
  const step = Math.max(200, Math.round(window.innerHeight * 0.9));
  for (let y = 0; y < document.body.scrollHeight; y += step) {
    window.scrollTo(0, y);
    await new Promise(r => setTimeout(r, 40));
  }
  window.scrollTo(0, 0);
  await Promise.all(Array.from(document.images).map(img => img.complete ? 0 : new Promise(resolve => {
    img.addEventListener('load', resolve, { once: true });
    img.addEventListener('error', resolve, { once: true });
    setTimeout(resolve, 5000);
  })));
  if (document.fonts) { try { await document.fonts.ready; } catch (e) {} }
  // Two frames so the decoded images are actually composited before the shot.
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  return Array.from(document.images).filter(img => !img.complete).length;
}"""

# A screenshot is only evidence if the page finished painting. Anything still
# incomplete after the waits above is reported rather than silently captured.
INCOMPLETE_WARN = 3


def session_cookies(base: str) -> dict[str, dict]:
    """Create one real Django session per role and return ready-to-inject cookies."""
    # Running from tools/ puts that directory on sys.path, not the project root
    # that DJANGO_SETTINGS_MODULE lives under.
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

    cookies: dict[str, dict] = {}
    for username in ("student", "landlord", "root"):
        user = user_model.objects.filter(username=username).first()
        if not user:
            print(f"  ! no user {username!r} — skipping that role", file=sys.stderr)
            continue
        store = SessionStore()
        store[SESSION_KEY] = str(user.pk)
        store[BACKEND_SESSION_KEY] = backend
        store[HASH_SESSION_KEY] = user.get_session_auth_hash()
        store.create()
        cookies[username] = {
            "name": dj.SESSION_COOKIE_NAME,
            "value": store.session_key,
            "url": base,
        }
    return cookies


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="http://127.0.0.1:8020")
    ap.add_argument("--out", default="docs/screenshots")
    ap.add_argument("--theme", choices=["light", "dark", "both"], default="light")
    ap.add_argument("--viewport", choices=["desktop", "mobile", "both"], default="desktop")
    ap.add_argument("--only", choices=list(ROLES))
    ap.add_argument("--channel", default="msedge")
    ap.add_argument("--no-full", action="store_true", help="capture the viewport only")
    ap.add_argument("--scale", type=int, default=1)
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    base = args.base_url.rstrip("/")
    themes = ["light", "dark"] if args.theme == "both" else [args.theme]
    viewports = {"desktop": DESKTOP, "mobile": MOBILE}
    if args.viewport != "both":
        viewports = {args.viewport: viewports[args.viewport]}
    roles = [args.only] if args.only else list(ROLES)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cookies = session_cookies(base)

    rows: list[tuple[str, str, str, str, int | None, str]] = []
    started = time.time()
    shots = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=args.channel, headless=True)
        for theme in themes:
            for vp_name, vp in viewports.items():
                for role in roles:
                    pages, account = ROLES[role]
                    if account and account not in cookies:
                        continue
                    # The audit lists are a superset; the same path can appear
                    # twice (admin-students/admin-student-list), which would
                    # only produce duplicate screenshots.
                    seen: set[str] = set()
                    pages = [(n, p) for n, p in pages if not (p in seen or seen.add(p))]
                    ctx = browser.new_context(
                        viewport=vp,
                        device_scale_factor=args.scale,
                        color_scheme=theme,
                        # Entrance animations are scroll-triggered, so a
                        # full-page capture would otherwise photograph whatever
                        # has not scrolled into view yet — blank sections.
                        reduced_motion="reduce",
                    )
                    ctx.add_init_script(
                        "try { localStorage.setItem('bhims-theme', '%s');"
                        " localStorage.setItem('bhims-theme-version', 'teal-v2'); } catch (e) {}" % theme
                    )
                    if account:
                        ctx.add_cookies([cookies[account]])
                    page = ctx.new_page()
                    for index, (name, path) in enumerate(pages, start=1):
                        target = f"{theme}-{vp_name}-{role}-{index:02d}-{name}.png"
                        status = None
                        try:
                            response = page.goto(base + path, wait_until="load", timeout=25000)
                            status = response.status if response else None
                            pending = page.evaluate(SETTLE_JS)
                            if pending and pending >= INCOMPLETE_WARN:
                                print(f"  ! {path}: {pending} images still loading at capture time",
                                      file=sys.stderr)
                            page.wait_for_timeout(220)
                            page.screenshot(path=str(out_dir / target), full_page=not args.no_full)
                            shots += 1
                        except Exception as exc:  # one bad page must not kill the run
                            print(f"  ! {role} {path}: {exc}", file=sys.stderr)
                        land = page.url.replace(base, "") or "/"
                        rows.append((target, role, path, land, status, name))
                        print(f"  {target}")
                    ctx.close()
        browser.close()

    index = out_dir / "INDEX.md"
    # Several runs (one theme, one viewport at a time) must not truncate each
    # other's index, so keep rows whose files are still on disk.
    previous: list[str] = []
    if index.exists():
        for line in index.read_text(encoding="utf-8").splitlines():
            if line.startswith("| `"):
                relative = line.split("`")[1]
                if (out_dir / relative).exists() and relative not in {r[0] for r in rows}:
                    previous.append(line)
    with index.open("w", encoding="utf-8") as fh:
        fh.write("# BHIMS screenshots\n\n")
        fh.write(f"Latest run: `tools/ui_screenshots.py` on {time.strftime('%Y-%m-%d %H:%M')} "
                 f"against {base} — {shots} capture(s) across {len(roles)} role(s), "
                 f"{len(themes)} theme(s), {len(viewports)} viewport(s).\n\n")
        fh.write(f"Total files: {len(rows) + len(previous)}.\n\n")
        fh.write("| file | role | page | requested | landed on | HTTP |\n")
        fh.write("| --- | --- | --- | --- | --- | --- |\n")
        for line in sorted(previous + [
            f"| `{target}` | {role} | {name} | `{path}` | `{land}`{' (redirect)' if land != path else ''} | {status} |"
            for target, role, path, land, status, name in rows
        ]):
            fh.write(line + "\n")

    print(f"\n{shots} screenshots -> {out_dir} in {time.time() - started:.1f}s "
          f"({len(rows)} pages visited)")
    print(f"index -> {index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

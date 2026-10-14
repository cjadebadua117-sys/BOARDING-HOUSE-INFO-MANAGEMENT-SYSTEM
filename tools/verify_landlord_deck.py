"""Verify the sweeping landlord sign-in deck in a browser, and its server half.

The landlord deck is the student deck cut the other way — mirrored geometry, the
same campus photograph under an ink-blue wash, and an "how to get an account"
panel where the student puts its registration form. This checks the things that
could break quietly: that the mirror really is the mirror at rest and after the
sweep, that the parked half is unreachable, that the white copy still clears
4.5:1 over the picture, that the phone gets the band, that a script-less visitor
still gets a working form and a way to the account route, and that a rejected
POST comes back on the sign-in half with the view's message intact.

Usage:
    ./venv/Scripts/python.exe tools/verify_landlord_deck.py --base http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import os
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

OUT = Path(".audit/landlord")
SWEEP_MS = 1150
checks: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    checks.append((bool(ok), label))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


SNAPSHOT = """
() => {
  const deck = document.getElementById('auth-main');
  const track = deck.querySelector('.auth-deck-forms');
  const blob = deck.querySelector('.auth-deck-blob');
  const live = deck.querySelector('.auth-deck-sheet:not([hidden])');
  const invite = (name) => {
    const el = deck.querySelector('[data-invite="' + name + '"]');
    const cta = el.querySelector('.auth-deck-cta');
    return {
      display: getComputedStyle(el).display,
      hidden: el.getAttribute('aria-hidden'),
      inert: el.hasAttribute('inert'),
      ctaTabindex: cta.getAttribute('tabindex'),
    };
  };
  return {
    mode: deck.dataset.mode,
    url: location.search,
    deckW: Math.round(deck.getBoundingClientRect().width),
    pinnedH: deck.style.height,
    deckH: deck.offsetHeight,
    trackX: Math.round(track.getBoundingClientRect().x),
    blobLeft: Math.round(blob.getBoundingClientRect().left),
    blobRight: Math.round(blob.getBoundingClientRect().right),
    liveSheet: live ? live.dataset.sheet : null,
    sheets: ['signin', 'account'].map((n) => {
      const s = deck.querySelector('.auth-deck-sheet--' + n);
      return { name: n, hidden: s.hidden, fields: s.querySelectorAll('input, select').length };
    }),
    steps: deck.querySelectorAll('.auth-deck-sheet--account .auth-deck-steps li').length,
    forms: document.querySelectorAll('.auth-deck form').length,
    formAction: document.querySelector('.auth-deck-sheet--signin form').getAttribute('action') || location.pathname,
    signin: invite('signin'),
    account: invite('account'),
    focus: document.activeElement ? (document.activeElement.id || document.activeElement.name || document.activeElement.className || document.activeElement.tagName) : null,
  };
}
"""


def snap(page):
    return page.evaluate(SNAPSHOT)


def channel(value: int) -> float:
    v = value / 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def backdrop_contrast(page, selector: str) -> tuple[float, float]:
    """Contrast between the white copy and the ground actually rendered behind it."""
    page.evaluate(
        """() => document.querySelectorAll('.auth-deck-invite > *')
              .forEach((el) => { el.style.visibility = 'hidden'; })"""
    )
    box = page.locator(selector).bounding_box()
    shot = page.screenshot(clip=box)
    page.evaluate(
        """() => document.querySelectorAll('.auth-deck-invite > *')
              .forEach((el) => { el.style.visibility = ''; })"""
    )
    image = Image.open(BytesIO(shot)).convert("RGB")
    lums = sorted(
        0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
        for r, g, b in image.getdata()
    )
    worst = lums[int(len(lums) * 0.9)]
    return 1.05 / (worst + 0.05), worst


def server_checks() -> None:
    import django

    django.setup()
    from django.test import Client

    print("\n== the server half ==")
    c = Client()
    r = c.get("/landlords/login/")
    html = r.content.decode("utf-8", "replace")
    check(r.status_code == 200, f"the page renders (got {r.status_code})")
    check('data-alt-mode="account"' in html, "the deck names its alt half in the markup")
    check('class="auth-deck-sheet auth-deck-sheet--signin"' in html
          and 'data-sheet="account"' in html and "hidden" in html,
          "sign-in is the sheet rendered open; the account panel starts hidden")
    check('name="password1"' not in html, "no registration form survives on the landlord page")

    r = c.post("/landlords/login/", {"username": "nobody-at-all", "password": "wrong-password"})
    html = r.content.decode("utf-8", "replace")
    check(r.status_code == 200, f"a rejected POST re-renders the page (got {r.status_code})")
    check("Invalid credentials or not an active landlord account." in html,
          "the view's own message is on the page")
    check('class="auth-deck-sheet auth-deck-sheet--signin"' in html,
          "and the sign-in half is the one that comes back")
    check('data-mode="signin"' in html and "auth-deck-sheet--account" in html,
          "the account panel is still parked, not reopened")

    r = c.get("/landlords/login/?next=/landlords/dashboard/")
    check('name="next" value="/landlords/dashboard/"' in r.content.decode("utf-8", "replace"),
          "?next= is carried into the form")

    r = c.get("/landlords/register/")
    check(r.status_code == 302 and r["Location"].endswith("/landlords/login/"),
          f"the invitation's no-JS target still redirects home ({r.status_code} -> {r.get('Location')})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    base = args.base.rstrip("/")
    url = f"{base}/landlords/login/"

    server_checks()

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ---- the mirrored resting composition --------------------------------
        print("\n== desktop: the sheet on the left, the ground on the right ==")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(url, wait_until="load")
        page.wait_for_timeout(600)

        before = snap(page)
        half = before["deckW"] / 2
        check(before["mode"] == "signin" and before["liveSheet"] == "signin",
              "sign in: the sign-in sheet is the one rendered open")
        check(abs(before["trackX"]) <= 2,
              f"sign in: the form column holds the LEFT half (x={before['trackX']})")
        check(abs(before["blobLeft"] - 0.48 * before["deckW"]) <= 8,
              f"sign in: the curve's edge sits just short of the middle, from the right "
              f"(left={before['blobLeft']}, half={half:.0f})")
        check(before["account"]["hidden"] == "false" and not before["account"]["inert"],
              "sign in: the invitation to get an account is the live one")
        check(before["signin"]["hidden"] == "true" and before["signin"]["inert"]
              and before["signin"]["ctaTabindex"] == "-1",
              "sign in: the parked sign-in invitation is aria-hidden, inert and out of the tab order")

        ground = page.evaluate(
            """() => {
              const cs = getComputedStyle(document.querySelector('.auth-deck-blob'));
              return { image: cs.backgroundImage, colour: cs.backgroundColor };
            }"""
        )
        check("dmmmsu-campus-hd.jpg" in ground["image"], "the curve is grounded in the campus photograph")
        check("rgb(7, 26, 44)" in ground["colour"],
              f"under an ink-blue wash, not the student deck's teal (got {ground['colour']})")

        for label, selector in (("heading", ".auth-deck-invite--account h2"),
                                ("kicker", ".auth-deck-invite--account .auth-deck-kicker"),
                                ("body copy", ".auth-deck-invite--account p:not(.auth-deck-kicker)")):
            ratio, worst = backdrop_contrast(page, selector)
            check(ratio >= 4.5,
                  f"sign in: the {label} clears 4.5:1 over the picture "
                  f"(worst backdrop L={worst:.3f} -> {ratio:.2f}:1)")

        # ---- the sweep --------------------------------------------------------
        print("\n== the curve travels, the halves trade ==")
        page.click('[data-goto="account"]')
        page.wait_for_timeout(380)
        mid = snap(page)
        check(mid["blobLeft"] < before["blobLeft"] - 40,
              f"the curve travels leftwards (left {before['blobLeft']} -> {mid['blobLeft']})")
        check(mid["trackX"] > before["trackX"] + 10,
              f"the form column travels the other way (x {before['trackX']} -> {mid['trackX']})")
        check(mid["pinnedH"] != "" or abs(mid["deckH"] - before["deckH"]) <= 4,
              f"the page does not jump under the visitor mid-sweep "
              f"(deck {before['deckH']} -> {mid['deckH']}, pinned={mid['pinnedH']!r})")

        page.wait_for_timeout(1400)
        after = snap(page)
        check(after["mode"] == "account" and after["liveSheet"] == "account",
              "the account panel took the screen")
        check(after["url"] == "?mode=account", f"the URL tracks the live half (got {after['url']!r})")
        check(abs(after["trackX"] - half) <= 2,
              f"the form column now holds the RIGHT half (x={after['trackX']}, half={half:.0f})")
        check(abs(after["blobRight"] - 0.52 * after["deckW"]) <= 8,
              f"the curve's edge mirrors it (right={after['blobRight']})")
        check(after["signin"]["hidden"] == "false" and not after["signin"]["inert"],
              "the invitation back to sign in is now the live one")
        check(after["account"]["hidden"] == "true" and after["account"]["inert"],
              "and the parked one went quiet")
        check(after["pinnedH"] == "", "the pinned height is released")
        check(after["steps"] == 4, f"the account panel lists the whole process ({after['steps']} steps)")
        check(after["forms"] == 1, f"only the sign-in form exists on the page ({after['forms']} form)")
        check(after["formAction"].endswith("/landlords/login/"),
              f"and it posts to the landlord view ({after['formAction']})")
        check("auth-deck-cta--ink" in (after["focus"] or ""),
              f"focus arrives on the panel's own control (got {after['focus']!r})")

        for label, selector in (("heading", ".auth-deck-invite--signin h2"),
                                ("kicker", ".auth-deck-invite--signin .auth-deck-kicker"),
                                ("body copy", ".auth-deck-invite--signin p:not(.auth-deck-kicker)")):
            ratio, worst = backdrop_contrast(page, selector)
            check(ratio >= 4.5,
                  f"account: the {label} clears 4.5:1 over the picture "
                  f"(worst backdrop L={worst:.3f} -> {ratio:.2f}:1)")

        reachable = page.evaluate(
            """() => {
              const parked = document.querySelector('.auth-deck-sheet[hidden] input');
              parked.focus();
              return document.activeElement === parked;
            }"""
        )
        check(not reachable, "the hidden sheet's fields cannot take focus")

        # ---- back again -------------------------------------------------------
        print("\n== and back to sign in ==")
        page.click('.auth-deck-cta--ink')
        page.wait_for_timeout(SWEEP_MS + 600)
        back = snap(page)
        check(back["mode"] == "signin" and back["url"] == "",
              f"it returns to sign in with a clean URL (got {back['url']!r})")
        check(abs(back["trackX"]) <= 2, "the form column is back on the left half")
        check(back["focus"] == "id_username", f"focus lands in the sign-in form (got {back['focus']!r})")
        ctx.close()

        # ---- reduced motion ----------------------------------------------------
        print("\n== reduced motion: swap without travel ==")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        page = ctx.new_page()
        page.goto(url, wait_until="load")
        page.wait_for_timeout(400)
        page.click('[data-goto="account"]')
        page.wait_for_timeout(150)
        instant = snap(page)
        check(instant["mode"] == "account" and instant["liveSheet"] == "account" and instant["pinnedH"] == "",
              "the halves still trade, in one frame")
        ctx.close()

        # ---- a phone ------------------------------------------------------------
        print("\n== mobile: the band above the sheet ==")
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        page.goto(url, wait_until="load")
        page.wait_for_timeout(500)
        phone = snap(page)
        check(phone["account"]["display"] == "flex" and phone["signin"]["display"] == "none",
              "the band shows exactly one invitation")
        check(page.evaluate("() => getComputedStyle(document.querySelector('.auth-deck-blob')).display") == "none",
              "the travelling ellipse is replaced by the band's own ground")
        band = page.evaluate(
            "() => getComputedStyle(document.querySelector('.auth-deck-invites')).backgroundImage"
        )
        check("dmmmsu-campus-hd.jpg" in band, "the band is drawn on the same photograph")
        check("rgba(4, 18, 32" in band, "under the landlord's ink-blue wash")
        ratio, worst = backdrop_contrast(page, ".auth-deck-invite--account h2")
        check(ratio >= 4.5,
              f"phone: the heading clears 4.5:1 over the picture "
              f"(worst backdrop L={worst:.3f} -> {ratio:.2f}:1)")
        page.click('[data-goto="account"]')
        page.wait_for_timeout(300)
        swapped = snap(page)
        check(swapped["mode"] == "account" and swapped["liveSheet"] == "account", "the tap swaps the panel")
        check(swapped["signin"]["display"] == "flex" and swapped["account"]["display"] == "none",
              "the band swaps with it")
        ctx.close()

        # ---- with no script at all ---------------------------------------------
        print("\n== no JavaScript: the form still posts, the invitation still links ==")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, java_script_enabled=False)
        page = ctx.new_page()
        page.goto(url, wait_until="load")
        html = page.content()
        check('href="/landlords/register/"' in html,
              "the account CTA is a plain link to the route that explains registration")
        check('data-invite="signin"' in html and 'aria-hidden="true" inert' in html,
              "the parked invitation is already inert without the script")
        check(page.locator(".auth-deck-sheet--signin").is_visible()
              and not page.locator(".auth-deck-sheet--account").is_visible(),
              "the sign-in half is the one rendered")
        check(page.locator('form button[type="submit"]').is_visible(),
              "and its submit button is live with no script")
        ctx.close()

        # ---- captures -----------------------------------------------------------
        print("\n== captures ==")
        for theme in ("light", "dark"):
            for vpname, (w, h) in {"desktop": (1440, 900), "mobile": (390, 844)}.items():
                ctx = browser.new_context(viewport={"width": w, "height": h})
                ctx.add_init_script(
                    f"try {{ localStorage.setItem('bhims-theme', '{theme}'); }} catch (e) {{}}"
                )
                page = ctx.new_page()
                page.goto(url, wait_until="load")
                page.wait_for_timeout(700)
                applied = page.evaluate("() => document.documentElement.dataset.theme")
                if applied != theme:
                    raise SystemExit(f"capture {theme}/{vpname} rendered {applied!r}, not {theme!r}")
                page.screenshot(path=str(OUT / f"{theme}-{vpname}-signin.png"))
                if vpname == "desktop":
                    page.click('[data-goto="account"]')
                    page.wait_for_timeout(SWEEP_MS + 500)
                    page.screenshot(path=str(OUT / f"{theme}-{vpname}-account.png"))
                print(f"  {theme:5s} {vpname:8s} -> {theme}-{vpname}-signin.png")
                ctx.close()

        browser.close()

    failed = [m for ok, m in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    for m in failed:
        print("  FAILED:", m)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

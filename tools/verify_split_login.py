"""Verify the sweeping student sign-in / create-account deck in a browser.

Where tools/verify_split_post.py checks the server-rendered halves, this checks
what only a browser can show: that the curve and the form column trade halves
in one motion, that only one sheet and one invitation are ever live (and that
the parked ones are out of the reading order and the tab order), that the
registration sheet's submit button is reachable on a short window, that the
deck is not dead weight under prefers-reduced-motion, and that a phone gets the
band layout with an instant swap instead.

Captures light/dark x desktop/mobile x both halves into .audit/deck/.

Usage:
    ./venv/Scripts/python.exe tools/verify_split_login.py --base http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

OUT = Path(".audit/deck")
VIEWPORTS = {"desktop": (1440, 900), "mobile": (390, 844)}
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
      x: Math.round(el.getBoundingClientRect().x),
      ctaX: Math.round(cta.getBoundingClientRect().x),
    };
  };
  return {
    mode: deck.dataset.mode,
    url: location.search,
    deckW: Math.round(deck.getBoundingClientRect().width),
    deckH: deck.offsetHeight,
    pinnedH: deck.style.height,
    trackX: Math.round(track.getBoundingClientRect().x),
    trackPosition: getComputedStyle(track).position,
    blobLeft: Math.round(blob.getBoundingClientRect().left),
    blobRight: Math.round(blob.getBoundingClientRect().right),
    liveSheet: live ? live.dataset.sheet : null,
    sheets: ['signin', 'signup'].map((n) => {
      const s = deck.querySelector('.auth-deck-sheet--' + n);
      return { name: n, hidden: s.hidden, overflowY: getComputedStyle(s).overflowY };
    }),
    signin: invite('signin'),
    signup: invite('signup'),
    focus: document.activeElement ? (document.activeElement.id || document.activeElement.name || document.activeElement.tagName) : null,
  };
}
"""


def snap(page):
    return page.evaluate(SNAPSHOT)


def channel(value: int) -> float:
    """One sRGB channel as the WCAG relative-luminance term."""
    v = value / 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def backdrop_contrast(page, selector: str) -> tuple[float, float]:
    """Contrast between white copy and the ground actually rendered behind it.

    The invitation's copy is hidden for one frame, its own box is photographed,
    and the ninth decile of that ground's luminance is used — the brightest
    pixels the glyphs could land on, rather than an average that a dark corner
    would flatter. Returns (ratio, luminance).
    """
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8010")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    base = args.base.rstrip("/")

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ---- the sweep, measured -----------------------------------------
        print("\n== desktop: the halves trade places ==")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(f"{base}/students/login/", wait_until="load")
        page.wait_for_timeout(600)

        before = snap(page)
        half = before["deckW"] / 2
        check(before["mode"] == "signin" and before["liveSheet"] == "signin",
              "sign in: the sign-in sheet is the one rendered open")
        check(abs(before["trackX"] - half) <= 2,
              f"sign in: the form column holds the right half (x={before['trackX']}, half={half:.0f})")
        check(abs(before["blobRight"] - 0.52 * before["deckW"]) <= 8,
              f"sign in: the curve's edge sits just past the middle (right={before['blobRight']})")
        check(before["signup"]["hidden"] == "false" and not before["signup"]["inert"]
              and before["signup"]["ctaTabindex"] is None,
              "sign in: the invitation to register is the live one")
        check(before["signin"]["hidden"] == "true" and before["signin"]["inert"]
              and before["signin"]["ctaTabindex"] == "-1",
              "sign in: the parked invitation is aria-hidden, inert and out of the tab order")
        check(before["pinnedH"] == "", "sign in: no height is pinned at rest")

        ground = page.evaluate(
            """() => {
              const cs = getComputedStyle(document.querySelector('.auth-deck-blob'));
              return { image: cs.backgroundImage, colour: cs.backgroundColor, size: cs.backgroundSize };
            }"""
        )
        check("dmmmsu-campus-hd.jpg" in ground["image"],
              "the curve is grounded in the campus photograph")
        check("rgb(8, 34, 30)" in ground["colour"],
              f"it has deep teal under the picture, not the canvas (got {ground['colour']})")

        for label, selector in (("heading", ".auth-deck-invite--signup h2"),
                                ("kicker", ".auth-deck-invite--signup .auth-deck-kicker"),
                                ("body copy", ".auth-deck-invite--signup p:not(.auth-deck-kicker)")):
            ratio, worst = backdrop_contrast(page, selector)
            check(ratio >= 4.5,
                  f"sign in: the {label} clears 4.5:1 over the picture "
                  f"(worst backdrop L={worst:.3f} -> {ratio:.2f}:1)")

        page.click('[data-goto="signup"]')
        page.wait_for_timeout(380)
        mid = snap(page)
        check(mid["blobRight"] > before["blobRight"] + 40,
              f"the curve travels (right {before['blobRight']} -> {mid['blobRight']})")
        check(mid["trackX"] < before["trackX"] - 10,
              f"the form column travels the other way (x {before['trackX']} -> {mid['trackX']})")
        check(mid["pinnedH"] != "",
              f"the deck's growth is eased, not a jump (pinned at {mid['pinnedH']})")

        page.wait_for_timeout(1400)
        after = snap(page)
        check(after["mode"] == "signup" and after["liveSheet"] == "signup",
              "create account: the registration sheet took over")
        check(after["url"] == "?mode=signup", f"the URL tracks the live half (got {after['url']!r})")
        check(abs(after["trackX"]) <= 2, f"create account: the form column holds the left half (x={after['trackX']})")
        check(abs(after["blobLeft"] - 0.48 * after["deckW"]) <= 8,
              f"create account: the curve's edge mirrors it (left={after['blobLeft']})")
        check(after["signin"]["hidden"] == "false" and not after["signin"]["inert"]
              and after["signin"]["ctaTabindex"] is None,
              "create account: the invitation to sign in is the live one")
        check(after["signup"]["hidden"] == "true" and after["signup"]["inert"],
              "create account: the parked invitation went quiet")
        check(after["pinnedH"] == "", "create account: the pinned height is released")
        check(after["focus"] == "reg_username", f"focus arrives in the new sheet (got {after['focus']!r})")

        for label, selector in (("heading", ".auth-deck-invite--signin h2"),
                                ("kicker", ".auth-deck-invite--signin .auth-deck-kicker"),
                                ("body copy", ".auth-deck-invite--signin p:not(.auth-deck-kicker)")):
            ratio, worst = backdrop_contrast(page, selector)
            check(ratio >= 4.5,
                  f"create account: the {label} clears 4.5:1 over the picture "
                  f"(worst backdrop L={worst:.3f} -> {ratio:.2f}:1)")

        # ---- the parked sheet is unreachable ---------------------------------
        print("\n== only one sheet is ever live ==")
        reachable = page.evaluate(
            """() => {
              const parked = document.querySelector('.auth-deck-sheet[hidden] input');
              parked.focus();
              return document.activeElement === parked;
            }"""
        )
        check(not reachable, "the hidden sheet's fields cannot take focus")
        check(all(s["hidden"] == (s["name"] == "signin") for s in after["sheets"]),
              "exactly one sheet is in the document at rest")

        # ---- the long form is still submittable ------------------------------
        print("\n== the registration sheet is reachable end to end ==")
        page.evaluate("() => scrollTo(0, document.documentElement.scrollHeight)")
        page.wait_for_timeout(200)
        submit = page.evaluate(
            """() => {
              const b = document.querySelector('.auth-deck-sheet--signup .auth-submit');
              const r = b.getBoundingClientRect();
              return { top: Math.round(r.top), bottom: Math.round(r.bottom), viewport: innerHeight,
                       reachable: r.top >= 0 && r.bottom <= innerHeight };
            }"""
        )
        check(submit["reachable"], f"the submit button scrolls into view (top={submit['top']}, viewport={submit['viewport']})")
        check(page.evaluate("() => scrollY > 0"), "the page itself scrolls, not the sheet")
        nested = page.evaluate(
            """() => {
              const s = document.querySelector('.auth-deck-sheet--signup');
              return { overflow: getComputedStyle(s).overflowY, scrollable: s.scrollHeight > s.clientHeight + 4 };
            }"""
        )
        check(not nested["scrollable"], f"the sheet is not a scroll box of its own (overflow-y={nested['overflow']})")

        # ---- and back again --------------------------------------------------
        print("\n== and back to sign in ==")
        page.evaluate("() => scrollTo(0, 0)")
        page.click('[data-goto="signin"]')
        page.wait_for_timeout(SWEEP_MS + 600)
        back = snap(page)
        check(back["mode"] == "signin" and back["url"] == "", f"it returns to sign in with a clean URL (got {back['url']!r})")
        check(abs(back["trackX"] - back["deckW"] / 2) <= 2, "the form column is back on the right half")
        check(back["focus"] == "id_username", f"focus lands in the sign-in form (got {back['focus']!r})")
        ctx.close()

        # ---- a ?mode=signup link opens without animating ---------------------
        print("\n== ?mode=signup opens straight away ==")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(f"{base}/students/login/?mode=signup", wait_until="load")
        page.wait_for_timeout(500)
        linked = snap(page)
        check(linked["mode"] == "signup" and linked["liveSheet"] == "signup",
              "the deep link opens the registration sheet")
        check(linked["pinnedH"] == "" and abs(linked["trackX"]) <= 2,
              "it does so in place — nothing sweeps on load")
        ctx.close()

        # ---- reduced motion --------------------------------------------------
        print("\n== reduced motion: swap without travel ==")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        page = ctx.new_page()
        page.goto(f"{base}/students/login/", wait_until="load")
        page.wait_for_timeout(400)
        durations = page.evaluate(
            """() => ['.auth-deck-blob', '.auth-deck-forms', '.auth-deck-sheet', '.auth-deck-invite']
              .map((k) => getComputedStyle(document.querySelector(k)).transitionDuration)"""
        )
        check(all(d.strip() in ("0s", "0ms, 0s", "0s, 0s") for d in durations),
              f"transitions are disabled (got {durations})")
        page.click('[data-goto="signup"]')
        page.wait_for_timeout(120)
        instant = snap(page)
        check(instant["mode"] == "signup" and instant["liveSheet"] == "signup" and instant["pinnedH"] == "",
              "the halves still trade, in one frame")
        ctx.close()

        # ---- a phone gets the band ------------------------------------------
        print("\n== mobile: the band above the sheet ==")
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        page.goto(f"{base}/students/login/", wait_until="load")
        page.wait_for_timeout(500)
        phone = snap(page)
        check(phone["signup"]["display"] == "flex" and phone["signin"]["display"] == "none",
              "the band shows exactly one invitation")
        check(phone["trackPosition"] == "static", f"the form column is in normal flow (got {phone['trackPosition']!r})")
        check(page.evaluate("() => getComputedStyle(document.querySelector('.auth-deck-blob')).display") == "none",
              "the travelling circle is replaced by the band's own ground")
        check("dmmmsu-campus-hd.jpg" in page.evaluate(
                  "() => getComputedStyle(document.querySelector('.auth-deck-invites')).backgroundImage"),
              "the band is drawn on the same photograph")
        for label, selector in (("heading", ".auth-deck-invite--signup h2"),
                                ("body copy", ".auth-deck-invite--signup p:not(.auth-deck-kicker)")):
            ratio, worst = backdrop_contrast(page, selector)
            check(ratio >= 4.5,
                  f"phone: the {label} clears 4.5:1 over the picture "
                  f"(worst backdrop L={worst:.3f} -> {ratio:.2f}:1)")
        page.click('[data-goto="signup"]')
        page.wait_for_timeout(250)
        swapped = snap(page)
        check(swapped["mode"] == "signup" and swapped["liveSheet"] == "signup",
              "the tap swaps the sheet")
        check(swapped["signin"]["display"] == "flex" and swapped["signup"]["display"] == "none",
              "the band swaps with it")
        check(page.evaluate("() => scrollY > 0"), "and the registration form is brought into view")
        ctx.close()

        # ---- with no script at all -------------------------------------------
        print("\n== no JavaScript: the invitation is still a way through ==")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, java_script_enabled=False)
        page = ctx.new_page()
        page.goto(f"{base}/students/login/", wait_until="load")
        html = page.content()
        check("auth-deck-cta" in html and 'href="/students/register/"' in html,
              "the create-account CTA is a plain link to the registration page")
        check('data-invite="signin"' in html and 'aria-hidden="true" inert' in html,
              "the parked invitation is already inert without the script")
        check(page.locator(".auth-deck-sheet--signin").is_visible()
              and not page.locator(".auth-deck-sheet--signup").is_visible(),
              "the server's half is the visible one")
        page.click('[data-goto="signup"]')
        page.wait_for_load_state("load")
        check(page.url.endswith("/students/register/"), f"the press navigates there (got {page.url})")
        check(page.locator(".auth-deck-sheet--signup").is_visible(),
              "and the registration sheet is the one rendered")
        ctx.close()

        # ---- the capture grid -------------------------------------------------
        print("\n== captures ==")
        for theme in ("light", "dark"):
            for vpname, (w, h) in VIEWPORTS.items():
                # The site stores its theme in localStorage rather than
                # following prefers-color-scheme, so color_scheme alone would
                # capture the light page under both labels.
                ctx = browser.new_context(viewport={"width": w, "height": h})
                ctx.add_init_script(
                    f"try {{ localStorage.setItem('bhims-theme', '{theme}'); }} catch (e) {{}}"
                )
                page = ctx.new_page()
                page.goto(f"{base}/students/login/", wait_until="load")
                page.wait_for_timeout(700)
                applied = page.evaluate("() => document.documentElement.dataset.theme")
                if applied != theme:
                    raise SystemExit(f"capture {theme}/{vpname} rendered {applied!r}, not {theme!r}")
                page.screenshot(path=str(OUT / f"{theme}-{vpname}-signin.png"))
                page.click('[data-goto="signup"]')
                page.wait_for_timeout(SWEEP_MS + 500)
                page.screenshot(path=str(OUT / f"{theme}-{vpname}-signup.png"))
                print(f"  {theme:5s} {vpname:8s} -> {theme}-{vpname}-signin.png, {theme}-{vpname}-signup.png")
                ctx.close()

        browser.close()

    failed = [m for ok, m in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    for m in failed:
        print("  FAILED:", m)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

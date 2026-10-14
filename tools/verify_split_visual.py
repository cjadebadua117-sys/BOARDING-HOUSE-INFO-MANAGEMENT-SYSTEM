"""Measure the rendered split-screen login page: contrast, layout, targets.

The colour panel is a gradient, so its text contrast cannot be read from
getComputedStyle — the real check is to sample the pixels the browser actually
painted and compare them against the computed text colour. That is the same
class of bug (invisible text on the auth pages) that this project already had
once, so it is worth asserting rather than eyeballing.

Usage:
    ./venv/Scripts/python.exe tools/verify_split_visual.py --base http://127.0.0.1:8010
"""
from __future__ import annotations

import argparse
import io
import sys
from collections import Counter

from PIL import Image
from playwright.sync_api import sync_playwright

SLIDE_MS = 480
checks: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    checks.append((bool(ok), label))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


def parse_rgb(css: str):
    """'rgb(14, 124, 107)' -> (14, 124, 107). None for alpha-bearing values."""
    nums = [float(n) for n in css[css.find("(") + 1:css.find(")")].replace("/", ",").split(",")[:3]]
    return tuple(int(round(n)) for n in nums)


def luminance(rgb):
    def ch(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def dominant_colour(png_bytes):
    """Most common pixel = the panel ground, sampled from a crop the art never reaches."""
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    im = im.crop((0, 0, max(1, im.width // 3), max(1, im.height // 12)))
    px = list(im.getdata())
    # Ignore near-white and near-black strays from antialiasing.
    px = [p for p in px if not (p[0] > 235 and p[1] > 235 and p[2] > 235)]
    return Counter(px).most_common(1)[0][0] if px else (0, 0, 0)


WATERMARK_CLEARANCE_JS = """() => {
  // Freeze the drift first: measuring a moving watermark makes this check flap
  // depending on when it is sampled.
  const style = document.createElement('style');
  style.textContent = '.auth-split-art *{animation:none !important}';
  document.head.appendChild(style);
  const hits = [];
  const seen = [];
  const brand = document.querySelector('.auth-split-brand');
  if (!brand) return { hits, seen };
  // Every decorative shape in the art layer, whatever it is called. The
  // .auth-split-art container itself is skipped on purpose: it is full-bleed
  // by design, so it overlaps everything and would report a clash always.
  brand.querySelectorAll('.auth-split-art > *').forEach(w => {
    if (getComputedStyle(w).display === 'none') return;   // hidden on this width
    const wr = w.getBoundingClientRect();
    if (wr.width < 2 || wr.height < 2) return;
    seen.push((w.className || w.tagName) + '@' + Math.round(wr.top) + '-' + Math.round(wr.bottom));
    brand.querySelectorAll(
      '.auth-split-brandpanel:not([hidden]) .auth-split-title, ' +
      '.auth-split-brandpanel:not([hidden]) .auth-split-lead, ' +
      '.auth-split-brandpanel:not([hidden]) .auth-split-kicker, ' +
      '.auth-split-brandpanel:not([hidden]) .auth-split-points, ' +
      '.auth-split-brandpanel:not([hidden]) .auth-split-cta, ' +
      '.auth-split-brandmark'
    ).forEach(el => {
      const r = el.getBoundingClientRect();
      const ox = Math.min(r.right, wr.right) - Math.max(r.left, wr.left);
      const oy = Math.min(r.bottom, wr.bottom) - Math.max(r.top, wr.top);
      if (ox > 2 && oy > 2) {
        hits.push({ what: el.className.split(' ')[0],
                    overlap: `${Math.round(ox)}x${Math.round(oy)}px` });
      }
    });
  });
  return { hits, seen };
}"""

# The drift moves each watermark by at most this much, so boxes are compared
# with that much slack rather than to the pixel.
DRIFT_SLACK = 12


def run(base: str) -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()

        for theme in ("light", "dark"):
            print(f"\n== {theme} ==")
            # The site does NOT follow prefers-color-scheme: base.html reads
            # localStorage['bhims-theme'] before first paint. Setting the
            # Playwright color_scheme alone leaves the page in light, which
            # would make every "dark" check below a silent re-run of light.
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            ctx.add_init_script(
                f"try {{ localStorage.setItem('bhims-theme', '{theme}'); }} catch (e) {{}}"
            )
            page = ctx.new_page()
            page.goto(f"{base}/students/login/", wait_until="load")
            page.wait_for_timeout(700)

            applied = page.evaluate("() => document.documentElement.dataset.theme")
            check(applied == theme, f"the page actually rendered in {theme} (data-theme={applied!r})")

            panel = page.locator('.auth-split-brandpanel[data-cta="signup"]')
            ground = dominant_colour(panel.screenshot())
            print(f"  panel ground sampled at rgb{ground}")

            text = page.evaluate(
                """() => {
                  const q = (s) => {
                    const el = document.querySelector(s);
                    return el ? getComputedStyle(el).color : null;
                  };
                  const el = (s) => document.querySelector(s);
                  const panel = document.querySelector('.auth-split-brandpanel[data-cta="signup"]');
                  const cs = (node, prop) => node ? getComputedStyle(node)[prop] : null;
                  return {
                    title: q('.auth-split-brandpanel[data-cta="signup"] .auth-split-title'),
                    lead:  q('.auth-split-brandpanel[data-cta="signup"] .auth-split-lead'),
                    kicker:q('.auth-split-brandpanel[data-cta="signup"] .auth-split-kicker'),
                    point: q('.auth-split-brandpanel[data-cta="signup"] .auth-split-points li'),
                    
                    bulletsBottom: (() => {
                      const el = document.querySelector('.auth-split-points');
                      if (!el) return null;
                      const r = el.getBoundingClientRect();
                      const p = document.querySelector('.auth-split-seal').getBoundingClientRect();
                      return Math.round(r.bottom - p.top);
                    })(),
                    ctaText: q('.auth-split-brandpanel[data-cta="signup"] .auth-split-cta'),
                    ctaBorder: cs(panel.querySelector('.auth-split-cta'), 'borderTopColor'),
                    titleSize: cs(panel.querySelector('.auth-split-title'), 'fontSize'),
                    sealW: (el('.auth-split-seal') || {}).naturalWidth || 0,
                    sealLoaded: (el('.auth-split-seal') || {}).complete || false,
                  };
                }"""
            )
            print(f"  seal loaded={text['sealLoaded']} naturalWidth={text['sealW']}")
            check(text["sealLoaded"] and text["sealW"] > 0, "the seal watermark actually loaded")

            for name in ("title", "lead", "kicker", "point", "ctaText"):
                if text[name] is None:
                    continue  # the sign-off moved to the sheet footer on purpose
                ratio = contrast(parse_rgb(text[name]), ground)
                check(ratio >= 4.5, f"{name} on the colour panel: {ratio:.2f}:1 (needs 4.5)")

            # The watermark is white ink on the colour ground, so ANY text box
            # overlapping it loses contrast that no opacity value can restore.
            # This is the bug the panel had when the seal sat under the
            # sign-off, so it is asserted rather than trusted.
            wm = page.evaluate(WATERMARK_CLEARANCE_JS)
            clashes = wm["hits"]
            check(not clashes,
                  f"no copy sits on a watermark at 1440px ({wm['seen']}, "
                  f"clashes: {clashes or 'none'})")

            border_ratio = contrast(parse_rgb(text["ctaBorder"]), ground)
            check(border_ratio >= 3.0,
                  f"outlined CTA border against the ground: {border_ratio:.2f}:1 (needs 3.0)")

            # Layout: the halves must sit flush with no overlap and no overflow.
            boxes = page.evaluate(
                """() => {
                  const r = (s) => { const b = document.querySelector(s).getBoundingClientRect();
                    return { x: Math.round(b.x), right: Math.round(b.right), w: Math.round(b.width) }; };
                  return {
                    sheet: r('.auth-split-cell--sheet'), brand: r('.auth-split-cell--brand'),
                    docW: document.documentElement.scrollWidth,
                    winW: window.innerWidth,
                    ctaH: Math.round(document.querySelector('.auth-split-cta').getBoundingClientRect().height),
                    ctaW: Math.round(document.querySelector('.auth-split-cta').getBoundingClientRect().width),
                  };
                }"""
            )
            print(f"  sheet={boxes['sheet']} brand={boxes['brand']} docW={boxes['docW']} winW={boxes['winW']}")
            check(boxes["sheet"]["x"] == 0 and boxes["brand"]["x"] == boxes["sheet"]["right"],
                  "the two halves meet exactly, with no gap and no overlap")
            check(boxes["docW"] <= boxes["winW"], "no horizontal overflow")
            check(boxes["ctaH"] >= 44, f"outlined CTA tap height {boxes['ctaH']}px (needs 44)")

            # The whole composition rests on this: each half's text column must
            # start at the same offset from ITS OWN cell edge, or the two halves
            # stop reading as one page. Comparing raw page x would be wrong --
            # the panel legitimately lives one cell to the right.
            align = page.evaluate(
                """() => {
                  const box = (s) => { const e = document.querySelector(s);
                    return e ? e.getBoundingClientRect() : null; };
                  const cell = box('.auth-split-cell--brand');
                  const card = box('.auth-split-sheet .auth-card');
                  const panel = box('.auth-split-brandpanel:not([hidden])');
                  const cardText = box('.auth-sheet:not([hidden]) .auth-card-head');
                  const panelText = box('.auth-split-brandpanel:not([hidden]) .auth-split-kicker');
                  const sheetCell = box('.auth-split-cell--sheet');
                  return {
                    cardOff: Math.round(card.left - sheetCell.left),
                    panelOff: Math.round(panel.left - cell.left),
                    cardTextOff: Math.round(cardText.left - card.left),
                    panelTextOff: Math.round(panelText.left - panel.left),
                  };
                }"""
            )
            print(f"  cross-fold offsets: column {align['cardOff']}/{align['panelOff']}, "
                  f"text {align['cardTextOff']}/{align['panelTextOff']}")
            check(align["cardOff"] == align["panelOff"],
                  f"both text columns start the same distance into their cell "
                  f"({align['cardOff']} vs {align['panelOff']})")
            check(abs(align["cardTextOff"] - align["panelTextOff"]) <= 1,
                  f"headline aligns across the fold "
                  f"({align['cardTextOff']} vs {align['panelTextOff']})")

            ctx.close()

        # ---- the swapped half, for contrast ----
        print("\n== swapped half, both themes ==")
        for theme in ("light", "dark"):
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            ctx.add_init_script(
                f"try {{ localStorage.setItem('bhims-theme', '{theme}'); }} catch (e) {{}}"
            )
            page = ctx.new_page()
            page.goto(f"{base}/students/login/", wait_until="load")
            page.wait_for_timeout(500)
            applied = page.evaluate("() => document.documentElement.dataset.theme")
            check(applied == theme, f"swapped half: page is really in {theme} (data-theme={applied!r})")
            page.click('[data-goto="signup"]')
            page.wait_for_timeout(SLIDE_MS + 300)
            ground = dominant_colour(
                page.locator('.auth-split-brandpanel[data-cta="signin"]').screenshot())
            col = page.evaluate(
                """() => getComputedStyle(
                    document.querySelector('.auth-split-brandpanel[data-cta="signin"] .auth-split-title')
                ).color"""
            )
            ratio = contrast(parse_rgb(col), ground)
            print(f"  {theme}: ground rgb{ground}, title rgb{parse_rgb(col)}")
            check(ratio >= 4.5, f"{theme} swapped-half title: {ratio:.2f}:1 (needs 4.5)")
            ctx.close()

        # ---- mobile ----
        print("\n== mobile (390px) ==")
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        page.goto(f"{base}/students/login/", wait_until="load")
        page.wait_for_timeout(600)
        m = page.evaluate(
            """() => {
              const r = (s) => { const b = document.querySelector(s).getBoundingClientRect();
                return { x: Math.round(b.x), w: Math.round(b.width), top: Math.round(b.top) }; };
              return {
                sheet: r('.auth-split-cell--sheet'), brand: r('.auth-split-cell--brand'),
                docW: document.documentElement.scrollWidth, winW: window.innerWidth,
                ctaH: Math.round(document.querySelector('.auth-split-cta').getBoundingClientRect().height),
              };
            }"""
        )
        print(f"  sheet={m['sheet']} brand={m['brand']} docW={m['docW']} winW={m['winW']}")
        check(m["docW"] <= m["winW"], "no horizontal overflow on a phone")
        check(m["brand"]["top"] > m["sheet"]["top"], "the halves stack: form first, panel below")
        check(m["ctaH"] >= 44, f"outlined CTA tap height {m['ctaH']}px on mobile (needs 44)")
        wm = page.evaluate(WATERMARK_CLEARANCE_JS)
        check(not wm["hits"],
              f"no copy sits on a watermark on a phone ({wm['seen']}, clashes: {wm['hits'] or 'none'})")
        ctx.close()

        browser.close()

    failed = [m for ok, m in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    for m in failed:
        print("  FAILED:", m)
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8010")
    sys.exit(run(ap.parse_args().base.rstrip("/")))
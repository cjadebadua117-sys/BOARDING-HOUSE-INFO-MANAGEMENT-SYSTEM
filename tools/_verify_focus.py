"""WCAG 1.4.11 focus-ring contrast, measured from rendered pixels.

Method: screenshot the element's region twice -- once unfocused, once
focused -- and diff. Pixels that CHANGED are exactly what the focus ring
painted, which avoids mistaking antialiased edges or neighbouring colours
for the ring. The background is sampled from pixels that did not change.
"""
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops
import io, json, sys

BASE = 'http://127.0.0.1:8017/'


def lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lum(rgb):
    r, g, b = [lin(v) for v in rgb[:3]]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


TARGETS = [
    ('skip-link', '.skip-link'),
    ('theme-toggle', '[data-theme-switch], [data-theme-toggle]'),
    ('landing-cta', '.landing-btn'),
    ('nav-link', '.navbar a[href], nav a[href]'),
    ('carousel-viewport', '.listing-carousel-viewport'),
    # Two more !important rings found in the sheets -- measured, not assumed.
    ('listing-card', '.listing-card'),
]


def measure(page, name, sel, theme):
    el = page.query_selector(sel)
    if el is None:
        return {'name': name, 'sel': sel, 'theme': theme, 'status': 'NOT FOUND'}

    # Below-the-fold elements report viewport-relative boxes; scroll first or
    # the capture crop clamps to zero. Never block on this: the auto-advancing
    # carousel is never "stable", so the waiting variant hangs forever.
    try:
        el.scroll_into_view_if_needed(timeout=1500)
    except Exception:
        pass
    page.wait_for_timeout(150)
    page.evaluate("document.activeElement && document.activeElement.blur()")
    page.wait_for_timeout(100)
    box = el.bounding_box()
    if not box:
        return {'name': name, 'sel': sel, 'theme': theme, 'status': 'NO BOX'}

    m = 12  # room for outline-offset + width
    vw, vh = page.viewport_size['width'], page.viewport_size['height']
    x0 = max(0, min(int(box['x'] - m), vw - 80))
    y0 = max(0, min(int(box['y'] - m), vh - 80))
    clip = {'x': x0, 'y': y0,
            'width': max(min(int(box['width'] + 2 * m), vw - x0), 80),
            'height': max(min(int(box['height'] + 2 * m), vh - y0), 80)}
    clip['width'] = min(clip['width'], vw - x0)
    clip['height'] = min(clip['height'], vh - y0)

    before = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert('RGB')
    # Keyboard focus, not programmatic .focus(), so :focus-visible matches.
    el.focus()
    page.keyboard.press('Shift')
    page.wait_for_timeout(150)
    after = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert('RGB')

    w, h = after.size
    diff = ImageChops.difference(before, after)
    # The ring is drawn just outside the element box. Measure the page surface
    # well clear of the box -- sampling the crop edge would catch a large
    # element's own glow/shadow and compare the ring against the wrong colour.
    bx0 = int(box['x'] - clip['x']); by0 = int(box['y'] - clip['y'])
    bx1 = bx0 + int(box['width']);  by1 = by0 + int(box['height'])
    changed, surface = [], []
    for xx in range(w):
        for yy in range(h):
            px = after.getpixel((xx, yy))
            if max(diff.getpixel((xx, yy))) > 12:
                changed.append(px)
                continue
            if bx0 <= xx < bx1 and by0 <= yy < by1:
                continue                      # element interior: not the surface
            if max(xx - bx1, bx0 - xx, yy - by1, by0 - yy) >= 12:
                surface.append(px)           # well clear of the ring
    if not changed:
        return {'name': name, 'sel': sel, 'theme': theme, 'status': 'NO RING PAINTED'}
    if not surface:
        return {'name': name, 'sel': sel, 'theme': theme, 'status': 'NO BACKGROUND SAMPLE'}

    bg = max(set(surface), key=surface.count)
    ring = max(changed, key=lambda p: ratio(p, bg))
    cr = ratio(ring, bg)
    return {'name': name, 'sel': sel, 'theme': theme, 'status': 'OK',
            'ring': list(ring), 'bg': list(bg),
            'changed_px': len(changed), 'contrast': round(cr, 2),
            'pass': cr >= 3.0}


results = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme in ('light', 'dark'):
        ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
        # base.html runs a one-time 'teal-v2' reset that overwrites
        # bhims-theme when the version key is absent -- seed both or the
        # dark run silently renders light.
        ctx.add_init_script(
            "try { localStorage.setItem('bhims-theme', '%s');"
            " localStorage.setItem('bhims-theme-version', 'teal-v2'); } catch(e){}" % theme)
        page = ctx.new_page()
        page.goto(BASE, wait_until='networkidle')
        page.wait_for_timeout(400)
        actual = page.evaluate("document.documentElement.getAttribute('data-theme')")
        for name, sel in TARGETS:
            r = measure(page, name, sel, theme)
            r['data_theme'] = actual
            results.append(r)
            print(f"[{theme:5}] data-theme={actual!s:6} {name:17} "
                  f"{r.get('contrast', '-'):>6}  "
                  f"{'PASS' if r.get('pass') else 'FAIL':4}  {r['status']}")
        ctx.close()
    browser.close()

json.dump(results, open('.audit/focus-ring.json', 'w'), indent=2)
bad = [r for r in results if not r.get('pass')]
print(f"\ntotal={len(results)}  pass={len(results)-len(bad)}  FAIL={len(bad)}")
for r in bad:
    print("  FAIL:", r['theme'], r['name'], r.get('contrast'), r['status'])
sys.exit(1 if bad else 0)

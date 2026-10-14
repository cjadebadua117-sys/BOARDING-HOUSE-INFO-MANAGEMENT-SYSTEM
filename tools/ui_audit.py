"""BHIMS UI/UX audit harness.

Renders real pages in a real browser (Edge/Chrome via Playwright) and reports
observable UI/UX problems instead of guessed ones:

  * contrast ratio of every text node against its effective background
  * horizontal overflow at 390px
  * tap targets smaller than 44px on mobile
  * unlabeled form controls, broken images, duplicate ids
  * console errors and failed requests
  * theme-specific problems (light vs dark)

Usage (dev server must already be running):

    python "tools/ui_audit.py" --base-url http://127.0.0.1:8010
    python "tools/ui_audit.py" --base-url http://127.0.0.1:8010 --json report.json
    python "tools/ui_audit.py" --base-url http://127.0.0.1:8010 --shots /tmp/bhims

Credentials default to the demo accounts created for review runs; override with
--student-user/--student-pass, --landlord-user/--landlord-pass and
--admin-user/--admin-pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import sync_playwright

DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}

PUBLIC_PAGES = [
    ("landing", "/"),
    ("browse", "/listings/"),
    ("listing-detail", "/listings/1/"),
    ("search", "/search/?q=room"),
    ("login-student", "/students/login/"),
    ("login-landlord", "/landlords/login/"),
    ("login-admin", "/admin/login/"),
    ("register-student", "/students/register/"),
    ("password-reset", "/password-reset/"),
    ("not-found", "/this-page-does-not-exist/"),
]

STUDENT_PAGES = [
    ("student-dashboard", "/students/dashboard/"),
    ("student-inquiries", "/students/inquiries/"),
    ("student-thread", "/students/inquiries/1/"),
    ("student-bookings", "/students/bookings/"),
    ("student-profile", "/profile/"),
    ("student-edit-profile", "/profile/edit/"),
    ("selected-listings", "/listings/"),
]

LANDLORD_PAGES = [
    ("landlord-dashboard", "/landlords/dashboard/"),
    ("landlord-inquiries", "/landlords/inquiries/"),
    ("landlord-thread", "/landlords/inquiries/1/"),
    ("landlord-houses", "/landlords/boarding-houses/"),
    ("landlord-house-detail", "/landlords/boarding-houses/1/"),
    ("landlord-bookings", "/landlords/bookings/"),
    ("landlord-ratings", "/landlords/ratings/"),
]

ADMIN_PAGES = [
    ("admin-dashboard", "/admin/dashboard/"),
    ("admin-analytics", "/admin/analytics/"),
    ("admin-pending", "/admin/listings/pending/"),
    ("admin-landlords", "/admin/landlords/"),
    ("admin-students", "/admin/students/"),
    ("admin-barangays", "/admin/barangays/"),
    ("admin-ratings", "/admin/ratings/"),
    ("admin-reports", "/admin/reports/"),
    ("admin-settings", "/admin/settings/"),
    ("admin-landlord-detail", "/admin/landlords/1/"),
    ("admin-student-list", "/admin/students/"),
]

# Runs inside the page: collects observable problems from the live DOM/CSSOM.
PROBE_JS = r"""
() => {
  const out = { overflow: null, contrast: [], tapTargets: [], unlabeled: [],
                brokenImages: [], duplicateIds: [], missingLandmarks: [], focus: {} };

  // --- horizontal overflow ---
  const de = document.documentElement;
  if (de.scrollWidth > window.innerWidth + 1) {
    const offenders = [];
    document.querySelectorAll('*').forEach(el => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.right > window.innerWidth + 2) {
        offenders.push({
          sel: el.tagName.toLowerCase() + (el.className && typeof el.className === 'string'
                ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : ''),
          right: Math.round(r.right), width: Math.round(r.width)
        });
      }
    });
    out.overflow = { scrollWidth: de.scrollWidth, viewport: window.innerWidth,
                     offenders: offenders.slice(0, 8) };
  }

  // --- contrast ---
  const parse = c => {
    const m = (c || '').match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map(v => parseFloat(v.trim()));
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const over = (fg, bg) => ({ r: fg.r*fg.a + bg.r*(1-fg.a), g: fg.g*fg.a + bg.g*(1-fg.a),
                              b: fg.b*fg.a + bg.b*(1-fg.a), a: 1 });
  const lum = c => {
    const f = v => { v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); };
    return 0.2126*f(c.r) + 0.7152*f(c.g) + 0.0722*f(c.b);
  };
  const ratio = (a, b) => {
    const l1 = lum(a), l2 = lum(b);
    return (Math.max(l1,l2) + 0.05) / (Math.min(l1,l2) + 0.05);
  };
  // Returns { bg } when the backdrop is a flat colour we can measure, or
  // { unverifiable: reason } when a gradient/image paint sits behind the text
  // (computed styles cannot tell us the rendered colour there).
  const effectiveBg = el => {
    let acc = null;
    let node = el;
    let depth = 0;
    while (node && node !== document.documentElement.parentNode && depth < 12) {
      const cs = getComputedStyle(node);
      // Pseudo-element scrims (the standard way to keep text legible over
      // photography) are invisible to the ancestor walk, so check them first.
      for (const pe of ['::before', '::after']) {
        let pcs = null;
        try { pcs = getComputedStyle(node, pe); } catch (e) { continue; }
        if (!pcs || !pcs.content || pcs.content === 'none') continue;
        const paints = /gradient\(|url\(/.test(pcs.backgroundImage || '');
        const tint = parse(pcs.backgroundColor);
        if (paints || (tint && tint.a > 0.05)) return { unverifiable: 'pseudo-backdrop' };
      }
      if (cs.backgroundImage && cs.backgroundImage !== 'none') {
        // Only treat it as blocking if it actually paints (gradient or url),
        // and only for the element that owns the text or a painted ancestor.
        if (/gradient\(|url\(/.test(cs.backgroundImage)) {
          return { unverifiable: 'background-image' };
        }
      }
      const bc = parse(cs.backgroundColor);
      if (bc && bc.a > 0) {
        acc = acc === null ? bc : over(acc, bc);
        if (acc.a >= 0.999) break;
      }
      node = node.parentElement;
      depth++;
    }
    // No opaque background anywhere in the ancestor chain: the text sits over
    // photography, a gradient, or a fixed scene layer, and computed styles
    // cannot say what is painted there. Assuming white used to manufacture
    // failures — dark photo hero text was reported as 1.09:1 — so report the
    // gap instead of guessing. Anything suspected here is confirmed by
    // sampling real pixels (tools/ui_check.py), never by this probe.
    if (!acc) return { unverifiable: 'no-opaque-backdrop' };
    if (acc.a < 0.999) return { unverifiable: 'translucent-backdrop' };
    // The walk only sees ancestors, and an opaque ancestor can still be a lie:
    // the auth pages paint a full-bleed photograph from a `position: fixed`
    // sibling *behind* the shell, so white hero text measured against the
    // shell's paper background and "failed" at 1.09:1. If a large non-ancestor
    // layer painting an image covers this element, the backdrop is unknown.
    if (sceneLayerBehind(el)) return { unverifiable: 'scene-layer' };
    return { bg: acc };
  };
  const hasOwnText = el => Array.from(el.childNodes)
    .some(n => n.nodeType === 3 && n.textContent.trim().length > 1);
  // Is a photo/gradient painted from a layer that is neither an ancestor nor a
  // descendant — i.e. from somewhere this walk cannot see?
  const sceneLayerBehind = el => {
    if (!cachedSceneLayers) {
      cachedSceneLayers = Array.from(document.querySelectorAll('body *')).filter(node => {
        const cs = getComputedStyle(node);
        if (cs.position !== 'fixed' && cs.position !== 'absolute') return false;
        if (cs.display === 'none' || cs.visibility === 'hidden') return false;
        const paintsImage = /gradient\(|url\(/.test(cs.backgroundImage || '') ||
                            !!node.querySelector('img[src]:not([src=""])');
        if (!paintsImage) return false;
        const r = node.getBoundingClientRect();
        // Only layers big enough to be a background scene, not a badge overlay.
        return r.width * r.height >= 0.12 * window.innerWidth * window.innerHeight;
      });
    }
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    return cachedSceneLayers.some(node => {
      if (node === el || node.contains(el) || el.contains(node)) return false;
      const nr = node.getBoundingClientRect();
      return cx >= nr.left && cx <= nr.right && cy >= nr.top && cy <= nr.bottom;
    });
  };
  let cachedSceneLayers = null;

  out.unverifiedBackground = 0;
  out.unverifiedReasons = {};
  document.querySelectorAll('body *').forEach(el => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.15) return;
    const rect = el.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return;
    // Off-screen (e.g. hidden skip link): judged in its :focus-visible state instead.
    if (rect.bottom < 0 || rect.top > window.innerHeight + 2000) {
      el.focus && el.focus({ preventScroll: true });
      const fr = el.getBoundingClientRect();
      if (fr.bottom < 0 || fr.top > window.innerHeight + 2000) { el.blur && el.blur(); return; }
    }
    if (!hasOwnText(el)) return;
    const fg = parse(cs.color);
    if (!fg) return;
    const measured = effectiveBg(el);
    if (measured.unverifiable) {
      out.unverifiedBackground++;
      out.unverifiedReasons[measured.unverifiable] = (out.unverifiedReasons[measured.unverifiable] || 0) + 1;
      return;
    }
    const bg = measured.bg;
    const fgc = over(fg, bg);
    const r = ratio(fgc, bg);
    const size = parseFloat(cs.fontSize);
    const weight = parseInt(cs.fontWeight, 10) || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    const min = large ? 3.0 : 4.5;
    if (r < min) {
      out.contrast.push({
        sel: el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className
              ? '.' + el.className.trim().split(/\s+/).slice(0, 3).join('.') : ''),
        text: (el.textContent || '').trim().slice(0, 60),
        ratio: Math.round(r * 100) / 100, required: min, fontSize: size,
        color: cs.color, bg: `rgb(${Math.round(bg.r)},${Math.round(bg.g)},${Math.round(bg.b)})`,
        // Kept so a disagreement can be settled with tools/ui_check.py, which
        // samples the pixels instead of trusting computed styles.
        rect: { x: Math.round(rect.x), y: Math.round(rect.y),
                w: Math.round(rect.width), h: Math.round(rect.height) }
      });
    }
  });

  // --- touch targets (only meaningful on small viewports) ---
  const vw = window.innerWidth;
  if (vw <= 820) {
    document.querySelectorAll('a[href], button, [role="button"], input[type="submit"], select').forEach(el => {
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') return;
      // WCAG 2.5.8 exempts targets that sit inside a sentence of text. A plain
      // inline box is exactly that: a name or a word inside a line of prose
      // (e.g. "… <a>Student Name</a> has been accepted into this room …").
      // Padding those out to 44px would wreck the line rhythm for no real gain,
      // so they are not reported. Every standalone control is a flex, grid or
      // block box — including flex ITEMS, which are blockified — so nothing
      // that ought to be finger-sized slips through this exemption.
      if (el.tagName === 'A' && cs.display === 'inline') return;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return;
      if (r.height < 44 || r.width < 44) {
        out.tapTargets.push({
          sel: el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className
                ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : ''),
          label: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 40),
          w: Math.round(r.width), h: Math.round(r.height)
        });
      }
    });
    out.tapTargets = out.tapTargets.slice(0, 40);
  }

  // --- a11y: unlabeled controls, duplicate ids, broken images, landmarks ---
  document.querySelectorAll('input:not([type=hidden]), select, textarea').forEach(el => {
    const labelled = (el.labels && el.labels.length) || el.getAttribute('aria-label') ||
                     el.getAttribute('aria-labelledby') || el.getAttribute('title');
    if (!labelled) out.unlabeled.push({
      name: el.getAttribute('name') || '', type: el.getAttribute('type') || el.tagName.toLowerCase(),
      id: el.id || ''
    });
  });
  const ids = {};
  document.querySelectorAll('[id]').forEach(el => { ids[el.id] = (ids[el.id] || 0) + 1; });
  Object.entries(ids).forEach(([id, n]) => { if (n > 1) out.duplicateIds.push({ id, count: n }); });
  document.querySelectorAll('img').forEach(img => {
    if (img.complete && img.naturalWidth === 0) out.brokenImages.push(img.getAttribute('src'));
  });
  out.missingLandmarks = ['main', 'h1'].filter(sel => !document.querySelector(sel));

  // --- focus visibility: outline on keyboard focus ---
  const focusables = Array.from(document.querySelectorAll('a[href], button, input, select, textarea'))
    // Reaching a control is a precondition for judging its ring: elements in a
    // hidden pane (a closed drawer, an inactive slider panel) cannot take focus
    // and must not be counted as "missing a ring".
    .filter(el => el.offsetParent !== null || getComputedStyle(el).position === 'fixed');
  let styled = 0;
  const noRing = [];
  focusables.forEach(el => {
    try {
      el.focus({ preventScroll: true });
      if (document.activeElement !== el) return;   // truly unreachable
      const cs = getComputedStyle(el);
      const hasOutline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0;
      const hasShadow = cs.boxShadow && cs.boxShadow !== 'none';
      if (hasOutline || hasShadow) styled++;
      else noRing.push(el.tagName.toLowerCase() + '.' + String(el.className || '').split(' ')[0]);
    } catch (e) {}
  });
  out.focus = { focusables: focusables.length, withVisibleRing: styled, noRing: noRing.slice(0, 8) };
  document.activeElement && document.activeElement.blur();
  return out;
}
"""


@dataclass
class PageResult:
    page: str
    path: str
    url: str
    status: int | None = None
    theme: str = "light"
    viewport: str = "desktop"
    probe: dict[str, Any] = field(default_factory=dict)
    console_errors: list[str] = field(default_factory=list)
    failed_requests: list[str] = field(default_factory=list)
    note: str = ""


def role_sessions(base: str) -> dict[str, dict]:
    """One real Django session per role, reused for every page that needs it.

    This replaced form-based logins, which had a silent failure mode: they
    needed a known password, so the run quietly audited only the public pages
    whenever the database held the real credentials. A session row needs no
    password and cannot silently downgrade a run.
    """
    from ui_screenshots import session_cookies

    return session_cookies(base)


def audit(context, base: str, pages: list[tuple[str, str]], theme: str, viewport_name: str,
          viewport: dict, shots_dir: str | None) -> list[PageResult]:
    results: list[PageResult] = []
    page = context.new_page()
    page.set_viewport_size(viewport)
    for name, path in pages:
        errors: list[str] = []
        failed: list[str] = []
        on_console = lambda msg: errors.append(msg.text[:200]) if msg.type == "error" else None
        on_failed = lambda req: failed.append(f"{req.failure} {req.url[:120]}") if req.failure else None
        on_response = lambda res: failed.append(f"HTTP {res.status} {res.url[:120]}") if res.status >= 400 else None
        page.on("console", on_console)
        page.on("requestfailed", on_failed)
        page.on("response", on_response)
        result = PageResult(page=name, path=path, url=base + path, theme=theme, viewport=viewport_name)
        try:
            response = page.goto(base + path, wait_until="domcontentloaded", timeout=20000)
            result.status = response.status if response else None
            page.wait_for_timeout(700)
            result.probe = page.evaluate(PROBE_JS)
            if shots_dir:
                import os
                os.makedirs(shots_dir, exist_ok=True)
                page.screenshot(path=f"{shots_dir}/{viewport_name}-{theme}-{name}.png", full_page=False)
        except Exception as exc:
            result.note = f"probe failed: {exc}"
        result.console_errors = errors
        result.failed_requests = failed
        results.append(result)
        page.remove_listener("console", on_console)
        page.remove_listener("requestfailed", on_failed)
        page.remove_listener("response", on_response)
    page.close()
    return results


def summarise(results: list[PageResult]) -> str:
    lines: list[str] = []
    for r in results:
        probe = r.probe or {}
        contrast = probe.get("contrast", []) or []
        taps = probe.get("tapTargets", []) or []
        issues = (len(contrast), len(taps), len(probe.get("unlabeled", []) or []),
                  len(probe.get("brokenImages", []) or []), len(r.console_errors), len(r.failed_requests))
        flag = "OK " if not any(issues[:2]) and not r.console_errors and not r.failed_requests else "!! "
        lines.append(
            f"{flag}{r.viewport:7s} {r.theme:5s} {r.page:24s} status={r.status} "
            f"contrast={issues[0]:2d} tap<44={issues[1]:2d} unlabeled={issues[2]} broken-img={issues[3]} "
            f"console={issues[4]} net={issues[5]}"
            + ("  " + r.note if r.note else "")
        )
        if probe.get("overflow"):
            ov = probe["overflow"]
            lines.append(f"      H-OVERFLOW scrollWidth={ov['scrollWidth']} viewport={ov['viewport']} "
                         f"first={ov['offenders'][:2]}")
        for c in contrast[:5]:
            lines.append(f"      CONTRAST {c['ratio']}:1 (needs {c['required']}) {c['sel']} "
                         f"“{c['text']}” {c['color']} on {c['bg']}")
        for t in taps[:3]:
            lines.append(f"      TAP {t['w']}x{t['h']} {t['sel']} “{t['label']}”")
        if probe.get('unlabeled'):
            lines.append(f"      UNLABELED {probe['unlabeled'][:4]}")
        if probe.get("unverifiedBackground"):
            lines.append(f"      ({probe['unverifiedBackground']} text nodes skipped: gradient, image or"
                         f" no opaque backdrop — needs a pixel check, not a guess)")
        if r.console_errors:
            lines.append(f"      CONSOLE {r.console_errors[:2]}")
        if r.failed_requests:
            lines.append(f"      NET {r.failed_requests[:2]}")
        if probe.get("missingLandmarks"):
            lines.append(f"      MISSING {probe['missingLandmarks']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="http://127.0.0.1:8010")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--shots")
    ap.add_argument("--channel", default="msedge")
    ap.add_argument("--only", choices=["public", "student", "landlord", "admin"],
                    help="audit only one role's pages")
    args = ap.parse_args()

    # Windows consoles default to cp1252 and choke on the peso sign etc.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    base = args.base_url.rstrip("/")
    all_results: list[PageResult] = []
    skipped: list[str] = []
    # Must run before the Playwright event loop starts: this touches the ORM.
    sessions = role_sessions(base)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=args.channel, headless=True)

        def fresh(theme: str, viewport: dict, touch: bool = False):
            # Entrance animations are scroll-triggered, so without this the probe
            # skips every element that has not scrolled into view yet — they sit
            # at opacity 0, and the probe ignores anything below 0.15. That hid
            # whole sections from the contrast and label checks. Reduced motion
            # makes the page render its settled state instead.
            #
            # touch=True gives the context a real phone profile. It matters:
            # the stylesheet guards its tap targets with `@media (pointer: coarse)`,
            # and a 390px viewport WITHOUT touch reports pointer:fine, so that
            # whole block was skipped and the audit was measuring a condition no
            # visitor ever gets. Mobile renders must therefore be audited as
            # touch devices or the numbers mean nothing.
            ctx = browser.new_context(viewport=viewport, color_scheme="light",
                                      reduced_motion="reduce",
                                      has_touch=touch, is_mobile=touch)
            ctx.add_init_script(
                "try { localStorage.setItem('bhims-theme', '%s');"
                " localStorage.setItem('bhims-theme-version', 'teal-v2'); } catch (e) {}" % theme
            )
            return ctx

        # --- public pages ---
        if args.only in (None, "public"):
            for theme in ("light", "dark"):
                for vp_name, vp in (("desktop", DESKTOP), ("mobile", MOBILE)):
                    ctx = fresh(theme, vp, touch=(vp_name == "mobile"))
                    all_results += audit(ctx, base, PUBLIC_PAGES, theme, vp_name, vp, args.shots)
                    ctx.close()

        # --- logged-in roles (desktop both themes + a light phone pass each) ---
        if args.only in (None, "student"):
            if "student" not in sessions:
                skipped.append("student")
            else:
                for theme in ("light", "dark"):
                    ctx = fresh(theme, DESKTOP)
                    ctx.add_cookies([sessions["student"]])
                    all_results += audit(ctx, base, STUDENT_PAGES, theme, "desktop", DESKTOP, args.shots)
                    ctx.close()
                ctx = fresh("light", MOBILE, touch=True)
                ctx.add_cookies([sessions["student"]])
                all_results += audit(ctx, base, [("student-dashboard", "/students/dashboard/"),
                                                 ("browse", "/listings/"),
                                                 ("student-thread", "/students/inquiries/1/")],
                                     "light", "mobile", MOBILE, args.shots)
                ctx.close()

        if args.only in (None, "landlord"):
            if "landlord" not in sessions:
                skipped.append("landlord")
            else:
                for theme in ("light", "dark"):
                    ctx = fresh(theme, DESKTOP)
                    ctx.add_cookies([sessions["landlord"]])
                    all_results += audit(ctx, base, LANDLORD_PAGES, theme, "desktop", DESKTOP, args.shots)
                    ctx.close()
                # Every role also gets a phone pass. Landlord and admin were
                # desktop-only, which left the tap-target and overflow fixes on
                # those pages unverified — and the admin area has its own dense
                # tables, which are exactly what breaks first on a phone.
                ctx = fresh("light", MOBILE, touch=True)
                ctx.add_cookies([sessions["landlord"]])
                all_results += audit(ctx, base, LANDLORD_PAGES, "light", "mobile", MOBILE, args.shots)
                ctx.close()

        if args.only in (None, "admin"):
            if "root" not in sessions:
                skipped.append("admin")
            else:
                for theme in ("light", "dark"):
                    ctx = fresh(theme, DESKTOP)
                    ctx.add_cookies([sessions["root"]])
                    all_results += audit(ctx, base, ADMIN_PAGES, theme, "desktop", DESKTOP, args.shots)
                    ctx.close()
                ctx = fresh("light", MOBILE, touch=True)
                ctx.add_cookies([sessions["root"]])
                all_results += audit(ctx, base, ADMIN_PAGES, "light", "mobile", MOBILE, args.shots)
                ctx.close()

        browser.close()

    print(summarise(all_results))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump([r.__dict__ for r in all_results], fh, indent=2)
        print(f"\nwrote {args.json_out}")

    hard = [r for r in all_results
            if r.console_errors or r.failed_requests or (r.probe or {}).get("overflow")]
    print(f"\n{len(all_results)} page renders audited, {len(hard)} with hard failures")
    if skipped:
        # Loud on purpose: a skipped role means most of the run never happened.
        print(f"!! SKIPPED ROLES (no session): {', '.join(skipped)} — run is incomplete",
              file=sys.stderr)
    return 1 if skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())

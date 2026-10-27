# BHIMS — Responsive Layout Audit

Date: 2026-10-17
Method: live Django dev server (`127.0.0.1:8000`), Chromium at 320 / 375 / 768 / 1024 / 1440 px.
Each page measured with `document.documentElement.scrollWidth` vs viewport width plus a
per-element right-edge scan (fixed and horizontally-scrollable containers excluded).

Pages checked: landing (signed out), listings (filters closed/open), listing detail,
student login, student dashboard (rail closed/open), admin dashboard, admin analytics,
admin students table.

## Verdict

The responsive base is sound: **no page produces horizontal scroll at any tested width**
(320, 375, 768, 1024, 1440). `viewport` meta is present on both root templates
(`core/templates/core/base.html`, `core/templates/core/auth/base.html`) and every page
extends one of them. Touch targets are fine (sidebar toggle 44×44, inputs 49–53 px,
no sub-32 px targets on the student dashboard). The drawer, dim/blur scrim, Escape-to-close
and ghost-click guards all work at 375 px.

The defects below are cascade/layout problems, not missing breakpoints.

## P1 — visible defects

### 1. Role chip is invisible in the mobile drawer (contrast ≈1.02:1)
`.sidebar-profile-role` renders `color: #fff` at **9.92 px** over a pale wash card.
Measured computed colour `rgb(255,255,255)`, background `rgba(255,255,255,.18)` over
`--ce-card` paper. The word "Student"/"Landlord" is effectively unreadable.

Cause: `core/static/core/css/Campus Editorial.css:1815-1825` still assumes the mobile
profile card sits on a **solid `--ce-accent` panel** ("accent-on-wash resolved to
#14563c on #14563c"), but `Campus Editorial.css:1796` changed `.sidebar-profile` to
`--ce-accent-wash` (pale). The white-ink override kept the old ground.

Fix: give the mobile chip dark ink + a light ground (e.g. `color: var(--ce-ink)` on
`rgba(255,255,255,.55)`), and raise the font from `0.62rem` (`sidebar.css:241`) to
`0.7rem` so it is not sub-10 px.

### 2. Tablets get one full-width listing card per row
At 768 px the listings grid resolves to a single 709 px column. `repeat(auto-fill,
minmax(300px,1fr))` fits two 300 px cards at that width, so the grid is being
overridden: `core/static/core/css/Premium Styles.css:2447-2449` sets
`.houses-grid, .listing-grid, .landing-listings-grid { grid-template-columns: 1fr !important }`
inside `@media (max-width: 768px)` — and the `!important` beats `browse_content.css`'s
`minmax(280px,1fr)`.

Fix: scope that `1fr` rule to `max-width: 640px` (where one column is correct), or use
`repeat(auto-fill, minmax(260px,1fr))` for the 641–768 range. The same rule also hits
`.houses-grid`, used by the landlord dashboard and my-listings pages
(`landlord_dashboard.html:73`, `landlord_boarding_house_list.html:20`);
`.landing-listings-grid` is in the selector but unused in templates.

### 3. Stat cards collapse to one column on phones
`Premium Styles.css:2623` (`@media (max-width: 480px)`) forces `.stats-row` to
`1fr !important`. Consequences measured at 375 px:
- admin dashboard: 4 cards × ~88 px, ~420 px of scroll before any chart
- admin analytics: same 4 stacked cards
- student dashboard: 3 cards × ~74 px

The inline comment says the 2-up grid "cramps long labels like CONFIRMED BOOKINGS".
Better fix: keep `repeat(2,1fr)` and shrink label type / allow wrapping instead of
dropping to one column. Three-card rows can use `repeat(3,1fr)` with compact padding.

## P2 — polish

4. **Empty gallery tiles.** `.listing-hero` (`Premium Styles.css:1984-2020`) is a fixed
   2×2 grid (1.65fr + 1fr, 420 px tall) with variants only for `is-single` (1 photo) and
   `is-empty` (0 photos). With 2–4 photos the unused cells fall through to the container
   background (`rgba(255,255,255,.18)`) over the teal section, which reads as solid green
   blocks — verified on `/listings/1/` (2 photos) at both 375 px and 1440 px.
   Fix: add `is-double` / `is-triple` grid variants (e.g. 50/50 with one row, or let the
   last image span), or collapse to a single hero + thumbnail strip below 3 photos.

5. **Hero copy contrast.** At 320/768 px the subtitle sits directly over the painted
   "I ♥ DMMMSU" sign and the palm/foliage area; white text on a light, busy area.
   Add a left-side scrim behind the copy block (or shift the crop with `object-position`).
   Also the hero `h1` is ~44 px at 768 and still ~44 px at 1440 (`36.8 px` at 320) — it
   does not scale up for desktop, so the 1440 hero reads under-sized.

6. **No persistent nav on desktop.** `app_base.css:53-56` makes the collapsed state
   `display: none` at ≥769 px, and JS defaults to collapsed on first visit, so 1024/1440
   users land on a page with only a hamburger. Consider a default-visible rail at
   ≥1024 px (or a collapsed icon rail instead of `display:none`).

7. **Mobile admin table.** The wrapper scrolls correctly, but at 375 px the Student ID
   column shows "—" and status/actions sit off-screen with no scroll affordance.

## Breakpoint inventory (18 distinct)

Most-used: 768 (15), 640 (6), 820 (5), 700 (4), 980/900/480 (3 each), plus one-off
992/576/420 and min-width twins (769/821/901/1024). Two near-identical pairs
(`768` + `769`, `820` + `821`) exist only to express "above/below the sidebar breakpoint".
Consolidating on 480 / 640 / 768 / 1024 / 1280 would remove the
`!important` fights between `Premium Styles.css`, `Campus Editorial.css`, `iOS Theme.css`
and `Liquid Glass.css`, which are the root cause of items 2 and 3.

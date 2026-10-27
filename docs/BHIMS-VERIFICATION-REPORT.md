# BHIMS — Read-Only System Verification

**Date:** Oct 15, 2026  ·  **Method:** no code changed. Environment + test suite + live HTTP probing + role-based route sweep.

## Bottom line
**The system is available and fully working.** Every route answers correctly, the whole test
suite passes, and role-based features load for student, landlord and admin.

## 1. Environment / availability
- Python 3.12.10, Django 6.0.8, venv present and working.
- `manage.py check` → **0 issues**.
- Database (XAMPP MariaDB) reachable; **all migrations applied** (`migrate --check` clean, 25 app migrations + sessions).
- Dev server started on 127.0.0.1:8000 and answered HTTP 200 (`/` = 123 KB, `/health/` = `{"status":"ok"}`).
- Server log during the full probe: **zero 500s / tracebacks**.
- `check --deploy` → only the 4 standard HTTPS/HSTS cookie warnings (deployment-time, expected with DEBUG on locally).

## 2. Test suite
- `manage.py test core` → **129 tests, 0 failures, 0 errors** (exit 0, ~250 s).
- Covers registration, browse, price validation, landlord rating, ratings pages, security hardening,
  all-pages smoke, plus `tests_regressions.py` and `tests_adversarial.py`.

## 3. Live route availability (anon)
| Route | Result |
|---|---|
| `/`, `/listings/`, `/listings/1/`, `/listing/1/` | 200 |
| `/search/`, `/search/?q=test` | 200 |
| `/students/register/`, `/students/login/`, `/landlords/login/`, `/admin/login/`, `/accounts/login/` | 200 |
| `/password-reset/`, `/password-reset/done/`, `/password-reset-complete/` | 200 |
| `/health/` | 200 (`ok`) |
| `/favicon.ico` | 301 → static icon |
| `/admin/` (honeypot, GET) | 200 fake login |
| `/landlords/register/`, `/landlord/login/` | 302 → `/landlords/login/` (by design) |
| protected pages (dashboards, `/profile/`, `/chat/`) | 302 → login (correct) |
| `/health/?deep=1` (anon) | 404 — **intentional**, staff-only DB probe |
| unknown URL | 404 |

## 4. Role-based route sweep (authenticated)
Real accounts exist (student, landlord, admin: `root`). Every page below returned **200**:
- **Student:** `/students/dashboard/`, `/students/inquiries/`, `/students/bookings/`, `/profile/`, `/profile/edit/`, `/profile/change-password/`; logged-in `/` → 302 `/students/dashboard/`.
- **Landlord:** `/landlords/dashboard/`, `/landlords/inquiries/`, `/landlords/bookings/`, `/landlords/ratings/`, `/landlords/boarding-houses/`, `/landlords/boarding-houses/add/`; `/` → 302 `/landlords/dashboard/`.
- **Admin:** `/admin/dashboard/`, `/admin/analytics/`, `/admin/ratings/`, `/admin/landlords/`, `/admin/students/`, `/admin/listings/pending/`, `/admin/barangays/`, `/admin/settings/`, `/admin/reports/`, `/admin/landlords/add/`; staff `/health/?deep=1` → 200 `{db:true}`; `/django-admin/` → 200.

## 5. Functional checks
- **Search filtering works and changes results:** unfiltered = 12; `?amenities=WiFi` = 0 (matches prior contract); `?q=nonexistentxyz` = 0; `?price_min=1000&price_max=1200` = 7; `?room_type=single` = 6; `?barangay=Bacnotan` = 12; invalid `?sort=bogus` still 200.
  - Note: price/room-type/amenity filters are **room-level** (a house matches if any of its rooms matches), so `price_min=5000` = 0 is consistent, not a bug.
- **Templates render:** home title `Home - BHIMS NLUC Bacnotan`; listing detail title renders; registration form exposes `username, full_name, email, student_id, program, program_custom, password`.
- **Static files served:** `/static/core/images/bhims-icon.png` → 200 `image/png`.
- **Health endpoint:** liveness 200 unauthenticated; deep DB check staff-only (404 anon / 200 staff with `db:true`).
- **Data present:** 14 boarding houses (all `approved`), 112 rooms, 142 photos, 2 inquiries, 4 messages, 17 bookings, 16 ratings, 6 barangays, 27 admin-log entries.

## 6. Notes (not defects, no action taken)
- `SiteSetting` and `UserReport` tables are empty (features unused; defaults apply) — not an error.
- The 302s on `/` for logged-in users are intentional role redirects.
- No code was modified; the only artifacts are this report and the run logs under `logs/`.

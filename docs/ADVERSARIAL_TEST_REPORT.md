# Adversarial test report — Build → Test → Find → Fix → Test again

> **The question this round asked was not "does the system work?" but
> "how can this system be destroyed?"** Every test below is an attack on an
> invariant, not a happy path. Numbers are measured, not estimated.

Run with:

```bash
# Behaviour + attack suite on the review (SQLite) stack
venv\Scripts\python.exe manage.py test core --settings=review_settings

# Same suite against the real MariaDB stack (includes the concurrency race)
venv\Scripts\python.exe manage.py test core --settings=myproject.settings --noinput
```

**Result after the fixes: 73 tests pass — 73/73 on MariaDB, 73/73 (1 skipped:
SQLite has no row locks) on the review stack.**

- Attack suite: `core/tests_adversarial.py` (44 tests, four categories)
- Regression suite: `core/tests.py` (29 tests, unchanged and still green)

---

## 1. Wrong output

| # | Attack | Before | After |
|---|--------|--------|-------|
| 1 | Advertise a price from a room the landlord had switched off | card showed **₱100** from an inactive room | shows **₱5000** (the real, bookable room) |
| 2 | "N rooms available" must respect the filter the student applied | badge said **2 open** while only 1 room fitted the ₱2000 cap | **1 open** |
| 3 | "N rooms available" must not count booked-out rooms | a room booked to capacity counted as free | excluded |
| 4 | "Lowest price first" must actually be ascending | rows interleaved per room | verified ascending in the browser |
| 5 | Accept a student into a **rejected** listing | confirmed booking created inside a listing students cannot see | refused |
| 6 | Accept a student into a **switched-off room** | booking created | refused |

## 2. Duplicate data

| # | Attack | Before | After |
|---|--------|--------|-------|
| 7 | One house with 3 matching rooms appears 3× in the grid | **3 identical cards** | 1 card |
| 8 | Same, on `/search/` | 3 cards | 1 card |
| 9 | Same, under a stacked filter (type + price + barangay + sort) | 3 cards | 1 card |
| 10 | Double/triple-click **Accept** | duplicates were possible | exactly 1 confirmed booking |
| 11 | Ask about the same room three times | 1 conversation (already correct) | 1 conversation |
| 12 | Opening the inquiry page creates a row | nothing created (already correct) | nothing created |
| 13 | Duplicate email / student ID registration | refused (already correct) | refused |

**Root cause of 7–9:** filters were written as JOINs across the `rooms`
relation, which multiplies a boarding house by its matching rooms. Sorting by
`rooms__monthly_rate` also defeated `.distinct()` because the ORDER BY column is
added to the SELECT list. Filters are now `EXISTS` subqueries and the sort uses a
correlated `Subquery`, so a house can never be produced twice.

## 3. High volume (what happens when the campus shows up at once)

Measured with the project's own tool, against the production server
(`Run Production Server.py`, Waitress + MariaDB + `DJANGO_DEBUG=0`):

```bash
BHIMS_PORT=8010 venv\Scripts\python.exe "Run Production Server.py"
LT_BASE=http://127.0.0.1:8010 venv\Scripts\python.exe "tools/Load Test.py" 500
```

| Scenario | Requests | Failures | p50 | p90 | rps |
|---|---|---|---|---|---|
| 200 users, **before** fixes | 1800 | **21 × HTTP 500** | 2025 ms | 3058 ms | 82 |
| 200 users, after fixes | 1800 | **0** | **149 ms** | 1259 ms | 112 |
| 500 users, 32 threads | 4464 | **197 × ConnectionRefused** | 4089 ms | 5779 ms | 100 |
| 500 users, **96 threads** | 4464 | **0** | 3677 ms | 8168 ms | 98 |

Findings that only appear under load:

- **21 × HTTP 500 at 200 users.** Every failure was `cache.get()` →
  `FileBasedCache` → `PermissionError: [Errno 13] Permission denied` on
  `/listings/`. The cache existed to absorb a stampede and was taking the site
  down during one. Fixed twice over: the resilient backend is back (LocMemCache
  is correct here — the launcher runs **one process with many threads**, so all
  users share it), and **page-cache failures can no longer 500 a page** — a
  broken cache now degrades to a normal render.
- **197 connection refusals at 500 users.** The accept queue drains only as
  fast as idle worker threads exist. Raised the launcher default from 32 to 96
  threads → 0 failures. (96 stays under MariaDB's `max_connections=151`, since
  Django holds one connection per active thread.)
- **N+1 query fan-out.** Per-request query counts before → after:

  | Page | Before | After |
  |---|---|---|
  | Listing detail, 12 rooms | 54 | 7 |
  | Landlord property page, 12 rooms | 104 | 19 |
  | Browse page | grew with catalogue | **flat** (asserted by test) |

  Root causes found by dumping the actual SQL:
  1. `Room.occupied_count` ran its own `COUNT(*)` per room in template loops.
  2. **`manager.first()` bypasses Django's prefetch cache** — `room.photos.first()`
     costs a query per room even when `photos` was prefetched. Replaced with a
     `primary_photo` property that iterates `all()` (verified: `first()` = 3
     queries, `all()` = 0).
  3. `house.rooms.count` / `house.rooms.all` inside template loops re-queried
     what the view had already loaded and annotated.
- **No pagination on the hottest public page.** `/listings/` rendered the entire
  catalogue (and counted every room in it) on every request. Now 12 per page,
  with the pager inside the AJAX fragment so filtering and paging compose.
- **A per-IP write throttle starves the campus.** One shared NAT/proxy address
  meant a normal classroom consumed a single allowance and innocent users got
  429s. Budgets are now per signed-in user (IP only for anonymous callers).
- **Security counters lost increments.** `get → +1 → set` drops updates when
  requests interleave. Now `cache.add` + `cache.incr`, which is atomic.

## 4. Network / dependency failure

| # | Attack | Result |
|---|---|---|
| 14 | Break the cache backend and hit the cached pages | `/` and `/listings/` still **200** (was a 500) |
| 15 | Static CSS revalidation | **304** on conditional GET; no re-download per page view |
| 16 | Path traversal `/media/../settings.py` | refused, no file contents leaked |
| 17 | Listing whose image file was deleted out-of-band | page still renders |
| 18 | Missing static asset | 404, not 500 |
| 19 | Database goes away on `/`, liveness `/health/` | graceful; `/health/` stays 200 by design |
| 20 | Unauthorised JSON poll | JSON error, never an HTML body that breaks the polling UI |
| 21 | Concurrent `accept` on the last bed (2 threads, MariaDB) | **exactly 1 booking** — no overbooking |

---

## 5. Bugs found by the *second* pass (fixing things broke things)

The re-verification pass is not a formality — it caught two regressions
introduced during this round:

1. **Multi-line `{# ... #}` comments rendered as visible text.** `{# #}` is a
   single-line comment in Django; written across several lines the whole block
   is printed verbatim onto the page. Five occurrences (including one on the
   login pages from an earlier round) were showing up in the page body.
   Converted to `{% comment %}` and guarded by
   `RenderedTemplateIntegrityTests`.
2. **The first "fix" for the cache made things worse.** Moving production to a
   file-based cache to share state between workers introduced the 21 × HTTP 500
   described above. Reverted, with a settings comment explaining *why*
   LocMemCache is the correct choice for a single-process server and a test
   asserting the launcher must not fork workers.

---

## 6. Files changed in this round

| File | Change |
|---|---|
| `core/tests_adversarial.py` | **new** — 44 attack tests in four categories |
| `core/views.py` | EXISTS/Subquery listing filters, filtered price + availability, pagination, `_cache_get/_cache_set` (cache can't 500), `_hit` (atomic counters), per-user throttle keys, booking guards for rejected/inactive listings, N+1 removals |
| `core/models.py` | annotation-aware `occupied_count`/`is_full`/`has_space`, `annotate_room_bookings()`, `primary_photo`, `get_photo_list` in one query, listing-cache invalidation via signals |
| `core/templates/core/includes/listing_grid_fragment.html` | pagination inside the AJAX fragment |
| `core/templates/core/includes/listing_card.html` | uses the prefetched room label; comment syntax fixed |
| `core/templates/core/includes/boarding_detail_content.html` | `primary_photo`; comment syntax fixed |
| `core/templates/core/includes/browse_content.html` | AJAX pager clicks |
| `core/templates/core/landlord_boarding_house_detail.html` | loops the annotated `rooms`; `primary_photo`; comment syntax fixed |
| `core/templates/core/landlord_boarding_house_list.html`, `landlord_dashboard.html`, `admin_pending_listings.html` | annotated `total_rooms` instead of per-row `rooms.count` |
| `core/templates/core/auth/base.html` | comment syntax fixed |
| `myproject/settings.py` | documented cache choice (and the Windows FileBasedCache trap) |
| `Run Production Server.py` | worker default 32 → 96, with the measurements that justify it |
| `core/static/core/css/Campus Editorial.css` | browse-pagination styling |
| `tools/Load Test.py` | `LT_BASE` env var so the tool can target any instance |

---

## 7. Honest limitations

- Latency at 500 concurrent users is ~3.7 s p50. That is queueing, not
  slowness: `concurrent users ÷ throughput` (500 ÷ ~100 rps ≈ 5 s). A single
  Python process on this machine tops out near **~100 rps**; more throughput
  needs real horizontal scaling, which is out of scope for the defence.
- `max_connections=151` on XAMPP's MariaDB caps how far `BHIMS_WORKERS` can be
  raised without raising that setting too.
- The review accounts (`review_student`, `review_landlord`, `review_admin`,
  password `CeReview#2026`) were created for this audit — change or delete them
  before the demonstration.
- The ten files in `core/static/core/js/` are loaded by **no template at all**
  (the theme toggle and filters are inline in the pages). They are dead weight,
  not a bug — deleting them is a deliberate decision, not a fix.

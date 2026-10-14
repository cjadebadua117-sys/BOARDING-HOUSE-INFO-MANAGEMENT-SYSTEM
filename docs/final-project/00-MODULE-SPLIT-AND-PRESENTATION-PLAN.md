# BHIMS — Final Project: Module Split & Presentation Plan

**System:** BHIMS — Boarding House Information Management System (DMMMSU–NLUC Bacnotan)
**Course:** Business Information Systems & Systems Analysis and Design — BSIS 3B
**Instructor:** Mr. Vincent Haber
**Group:** Badua, Christian Jade B. · Bayubay, Jerome O. · Layco, Mac Gabrielle L. · Valdriz, Noemi G.
**Basis:** `Final_Project_Instructions.docx` (Individual System Presentation) + `BHIMS MIDTERM PROJECT.docx`

> This file is the written split the instructions ask for: *"Agree on the split with your group and
> the instructor, and write it down before you start."*

---

## 1. What the final actually requires

| Rule (from the instructions) | What it means for us |
|---|---|
| "This task is individual. You are graded on your own module, your own demo, and your own answers, even though the system itself belongs to the group." | One running system, four separate module presentations. |
| "Every member of the group takes a different module… One module per student." | No two members may present the same function. |
| "Choose a module that has real inputs, processing, and outputs. A login page alone is not enough." | Each module below has all three. |
| "You present the real, running system for your module. Do not use PowerPoint, Google Slides, Canva, Figma…" | Demo from the live Django app, on your own laptop. Deliverable B is only opened to show diagrams/test results. |
| "Run at least 5 test cases and report the results." | 5+ honest test cases **per member**, on that member's module. |
| Each member submits their own files + own printed midterm exam | `FinalProject_[LastName]_BSIS3B` + `FinalProject_[LastName]_Summary.docx/pdf`, plus the printed exam. |

---

## 2. The situation, stated honestly

Christian built and integrated the entire running system; the group's shared work so far is the
midterm analysis and design. The instructions already cover this: the system belongs to the group,
and each member is graded on **their module, their demo, and their answers** — not on typing all the
code. So the correct move is *not* to fake four separate systems. It is to:

1. Split the system into four modules that match the midterm's IPO table (done below).
2. Write the split down and show it to Mr. Haber **before** presentation day.
3. Let each member present their own module, with their **own** test cases, own Summary, own demo
   scenario, own printed exam.
4. If the instructor asks "who wrote this code?", answer truthfully: Christian built and integrated
   the system; each member is presenting and defending their assigned module of it. Do not claim
   authorship anyone cannot defend — that is the fastest way to lose the 10 Q&A points.

Nobody should present a module they cannot explain. If a member cannot defend a module, swap modules
now, not on presentation day.

---

## 3. The written module split

The midterm IPO table already defined 8 modules. The final gives 4 students, so the 8 fold into 4
presentable modules — each still a real input → process → output unit, each with its own screens,
its own tables, and its own test evidence.

| # | Module | Midterm IPO modules covered | Owner (proposed) |
|---|---|---|---|
| **A** | **Boarding House & Room Management + Verification** | 2. Boarding House & Room Management · 8. Administration & Analytics (verification half) | **Noemi** |
| **B** | **Search, Inquiry & Booking** | 3. Search & Availability · 4. Inquiry & Messaging · 5. Booking Management | **Christian** |
| **C** | **Review, Rating & User Reporting** | 6. Review & Rating · 7. User Reporting | **Jerome** |
| **D** | **Accounts, Administration & Analytics** | 1. User & Account Management · 8. Administration & Analytics (oversight half) | **Mac** |

Why Christian takes B: it is the core end-to-end workflow of the system (3 of the 8 midterm
modules), it has the richest processing and the strongest test evidence, and it is the module the
builder can defend to the last detail. Everyone else gets one landlord/student-facing module and one
admin-facing module, so no one is stuck in a single role's screens.

---

## 4. Module detail cards

Every card lists: **Inputs → Processing → Outputs**, the live demo path, the data it exchanges with
the other modules (this is the "where your module fits" section, 1:30), and the automated tests that
already exist in `core/` that the member can cite and re-run.

### Module A — Boarding House & Room Management + Verification — *Noemi*

- **Inputs:** landlord registration of boarding house (name, barangay, address, description), room
  details (room type, capacity, monthly rate, amenities, photos), availability toggles, resubmission
  of a rejected listing; admin approve/reject decision; barangay reference data.
- **Processing:** validation (negative price rejected, capacity must be ≥ 1, photo upload cap),
  listing approval state machine (`pending → approved / rejected → resubmit`), availability flag
  per room, barangay master data maintenance.
- **Outputs:** approved, publicly visible listings with rooms/photos/amenities; room availability
  board on the landlord dashboard; admin moderation (pending) queue; audit trail of admin actions.
- **Demo path:** `/landlords/boarding-houses/add/` → `/landlords/boarding-houses/<pk>/rooms/add/` →
  `/landlords/rooms/<pk>/toggle-availability/` → `/admin/listings/pending/` →
  `/admin/listings/<pk>/approve/` (and one reject → `/landlords/boarding-houses/<pk>/edit/` resubmit)
  → verify the listing now appears on `/listings/`.
- **Hands to other modules:** approved listing + room records are *the* input of Module B's search;
  the approval status decides whether Module D's analytics count the listing.
- **Existing tests to cite/re-run:** `ListingPriceValidationTests`, `RoomPhotoUploadCapTests`,
  `RoomFormPageTitleTests`, plus the approval guards in `WrongOutputBookingTests`
  (accepting into a rejected listing is refused).

### Module B — Search, Inquiry & Booking — *Christian*

- **Inputs:** search/filter criteria (barangay, price range, room type, amenities, availability only,
  sort), inquiry text + chat messages, booking request on a specific room, landlord accept/reject
  decision.
- **Processing:** `EXISTS`-based filtering over rooms (a house can never be produced twice), price
  sort via correlated subquery, availability computed from *bookable* rooms only (capacity minus
  confirmed bookings, inactive rooms excluded), one conversation per student–room pair, booking
  state machine `pending → confirmed / declined`, capacity + listing-status guards, race-safe accept.
- **Outputs:** result grid with an honest "N rooms available" badge and lowest bookable price,
  boarding-house detail page, saved inquiry threads with timestamps, confirmed/declined booking,
  updated availability counts.
- **Demo path:** `/listings/` (apply stacked filters + "lowest price first") → `/listings/<pk>/` →
  send inquiry → `/landlords/inquiries/` as landlord → reply in thread → `/landlords/inquiries/<pk>/accept/`
  → back as student: `/students/bookings/` shows the confirmed booking and the listing's open-room
  count drops.
- **Hands to other modules:** consumes Module A's listings; the confirmed booking it produces is the
  *eligibility key* for Module C's rating; its booking counts feed Module D's analytics.
- **Existing tests to cite/re-run:** `WrongOutputPriceTests`, `WrongOutputAvailabilityTests`,
  `WrongOutputSortTests`, `WrongOutputBookingTests`, `DuplicateCardTests`, `AcceptRaceTests`,
  `HighVolumeQueryBudgetTests`, `HighVolumePaginationTests`, `HighVolumeCacheTests`.
- **Best bug story in the whole system:** before the fix, one house with 3 matching rooms appeared
  3× in the grid, the card price came from a room the landlord had switched off, and "2 open" showed
  while only 1 room fit the student's price cap. Root cause (JOIN filters + `ORDER BY` defeating
  `.distinct()`) and fix (EXISTS subqueries + correlated subquery sort) are documented in
  `docs/ADVERSARIAL_TEST_REPORT.md` §1–§2 — perfect for the Testing part (1:30).

### Module C — Review, Rating & User Reporting — *Jerome*

- **Inputs:** landlord rating (1–5 stars + comment) from a student, submitted from the booking;
  user report (reason + details) filed by a student or landlord.
- **Processing:** eligibility validation (only the student with a **confirmed booking** can rate that
  landlord, exactly once — DB unique constraint per student–landlord pair; landlords cannot rate;
  students without a booking are blocked), average recomputation for display, report recording and
  the admin resolve/dismiss workflow.
- **Outputs:** average landlord rating shown on listings and detail pages; rating statistics and
  filters on `/landlords/ratings/` and `/admin/ratings/`; resolved report with the action taken and
  the audit record.
- **Demo path:** as a student with a confirmed booking → `/users/<pk>/rate/` → see the average change
  on `/listings/<pk>/` → try to rate again (blocked, one rating only) → `/users/<pk>/report/` to file
  a report → as admin `/admin/reports/` → `/admin/reports/<pk>/update/` to resolve it.
- **Hands to other modules:** needs Module B's confirmed booking as its eligibility key; surfaces its
  averages in Module A's listing cards and Module D's admin ratings overview.
- **Existing tests to cite/re-run:** `LandlordRatingTests` (can rate once with a confirmed booking,
  cannot rate without one, landlord cannot rate), `RatingsPagesTests` (stats + filters + role guards),
  `PublicNameDisplayTests`.
- **Say this in "What Changed":** the midterm proposed free-standing house *reviews*; the built system
  tightened this into a booking-tied landlord rating (see `CHANGES-SINCE-MIDTERM.md` #1). That is a
  real, explainable design decision — exactly what the 15 continuity points want.

### Module D — Accounts, Administration & Analytics — *Mac*

- **Inputs:** student/landlord registration details (name, contact, e-mail, program or K-12 grade
  level), login credentials, admin commands (create/edit/deactivate/delete landlord accounts,
  manage students, barangays, site settings), report assignments.
- **Processing:** registration validation (duplicate e-mail/student ID refused), role assignment and
  role-based access, login hardening (lockout after 15 failed attempts, admin IP allowlist, honeypot
  probe logging), audit logging, aggregation for the dashboard/analytics.
- **Outputs:** active role-based accounts and secured sessions, deactivated/reactivated accounts,
  maintained barangay + settings reference data, admin dashboard and analytics summaries, Power BI
  dataset export (`BHIMS_PowerBI_Data.xlsx` via `generate_powerbi_excel.py`), audit log.
- **Demo path:** `/students/register/` (invalid e-mail/ID rejected → valid registration succeeds) →
  `/admin/landlords/add/` → `/admin/landlords/<pk>/toggle/` (deactivate → the account can no longer
  log in → reactivate) → `/admin/barangays/` → `/admin/settings/` → `/admin/analytics/` +
  the Power BI workbook.
- **Hands to other modules:** it owns every account the other three modules act as, and it reads the
  listings (A), inquiries/bookings (B), and ratings/reports (C) to build analytics.
- **Existing tests to cite/re-run:** `StudentRegistrationFlowTests`, `SecurityHardeningTests`
  (account lockout, admin IP allowlist, honeypot, audit log, security headers),
  `AllPagesSmokeTest`, `ProfileEditKeepsDisplayNameTests`, `CrossRoleRedirectLoopTests`.

---

## 4b. Diagrams for Deliverable B — the updated set exists now

The midterm diagrams in `docs/diagrams/` were deliberately left untouched (you need them for the
"what changed" comparison). The updated set for the final lives in `docs/final-project/diagrams/`,
rendered from Mermaid sources next to each PNG:

| File | Use it for |
|---|---|
| `Level 0 - Context Diagram (built).png` | Part 2 "Midterm Recap" — the system boundary |
| `Level 1 - Data Flow Diagram (built).png` | Part 4 "Where your module fits". Process numbering matches the midterm IPO table 1:1, so module **A = 2.0**, **B = 3.0 + 4.0 + 5.0**, **C = 6.0 + 7.0**, **D = 1.0 + 8.0** |
| `Entity Relationship Diagram (built).png` | Part 5 "Module Design" — the matching tables |
| `Module A–D - DFD (…).png` | The page-sized extract each member actually pastes into their own 2–4 page Summary |
| `Module A–D - ERD (…).png` | That member's ERD extract (e.g. Module C shows the rating → booking one-to-one that enforces eligibility) |

Re-render after editing any `.mmd`:

```powershell
venv\Scripts\python.exe tools\render_diagrams.py docs\final-project\diagrams
```

Rendering is offline and needs no Node: `tools/vendor/mermaid.min.js` is vendored and the script uses
the project's existing Playwright Chromium at 3x, so the PNGs stay sharp when projected.

**Say this in part 3 (What Changed) about the diagrams:** process **6.0 Rating & Review** now exists
(the midterm DFD jumped from reporting straight to administration), the ERD gained `LANDLORD_RATING`
(1:1 with `BOOKING`, which is what makes "confirmed booking only" a schema rule rather than a
promise), `BARANGAY`, `SITE_SETTING` and `ADMIN_ACTION_LOG`, booking status is the implemented
`pending / confirmed / declined / cancelled`, and rent lives on the room as `monthly_rate` — the
house-level `price` is only a displayed range.

**Printing tip:** the full Level 1 DFD is a wide poster — print it alone on its own sheet (landscape),
and put your *module* extract on the Summary page where it is actually readable.

---

## 5. Per-member checklist (identical for all four, non-negotiable)

1. **Deliverable A — the running system, live.** Your own laptop, your module's screens only.
   Rehearse the exact click path above; have a DB backup ready (`boarding_house_system_backup_*.sql`).
2. **Deliverable B — 2–4 page Summary** (`FinalProject_[LastName]_Summary.docx/pdf`) containing:
   (1) your updated Level 0/1 DFD and ERD extract for your module,
   (2) ≥5 test cases in the table format *Input | Expected | Actual | Pass/Fail*,
   (3) changes since midterm + reason (reuse `CHANGES-SINCE-MIDTERM.md`),
   (4) implementation plan — conversion method (**recommend phased or pilot**, justify it), training
   (who, what, how long), support & maintenance.
3. **Deliverable C — printed graded Midterm Exam**, name + section on page 1, bond paper, single
   sided, stapled top-left, handed over **before** presenting.
4. **Your own ≥5 test cases** run for real, with honest pass/fail. Cite automated test class results
   as supporting evidence, but the table is your 5 manual cases.
5. **Files:** folder/zip `FinalProject_[LastName]_BSIS3B`, summary `FinalProject_[LastName]_Summary`.
   One set per student — never a group bundle.
6. **References section** in the Summary citing any source, template, or code you did not write
   (this covers the group's shared midterm diagrams and the libraries used).

---

## 6. Presentation script template (10–12 min, from the instructor's flow)

| # | Part | Time | What you say / do (module-specific) |
|---|---|---|---|
| 1 | Introduction | 0:30 | Name, BHIMS, your module, the one-line problem it solves. |
| 2 | Midterm Recap | 1:00 | Problem, objectives, proposed system; show the **Context Diagram** from your Summary. |
| 3 | What Changed | 1:00 | Your 2–3 changes from `CHANGES-SINCE-MIDTERM.md` that touch your module, and why. |
| 4 | Where Your Module Fits | 1:30 | Updated Level 0/1 DFD; name the data you receive from / send to the other three modules. |
| 5 | Module Design | 1:30 | ERD; point at the matching tables, forms, and reports in the running system. |
| 6 | Live Demo | 3:00 | The scenario in your module card, start to finish, real data in → real output out. |
| 7 | Testing | 1:30 | Your test table, the bugs you found, how you fixed them, then run 1–2 tests live. |
| 8 | Implementation Plan | 1:00 | Conversion method, training, support & maintenance. |
| 9 | Results vs Objectives | 0:30 | Each measurable midterm objective your module covers: met / partly / not met. |
| 10 | Conclusion | 0:30 | Takeaways, limitations, future improvements → Q&A. |

Rehearse with a timer at least twice. Going over is stopped by the instructor.

---

## 7. Q&A drills (expect these)

Every member should be able to answer, for **their** module:

1. Show me where your module's data is stored — which tables and which relationship?
2. What happens if two students book the last slot in the same room at the same time?
3. Which requirement from the midterm does this screen satisfy?
4. What did you change from the midterm design and why?
5. How does your module connect to the other three? (Answer from the "Hands to other modules" line.)
6. What is a limitation of your module, and how would you improve it?
7. (System-wide, anyone may be asked) What are the BIS components / which SDLC phases did you do in
   which order / what are the levels of requirements?

For #2 the correct answer comes from the measured evidence: accepting a student twice creates exactly
one confirmed booking, and accepting into a rejected listing or an inactive room is refused
(`core/tests_adversarial.py`, `AcceptRaceTests`).

---

## 8. Run commands (for test evidence on presentation day)

```bash
# whole suite — 123 tests (54 adversarial + 29 behaviour + 27 regression + 13 exploration)
venv\Scripts\python.exe manage.py test core

# one module's evidence
venv\Scripts\python.exe manage.py test core.tests_regressions
venv\Scripts\python.exe manage.py test core.tests.LandlordRatingTests core.tests.RatingsPagesTests
venv\Scripts\python.exe manage.py test core.tests.SecurityHardeningTests core.tests.StudentRegistrationFlowTests
venv\Scripts\python.exe manage.py test core.tests_adversarial.DuplicateCardTests core.tests_adversarial.WrongOutputPriceTests

# the system itself, live
venv\Scripts\python.exe manage.py runserver
```

**Measured on October 14, 2026: 123/123 pass** (MariaDB, the real database).

---

## 9. Bug log — found and fixed while preparing (use for presentation part 7 "Testing")

Part 7 asks you to "name the bugs you found and how you fixed them". These three are real,
reproduced, and measured — each one is a stronger answer than "we tested the forms":

| Bug | Symptom | Root cause | Fix | Evidence |
|---|---|---|---|---|
| Every page died | The suite collapsed with **123 errors** and every URL returned 500 | The templates had been reorganised to bare names (`base.html`, `app_base.html`, `includes/…`, `auth/…`) but `TEMPLATES['DIRS']` was never pointed at the folder holding them, so no template could be found | Point `DIRS` at `core/templates/core` (`myproject/settings.py`) | 123 errors → 0; landing, listings, all three login pages return 200 |
| Template text printed on the page | `/listings/` showed a raw comment block and dump of example HTML above the results grid | The comment used `{# … #}`, which Django only strips when it opens and closes on the **same line** — the block in `includes/listing_grid_fragment.html` spanned 13 lines and had no closing `#}` at all | Rewrote both multi-line comments as `{% comment %} … {% endcomment %}` | Rendered page: no `{#`, no `{%`, grid renders 12 real cards |
| Browse got slower as listings grew | Cost rose with the catalogue: **8 queries for 1 house → 16 for 9 houses** (one page shows 12) | The card prints the first bookable room's amenities, and the prefetched room set did not include them → **one extra query per house** | Prefetch the amenities with the rooms in `decorate_house_cards()` (`core/views.py`) | Query count is now flat in the number of houses; `HighVolumeQueryBudgetTests` passes |

Say it the way the rubric wants it: *defect found → root cause → fix → re-tested.* The query-budget
number is the one to quote, because it is the difference between a system that survives a
campus-wide surge and one that does not.

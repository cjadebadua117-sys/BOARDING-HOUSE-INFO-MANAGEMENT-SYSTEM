# BHIMS — What Changed Since the Midterm (and Why)

Source of truth: `BHIMS MIDTERM PROJECT.docx` (proposal) vs the **built system**
(`core/models.py`, `core/views.py`, `core/urls.py`), plus the measured evidence in
`docs/ADVERSARIAL_TEST_REPORT.md` and `.audit/AUDIT_REPORT.md`.

Use this for presentation part **3. What Changed (1:00)** and Summary item **(3) list of changes
made to the midterm design, and why**. Every member should present only the rows that touch their
module.

| # | Midterm said | Built system does | Why | Presented by |
|---|---|---|---|---|
| 1 | Module 6: students with a confirmed booking submit/edit **boarding-house reviews**; students also rate landlords after an inquiry is accepted or declined | There is **no free-standing Review entity**. Ratings are `LandlordRating`: 1–5 stars + comment, unique per (student, landlord), allowed once the landlord settles the inquiry — accepted (linked to the confirmed booking) or declined (booking left empty), exactly once | One eligibility rule instead of two, no orphan or duplicate reviews, and the rating is tied to a real transaction — which makes the average meaningful rather than anonymous | Jerome (C) |
| 2 | Scope L: "real-time in-app notifications" | **Not built.** Information is carried by inquiry threads, booking status, dashboards, and the accept/decline response instead | A notification layer needs polling/push infrastructure that competes with the time available for the search, booking and moderation logic. Listed honestly as *partly met / not met* and as the top future improvement | Mac (D) — results vs objectives |
| 3 | Module 3: filter by price, room type, amenity, barangay, availability; sort results | Same filters, but the implementation was **rewritten**: filters are `EXISTS` subqueries over rooms and the price sort is a correlated `Subquery` | The original JOIN-based filters multiplied a boarding house by each matching room — one house with 3 matching rooms produced **3 identical cards** — and `ORDER BY rooms__price` defeated `.distinct()` because the sort column joins the SELECT list. Measured before/after in `ADVERSARIAL_TEST_REPORT.md` §2 | Christian (B) |
| 4 | Module 3/5: show price and room availability | The card price comes only from **bookable** rooms (a room the landlord switched off can no longer advertise its price), and "N rooms available" counts only active rooms that still have free capacity | The badge was promising rooms a student could not actually book — the exact problem BHIMS exists to solve ("travelling to a boarding house only to find the room already taken") | Christian (B) |
| 5 | Module 5: landlord approves or declines the booking request | Accepting writes a confirmed **booking** with guards: a **rejected listing**, an **inactive or full room** and a second accept are refused; double/triple-submitting Accept yields exactly **one** confirmed booking (row-level locking; concurrency test runs on MariaDB) | The guards protect the invariant "a confirmed booking always points at a bookable room", and the race test proves it under simultaneous requests | Jerome (C) |
| 6 | — (not in the midterm) | **Audit log** (`AdminActionLog`), **admin IP allowlist**, **account lockout after 15 failed logins**, security headers, a **fake `/admin/` honeypot** that logs probes, and a health check endpoint | Verification and oversight were a stated objective; recording every admin action and every probe makes the administrator module defensible instead of cosmetic | Mac (D) |
| 7 | Module 2: landlord submits listing for administrator approval | Built as a real state machine `pending → approved / rejected → resubmit`, with moderation queue, barangay master data, and admin settings | Verification needed an actual workflow with a queue and a resubmission path, otherwise rejected listings were a dead end | Noemi (A) |
| 8 | Resources table: MySQL via XAMPP | Same, plus a **custom compatibility backend** (`myproject/mysql_backend/`): XAMPP ships MariaDB 10.4 while Django 6 requires 10.5+, and BHIMS uses only basic SQL features | Honest infrastructure note; documented and removable for production | Anyone asked about deployment |
| 9 | Module 8: administrator analytics/dashboard | Built: the admin dashboard and analytics summaries aggregate the live listings, inquiries, bookings, ratings and reports inside the system | Turns "analytics" from a screenshot into a working view of the real database | Mac (D) |
| 10 | Design Specification: Input/Output sketches, UI | One design system in light and dark themes, with accessible focus states; static assets carry explicit `?v=` cache-busting versions | The midterm only had sketches; the built UI is the reviewed version of them | Anyone asked about design |

## Design documents that must be refreshed for the final

The midterm diagrams no longer match the built system, and the final *requires* the updated set:

- **Level 0/1 DFD** (`docs/diagrams/Data Flow Diagram - Level 1.mmd`) — shows 7 processes and has
  **no rating/review process**, although rating is built and presented by Module C.
- **ERD** (`docs/diagrams/Entity Relationship Diagram.mmd`) — missing `LANDLORD_RATING`, `BARANGAY`,
  `SITE_SETTING`, `ADMIN_ACTION_LOG`, the `ROOM ↔ AMENITY` many-to-many, and shows booking status as
  `pending / approved / declined` instead of the implemented `pending / confirmed / declined / cancelled`.
- **Context diagram** — still accurate; only the list of flows into process 6.0 (review & rating)
  needs to be restated as rating.

## Known open issue to disclose or fix before presentation day

`send_inquiry` (`core/views.py:1362`) still performs its **delete of a rejected inquiry on a plain
GET**, before it checks the request method — the H1 finding in `.audit/AUDIT_REPORT.md`. Revisiting
an old link can therefore wipe a rejected conversation and its messages. Everything else destructive
in the system is behind POST + CSRF (11 `@require_POST` guards). Either fix it (move the
delete/recreate behind POST) or present it as a known limitation — but do not let a demo click an old
rejected-inquiry link while it is unfixed.

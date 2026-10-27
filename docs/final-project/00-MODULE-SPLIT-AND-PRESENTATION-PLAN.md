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
| **B** | **Search & Inquiry (Messaging)** | 3. Search & Availability · 4. Inquiry & Messaging | **Christian** |
| **C** | **Booking, Acceptance & Ratings** | 5. Booking Management · 6. Review & Rating | **Jerome** |
| **D** | **Accounts, Administration, Analytics & Reporting** | 1. User & Account Management · 7. User Reporting · 8. Administration & Analytics (oversight half) | **Mac** |

*Split revised October 14: Booking Management moved from B to C and User Reporting moved from C to
D, so the concurrency-critical work (acceptance) sits with the booking module and reporting sits
with the admin workflow that resolves reports.*

Why the split lands this way: **B** is the student-facing entry point (search and the inquiry
thread) and carries the richest display logic and test evidence; **C** continues exactly where B
ends — B's inquiry produces the booking request C accepts, and C's confirmed booking gates C's own
rating; **D** absorbs reporting because D already owns the admin workflow that resolves reports.
Everyone still acts on their own screens: Noemi moderates listings, Christian searches and inquires,
Jerome accepts and is rated, Mac administers.

### 3b. Presentation run order (confirmed)

The four presentations are independent (each with its own Summary, own test table, own defense) but
their live demos chain into one continuous story — the inquiry Christian sends in slot 1 is the same
inquiry Jerome accepts in slot 2.

| Slot | Presenter | Module | Live demo | Handoff line |
|---|---|---|---|---|
| **1st** | Badua, Christian Jade B. | **B — Search & Inquiry** | student searches with stacked filters → opens a listing → sends the inquiry | "…and that's the inquiry Jerome will now accept." |
| **2nd** | Bayubay, Jerome O. | **C — Booking, Acceptance & Ratings** | opens the same inquiry thread → accepts it (guards visible) → student sees the booking → rates the landlord | "…and behind every account and report is Mac's back office." |
| **3rd** | Layco, Mac Gabrielle L. | **D — Accounts, Administration, Analytics & Reporting** | registers a student → manages a landlord account → barangays/settings → resolves a report → analytics dashboard | "…but none of these listings existed until Noemi's side created and verified them." |
| **4th** | Valdriz, Noemi G. | **A — Boarding House & Room Management + Verification** | creates a house → adds a room + photo → admin approves it → it appears in Browse (closes the loop back to slot 1) | closing statement, then Q&A. |

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
  the approval status also gates Module C's acceptance (a rejected listing cannot be booked) and
  decides whether Module D's analytics count the listing.
- **Existing tests to cite/re-run:** `ListingPriceValidationTests`, `RoomPhotoUploadCapTests`,
  `RoomFormPageTitleTests`, plus the approval guards in `WrongOutputBookingTests`
  (accepting into a rejected listing is refused).

### Module B — Search & Inquiry (Messaging) — *Christian*

- **Inputs:** search/filter criteria (barangay, price range, room type, amenities, availability only,
  sort), inquiry text + chat messages on a specific room.
- **Processing:** `EXISTS`-based filtering over rooms (a house can never be produced twice), price
  sort via correlated subquery, availability derived from *bookable* rooms only (capacity minus
  confirmed bookings, inactive rooms excluded), one conversation per student–room pair, unread/NEW
  tracking from the student's last-seen marker.
- **Outputs:** result grid with an honest "N rooms available" badge and lowest bookable price,
  boarding-house detail page with rooms/photos/amenities and landlord averages, saved inquiry
  threads with timestamps and read state.
- **Demo path:** `/listings/` (apply stacked filters + "lowest price first") → `/listings/<pk>/` →
  send inquiry → `/landlords/inquiries/` as landlord → reply in the thread → back as student, the
  thread shows the reply with the NEW badge. (Accepting the inquiry is Module C.)
- **Hands to other modules:** consumes Module A's approved listings; its inquiry thread produces the
  booking request Module C accepts; its open-room counts drop when C confirms a booking; search and
  inquiry volume feed Module D's analytics.
- **Existing tests to cite/re-run:** `WrongOutputPriceTests`, `WrongOutputAvailabilityTests`,
  `WrongOutputSortTests`, `DuplicateCardTests`, `DuplicateRecordTests` (one conversation per
  student–room), `HighVolumeQueryBudgetTests`, `HighVolumePaginationTests`, `HighVolumeCacheTests`,
  `SearchResultsCountTests`, `SearchPaginationOrderTests`, `SearchFilterContractTests`,
  `InquiryStatusFollowsActivityTests`, `InquiryNewBadgeTests`, `RejectedInquiryGetSafetyTests`.
- **Best bug story in the whole system:** before the fix, one house with 3 matching rooms appeared
  3× in the grid, the card price came from a room the landlord had switched off, and "2 open" showed
  while only 1 room fit the student's price cap. Root cause (JOIN filters + `ORDER BY` defeating
  `.distinct()`) and fix (EXISTS subqueries + correlated subquery sort) are documented in
  `docs/ADVERSARIAL_TEST_REPORT.md` §1–§2 — perfect for the Testing part (1:30).

### Module C — Booking, Acceptance & Ratings — *Jerome*

- **Inputs:** the booking request produced from an inquiry thread, the landlord's accept/reject
  decision, and a 1–5★ rating + comment from a student who holds a **confirmed** booking.
- **Processing:** accepting the inquiry writes the **confirmed booking** (the only path that creates
  one) with guards — a rejected or inactive listing, a switched-off or full room and a second accept
  are all refused; **race-safe acceptance** (`select_for_update()` inside `transaction.atomic()` so
  two simultaneous accepts create exactly one confirmation), the system message written in the same
  transaction, availability recomputed as capacity minus confirmed bookings, and the rating allowed
  only once the landlord **settles the inquiry** — accepted (confirmed booking) or declined (rejected
  inquiry) — one rating per student–landlord pair (DB unique constraint), average recomputation for
  display.
- **Outputs:** the confirmed booking visible to the student (or the decline notice when rejected),
  updated open-room counts, average landlord rating shown on listing cards and detail pages, rating
  statistics and filters on `/landlords/ratings/` and `/admin/ratings/`.
- **Demo path:** as landlord → `/landlords/inquiries/` → open the thread → accept (show the guards:
  a rejected listing and a switched-off room are refused; a repeated accept still leaves exactly one
  booking) → as student → `/students/bookings/` shows the confirmed booking and the listing's
  open-room count drops → `/users/<pk>/rate/` → the average changes on `/listings/<pk>/` → rate
  again (blocked).
- **Hands to other modules:** its input is Module B's inquiry thread; its confirmations lower the
  open-room counts B displays; its averages surface on Module A's listing pages and Module D's admin
  ratings overview; its booking counts feed Module D's analytics.
- **Existing tests to cite/re-run:** `AcceptRaceTests`, `AcceptFlowAtomicityTests`,
  `WrongOutputBookingTests`, `DuplicateRecordTests` (double-accept leaves one booking),
  `RatingBookingDeterminismTests`, `LandlordRatingTests`, `RatingsPagesTests`,
  `PublicNameDisplayTests`.
- **Say this in "What Changed":** the midterm proposed free-standing house *reviews*; the built system
  tightened this into a booking-tied landlord rating (see `CHANGES-SINCE-MIDTERM.md` #1). That is a
  real, explainable design decision — exactly what the 15 continuity points want.
- **Say this in "Testing":** the hardest defect class in the whole system is double-acceptance of the
  last slot. The fix is a row lock (`select_for_update`) inside the transaction; the measured result
  is that a repeated accept leaves exactly one confirmed booking — quote `AcceptRaceTests` and
  `AcceptFlowAtomicityTests`.

### Module D — Accounts, Administration, Analytics & Reporting — *Mac*

- **Inputs:** student/landlord registration details (name, contact, e-mail, program or K-12 grade
  level), login credentials, admin commands (create/edit/deactivate/delete landlord accounts,
  manage students, barangays, site settings), and user reports (reason + details) filed by students
  or landlords.
- **Processing:** registration validation (duplicate e-mail/student ID refused), role assignment and
  role-based access, login hardening (lockout after 15 failed attempts, admin IP allowlist, honeypot
  probe logging), audit logging, report recording and the admin resolve/dismiss workflow,
  aggregation for the dashboard/analytics.
- **Outputs:** active role-based accounts and secured sessions, deactivated/reactivated accounts,
  maintained barangay + settings reference data, resolved reports with the action taken and the
  audit record, admin dashboard and analytics summaries, audit log.
- **Demo path:** `/students/register/` (invalid e-mail/ID rejected → valid registration succeeds) →
  `/admin/landlords/add/` → `/admin/landlords/<pk>/toggle/` (deactivate → the account can no longer
  log in → reactivate) → `/admin/barangays/` → `/admin/settings/` → a report filed as a student
  (`/users/<pk>/report/`) → as admin `/admin/reports/` → `/admin/reports/<pk>/update/` (resolve it)
  → `/admin/analytics/` (the dashboard and analytics summaries).
- **Hands to other modules:** it owns every account the other three modules act as, and it reads the
  listings (A), inquiries/bookings (B/C), ratings (C) and user reports to build analytics — the
  reporting half moved here because the admin workflow that resolves a report is already here.
- **Existing tests to cite/re-run:** `StudentRegistrationFlowTests`, `SecurityHardeningTests`
  (account lockout, admin IP allowlist, honeypot, audit log, security headers),
  `AllPagesSmokeTest`, `LandlordStudentProfileAccessTests`, `ProfileEditKeepsDisplayNameTests`,
  `CrossRoleRedirectLoopTests`.

---

## 4b. Diagrams for Deliverable B — the updated set exists now

The midterm diagrams in `docs/diagrams/` were deliberately left untouched (you need them for the
"what changed" comparison). The updated set for the final lives in `docs/final-project/diagrams/`,
rendered from Mermaid sources next to each PNG:

| File | Use it for |
|---|---|
| `Level 0 - Context Diagram (built).png` | Part 2 "Midterm Recap" — the system boundary |
| `Level 1 - Data Flow Diagram (built).png` | Part 4 "Where your module fits". Process numbering matches the midterm IPO table 1:1, so module **A = 2.0**, **B = 3.0 + 4.0**, **C = 5.0 + 6.0**, **D = 1.0 + 7.0 + 8.0** |
| `Entity Relationship Diagram (built).png` | Part 5 "Module Design" — the matching tables |
| `Module A–D - DFD (…).png` | The page-sized extract each member actually pastes into their own 2–4 page Summary |
| `Module A–D - ERD (…).png` | That member's ERD extract (e.g. Module C shows the rating table: one per student + landlord, linked to the booking when the landlord accepted) |

**Updated October 14:** the Module B, C and D extracts were re-cut to the split above and
re-rendered — B shows search + inquiry only, C shows booking/acceptance/ratings, D now includes user
reporting. The Level 0/1 and full ERD diagrams were only corrected where a flow did not match the
built system: the landlord's **accept** is what creates the confirmed booking, availability is
computed from bookings (not written back to the houses store), and a **settled** inquiry — accepted
(confirmed booking) or declined (rejected inquiry) — is what unlocks one rating.

Re-render after editing any `.mmd`:

```powershell
venv\Scripts\python.exe tools\render_diagrams.py docs\final-project\diagrams
```

Rendering is offline and needs no Node: `tools/vendor/mermaid.min.js` is vendored and the script uses
the project's existing Playwright Chromium at 3x, so the PNGs stay sharp when projected.

**Say this in part 3 (What Changed) about the diagrams:** process **6.0 Rating & Review** now exists
(the midterm DFD jumped from reporting straight to administration), the ERD gained `LANDLORD_RATING`
(unique per student–landlord, linked to the booking when the landlord accepted), `BARANGAY`, `SITE_SETTING` and `ADMIN_ACTION_LOG`, booking status is the implemented
`pending / confirmed / declined / cancelled`, and rent lives on the room as `monthly_rate` — the
house-level `price` is only a displayed range.

**Printing tip:** the full Level 1 DFD is a wide poster — print it alone on its own sheet (landscape),
and put your *module* extract on the Summary page where it is actually readable.

---

## 4c. Code map — the exact lines per module (October 14, 2026)

Line numbers are from the current working tree. If a file changes, **search the name** instead of
trusting the number. All paths are relative to the repo root.

### Module B — Search & Inquiry — *Christian*

| Layer | What | Where |
|---|---|---|
| Models | `Inquiry`, `InquiryMessage` | `core/models.py:413`, `:456` |
| Forms | `InquiryForm`, `ListingFilterForm` | `core/forms.py:262`, `:318` |
| Search core | `visible_listings`; amenity + filter helpers; `decorate_house_cards` | `core/views.py:80`; `:125`–`:246`; `:247` |
| Pages | `listing_list` (Browse), `boarding_detail`, `search_results` | `core/views.py:616`, `:706`, `:2415` |
| Inquiry | `send_inquiry`, `inquiry_thread`, `inquiry_messages_json`; NEW tracking `_with_latest_message`, `_inquiry_has_new_message` | `core/views.py:1550`, `:1361`, `:1525`; `:446`, `:461` |
| Inboxes | `student_inquiry_list`; `landlord_inquiry_list` (Accept/Reject buttons are C's) | `core/views.py:1300`; `:1790` |
| Templates | `search_results.html`, `boarding_detail.html`, `send_inquiry.html`, `inquiry_thread.html`, `student_inquiry_list.html`, `landlord_inquiry_list.html`, `includes/{browse_content,listing_card,listing_grid_fragment,boarding_detail_content,search_grid_fragment}.html` | `core/templates/core/` |
| CSS / JS | `css/pages/{search_results,browse_content,boarding_detail_content,inquiry_thread}.css`; `js/{Search Filters,Listing Filters,Inquiry Thread}.js` | `core/static/core/` |
| Tests | `WrongOutputPriceTests:73`, `WrongOutputAvailabilityTests:122`, `WrongOutputSortTests:166`, `DuplicateCardTests:239`, `HighVolumeQueryBudgetTests:353`, `HighVolumePaginationTests:435`, `HighVolumeCacheTests:554`; `SearchResultsCountTests:53`, `SearchPaginationOrderTests:191`, `SearchFilterContractTests:245`, `InquiryStatusFollowsActivityTests:340`, `InquiryNewBadgeTests:426`, `RejectedInquiryGetSafetyTests:117`; `BrowsePageTests:49` | `tests_adversarial.py` · `tests_regressions.py` · `tests.py` |

### Module C — Booking, Acceptance & Ratings — *Jerome*

| Layer | What | Where |
|---|---|---|
| Models | `Booking`, `LandlordRating`; `annotate_room_bookings` (capacity math) | `core/models.py:473`, `:495`; `:331` |
| Form | `LandlordRatingForm` | `core/forms.py:275` |
| Accept / reject | `accept_student` (row lock `:1445`, booking created `:1474`), `reject_student` | `core/views.py:1433`, `:1503` |
| Rating | `rate_landlord`, `_rating_redirect` | `core/views.py:1188`, `:1169` |
| Booking pages | `student_bookings`, `landlord_bookings`, `landlord_my_ratings`, `admin_ratings` | `core/views.py:1351`, `:1811`, `:2563`, `:2519` |
| Shared with B | `inquiry_thread` shows the accept state; `landlord_inquiry_list` holds the Accept/Reject buttons | `core/views.py:1361`, `:1790` |
| Templates | `student_bookings.html`, `landlord_bookings.html`, `landlord_my_ratings.html`, `inquiry_thread.html` (shared), `landlord_inquiry_list.html` (shared), `admin_ratings.html` (admin frame = D) | `core/templates/core/` |
| CSS | `css/pages/{student_bookings,landlord_bookings,landlord_my_ratings}.css` (+ shared `inquiry_thread.css`) | `core/static/core/` |
| Tests | `AcceptRaceTests:640`, `WrongOutputBookingTests:194`, `PublicNameDisplayTests:979`, `DuplicateRecordTests:288` (double-accept); `AcceptFlowAtomicityTests:374`, `RatingBookingDeterminismTests:163`; `LandlordRatingTests:148`, `RatingsPagesTests:257` | `tests_adversarial.py` · `tests_regressions.py` · `tests.py` |

### Module D — Accounts, Administration, Analytics & Reporting — *Mac*

| Layer | What | Where |
|---|---|---|
| Models | `UserManager` `:79`, `User` `:109`, `AdminActionLog:535` + `log_admin_action:558`, `SiteSetting:572` + `site_setting:590`, `UserReport:599` | `core/models.py` |
| Forms | `StudentRegistrationForm:30`, `LandlordRegistrationForm:93`, `LandlordCreateForm:303`, `LandlordEditForm:307`, `SystemSettingsForm:377`, `UserReportForm:394`, `BHIMSPasswordChangeForm:295` | `core/forms.py` |
| Auth views | `student_register:775`, `accounts_login:802`, `landlord_register:861`, `student_login:868`, `landlord_login:921`, `admin_login:954`, `logout_view:1000` | `core/views.py` |
| Login hardening | `_client_ip:355`, `_throttle_login:409`, `_throttle_key:421`, `_throttle_generic:435`, `_lockout_state:473`, `_record_login_failure:490`, `_clear_login_failures:510` | `core/views.py` |
| Reports | `report_user:1240`; `admin_reports:2041`, `admin_report_detail:2056`, `admin_report_update:2066` | `core/views.py` |
| Admin | `admin_dashboard:1821`, `admin_analytics:1859`, `admin_create_landlord:1986`, `admin_landlord_list:2083`, `admin_landlord_detail:2103`, `admin_edit_landlord:2118`, `toggle_landlord_active:2137`, `admin_delete_landlord:2151`, `admin_student_list:2166`, `admin_delete_student:2187`, `admin_settings:2317`; profile cluster `:1007`–`:1112`, `:2341`–`:2414` | `core/views.py` |
| Templates | `auth/…`, `admin_dashboard.html`, `admin_analytics.html`, `admin_reports.html`, `admin_report_detail.html`, `admin_landlord_list.html`, `admin_landlord_detail.html`, `landlord_create.html`, `landlord_edit.html`, `admin_student_list.html`, `admin_settings.html`, `report_user.html`, `admin_honeypot.html`, `404.html`, `500.html` | `core/templates/core/` |
| CSS / JS | `css/pages/{admin_analytics,admin_reports,admin_report_detail,admin_styles,report_user,user_profile,edit_profile,change_password}.css`; `js/{auth-deck,Theme Toggle,Form Validation}.js` | `core/static/core/` |
| Tests | `StudentRegistrationFlowTests:7`, `SecurityHardeningTests:355`, `AllPagesSmokeTest:464`; `HighVolumeThrottleTests:461`; `LandlordStudentProfileAccessTests:75`; `ProfileEditKeepsDisplayNameTests:51`, `CrossRoleRedirectLoopTests:118` | `tests.py` · `tests_adversarial.py` · `tests_regressions.py` · `tests_exploration.py` |

### Module A — Boarding House & Room Management + Verification — *Noemi*

| Layer | What | Where |
|---|---|---|
| Models | `validate_image_size:16`, `_upload_image_to:22`, `_generated_image_path:35`, `validate_image_file:40`, `BoardingHouse:185`, `Room:264`, `Amenity:345`, `Barangay:352` + `barangay_display_map:378`, `RoomPhoto:402` | `core/models.py` |
| Forms | `BoardingHouseForm:167`, `RoomForm:221`, `BarangayForm:367` | `core/forms.py` |
| Management | `landlord_dashboard:1617`, `boarding_house_create:1658`, `boarding_house_edit:1682`, `room_create:1700`, `room_edit:1724`, `toggle_room_availability:1749`, `landlord_boarding_house_list:1644`, `landlord_boarding_house_detail:1760` | `core/views.py` |
| Verification | `admin_pending_listings:2202`, `admin_approve_listing:2217`, `admin_reject_listing:2231`; barangay admin `:2244`, `:2276`, `:2305`; cache invalidation `invalidate_listing_caches:100` (+ signals `:646`) | `core/views.py` |
| Templates | `landlord_boarding_house_list.html`, `landlord_boarding_house_detail.html`, `boarding_house_form.html`, `room_form.html`, `landlord_dashboard.html`, `admin_pending_listings.html`, `admin_barangays.html` | `core/templates/core/` |
| CSS | `css/pages/{landlord_boarding_house_list,landlord_boarding_house_detail,boarding_house_form,room_form,landlord_dashboard}.css` | `core/static/core/` |
| Tests | `ListingPriceValidationTests:105`; `RoomPhotoUploadCapTests:851`, `RoomFormPageTitleTests:942`; `BarangayDropdownTests:403` | `tests.py` · `tests_adversarial.py` · `tests_regressions.py` |

**One ownership call to make:** barangay management currently appears in *both* A's processing and
D's admin commands. The screen is `admin_barangay_*` — decide once whether Mac demos it (D) or Noemi
cites it (A), and make both docs say the same thing before the approval signature.

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

# one module's evidence — one line per presenter, in run order (B, C, D, A)
venv\Scripts\python.exe manage.py test core.tests_adversarial.DuplicateCardTests core.tests_adversarial.WrongOutputPriceTests
venv\Scripts\python.exe manage.py test core.tests_adversarial.AcceptRaceTests core.tests_regressions.AcceptFlowAtomicityTests core.tests.LandlordRatingTests
venv\Scripts\python.exe manage.py test core.tests.SecurityHardeningTests core.tests.StudentRegistrationFlowTests
venv\Scripts\python.exe manage.py test core.tests.ListingPriceValidationTests core.tests_adversarial.RoomPhotoUploadCapTests

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

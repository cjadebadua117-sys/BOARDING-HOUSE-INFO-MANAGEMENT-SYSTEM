# BHIMS — Individual Module Split (for instructor approval)

**System:** BHIMS — Boarding House Information Management System (DMMMSU–NLUC, Bacnotan)
**Course / Section:** Business Information Systems & Systems Analysis and Design — BSIS 3B
**Instructor:** Mr. Vincent Haber
**Group:** Badua, Christian Jade B. · Bayubay, Jerome O. · Layco, Mac Gabrielle L. · Valdriz, Noemi G.

Per Final Project Instructions **§3**: every member takes a different module of the same proposed
system, each module must have real inputs, processing and outputs, and **the split is agreed with the
instructor and written down before work starts**. This is that written split.

## The split — one module per student

| Member | Module | Inputs | Processing | Outputs |
|---|---|---|---|---|
| **Valdriz, Noemi G.** | **A — Boarding House & Room Management + Listing Verification** | Landlord's house details; room type, capacity, rate, amenities, photos; availability toggles; admin approve/reject decision; barangay reference data | Validation (price > 0, capacity ≥ 1, image type + size cap); listing state machine `pending → approved / rejected → resubmit`; room availability flag; barangay master data | Approved, publicly visible listings with rooms/photos/amenities; pending-moderation queue; admin action log |
| **Badua, Christian Jade B.** | **B — Search & Inquiry (Messaging)** | Search filters (barangay, price, type, amenities, availability, sort); inquiry text and chat messages | EXISTS-based filtering (a house can never appear twice); price sort via correlated subquery; availability computed from bookable rooms only (capacity − confirmed bookings); one conversation per student–room; unread/NEW tracking | Result grid with honest open-room count and lowest bookable price; boarding-house detail page; saved inquiry threads with read state |
| **Bayubay, Jerome O.** | **C — Booking, Acceptance & Ratings** | Landlord accept/reject decision on an inquiry; 1–5★ rating + comment from a student whose inquiry was settled (accepted or declined) | Accept writes the confirmed booking (guards: rejected listing, inactive/full room, second accept); race-safe acceptance (`select_for_update` inside a transaction); rating allowed only after the inquiry is settled, once per student–landlord pair (DB unique constraint); average recomputation | Confirmed bookings and updated open-room counts; average landlord rating on listings; rating statistics and filters |
| **Layco, Mac Gabrielle L.** | **D — Accounts, Administration, Analytics & Reporting** | Registration details (e.g. program, contact); login credentials; admin commands (create / edit / deactivate / delete accounts, barangays, system settings); user reports (reason + details) | Duplicate account refusal; role assignment and role-based access; login hardening (lockout after repeated failures, admin IP allowlist, honeypot logging); audit logging; report resolve/dismiss workflow; aggregation for dashboards | Role-based accounts and secured sessions; maintained barangay + settings reference data; resolved reports with the action taken; admin dashboard and analytics summaries |

## How each module connects to the others (§3, third bullet)

- **A → B:** approved listing and room records are the input of B's search; approval status decides whether a house is findable at all.
- **B → C:** an inquiry thread produces the booking request that C accepts; the **confirmed booking** is also the eligibility key for C's rating — without it, rating is refused.
- **C → B / C → A:** a confirmation lowers the open-room count B displays; landlord averages are shown on A's listing cards and detail pages.
- **A, B, C → D:** D reads listings, inquiries/bookings, ratings and user reports to build its dashboards and analytics; D owns the accounts and permissions the other three act as, and resolves the reports users file.

## Demonstration path each member will present

- **A:** add boarding house → add room + photo → toggle availability → admin approves pending listing → the house appears in Browse.
- **B:** filter listings → open a listing → send an inquiry → landlord replies in the thread (the reply shows as NEW for the student).
- **C:** landlord accepts the inquiry (guards on show: a rejected listing and a switched-off room are refused; a repeated accept still leaves one booking) → student sees the confirmed booking → rates the landlord → average changes on the listing → second rating refused.
- **D:** register a student → admin creates / deactivates a landlord → manage barangays and settings → resolve a filed user report → show the analytics dashboard.

## Presentation order (live demos)

1. **Badua, Christian Jade B.** — Module B (Search & Inquiry)
2. **Bayubay, Jerome O.** — Module C (Booking, Acceptance & Ratings)
3. **Layco, Mac Gabrielle L.** — Module D (Accounts, Administration, Analytics & Reporting)
4. **Valdriz, Noemi G.** — Module A (Boarding House & Room Management + Verification)

The demos chain into one story: the inquiry Christian sends in slot 1 is the inquiry Jerome accepts
in slot 2; Mac then opens the back office behind every account and report; Noemi closes with where
the listings came from and how they were verified.

## Testing (each member, 5+ cases)

Every member runs and reports **their own** five or more test cases (input, expected, actual,
pass/fail) for the module above. The suite in `core/` is cited only as supporting evidence.

## Work-separately statement (§3, fourth bullet)

The running system was built and integrated by **Badua, Christian Jade B.** Each member owns their
own module's design refinement, test results, demo and defense, and presents individually. Shared
midterm diagrams (and the module DFD/ERD extracts derived from them) are cited in the References
section of each member's Summary.

---

**Instructor decision:** ☐ Approved as listed ☐ Approved with amendments (write below)

Amendments: ______________________________________________________________

Signature: ______________________________  Date: __________________

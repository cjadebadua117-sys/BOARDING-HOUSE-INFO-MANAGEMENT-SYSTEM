# BHIMS module diagrams - Mermaid source

Every module diagram below is the exact source used to render the PNG beside it.
The `.mmd` file is the source of truth: edit the code, then re-render.

```bat
venv\Scripts\python.exe tools\render_diagrams.py docs\final-project\diagrams
```

Each PNG is rendered at 3x from its matching `.mmd`, so the pair must keep the same name.
Paste any block into https://mermaid.live to preview or export it.

| Owner | Module | Diagram files |
|---|---|---|
| **Noemi** | A - Boarding House & Room Management with Verification | `Module A - Noemi - DFD (Boarding House & Room Management with Verification)` / `Module A - Noemi - ERD (Boarding House & Room Management with Verification)` |
| **mac** | B - Search & Inquiry | `Module B - mac - DFD (Search & Inquiry)` / `Module B - mac - ERD (Search & Inquiry)` |
| **Jerome** | C - Booking, Acceptance & Ratings | `Module C - Jerome - DFD (Booking, Acceptance & Ratings)` / `Module C - Jerome - ERD (Booking, Acceptance & Ratings)` |
| **cjade** | D - Accounts, Administration, Analytics & Reporting | `Module D - cjade - DFD (Accounts, Administration, Analytics & Reporting)` / `Module D - cjade - ERD (Accounts, Administration, Analytics & Reporting)` |

## Module A - Boarding House & Room Management with Verification - Noemi - DFD

`Module A - Noemi - DFD (Boarding House & Room Management with Verification).mmd`

```mermaid
%% Module A - Level 1 DFD extract: Boarding House & Room Management (process 2.0)
%% Owner: Noemi. Shows only the processes, stores and flows this module touches.
%% Render: venv\Scripts\python.exe tools\render_diagrams.py docs\final-project\diagrams
flowchart LR
    LAN["<b>LANDLORD</b>"]
    ADM["<b>ADMINISTRATOR</b>"]
    STU["<b>STUDENT</b>"]

    P2("<b>2.0 Boarding House &amp;<br/>Room Management</b>")

    D2[("D2 | HOUSES &amp; ROOMS")]
    D3[("D3 | AMENITIES &amp; BARANGAYS")]

    LAN -- "house, room, rate, capacity,<br/>amenity and photo data,<br/>availability toggles" --> P2
    P2 -- "listing &amp; room records<br/>(status pending)" --> D2
    D2 -- "existing listing data<br/>(edit, resubmit rejected)" --> P2
    D3 -- "amenity list, barangay list<br/>+ distance from campus" --> P2
    ADM -- "approve / reject" --> P2
    P2 -- "approval status<br/>(pending / approved / rejected)" --> LAN
    P2 -- "approved listing with bookable<br/>rooms reaches search results" --> STU

    classDef entity fill:#f8eae4,stroke:#8c4a2f,stroke-width:2.5px,color:#3a2a20
    classDef process fill:#ffffff,stroke:#c1592a,stroke-width:3px,color:#3a2a20
    classDef store fill:#eef2f7,stroke:#4a6785,stroke-width:2px,color:#22303f
    class STU,LAN,ADM entity
    class P2 process
    class D2,D3 store
```

## Module A - Boarding House & Room Management with Verification - Noemi - ERD

`Module A - Noemi - ERD (Boarding House & Room Management with Verification).mmd`

```mermaid
%% Module A - ERD extract: Boarding House & Room Management (owner: Noemi)
%% Only the entities this module writes, with the fields it manages.
%% Render: venv\Scripts\python.exe tools\render_diagrams.py docs\final-project\diagrams
erDiagram
    USER ||--o{ BOARDING_HOUSE : "owns"
    BOARDING_HOUSE ||--|{ ROOM : "contains"
    ROOM ||--o{ ROOM_PHOTO : "has"
    ROOM }o--o{ AMENITY : "offers"
    BARANGAY ||--o{ BOARDING_HOUSE : "referenced by name"

    USER {
        int id PK
        string role "landlord or admin"
        string landlord_id "issued on registration"
        boolean is_active
    }
    BOARDING_HOUSE {
        int id PK
        int owner_id FK
        string name
        string address
        string barangay "matches BARANGAY.name"
        decimal price "monthly"
        string gender_allowed "male / female / both"
        text description
        image image
        boolean is_active
        string status "pending / approved / rejected"
    }
    ROOM {
        int id PK
        int boarding_house_id FK
        string room_type
        decimal monthly_rate
        int capacity
        boolean is_available
        boolean is_active
    }
    ROOM_PHOTO {
        int id PK
        int room_id FK
        image image
    }
    AMENITY {
        int id PK
        string name UK
    }
    BARANGAY {
        int id PK
        string name UK
        string distance_from_campus
    }
```

## Module B - Search & Inquiry - mac - DFD

`Module B - mac - DFD (Search & Inquiry).mmd`

```mermaid
%% Module B - Level 1 DFD extract: Search & Inquiry (processes 3.0, 4.0)
%% Owner: Mac. The student-facing entry point: find a room with honest
%% availability, then talk to the landlord. Acceptance and ratings are Module C.
%% Render: venv\Scripts\python.exe tools\render_diagrams.py docs\final-project\diagrams
flowchart LR
    STU["<b>STUDENT</b>"]
    LAN["<b>LANDLORD</b>"]

    P3("<b>3.0 Search &amp;<br/>Availability</b>")
    P4("<b>4.0 Inquiry &amp;<br/>Messaging</b>")

    D2[("D2 | HOUSES &amp; ROOMS")]
    D4[("D4 | INQUIRIES &amp; MESSAGES")]
    D6[("D6 | LANDLORD RATINGS")]

    STU -- "search &amp; filter criteria<br/>(barangay, price, room type,<br/>amenity, availability, sort)" --> P3
    D2 -- "approved houses +<br/>bookable rooms only" --> P3
    D6 -. "average landlord rating<br/>(Module C output)" .-> P3
    P3 -- "results: open-room count<br/>+ lowest bookable price" --> STU

    STU -- "inquiry text / chat message" --> P4
    LAN -- "reply in the thread" --> P4
    P4 -- "thread with read / NEW state" --> STU
    P4 -- "inquiry list with NEW badge" --> LAN
    P4 -- "inquiry &amp; message records" --> D4
    D4 -- "thread history &amp; timestamps" --> P4

    classDef entity fill:#f8eae4,stroke:#8c4a2f,stroke-width:2.5px,color:#3a2a20
    classDef process fill:#ffffff,stroke:#c1592a,stroke-width:3px,color:#3a2a20
    classDef store fill:#eef2f7,stroke:#4a6785,stroke-width:2px,color:#22303f
    class STU,LAN entity
    class P3,P4 process
    class D2,D4,D6 store
```

## Module B - Search & Inquiry - mac - ERD

`Module B - mac - ERD (Search & Inquiry).mmd`

```mermaid
%% Module B - ERD extract: Search & Inquiry (owner: Mac)
%% The tables this module writes: one conversation per student + room, with a
%% per-side read marker that drives the NEW badge. Booking lives in Module C.
%% Render: venv\Scripts\python.exe tools\render_diagrams.py docs\final-project\diagrams
erDiagram
    USER ||--o{ INQUIRY : "sends"
    ROOM ||--o{ INQUIRY : "is asked about"
    INQUIRY ||--o{ INQUIRY_MESSAGE : "contains"
    USER ||--o{ INQUIRY_MESSAGE : "posts"
    BOARDING_HOUSE ||--|{ ROOM : "contains"

    USER {
        int id PK
        string role "student or landlord"
        string full_name
    }
    BOARDING_HOUSE {
        int id PK
        string name
        string barangay
        string status "must be approved to be searchable"
        boolean is_active
    }
    ROOM {
        int id PK
        int boarding_house_id FK
        string room_type
        decimal monthly_rate
        int capacity
        boolean is_available
        boolean is_active
    }
    INQUIRY {
        int id PK
        int student_id FK
        int room_id FK
        string status "pending / open / closed / rejected"
        string subject
        text message_text
        datetime last_viewed_by_landlord "NEW badge for the landlord"
        datetime last_viewed_by_student "NEW badge for the student"
        datetime created_at
    }
    INQUIRY_MESSAGE {
        int id PK
        int inquiry_id FK
        int sender_id FK
        text message_text
        datetime sent_at
    }
```

## Module C - Booking, Acceptance & Ratings - Jerome - DFD

`Module C - Jerome - DFD (Booking, Acceptance & Ratings).mmd`

```mermaid
%% Module C - Level 1 DFD extract: Booking, Acceptance & Ratings (processes 5.0, 6.0)
%% Owner: Jerome. The landlord's decision on an inquiry becomes the booking:
%% accept -> a confirmed booking (row-locked guards), decline -> the inquiry is
%% rejected. Either settled outcome unlocks one rating per student + landlord.
%% Render: venv\Scripts\python.exe tools\render_diagrams.py docs\final-project\diagrams
flowchart LR
    STU["<b>STUDENT</b>"]
    LAN["<b>LANDLORD</b>"]

    P5("<b>5.0 Booking<br/>Management</b>")
    P6("<b>6.0 Rating &amp;<br/>Review</b>")

    D4[("D4 | INQUIRIES &amp; MESSAGES")]
    D5[("D5 | BOOKINGS")]
    D6[("D6 | LANDLORD RATINGS")]

    D4 -- "open inquiry (from Module B)" --> P5
    LAN -- "accept or decline" --> P5
    D5 -- "confirmed bookings<br/>(capacity check)" --> P5
    P5 -- "confirmed booking record<br/>(row-locked accept)" --> D5
    P5 -- "inquiry closed (accepted)<br/>or rejected (declined)" --> D4
    P5 -- "acceptance confirmation<br/>or decline notice" --> STU

    D5 -- "confirmed booking<br/>(unlocks rating)" --> P6
    D4 -- "rejected inquiry<br/>(also unlocks rating)" --> P6
    STU -- "1-5 star rating + comment" --> P6
    P6 -- "rating record<br/>(once per student + landlord)" --> D6
    P6 -- "updated average rating" --> STU
    P6 -- "average rating received" --> LAN

    classDef entity fill:#f8eae4,stroke:#8c4a2f,stroke-width:2.5px,color:#3a2a20
    classDef process fill:#ffffff,stroke:#c1592a,stroke-width:3px,color:#3a2a20
    classDef store fill:#eef2f7,stroke:#4a6785,stroke-width:2px,color:#22303f
    class STU,LAN entity
    class P5,P6 process
    class D4,D5,D6 store
```

## Module C - Booking, Acceptance & Ratings - Jerome - ERD

`Module C - Jerome - ERD (Booking, Acceptance & Ratings).mmd`

```mermaid
%% Module C - ERD extract: Booking, Acceptance & Ratings (owner: Jerome)
%% Accepting creates the BOOKING (guarded, row-locked); declining rejects the
%% INQUIRY. LANDLORD_RATING is unique per student + landlord, and its booking
%% link is set only when the landlord accepted.
%% Render: venv\Scripts\python.exe tools\render_diagrams.py docs\final-project\diagrams
erDiagram
    USER ||--o{ INQUIRY : "sends"
    ROOM ||--o{ INQUIRY : "is asked about"
    USER ||--o{ BOOKING : "books"
    ROOM ||--o{ BOOKING : "is booked in"
    BOOKING ||--o| LANDLORD_RATING : "unlocks one"
    USER ||--o{ LANDLORD_RATING : "gives"
    USER ||--o{ LANDLORD_RATING : "receives"

    USER {
        int id PK
        string role "student or landlord"
        string full_name
    }
    ROOM {
        int id PK
        int boarding_house_id FK
        decimal monthly_rate
        int capacity
        boolean is_available
        boolean is_active
    }
    INQUIRY {
        int id PK
        int student_id FK
        int room_id FK
        string status "rejected inquiry can still be rated"
        text message_text
    }
    BOOKING {
        int id PK
        int student_id FK
        int room_id FK
        string status "confirmed on accept"
        datetime requested_at
        datetime confirmed_at
        date move_in_date
        text notes
    }
    LANDLORD_RATING {
        int id PK
        int student_id FK
        int landlord_id FK
        int booking_id FK "OneToOne, empty after a decline"
        int rating "1 to 5"
        text comment "unique: one per student + landlord"
        datetime created_at
    }
```

## Module D - Accounts, Administration, Analytics & Reporting - cjade - DFD

`Module D - cjade - DFD (Accounts, Administration, Analytics & Reporting).mmd`

```mermaid
%% Module D - Level 1 DFD extract: Accounts, Administration, Analytics &
%% Reporting (processes 1.0, 7.0, 8.0). Owner: cjade (Christian Jade Badua).
%% Owns every account the other modules act as, resolves the reports users file,
%% and reads the other stores to build the dashboard and the audit trail.
%% Render: venv\Scripts\python.exe tools\render_diagrams.py docs\final-project\diagrams
flowchart LR
    STU["<b>STUDENT</b>"]
    LAN["<b>LANDLORD</b>"]
    ADM["<b>ADMINISTRATOR</b>"]

    P1("<b>1.0 User &amp;<br/>Account Management</b>")
    P7("<b>7.0 User<br/>Reporting</b>")
    P8("<b>8.0 Administration &amp;<br/>Analytics</b>")

    D1[("D1 | USERS")]
    D2[("D2 | HOUSES &amp; ROOMS")]
    D3[("D3 | AMENITIES &amp; BARANGAYS")]
    D5[("D5 | BOOKINGS")]
    D6[("D6 | LANDLORD RATINGS")]
    D7[("D7 | USER REPORTS")]
    D8[("D8 | AUDIT LOG &amp; SETTINGS")]

    STU -- "registration (program or<br/>K-12 grade level), login" --> P1
    LAN -- "registration, login" --> P1
    ADM -- "create / edit / deactivate<br/>accounts" --> P1
    P1 -- "account &amp; role records" --> D1
    D1 -- "verified credentials, role" --> P1
    P1 -- "session with role-based access" --> STU
    P1 -- "landlord ID, account status" --> LAN

    STU -- "report a user<br/>(reason + details)" --> P7
    LAN -- "report a user" --> P7
    P7 -- "report record (pending)" --> D7
    D7 -- "pending reports" --> P7
    ADM -- "resolve / dismiss" --> P7
    P7 -- "outcome of the report" --> STU

    D2 -- "listing counts" --> P8
    D5 -- "booking &amp; occupancy stats" --> P8
    D6 -- "rating stats" --> P8
    D7 -- "report stats" --> P8
    ADM -- "manage barangays &amp; settings" --> P8
    P8 -- "barangay records" --> D3
    P8 -- "admin action record" --> D8
    D8 -- "site settings" --> P8
    P8 -- "dashboard, analytics, audit trail" --> ADM
    P8 -- "account updates" --> D1

    classDef entity fill:#f8eae4,stroke:#8c4a2f,stroke-width:2.5px,color:#3a2a20
    classDef process fill:#ffffff,stroke:#c1592a,stroke-width:3px,color:#3a2a20
    classDef store fill:#eef2f7,stroke:#4a6785,stroke-width:2px,color:#22303f
    class STU,LAN,ADM entity
    class P1,P7,P8 process
    class D1,D2,D3,D5,D6,D7,D8 store
```

## Module D - Accounts, Administration, Analytics & Reporting - cjade - ERD

`Module D - cjade - ERD (Accounts, Administration, Analytics & Reporting).mmd`

```mermaid
%% Module D - ERD extract: Accounts, Administration, Analytics & Reporting (owner: cjade, Christian Jade Badua)
%% Entities this module writes: USER, BARANGAY, SITE_SETTING, ADMIN_ACTION_LOG
%% and USER_REPORT (the reports it resolves).
%% Render: venv\Scripts\python.exe tools\render_diagrams.py docs\final-project\diagrams
erDiagram
    USER ||--o{ ADMIN_ACTION_LOG : "performs"
    USER ||--o{ USER_REPORT : "files"
    USER ||--o{ USER_REPORT : "is reported in"
    USER ||--o{ BOARDING_HOUSE : "owns"
    BARANGAY ||--o{ BOARDING_HOUSE : "referenced by name"

    USER {
        int id PK
        string username
        string email UK
        string role "student / landlord / admin"
        string full_name
        string student_id UK "students"
        string landlord_id UK "landlords"
        string program "college"
        string program_custom "grade level or course"
        string phone_number
        boolean is_active
    }
    BARANGAY {
        int id PK
        string name UK
        string distance_from_campus
    }
    SITE_SETTING {
        int id PK
        string key UK
        text value
    }
    ADMIN_ACTION_LOG {
        int id PK
        int actor_id FK
        string action
        string target_model
        string target_id
        string target_repr
        datetime created_at
    }
    USER_REPORT {
        int id PK
        int reporter_id FK
        int reported_user_id FK
        string reason "harassment / scam / fake_listing / inappropriate / other"
        text details
        string status "pending / resolved / dismissed"
        datetime created_at
        datetime resolved_at
    }
    BOARDING_HOUSE {
        int id PK
        int owner_id FK
        string name
        string status "pending / approved / rejected"
        boolean is_active
    }
```

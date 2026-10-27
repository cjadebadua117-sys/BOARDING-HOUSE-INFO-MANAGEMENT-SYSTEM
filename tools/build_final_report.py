# -*- coding: utf-8 -*-
"""Build the BHIMS Final Project report on the Desktop.

Mirrors the classmate's PawCare_Report_MidtermProject.docx (their document is
17 pages / ~3,000 words / 7 figures), so the shape is deliberately the same:
cover with the member list, CHAPTER 1-8, a member/role table in Chapter 1, and
figures with captions. The content is BHIMS, packed with the running system's
own screenshots.

Format taken from the classmate's file: Letter page, 0.8" side / 0.7" top-bottom
margins, Times New Roman 12 pt, Table Grid tables, centered bold cover block.

Usage:
    ./venv/Scripts/python.exe tools/build_final_report.py
"""

import os

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

ROOT = r"C:\Users\Admin\Desktop\BOARDING HOUSE INFO MANAGEMENT SYSTEMS"
OUT = r"C:\Users\Admin\Desktop\FinalProject_Badua_Summary.docx"
DIAG = os.path.join(ROOT, "docs", "final-project", "diagrams")
SHOTS = os.path.join(ROOT, ".audit", "deck-shots")

BODY = "Times New Roman"
doc = Document()

# ---------------------------------------------------------------- page + font
s = doc.sections[0]
s.page_width, s.page_height = Inches(8.5), Inches(11)
s.left_margin = s.right_margin = Inches(0.8)
s.top_margin = s.bottom_margin = Inches(0.7)

st = doc.styles["Normal"]
st.font.name = BODY
st.font.size = Pt(12)
st.element.rPr.rFonts.set(qn("w:eastAsia"), BODY)
st.element.rPr.rFonts.set(qn("w:cs"), BODY)
st.paragraph_format.space_after = Pt(4)
st.paragraph_format.line_spacing = 1.06

cp = doc.core_properties
cp.title = ("BHIMS: Boarding House Information Management System for Efficient "
            "Vacancy Search Among NLUC Bacnotan Students")
cp.author = "Badua, Christian Jade B."
cp.subject = "Business Information Systems & Systems Analysis and Design - Final Project"
cp.comments = "Final Project report, BSIS 3B, DMMMSU-NLUC Bacnotan"


# ---------------------------------------------------------------- helpers
def para(text="", align=None, bold=False, italic=False, size=12,
         before=0, after=4, style=None):
    p = doc.add_paragraph(style=style)
    if align is not None:
        p.alignment = align
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if text:
        r = p.add_run(text)
        r.bold = bold
        r.italic = italic
        r.font.size = Pt(size)
        r.font.name = BODY
        r._element.rPr.rFonts.set(qn("w:eastAsia"), BODY)
    return p


def body(text, after=6):
    return para(text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, after=after)


def chapter(num, title):
    # The classmate's document does NOT start each chapter on a new page -- its
    # pages are full and a chapter heading appears mid-page. Matching that is
    # what keeps 3,000 words and 7 figures inside 17 pages.
    para("CHAPTER %d" % num, align=WD_ALIGN_PARAGRAPH.CENTER, bold=True,
         size=14, before=16, after=2)
    para(title, align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14, after=10)


def h2(text, pb=False):
    p = para(text, bold=True, size=12, before=11, after=3)
    if pb:
        p.paragraph_format.page_break_before = True
    return p


def h3(text):
    return para(text, bold=True, italic=True, size=12, before=8, after=2)


def lead(label, text, after=3):
    """A bullet whose first words are bold, the way the classmate's doc does it."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf = p.paragraph_format
    pf.left_indent = Inches(0.32)
    pf.first_line_indent = Inches(-0.32)
    pf.space_after = Pt(after)
    r = p.add_run("\u2022  ")
    r.font.size = Pt(12)
    r.font.name = BODY
    r2 = p.add_run(label)
    r2.bold = True
    r2.font.size = Pt(12)
    r2.font.name = BODY
    r3 = p.add_run(" " + text)
    r3.font.size = Pt(12)
    r3.font.name = BODY
    return p


def number(n, text, after=3):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf = p.paragraph_format
    pf.left_indent = Inches(0.32)
    pf.first_line_indent = Inches(-0.32)
    pf.space_after = Pt(after)
    r = p.add_run("%s  " % n)
    r.font.size = Pt(12)
    r.font.name = BODY
    r2 = p.add_run(text)
    r2.font.size = Pt(12)
    r2.font.name = BODY
    return p


def _shade(cell, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(shd)


def table(headers, rows, widths, size=9.5, header_fill="D9D9D9"):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    hdr = t.rows[0]
    trPr = hdr._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    th.set(qn("w:val"), "true")
    trPr.append(th)
    for i, htxt in enumerate(headers):
        c = hdr.cells[i]
        c.text = ""
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.line_spacing = 1.0
        r = p.add_run(htxt)
        r.bold = True
        r.font.size = Pt(size)
        r.font.name = BODY
        _shade(c, header_fill)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.line_spacing = 1.0
            r = p.add_run(str(val))
            r.font.size = Pt(size)
            r.font.name = BODY
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return t


def figure(path, width_in, caption):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(7)
    p.paragraph_format.space_after = Pt(1)
    p.add_run().add_picture(path, width=Inches(width_in))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_after = Pt(9)
    r = c.add_run(caption)
    r.italic = True
    r.font.size = Pt(10)
    r.font.name = BODY


def page_footer():
    p = doc.sections[0].footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.font.size = Pt(10)
    run.font.name = BODY
    b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin")
    i = OxmlElement("w:instrText"); i.set(qn("xml:space"), "preserve"); i.text = "PAGE"
    e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end")
    run._r.append(b); run._r.append(i); run._r.append(e)


def new_section(landscape=False):
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    if landscape:
        sec.orientation = WD_ORIENT.LANDSCAPE
        sec.page_width, sec.page_height = Inches(11), Inches(8.5)
    else:
        sec.orientation = WD_ORIENT.PORTRAIT
        sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    sec.left_margin = sec.right_margin = Inches(0.8)
    sec.top_margin = sec.bottom_margin = Inches(0.7)
    return sec


page_footer()

# =====================================================================
# COVER  (same shape as the classmate's PawCare cover)
# =====================================================================
para("BHIMS: BOARDING HOUSE INFORMATION MANAGEMENT SYSTEM FOR EFFICIENT "
     "VACANCY SEARCH AMONG NLUC BACNOTAN STUDENTS",
     align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=15, after=16)
for name in ("Badua, Christian Jade B.",
             "Bayubay, Jerome O.",
             "Layco, Mac Gabrielle L.",
             "Valdriz, Noemi G."):
    para(name, align=WD_ALIGN_PARAGRAPH.CENTER, size=13, after=0)
para("", after=16)
para("DON MARIANO MARCOS MEMORIAL STATE UNIVERSITY", align=WD_ALIGN_PARAGRAPH.CENTER,
     size=13, after=0)
for line in ("NORTH LA UNION CAMPUS", "COLLEGE OF INFORMATION SYSTEMS",
             "BACNOTAN, LA UNION", "BACHELOR OF SCIENCE IN INFORMATION SYSTEMS",
             "OCTOBER 2026"):
    para(line, align=WD_ALIGN_PARAGRAPH.CENTER, size=13, after=0)
para("", after=14)
para("Submitted to: Mr. Vincent Haber  |  Instructor, Business Information Systems "
     "and Systems Analysis and Design  |  Section BSIS 3B",
     align=WD_ALIGN_PARAGRAPH.CENTER, italic=True, size=11, after=0)

doc.add_page_break()

# =====================================================================
# CHAPTER 1
# =====================================================================
chapter(1, "INTRODUCTION")

body('This system entitled "BHIMS: Boarding House Information Management System for '
     'Efficient Vacancy Search Among NLUC Bacnotan Students" presents a web-based '
     'Business Information System designed to improve how boarding-house vacancies near '
     'the Don Mariano Marcos Memorial State University - North La Union Campus are '
     'advertised, searched, and booked. Landlords publish and maintain their own '
     'boarding houses and rooms; students search and filter listings, view a house, and '
     'inquire about a specific room; and an administrator verifies listings, manages '
     'accounts, resolves reports, and monitors the system.')

body("The paper was prepared by the following members as part of the course requirements "
     "in Business Information Systems and Systems Analysis and Design. It continues the "
     "proposal the group submitted at midterm and adds the later phases of the Systems "
     "Development Life Cycle: each member built, tested, and presents one working module "
     "of the same system, on their own.")

table(["Role", "Member", "Responsibilities"],
      [["Module B - Search & Inquiry (Messaging)",
        "Badua, Christian Jade B.",
        "Search, filtering, listing detail, and the inquiry threads. Built and integrated the "
        "running system; wrote this report and the Module B test cases."],
       ["Module C - Booking, Acceptance & Ratings",
        "Bayubay, Jerome O.",
        "Landlord accept or decline, confirmed bookings, availability, and landlord ratings."],
       ["Module D - Accounts, Administration, Analytics & Reporting",
        "Layco, Mac Gabrielle L.",
        "Registration and roles, landlord accounts, user reports, audit log, and the analytics dashboard."],
       ["Module A - Boarding House & Room Management with Verification",
        "Valdriz, Noemi G.",
        "Landlord listings, rooms, photos, amenities, availability, and administrator approval."]],
      widths=[1.7, 1.4, 3.8])

h2("Overview of the System")
body("BHIMS is built on Python and Django with a MySQL or MariaDB database and a front "
     "end in HTML, CSS, and JavaScript. Its organizing rule is that the people who own the "
     "vacancy information maintain it: landlords publish their own listings, and an "
     "administrator verifies a listing before students can see it. Availability is never "
     "typed in as a fixed number, but computed from the rooms the landlord has left active "
     "and the capacity that confirmed bookings have already used, so the figure a student "
     "sees reflects the house as it is at that moment.")
body("The four modules interlock: Module A's approved listings are the input of Module B's "
     "search and also gate Module C, since a rejected listing cannot be booked; Module B's "
     "inquiry produces the request Module C accepts; Module C's confirmation lowers the "
     "open-room count Module B displays, and its landlord averages appear on Module A's "
     "cards; and all three feed Module D, which owns the accounts they act as and reads "
     "their data to build the dashboards.")

# =====================================================================
# CHAPTER 2
# =====================================================================
chapter(2, "PROBLEM STATEMENT")

h2("Situation Analysis")
body("Nesta et al. (2025) note that rapid urban migration, especially among students, has "
     "increased the need for integrated boarding-house management systems, and that many "
     "operators still handle data recording and tenant registration manually, which produces "
     "inaccurate data. Their study designed a web-based boarding-house management information "
     "system using the rapid application development approach, which relies on iterative "
     "prototyping, user involvement, and quick feedback. Bisquera et al. (2026) point out "
     "that finding reasonably priced, easily accessible housing is often hard for students "
     "unfamiliar with the area; their boarding-house locator for Nueva Vizcaya State "
     "University combined spatial data, real-time updates, and filtering, and greatly reduced "
     "the time and expense of conventional housing searches.")
body("The same difficulty exists at NLUC. Students looking for a room near campus have no "
     "centralized way to check what is available, so they rely on word of mouth and physical "
     "visits, and often travel to a boarding house only to find the room already taken. "
     "Landlords face the mirror image: without a shared platform they depend on existing "
     "tenants and neighbours, which reaches a fraction of the students who are looking and "
     "leaves rooms vacant longer than necessary. Neither side can verify the other, and "
     "there is no channel for reporting inappropriate behaviour or content.")

h2("Concrete Problems Identified")
number("1.", "No centralized and current source of vacancy information. Students cannot check "
             "in one place which boarding houses near campus have rooms free at the moment.")
number("2.", "Wasted cost and time from uninformed visits. A student may travel to a house "
             "only to learn the room is gone, and must spend more time and fare searching elsewhere.")
number("3.", "Rooms stay vacant longer than necessary. Landlords who advertise only by word "
             "of mouth reach a small fraction of the students who are actually looking.")
number("4.", "No verification and no trust signal. Nothing in the informal process confirms "
             "that a poster genuinely manages the property, and no aggregated feedback helps "
             "the next student judge a landlord.")

# =====================================================================
# CHAPTER 3
# =====================================================================
chapter(3, "OBJECTIVES & SCOPE")

h2("Statement of Objectives")
body("The study aims to develop BHIMS, a web-based boarding-house information and "
     "management system that streamlines how NLUC students find available boarding houses "
     "and improves the management of listings, room availability, inquiries, bookings, "
     "landlord ratings, and user reports. Specifically, the system aims to:")
lead("Centralize the search.", "Allow students to search and filter boarding houses by "
     "price, room type, amenities, barangay, and room availability.")
lead("Digitize listing management.", "Let landlords add, edit, and update property and room "
     "details, prices, amenities, photos, and availability.")
lead("Provide inquiry and booking.", "Let students inquire about a specific available room, "
     "which the landlord may accept (confirming a booking) or decline.")
lead("Add ratings and reporting.", "Let a student rate a landlord after their inquiry is "
     "settled, with an optional comment, and let both sides report inappropriate behaviour "
     "or content.")
lead("Support administration.", "Let administrators create and manage landlord accounts, "
     "verify listings, manage reports and barangay data, and view system analytics.")

h2("Project Scope")
body("The proposed BHIMS is a centralized web-based platform for finding and managing "
     "boarding-house information for NLUC students in Bacnotan, La Union. Students use it "
     "to search for available boarding houses, landlords manage the listings, and "
     "administrators handle verification and system oversight.")
h3("The system will:")
for line in [
    "Allow students to register and log in with their program or K-12 grade level.",
    "Allow students to search and filter boarding houses by price, room type, amenities, barangay, and availability.",
    "Display boarding-house information, room details, prices, amenities, photos, and availability, with average landlord ratings.",
    "Allow students to send inquiries about specific rooms and track their inquiry and booking history.",
    "Allow landlords to manage multiple listings and rooms, reply to inquiries, and accept or decline them.",
    "Allow administrators to manage landlord accounts, verify listings, and manage reports, barangays, and settings.",
    "Provide account security, including password reset, failed-login lockout, and an audit log of administrator actions.",
]:
    lead("", line, after=2)

h3("The system will NOT:")
for line in [
    "Process rental payments, billing, accounting, or other financial transactions.",
    "Provide maintenance, repair, or housekeeping management, or integrate with smart locks, RFID, or other IoT devices.",
    "Provide a dedicated Android or iOS application; it is web-based only.",
    "Replace the physical boarding-house inspection or the actual agreement between students and landlords.",
    "Integrate with external institutional information systems, or serve as a general-purpose property platform.",
]:
    lead("", line, after=2)

# =====================================================================
# CHAPTER 4
# =====================================================================
chapter(4, "PROPOSED SYSTEM")

h2("The Proposed BHIMS and Its Rationale")
body("The proposed BHIMS replaces a search built on word of mouth with one built on "
     "information that is shared, verified, and current. The core operational workflow "
     "follows these sequential steps:")

h3("Step 1: Registration and Role Assignment")
body("A student registers with their program or K-12 grade level and contact details; "
     "landlord accounts are created by the administrator, which keeps listing ownership "
     "verifiable, and the role decides what an account can do.")
h3("Step 2: Listing and Verification (Module A)")
body("The landlord registers a boarding house and adds rooms with their type, capacity, "
     "monthly rate, amenities and photos. A new listing waits in the administrator's "
     "moderation queue until it is approved or rejected, and a rejected listing can be "
     "corrected and resubmitted.")
h3("Step 3: Search and Availability Checking (Module B)")
body("The student applies any combination of filters - barangay, price range, room type, "
     "amenities, availability only, and sort order. The system returns each matching "
     "boarding house exactly once, with an honest open-room count and the lowest monthly "
     "rate that is actually bookable.")
h3("Step 4: Inquiry and Messaging (Module B)")
body("The student inquires about one specific room, in a thread dedicated to that student "
     "and room. The landlord replies inside the same thread, which keeps its full history "
     "and its read state.")
h3("Step 5: Acceptance and Confirmed Booking (Module C)")
body("Accepting writes a confirmed booking, the room's open capacity drops, and the student "
     "sees the confirmation. The system refuses to accept into a rejected listing or a room "
     "the landlord has switched off, and two simultaneous attempts on the last slot still "
     "produce exactly one booking.")
h3("Step 6: Rating (Module C)")
body("Once the landlord has settled the inquiry, the student may rate that landlord once, "
     "one to five stars with an optional comment. The average is shown on the landlord's "
     "listing cards and detail pages.")
h3("Step 7: Administration and Analytics (Module D)")
body("Students and landlords may report inappropriate behaviour, and the administrator "
     "resolves each report with the action recorded. The administrator also maintains "
     "accounts, barangays and settings, and reads the dashboard and analytics summaries that "
     "aggregate live listings, inquiries, bookings, ratings and reports.")

# =====================================================================
# CHAPTER 5
# =====================================================================
chapter(5, "DESIGN SPECIFICATIONS")

h2("Requirements Gathering")
number("1.", "Semi-structured interviews with student boarders and landlords near the NLUC "
             "Bacnotan campus about how they find or advertise vacancies and what they would "
             "need before trusting a listing.")
number("2.", "Direct observation of the search from the student's side, so the cost of a "
             "failed visit could be described from what actually happens.")
number("3.", "Document analysis of existing announcements, chat messages and landlord "
             "notes, to establish which details a written listing must carry.")

h2("Four Levels of Requirements")
h3("Business Requirements")
for line in [
    "Provide one current source of vacancy information so no student travels to a house that is already full.",
    "Digitize listing management so landlords publish and update their own vacancies.",
    "Shorten the search cycle for students and the vacancy period for landlords, with moderated listing information.",
]:
    lead("", line, after=2)
h3("Stakeholder Requirements")
for line in [
    "Students need to search and filter listings, view houses and rooms, inquire about a room, track their history, and rate a landlord after settlement.",
    "Landlords need to manage multiple houses and rooms, reply to inquiries, and accept or decline them.",
    "Administrators need to manage landlord accounts, verify listings, handle reports, and see analytics.",
]:
    lead("", line, after=2)
h3("Functional Requirements")
for line in [
    "Search and filtering. Each boarding house shall be returned exactly once however many of its rooms match, with filters for barangay, price, room type, amenities, and availability.",
    "Availability. The open-room count and the displayed price shall be computed from bookable rooms only.",
    "Inquiry. A student shall inquire about a specific room and both parties shall exchange messages in one thread per student-room pair.",
    "Booking. Accepting shall create exactly one confirmed booking, and acceptance into a rejected listing, an inactive room, or a room at capacity shall be refused.",
    "Ratings and verification. A rating shall be allowed once, after settlement, and every new listing shall be held pending until an administrator approves it.",
]:
    lead("", line, after=2)
h3("Non-Functional Requirements")
for line in [
    "Performance. The Browse page shall respond within a few seconds and its query count shall not grow with the catalogue.",
    "Reliability and scalability. A failing cache or missing asset shall degrade a page rather than crash it, and the system shall absorb a campus-wide surge.",
    "Security. Access shall be controlled by role, destructive actions shall sit behind POST with CSRF protection, and failed logins shall be locked out.",
    "Usability and maintainability. One consistent interface in light and dark themes, on a standard stack any BSIS student can maintain.",
]:
    lead("", line, after=2)

h2("Process Models and Design Figures")
body("The midterm diagrams were checked against the system as built and corrected where a "
     "flow no longer matched it. A rating process now exists as its own process 6.0; the "
     "landlord's acceptance is what creates the confirmed booking; and availability is "
     "computed from bookings against room capacity rather than written back to the house record.")
figure(os.path.join(DIAG, "Level 0 - Context Diagram (built).png"), 6.4,
       "Figure 1. Updated Level 0 Context Diagram, showing the system boundary and the "
       "flows between BHIMS and its external entities: the student, the landlord, and the "
       "administrator.")

new_section(landscape=True)
figure(os.path.join(DIAG, "Level 1 - Data Flow Diagram (built).png"), 9.4,
       "Figure 2. Updated Level 1 Data Flow Diagram. Processes match the midterm IPO table "
       "1:1 (1.0 User and Account Management to 8.0 Administration and Analytics); Module B "
       "owns 3.0 Search and Availability and 4.0 Inquiry Management. This is a wide poster - "
       "a full-resolution copy is supplied as a separate file for printing on its own sheet.")
new_section()

figure(os.path.join(DIAG, "Entity Relationship Diagram (built).png"), 6.9,
       "Figure 3. Updated Entity Relationship Diagram. Booking status is the implemented "
       "pending / confirmed / declined / cancelled, rent is held on the room as monthly_rate, "
       "and LANDLORD_RATING, BARANGAY, SITE_SETTING, ADMIN_ACTION_LOG and the "
       "ROOM-to-AMENITY link are present.")
figure(os.path.join(DIAG, "Module B - mac - DFD (Search & Inquiry).png"), 6.6,
       "Figure 4. Module B Data Flow Diagram: 3.0 Search and Availability, which reads the "
       "boarding-house, room and amenity stores to build the result grid, and 4.0 Inquiry "
       "Management, which writes inquiry and message records against a specific room.")
figure(os.path.join(DIAG, "Module B - mac - ERD (Search & Inquiry).png"), 4.3,
       "Figure 5. Module B Entity Relationship Diagram extract. An inquiry belongs to one "
       "student and one room, so that pair identifies a single conversation, and the read "
       "markers on the inquiry drive the unread badge.")

h2("The System as Built")
body("The figures that follow are captures of the running system, taken from the "
     "implementation itself rather than drawn. The first four show the student's path "
     "through the system in the light theme, and the last four show the landlord and "
     "administrator side in the dark theme.")

figure(os.path.join(SHOTS, "light-01-student-dashboard.png"), 6.25,
       "Figure 6. Student dashboard, light theme, sidebar open. The student's inquiries and "
       "bookings in one place.")
figure(os.path.join(SHOTS, "light-02-browse-listings.png"), 6.25,
       "Figure 7. Browse and search, light theme. Filters for price, room type, barangay, "
       "amenities and sort, with each verified listing showing its open-room count and "
       "lowest bookable rate.")

figure(os.path.join(SHOTS, "light-03-listing-detail.png"), 6.25,
       "Figure 8. Boarding-house detail page, light theme. Description, rooms, photos, "
       "amenities, and the landlord's average rating.")
figure(os.path.join(SHOTS, "light-04-send-inquiry.png"), 6.25,
       "Figure 9. Sending an inquiry, light theme, sidebar open. The student requests a "
       "specific room and the message is held against that room's conversation.")

figure(os.path.join(SHOTS, "dark-01-landlord-dashboard.png"), 6.25,
       "Figure 10. Landlord dashboard, dark theme, sidebar open. Boarding houses, available "
       "rooms and open inquiries at a glance.")
figure(os.path.join(SHOTS, "dark-03-landlord-inquiries.png"), 6.25,
       "Figure 11. Landlord inquiry inbox, dark theme, sidebar open. Incoming student "
       "inquiries with the room and the conversation that carries the accept or decline.")

figure(os.path.join(SHOTS, "dark-02-admin-dashboard.png"), 6.25,
       "Figure 12. Administrator dashboard, dark theme, sidebar open. Live counts of "
       "students, landlords, boarding houses, rooms, pending listings, inquiries, and the "
       "most-inquired listings.")
figure(os.path.join(SHOTS, "dark-04-student-thread.png"), 6.25,
       "Figure 13. Inquiry thread, dark theme, sidebar open. The conversation, the booking "
       "confirmation written on acceptance, and the single rating the settlement unlocks.")

h2("System Inputs and Outputs")
for line in [
    ("Inputs.", "Registration details and login credentials for every role; search and filter "
                "criteria; inquiry text and messages; landlord house and room details with rates, "
                "capacity, amenities and photos; the accept or decline decision; a rating with an "
                "optional comment; a report reason and details; and administrator actions on accounts, "
                "listings, barangays and settings."),
    ("Outputs.", "The result grid and boarding-house detail page with honest availability and "
                 "lowest bookable rate; inquiry threads with read state; the confirmed booking or "
                 "decline notice; average landlord ratings on the listings; the moderation queue and "
                 "administrator audit record; resolved reports; and the dashboard and analytics "
                 "summaries."),
]:
    lead(line[0], line[1], after=4)

# =====================================================================
# CHAPTER 6
# =====================================================================
chapter(6, "FEASIBILITY STUDY")

h2("Technical Feasibility")
body("BHIMS is technically feasible because it uses standard, widely supported technologies: "
     "Python and Django, HTML, CSS and JavaScript, and MySQL or MariaDB through the Django "
     "object-relational mapper, hosted locally with XAMPP. It needs no specialized hardware "
     "and no external integration, because inquiries and bookings live in the database rather "
     "than a third-party messaging service. Feasibility here is demonstrated rather than "
     "argued: every module runs, saves data, and was tested against the real MariaDB database.")

h2("Operational Feasibility")
body("BHIMS fits the way students already search instead of asking them to learn a new "
     "process. A student who today asks around and then travels to inspect can instead filter "
     "by barangay, rate, room type and availability and see which houses genuinely have rooms "
     "free before leaving campus. Landlords keep control of their listings, switch a room off "
     "the moment it is taken, and answer inquiries in one thread that keeps its history. "
     "Because landlord accounts are created by the administrator and every listing is "
     "verified before it is visible, the oversight the design called for is a real workflow "
     "rather than a policy.")

h2("Economic Feasibility")
body("The system is economically feasible because it is built and run with free, "
     "open-source tools on standard devices - Python, Django, MySQL or MariaDB, XAMPP, "
     "Visual Studio Code and draw.io carry no license cost - so the recurring expenses are "
     "only modest hosting, a domain and internet access. The benefits are concrete on both "
     "sides: students avoid the fare spent on visits to houses whose rooms are taken, and "
     "landlords shorten the period a room sits vacant. Verified listings and aggregated "
     "ratings reduce the information asymmetry that makes both sides rely on guesswork.")

h2("Schedule Feasibility")
body("The project is schedule-feasible because it uses technologies the team is already "
     "trained in and concentrates on defined core functions. Planning, requirements analysis "
     "and design were completed on schedule, and development built and integrated the core "
     "search, listing, inquiry, booking and verification functions first, with ratings, "
     "reporting and analytics afterwards. The final requirement adds the individual module "
     "build, testing and presentation, which fits the suggested seven-day schedule because "
     "each member owns one module of an already-integrated system.")

# =====================================================================
# CHAPTER 7
# =====================================================================
chapter(7, "TIMELINE, RESOURCES & IMPLEMENTATION PLAN")

h2("Implementation and Conversion Plan")
body("BHIMS should be put into use with a pilot conversion followed by a phased rollout. A "
     "pilot runs the system first with three to five landlords in one barangay near campus "
     "while the informal process continues for everyone else, which proves the part everything "
     "else depends on - whether landlords will maintain their own listings and whether the "
     "verification queue is workable in daily use - while confining any problem to a handful "
     "of students. The phased rollout then brings the campus in module by module in the order "
     "the data flows, each phase going live only when the previous one is stable. Direct "
     "conversion was rejected because a student who finds the platform empty during midterms "
     "has no fallback and will go back to word of mouth; parallel operation was rejected "
     "because it doubles the landlord's work, since the same vacancy would have to be "
     "advertised both in the platform and by word of mouth.")

h2("User Training, Support and Maintenance")
body("Training is organized by role and kept short, because the interface was designed to "
     "be learned by use. Support is then delivered through a named system administrator as "
     "the single point of contact, with a published weekly office hour and an escalation "
     "path to the course instructor. Concerns filed through the report function are tracked "
     "inside the system, so the support queue and the moderation queue stay in one place.")

table(["User group", "Covers", "How and how long"],
      [["Students",
        "Registering and logging in, searching and stacking filters, reading a listing, "
        "sending an inquiry, tracking the thread and the booking, and rating after settlement",
        "A 30-minute orientation session, plus a one-page quick-start leaflet and a short "
        "demonstration video that stays online"],
       ["Landlords",
        "Registering a house and its rooms, setting rates, capacity, amenities and photos, "
        "toggling availability, resubmitting a rejected listing, replying to inquiries, and "
        "accepting or declining",
        "A 60- to 90-minute hands-on workshop in a computer laboratory using their own "
        "listings, plus a one-page cheat sheet"],
       ["Administrators",
        "The verification queue, landlord account management, barangay and site settings, "
        "the report workflow, the audit log, and the dashboard and analytics",
        "A half-day hands-on workshop, plus a written administrator's guide and a short "
        "runbook for backups and routine tasks"]],
      widths=[1.2, 3.0, 2.7])

body("Maintenance is planned across the four standard categories: corrective (defects logged "
     "with the module owner as first responder and re-tested against the case that exposed "
     "them), adaptive (new releases, barangays, or listing fields), perfective (notifications, "
     "and a map or distance view), and preventive (a nightly backup with a rehearsed restore, "
     "dependency and security updates, and a review of the audit log for probe attempts).")

h2("Estimated Development Timeline")
table(["Phase / Activity", "Duration", "Main Activities"],
      [["1. Planning and requirements analysis", "Week 1",
        "Identify requirements, finalize scope, define the student, landlord and administrator functions."],
       ["2. System design", "Week 2",
        "Design the architecture, database structure, user interface, DFDs, and ERD."],
       ["3. Database development", "Week 3",
        "Create the structures for accounts, houses, rooms, amenities, photos, inquiries, bookings, ratings, reports and the audit log."],
       ["4. Student and landlord modules", "Weeks 4-7",
        "Develop registration and login, search, filtering, listing detail, inquiry, rating, reporting, listing and room management, and booking decisions."],
       ["5. Administrator module and integration", "Weeks 8-9",
        "Develop verification, account management, report handling, analytics, and connect every module into one working system."],
       ["6. Testing, refinement and documentation", "Weeks 10-12",
        "Run the behavioural and adversarial suites, fix defects, evaluate with users, finalize documentation, and prepare the presentation."]],
      widths=[1.8, 0.85, 4.25])

h2("Resources Needed")
for line in [
    "Development environment and stack: Visual Studio Code, Python and Django, HTML, CSS and JavaScript.",
    "Database: MySQL or MariaDB through the Django ORM, hosted locally with XAMPP and inspected in phpMyAdmin.",
    "Diagramming and documentation: draw.io for the context diagram, DFDs and ERD, and Microsoft Word for the reports.",
    "Testing: the Django test suites, web browsers on desktop and mobile widths, and the project's own load-test tooling.",
    "Hardware and connectivity: smartphones, laptops and desktop computers, on a standard internet connection.",
    "Backup: the project's database backup script with an off-server copy, so a restore can be rehearsed.",
]:
    lead("", line, after=2)

# =====================================================================
# CHAPTER 8
# =====================================================================
chapter(8, "TESTING, CHANGES & CONCLUSION")

h2("Testing and Results")
body("Testing was done in two layers: manual cases run against the running system with real "
     "data entered through the interface, and an automated suite that turns each finding into "
     "a case that runs on demand, so a fixed defect cannot return unnoticed. The cases below "
     "are Module B's. Re-run on October 15, 2026, its nine test classes passed thirty tests "
     "with no failures; the full system suite was measured at 123 of 123 passing against "
     "MariaDB.")

table(["#", "Input / Action", "Expected Result", "Actual Result", "Result"],
      [["TC-01",
        "Apply stacked filters: Barangay, Room Type, Max Price and Available only",
        "Each matching boarding house appears exactly once, and only houses with an active, unbooked room inside the price cap are listed",
        "Before the fix, one house with three matching rooms produced three identical cards; after the filter rewrite, one card per house",
        "PASS"],
       ["TC-02",
        "Read the open-room badge on a house holding a PHP 1,500 and a PHP 5,000 room, with the student's cap at PHP 2,000",
        "The badge reports 1 room available, because it must respect the filter the student applied",
        "Before, the badge read 2 open; after, 1 open, matching the single room inside the cap",
        "PASS"],
       ["TC-03",
        "Read the card price of a house whose cheap room has been switched off (PHP 100 inactive, PHP 5,000 active)",
        "The card advertises PHP 5,000, the real bookable rate, never a price from a room taken off the market",
        "Before, the card showed PHP 100 from the inactive room; after, PHP 5,000",
        "PASS"],
       ["TC-04",
        "Sort the results with Lowest price first across listings with different ranges",
        "Rows are ordered ascending by the lowest bookable rate with no boarding house repeated",
        "Verified ascending in the browser; ordering and no-duplicate cases pass in the suite",
        "PASS"],
       ["TC-05",
        "Apply Available only to a room with capacity 1 that already holds one confirmed booking",
        "The room is excluded from the results and from the open-room count",
        "Excluded, as expected: capacity minus confirmed bookings is zero",
        "PASS"],
       ["TC-06",
        "Load test the Browse page with 200 concurrent users",
        "No server errors, and the page keeps responding within a few seconds",
        "Before, 21 requests returned HTTP 500 with a median of about 2,025 ms; after the fixes, 0 failures and a median of about 149 ms",
        "PASS"]],
      widths=[0.4, 1.6, 1.85, 1.8, 0.45], size=8.5)

h2("Changes Made to the Midterm Design and Why")
table(["#", "The midterm said", "What was built instead", "Why"],
      [["1",
        "Students with a confirmed booking submit or edit boarding-house reviews, and students also rate landlords after an inquiry is settled",
        "No free-standing review entity. A rating is one to five stars plus an optional comment, unique per student and landlord, allowed once the landlord settles the inquiry",
        "One eligibility rule instead of two, no orphan or duplicate reviews, and a rating tied to a real transaction so the average means something"],
       ["2",
        "Real-time in-app notifications to students and landlords",
        "Not built. Information is carried by the inquiry threads, booking status, dashboards, and the accept or decline response",
        "A notification layer needs polling or push infrastructure that would compete with the time available for the search, booking and moderation logic; reported honestly as not met"],
       ["3",
        "Filter by price, room type, amenity, barangay and availability, and sort the results",
        "The same filters, reimplemented with EXISTS subqueries and a correlated subquery for the price sort",
        "The original join-based filters produced one identical card per matching room and the rate sort defeated de-duplication; the rewrite makes duplicates structurally impossible"],
       ["4",
        "Display the price and room availability on the listing",
        "The card price comes only from bookable rooms, and the open count counts only active rooms with free capacity",
        "The badge was promising rooms a student could not book, which is the exact problem the system exists to solve"],
       ["5",
        "The landlord approves or declines the booking request",
        "Accepting writes a confirmed booking under guards, and simultaneous attempts on the last slot are serialized with a row lock inside a transaction",
        "It preserves the invariant that a confirmed booking always points at a bookable room, and the concurrency test proves it under simultaneous requests"],
       ["6",
        "Not in the midterm: an audit log, an administrator IP allowlist, a failed-login lockout and a decoy administration path",
        "All four are built, together with security headers and a health-check endpoint",
        "Verification and oversight were a stated objective, and recording every administrative action makes the administration module defensible"]],
      widths=[0.3, 1.9, 2.05, 2.35], size=8.5)

h2("Results Against the Midterm Objectives")
number("Met.", "The centralized platform, with all five filters plus sort and correct results "
               "under stacked filters; the inquiry and booking function, since Module B's thread "
               "feeds the decision that writes exactly one confirmed booking; the rating function, "
               "unlocked only by a settled inquiry; user reporting with the action recorded; and the "
               "administrator function covering accounts, verification, reports and analytics.")
number("Not met.", "Real-time in-app notifications (scope item L). The inquiry thread, booking "
                   "status and dashboards carry the information instead, and this is the first "
                   "item listed as a future improvement.")

h2("Conclusion")
body("BHIMS addresses a specific, measurable problem: NLUC Bacnotan students lose time and "
     "fare visiting boarding houses whose rooms are already taken, and landlords leave rooms "
     "vacant because they can only reach students by word of mouth. The system answers both "
     "sides at once. A landlord who can no longer advertise a room that is not really free, "
     "because availability is computed from active rooms and confirmed bookings, and a "
     "student who can see an honest open-room count and the real bookable rate before leaving "
     "campus, are two halves of the same fix. The administrator's verification queue and "
     "audit log keep the platform trustworthy, and the ratings that follow a settled inquiry "
     "give the next student something better than a stranger's word to rely on.")
body("The design work of the midterm was carried through into a running system, and the "
     "parts that changed were changed for reasons recorded in this report: the search filters "
     "were rewritten once testing showed a house could appear three times and a card could "
     "advertise a switched-off room; the availability badge was corrected to count only "
     "bookable rooms; inquiry handling moved behind a POST after a plain page view was found "
     "able to delete a conversation; and the catalogue page was made to survive a load it was "
     "not originally built for. Each came out of testing rather than a specification, which "
     "is the useful lesson of the project.")
body("The limitations are equally clear: notifications are not built, the system is web-only, "
     "it stops at information and booking rather than rental payments, it cannot replace a "
     "physical inspection, and it does not integrate with institutional systems. The next "
     "improvements follow from those limits - notifications, a map or distance view, and "
     "continued work on the heaviest pages. For a student looking for a room, a landlord with "
     "a room to fill, and an administrator who must keep the information believable, BHIMS "
     "replaces a search built on chance with one built on verified, current, shared "
     "information.")

h2("Reference List")
for ref in [
    "Badua, C. J. B., Bayubay, J. O., Layco, M. G. L., & Valdriz, N. G. (2026). BHIMS: Boarding house information management system for efficient vacancy search among NLUC Bacnotan students [Midterm project design proposal]. Don Mariano Marcos Memorial State University, North La Union Campus, College of Information Systems. (The group's shared midterm diagrams are cited here as the source of the corrected models in Figures 1 to 5.)",
    "Bisquera, C. A. D., Perdido, V. G., & Mendoza, N. A. M. (2026). Smart accommodation solution: Innovative boarding house locator in Bayombong municipality. International Journal of Informatics and Communication Technology, 15(1), 1-12. https://doi.org/10.11591/ijict.v15i1.pp1-12",
    "Dennis, A., Wixom, B. H., & Roth, R. M. (2018). Systems analysis and design (7th ed.). John Wiley & Sons.",
    "Django Software Foundation. (2026). Django documentation (Version 6). https://docs.djangoproject.com/",
    "Laudon, K. C., & Laudon, J. P. (2020). Management information systems: Managing the digital firm (16th ed.). Pearson.",
    "Nesta, M. I. P. A., Najaf, A. R. E., & Wati, S. F. A. (2025). Design and development of a web-based boarding-house management information system using RAD method. bit-Tech, 8(2), 2685-2695. https://doi.org/10.32877/bt.v8i2.3342",
]:
    lead("", ref, after=4)

doc.save(OUT)
print("SAVED:", OUT)
print("paragraphs:", len(doc.paragraphs), "tables:", len(doc.tables),
      "images:", len(doc.inline_shapes))

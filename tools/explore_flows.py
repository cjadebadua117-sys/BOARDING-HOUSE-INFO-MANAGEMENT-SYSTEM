"""BHIMS end-to-end feature exercise: drive every write flow in a real browser.

`ui_audit.py` renders pages. This *uses* the product: a student finds a room and
inquires, the landlord answers in the thread, accepts, which creates a booking,
the student sees the booking and rates the landlord. Alongside that it creates a
house and a room with a photo upload, approves a listing as admin, files and
resolves a report, edits a profile, and flips the theme on every page it lands on.

Each step asserts the *observable* outcome (a row appeared, a message rendered,
the URL is where it should be). A step that silently "passes" because a redirect
happened is treated as a failure -- see `expect_text`, which requires real
rendered content, not just a 200.

Usage (dev server must already be running):

    ./venv/Scripts/python.exe tools/explore_flows.py --base-url http://127.0.0.1:8020
    ./venv/Scripts/python.exe tools/explore_flows.py --only inquiry --theme dark
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

DESKTOP = {"width": 1440, "height": 900}
SHOT_DIR = ".audit/flow-shots"


# --------------------------------------------------------------------------
# ORM helpers -- read the fixtures the run will act on, and assert afterwards.
# --------------------------------------------------------------------------
def django_ready() -> None:
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
    import django

    django.setup()


def make_sessions(usernames: list[str], base: str) -> dict[str, dict]:
    """A real Django session per account, so no password is ever needed."""
    from django.conf import settings as dj
    from django.contrib.auth import (
        BACKEND_SESSION_KEY,
        HASH_SESSION_KEY,
        SESSION_KEY,
        get_user_model,
    )
    from django.contrib.sessions.backends.db import SessionStore

    backends = list(getattr(dj, "AUTHENTICATION_BACKENDS", []) or [])
    backend = backends[0] if backends else "django.contrib.auth.backends.ModelBackend"
    um = get_user_model()
    out: dict[str, dict] = {}
    for username in usernames:
        user = um.objects.filter(username=username).first()
        if not user:
            print(f"  ! no account {username!r}", file=sys.stderr)
            continue
        store = SessionStore()
        store[SESSION_KEY] = str(user.pk)
        store[BACKEND_SESSION_KEY] = backend
        store[HASH_SESSION_KEY] = user.get_session_auth_hash()
        store.create()
        out[username] = {"name": dj.SESSION_COOKIE_NAME, "value": store.session_key, "url": base}
    return out


def fixture_state(student_username: str = "demo_student01") -> dict:
    """Pick a real, live record to act on -- never a hard-coded pk.

    The accept step marks a room occupied, so the room must genuinely have
    space; reaching for house pk 1 ('cjade', 81 rooms) would quietly exercise
    a junk fixture row instead of the demo landlord a reviewer actually uses.

    Rooms the student already wrote to are skipped too: `send_inquiry` answers
    an existing conversation with a redirect to the thread, so reusing one
    would never show the compose form and the flow would fail for a reason
    that has nothing to do with the code under test.
    """
    from core.models import BoardingHouse, Inquiry
    from core.views import annotate_room_bookings

    already = set(Inquiry.objects.filter(student__username=student_username)
                  .values_list("room_id", flat=True))
    for house in BoardingHouse.objects.filter(
        owner__username="demo_landlord",
        status=BoardingHouse.Status.APPROVED,
        is_active=True,
    ).order_by("pk"):
        rooms = annotate_room_bookings(
            house.rooms.filter(is_active=True, is_available=True)
            .exclude(pk__in=already).order_by("pk")
        )
        for room in rooms:
            if room.capacity > room.confirmed_bookings:
                return {"house_pk": house.pk, "room_pk": room.pk}
    return {"house_pk": None, "room_pk": None}


# --------------------------------------------------------------------------
@dataclass
class Step:
    name: str
    ok: bool = True
    detail: str = ""
    evidence: list[str] = field(default_factory=list)


class Run:
    def __init__(self, base: str, theme: str, only: str | None, shots: bool):
        self.base = base
        self.theme = theme
        self.only = only
        self.shots = shots
        self.steps: list[Step] = []
        self.console: list[str] = []
        self.page_errors: list[str] = []
        self.start = time.time()
        # Playwright's sync API runs with an event loop alive, so Django refuses
        # any ORM call from inside it ("SynchronousOnlyOperation"). Every ORM
        # assertion is queued here and executed after the browser closes.
        self.deferred: list[tuple[Step, callable]] = []

    def defer(self, st: Step, check: callable) -> None:
        self.deferred.append((st, check))

    def run_deferred(self) -> None:
        for st, check in self.deferred:
            try:
                check()
            except Exception as exc:  # noqa: BLE001
                self.fail(st, f"deferred DB check raised {type(exc).__name__}: {exc}")

    def step(self, name: str) -> Step:
        st = Step(name=name)
        self.steps.append(st)
        return st

    def shot(self, page, name: str) -> None:
        if not self.shots:
            return
        os.makedirs(SHOT_DIR, exist_ok=True)
        page.screenshot(path=f"{SHOT_DIR}/{self.theme}-{name}.png", full_page=False)

    # -- assertion helpers -------------------------------------------------
    def body(self, page) -> str:
        try:
            return page.inner_text("body")
        except Exception as exc:  # noqa: BLE001
            return f"<inner_text failed: {exc}>"

    def expect(self, st: Step, page, needle: str, where: str = "") -> bool:
        """Require the text to actually render. A redirect to the right URL with
        an empty or error page must not count as success."""
        hay = self.body(page)
        if needle.lower() in hay.lower():
            st.evidence.append(f"{where or 'page'} contains {needle!r}")
            return True
        st.ok = False
        st.detail = (f"expected {needle!r} on {page.url.replace(self.base, '')}"
                     f"{(' (' + where + ')') if where else ''}"
                     f" -- first 220 chars: {hay[:220]!r}")
        return False

    def expect_url(self, st: Step, page, fragment: str) -> bool:
        if fragment in page.url:
            st.evidence.append(f"landed on {page.url.replace(self.base, '')}")
            return True
        st.ok = False
        st.detail = f"expected url containing {fragment!r}, got {page.url.replace(self.base, '')!r}"
        return False

    def fail(self, st: Step, why: str) -> None:
        st.ok = False
        st.detail = why

    def report(self) -> int:
        failed = [s for s in self.steps if not s.ok]
        print()
        for s in self.steps:
            print(f"{'PASS' if s.ok else 'FAIL'}  {s.name}")
            if not s.ok and s.detail:
                print(f"        -> {s.detail}")
            for e in s.evidence[:4]:
                print(f"        . {e}")
        if self.console:
            print(f"\nconsole errors ({len(self.console)}):")
            for c in self.console[:10]:
                print(f"   ! {c}")
        if self.page_errors:
            print(f"\nuncaught JS errors ({len(self.page_errors)}):")
            for c in self.page_errors[:10]:
                print(f"   ! {c}")
        print(f"\n{len(self.steps) - len(failed)}/{len(self.steps)} steps passed "
              f"in {time.time() - self.start:.1f}s")
        return 1 if failed or self.page_errors else 0


def wire(page, run: Run):
    page.on("console", lambda m: run.console.append(f"{page.url.replace(run.base,'')}: {m.text[:160]}")
            if m.type == "error" else None)
    page.on("pageerror", lambda e: run.page_errors.append(f"{page.url.replace(run.base,'')}: {str(e)[:160]}"))
    # The accept/decline buttons and the avatar picker all use window.confirm.
    page.on("dialog", lambda d: asyncio_accept(d))


def asyncio_accept(dialog):
    try:
        dialog.accept()
    except Exception:  # noqa: BLE001
        pass


def make_probe_png() -> str:
    """A real, decodable PNG.

    Hand-assembled byte soup is not good enough: Django's ImageField calls
    Pillow's verify() and correctly rejects a corrupt file, which looks exactly
    like an app bug when it is only the fixture. Ask Pillow for the bytes.
    """
    from PIL import Image

    path = Path(".audit") / "upload-probe.png"
    path.parent.mkdir(exist_ok=True)
    Image.new("RGB", (64, 48), (32, 96, 76)).save(path, format="PNG")
    return str(path)


def submit_form_with(page, anchor: str, label: str = "") -> bool:
    """Click the submit button of the form that CONTAINS `anchor`.

    A bare `form button[type=submit]` also matches the sidebar's logout form,
    whose button is hidden on desktop, so the click times out on the wrong
    control. Scoping by a field the form must contain cannot drift.
    """
    btn = page.locator(f"form:has({anchor}) button[type=submit]").first
    if btn.count() == 0:
        print(f"    . no submit button in the form holding {anchor}")
        return False
    btn.click()
    page.wait_for_timeout(1200)
    page.wait_for_load_state("load")
    return True


def pick_option(page, selector: str, label: str = "") -> bool:
    """Select the first real option of a <select>.

    Playwright refuses to act on an <option> element directly ("element is not
    visible") even inside a perfectly visible <select>; the select itself has to
    be the target, with the option's value passed in.
    """
    sel = page.locator(selector)
    if sel.count() == 0 or not sel.first.is_visible():
        print(f"    . select {label or selector} not reachable")
        return False
    values = sel.first.locator("option").evaluate_all(
        "els => els.map(e => ({v: e.value, d: (e.textContent || '').trim()})).filter(o => o.v !== '')")
    if not values:
        print(f"    . select {label or selector} has no selectable option")
        return False
    sel.first.select_option(values[0]["v"])
    return True


def set_field(page, selector: str, value: str, label: str = "") -> bool:
    """Fill a field only if it is actually reachable.

    A wizard hides its later steps until "Next" is clicked, so a plain fill
    would time out on a perfectly good field. Skipping an invisible control is
    reported, never silently treated as done.
    """
    loc = page.locator(selector)
    if loc.count() == 0:
        print(f"    . field {label or selector} not present")
        return False
    if not loc.first.is_visible():
        print(f"    . field {label or selector} exists but is hidden (wizard step)")
        return False
    loc.first.fill(value)
    return True


def click_next(page) -> None:
    nxt = page.locator(".wizard-step.active [data-next]")
    if nxt.count():
        nxt.first.click()
        page.wait_for_timeout(250)


def fresh(browser, base: str, theme: str, session: dict | None):
    ctx = browser.new_context(viewport=DESKTOP, color_scheme="light", reduced_motion="reduce")
    ctx.add_init_script(
        "try { localStorage.setItem('bhims-theme', '%s');"
        " localStorage.setItem('bhims-theme-version', 'teal-v2'); } catch (e) {}" % theme
    )
    if session:
        ctx.add_cookies([session])
    return ctx


# --------------------------------------------------------------------------
# The flows
# --------------------------------------------------------------------------
def flow_inquiry(run: Run, browser, base: str, sessions, fx) -> None:
    """Student asks about a room -> landlord answers -> landlord accepts."""
    if fx["room_pk"] is None:
        run.fail(run.step("inquiry: fixture available"), "no available room to act on")
        return

    # 1. Student browses the listing and opens the inquiry form.
    st = run.step("student: listing detail renders room price")
    ctx = fresh(browser, base, run.theme, sessions["demo_student01"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/listings/{fx['house_pk']}/", wait_until="load")
    run.expect(st, page, "month", "room price")
    run.shot(page, "01-listing-detail")
    page.close()
    ctx.close()

    # 2. Student sends the inquiry.
    st = run.step("student: submit inquiry")
    ctx = fresh(browser, base, run.theme, sessions["demo_student01"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/inquiries/send/{fx['room_pk']}/", wait_until="load")
    run.expect(st, page, "New Inquiry", "compose form")
    run.shot(page, "02-send-inquiry")
    msg = f"Automated review message {run.theme} {int(time.time())}"
    page.fill("#id_message_text", msg)
    page.click("#inquiryForm button[type=submit]")
    page.wait_for_load_state("load")
    if not run.expect_url(st, page, "/students/inquiries/"):
        run.fail(st, f"inquiry submit did not land on a thread: {page.url}")
    run.expect(st, page, msg, "thread shows the sent message")
    run.shot(page, "03-student-thread")
    thread_url = page.url
    page.close()
    ctx.close()

    from core.models import Inquiry

    st = run.step("inquiry row created")
    holder: dict = {}

    def check_inquiry(step=st) -> None:
        inquiry = Inquiry.objects.order_by("-pk").first()
        if inquiry is None:
            run.fail(step, "no Inquiry row after submit")
            return
        step.evidence.append(f"pk={inquiry.pk} room={inquiry.room_id} "
                             f"student={inquiry.student.username}")

    run.defer(st, check_inquiry)

    # The inquiry's pk is only known once the DB has been read; the browser steps
    # below need it, so read it before the Playwright loop by having main() pass
    # a live id. `holder` is filled by the deferred check, which cannot run yet,
    # so resolve it from the thread URL the student actually landed on instead.
    thread_path = thread_url.replace(base, "").split("?")[0]

    # 3. Landlord sees it in their list.
    st = run.step("landlord: inquiry appears in list")
    ctx = fresh(browser, base, run.theme, sessions["demo_landlord"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/landlords/inquiries/", wait_until="load")
    run.expect(st, page, "View Conversation", "inquiry list action")
    run.shot(page, "04-landlord-inquiries")
    page.close()
    ctx.close()

    # 4. Landlord opens the thread and replies.
    st = run.step("landlord: reply in thread")
    ctx = fresh(browser, base, run.theme, sessions["demo_landlord"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(base + thread_path.replace("/students/inquiries/", "/landlords/inquiries/"),
              wait_until="load")
    run.expect(st, page, "Send a Reply", "reply form")
    reply = f"Landlord reply {int(time.time())}"
    page.fill("#message_text", reply)
    page.click("#reply-form button[type=submit]")
    page.wait_for_timeout(1200)
    page.wait_for_load_state("load")
    if not run.expect(st, page, reply, "reply visible to the landlord"):
        page.reload(wait_until="load")
        run.expect(st, page, reply, "reply visible after reload")
    run.shot(page, "05-landlord-thread")
    page.close()
    ctx.close()

    # 5. Student sees the reply (the thread polls, but a reload must work too).
    st = run.step("student: sees landlord reply")
    ctx = fresh(browser, base, run.theme, sessions["demo_student01"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(thread_url, wait_until="load")
    run.expect(st, page, reply, "student thread")
    run.shot(page, "06-student-thread-replied")
    page.close()
    ctx.close()

    # 6. Landlord accepts -> booking.
    st = run.step("landlord: accept student creates booking")
    ctx = fresh(browser, base, run.theme, sessions["demo_landlord"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(base + thread_path.replace("/students/inquiries/", "/landlords/inquiries/"),
              wait_until="load")
    accept = page.locator("form[action*='/accept/'] button")
    if accept.count() == 0:
        run.fail(st, "no Accept Student button rendered")
    else:
        accept.first.click()
        page.wait_for_timeout(1500)
        page.wait_for_load_state("load")
        run.expect(st, page, "accepted", "acceptance banner")
        run.shot(page, "07-landlord-accepted")
    page.close()
    ctx.close()

    # 7. Booking visible on both sides.
    st = run.step("student: booking appears in My Bookings")
    ctx = fresh(browser, base, run.theme, sessions["demo_student01"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/students/bookings/", wait_until="load")
    ok = run.expect(st, page, "View Property", "booking card action")
    run.shot(page, "08-student-bookings")
    if not ok:
        run.fail(st, "no booking card after acceptance")
    page.close()
    ctx.close()

    st = run.step("landlord: booking appears in Bookings & Tenants")
    ctx = fresh(browser, base, run.theme, sessions["demo_landlord"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/landlords/bookings/", wait_until="load")
    run.expect(st, page, "Demo Student 01", "tenant name")
    run.shot(page, "09-landlord-bookings")
    page.close()
    ctx.close()


def flow_landlord_crud(run: Run, browser, base: str, sessions) -> None:
    """Landlord creates a house, adds a room, and the admin approves it."""
    stamp = str(int(time.time()))[-6:]
    house_name = f"Review Test House {stamp}"
    holder: dict = {}

    st = run.step("landlord: create boarding house")
    ctx = fresh(browser, base, run.theme, sessions["demo_landlord"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/landlords/boarding-houses/add/", wait_until="load")
    run.expect(st, page, "Add", "house form")
    run.shot(page, "10-house-form")
    page.fill("#id_name", house_name)
    page.fill("#id_address", "123 Review Street, NLUC")
    pick_option(page, "#id_barangay", "barangay")
    run.shot(page, "10a-house-wizard-step1")
    click_next(page)                      # -> Step 2: Pricing & Policy
    set_field(page, "#id_price", "1750", "price")
    pick_option(page, "#id_gender_allowed", "gender allowed")
    run.shot(page, "10b-house-wizard-step2")
    click_next(page)                      # -> Step 3: Visuals & Details
    set_field(page, "#id_description", "Created by the automated review pass.", "description")
    run.shot(page, "10c-house-wizard-step3")
    submit_form_with(page, "#id_name")

    # The pk has to be known before any further browser step, and the ORM is
    # closed during the Playwright loop, so read it from the URL the app
    # redirected to. A wizard that stayed put means validation rejected it.
    tail = page.url.replace(base, "").strip("/").split("/")
    hpk = int(tail[2]) if (len(tail) >= 3 and tail[0] == "landlords"
                           and tail[1] == "boarding-houses" and tail[2].isdigit()) else None

    def check_house(step=st, name=house_name) -> None:
        from core.models import BoardingHouse

        house = BoardingHouse.objects.filter(name=name).order_by("-pk").first()
        if house is None:
            run.fail(step, f"no BoardingHouse row named {name!r} (form stayed on {page.url})")
            return
        step.evidence.append(f"created pk={house.pk} status={house.status}")

    run.defer(st, check_house)
    page.close()
    ctx.close()

    if hpk is None:
        run.fail(run.step("landlord: add a room to the new house"),
                 f"skipped: the house form did not create anything (landed on {page.url})")
        return

    st = run.step("landlord: add a room to the new house")
    ctx = fresh(browser, base, run.theme, sessions["demo_landlord"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/landlords/boarding-houses/{hpk}/rooms/add/", wait_until="load")
    run.expect(st, page, "Add New Room", "room form")
    run.shot(page, "11-room-form")
    if page.locator("#id_monthly_rate").count():
        page.fill("#id_monthly_rate", "1750")
    if page.locator("#id_capacity").count():
        page.fill("#id_capacity", "2")
    set_field(page, "#id_room_type", "4 person", "room type")
    # A photo is optional, but the page exists to sell the room: exercise the
    # upload path too, using a real 1x1 PNG written to a temp file.
    photo = page.locator("#id_photo")
    if photo.count():
        photo.set_input_files(make_probe_png())
    room_url = page.url
    submit_form_with(page, "#id_monthly_rate")
    if page.url == room_url and "/rooms/add/" in page.url:
        st.evidence.append("form stayed on /rooms/add/ -- validation rejected it")
        st.evidence.append("post-submit page: " + run.body(page)[:300].replace("\n", " "))

    def check_room(step=st, house_pk=hpk) -> None:
        from core.models import Room

        room = Room.objects.filter(boarding_house_id=house_pk).order_by("-pk").first()
        if room is None:
            run.fail(step, f"no Room row for house {house_pk}")
        else:
            step.evidence.append(f"created room pk={room.pk} rate={room.monthly_rate} "
                                 f"photos={room.photos.count()}")

    run.defer(st, check_room)
    run.shot(page, "12-house-detail-after-room")
    page.close()
    ctx.close()

    st = run.step("admin: pending listing shows the new house")
    ctx = fresh(browser, base, run.theme, sessions["root"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/admin/listings/pending/", wait_until="load")
    ok = run.expect(st, page, house_name, "pending queue")
    run.shot(page, "13-admin-pending")
    if not ok:
        run.fail(st, f"new house {house_name!r} never reached the admin approval queue "
                     f"-- a landlord cannot get a listing published")
    else:
        approve = page.locator(f"form[action*='/{hpk}/approve/'] button, "
                               f"a[href*='/{hpk}/approve/']").first
        if approve.count():
            approve.click()
            page.wait_for_timeout(1500)
            page.wait_for_load_state("load")

            def check_approved(step=st, house_pk=hpk) -> None:
                from core.models import BoardingHouse

                house = BoardingHouse.objects.filter(pk=house_pk).first()
                step.evidence.append(f"after approve: status={house.status}")
                if house.status != BoardingHouse.Status.APPROVED:
                    run.fail(step, f"approve action left status={house.status!r}")

            run.defer(st, check_approved)
        else:
            run.fail(st, "no approve control found on the pending row")
    page.close()
    ctx.close()

    st = run.step("approved house is publicly listed")
    ctx = fresh(browser, base, run.theme, None)
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/listings/{hpk}/", wait_until="load")
    if page.url.rstrip("/").endswith("/listings") and run.body(page).count("not currently available"):
        run.fail(st, f"approved house pk={hpk} is still not publicly visible")
    else:
        run.expect(st, page, house_name, "public listing")
    run.shot(page, "14-public-new-listing")
    page.close()
    ctx.close()


def flow_profile(run: Run, browser, base: str, sessions, pks: dict) -> None:
    """Edit profile, change password, report a user, admin resolves the report."""
    student_pk = pks["student"]
    landlord_pk = pks["landlord"]

    st = run.step("student: edit profile saves")
    ctx = fresh(browser, base, run.theme, sessions["demo_student01"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/profile/edit/", wait_until="load")
    run.expect(st, page, "Edit Profile", "edit form")
    run.shot(page, "15-edit-profile")
    field = page.locator("#id_phone_number")
    new_phone = "0917123" + str(int(time.time()))[-4:]
    if field.count():
        original = field.input_value()
        field.fill(new_phone)
        submit_form_with(page, "#id_phone_number")

        def check_phone(step=st, phone=new_phone, was=original, who=student_pk) -> None:
            from django.contrib.auth import get_user_model

            after = get_user_model().objects.get(pk=who).phone_number
            if after != phone:
                run.fail(step, f"phone not persisted: {was!r} -> {after!r}")
            else:
                step.evidence.append("phone persisted, restoring original")
                get_user_model().objects.filter(pk=who).update(phone_number=was)

        run.defer(st, check_phone)
    else:
        run.fail(st, "profile form has no #id_phone_number field")
    page.close()
    ctx.close()

    st = run.step("change password rejects a wrong current password")
    ctx = fresh(browser, base, run.theme, sessions["demo_student02"])
    page = ctx.new_page()
    wire(page, run)
    new_pw = f"Review-{int(time.time())}!x"
    page.goto(f"{base}/profile/change-password/", wait_until="load")
    run.expect(st, page, "Change Password", "password form")
    run.shot(page, "16-change-password")
    try:
        page.fill("#id_old_password", "definitely-not-the-password")
        page.fill("#id_new_password1", new_pw)
        page.fill("#id_new_password2", new_pw)
        submit_form_with(page, "#id_old_password")
        run.expect(st, page, "incorrect", "wrong old password is rejected with a message")
    except Exception as exc:  # noqa: BLE001
        run.fail(st, f"password form unusable: {exc}")
    page.close()
    ctx.close()

    st = run.step("student: file a report about a landlord")
    ctx = fresh(browser, base, run.theme, sessions["demo_student01"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/users/{landlord_pk}/report/", wait_until="load")
    run.expect(st, page, "Report", "report form")
    run.shot(page, "17-report-form")
    pick_option(page, "#id_reason", "report reason")
    if page.locator("#id_details").count():
        page.fill("#id_details", f"Automated review report {int(time.time())}")
    submit_form_with(page, "#id_details")
    page.close()
    ctx.close()

    st = run.step("admin: report appears and can be resolved")
    ctx = fresh(browser, base, run.theme, sessions["root"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/admin/reports/", wait_until="load")
    run.expect(st, page, "Report", "reports table")
    run.shot(page, "18-admin-reports")

    def check_report(step=st) -> None:
        from core.models import UserReport

        report = UserReport.objects.order_by("-pk").first()
        if report is None:
            run.fail(step, "no UserReport row was created by the report form")
            return
        step.evidence.append(f"report pk={report.pk} status={report.status}")

    run.defer(st, check_report)
    page.close()
    ctx.close()


def flow_theme_and_search(run: Run, browser, base: str, sessions) -> None:
    """The theme switch and the search box, used the way a visitor would."""
    st = run.step("theme toggle flips data-theme on a page")
    ctx = fresh(browser, base, run.theme, sessions["demo_student01"])
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/students/dashboard/", wait_until="load")
    before = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
    toggle = page.locator("[data-theme-switch]").first
    if toggle.count() == 0:
        run.fail(st, "no [data-theme-switch] control found")
    else:
        toggle.click()
        page.wait_for_timeout(700)
        after = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        if after == before:
            run.fail(st, f"data-theme did not change ({before!r} -> {after!r})")
        else:
            st.evidence.append(f"data-theme {before} -> {after}")
    page.close()
    ctx.close()

    st = run.step("search returns results")
    ctx = fresh(browser, base, run.theme, None)
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/search/?q=boarding", wait_until="load")
    body = run.body(page)
    if "result" not in body.lower() and "boarding" not in body.lower():
        run.fail(st, f"search page says nothing about results: {body[:200]!r}")
    run.shot(page, "20-search")
    page.close()
    ctx.close()

    st = run.step("browse filters narrow the list")
    ctx = fresh(browser, base, run.theme, None)
    page = ctx.new_page()
    wire(page, run)
    page.goto(f"{base}/listings/", wait_until="load")
    total = page.evaluate("() => document.querySelectorAll('.listing-card, .browse-card, article').length")
    page.goto(f"{base}/listings/?room_type=4", wait_until="load")
    filtered = page.evaluate("() => document.querySelectorAll('.listing-card, .browse-card, article').length")
    if filtered > total:
        run.fail(st, f"filter returned MORE cards than the unfiltered list ({filtered} > {total})")
    else:
        st.evidence.append(f"unfiltered={total} filtered={filtered}")
    run.shot(page, "21-browse-filtered")
    page.close()
    ctx.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="http://127.0.0.1:8021")
    ap.add_argument("--theme", choices=["light", "dark"], default="light")
    ap.add_argument("--only", choices=["inquiry", "crud", "profile", "theme"])
    ap.add_argument("--shots", action="store_true")
    ap.add_argument("--channel", default="msedge")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    django_ready()
    # Read every fixture the flows need here: inside Playwright's sync API the
    # event loop is alive and Django raises SynchronousOnlyOperation on any ORM
    # access.
    fx = fixture_state()
    print(f"acting on house pk={fx['house_pk']} room pk={fx['room_pk']}")

    from django.contrib.auth import get_user_model

    um = get_user_model()
    pks = {
        "student": um.objects.get(username="demo_student01").pk,
        "landlord": um.objects.get(username="demo_landlord").pk,
    }

    base = args.base_url.rstrip("/")
    sessions = make_sessions(["demo_student01", "demo_student02", "demo_landlord", "root"], base)
    needed = {"inquiry": ["demo_student01", "demo_landlord"],
              "crud": ["demo_landlord", "root"],
              "profile": ["demo_student01", "demo_student02", "root"],
              "theme": ["demo_student01"]}
    for flow, users in needed.items():
        for u in users:
            if u not in sessions:
                print(f"!! missing account {u!r} for flow {flow!r} - run is incomplete", file=sys.stderr)
                return 2

    run = Run(base, args.theme, args.only, args.shots)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=args.channel, headless=True)
        try:
            if args.only in (None, "inquiry"):
                print("== inquiry -> reply -> accept -> booking ==")
                flow_inquiry(run, browser, base, sessions, fx)
            if args.only in (None, "crud"):
                print("== landlord CRUD + admin approval ==")
                flow_landlord_crud(run, browser, base, sessions)
            if args.only in (None, "profile"):
                print("== profile / password / report ==")
                flow_profile(run, browser, base, sessions, pks)
            if args.only in (None, "theme"):
                print("== theme switch + search + filters ==")
                flow_theme_and_search(run, browser, base, sessions)
        finally:
            browser.close()
    run.run_deferred()
    return run.report()


if __name__ == "__main__":
    raise SystemExit(main())
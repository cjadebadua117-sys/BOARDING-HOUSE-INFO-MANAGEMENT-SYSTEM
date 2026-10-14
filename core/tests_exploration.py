"""Regression tests for the defects found by the full-system exploration pass.

`tests_adversarial.py` attacks volume, duplication and malformed input.
These three cover what a complete walk of every page, every role and every
write flow turned up instead: a form that destroyed a field nobody was
editing, a redirect cycle that ended in a browser error page rather than a
page, and a screen that named its subject without ever showing it.
"""

from django.core.cache import cache
from django.test import TestCase

from .models import BoardingHouse, Booking, Inquiry, Room, User

PASSWORD = 'Exploration123'


def landlord(email, full_name='Elena Villaflor'):
    return User.objects.create_user(
        email=email, password=PASSWORD, role=User.Role.LANDLORD,
        full_name=full_name, username=email,
    )


def student(email, full_name='Ana Reyes'):
    return User.objects.create_user(
        email=email, password=PASSWORD, role=User.Role.STUDENT,
        full_name=full_name, username=email,
    )


def admin(email):
    return User.objects.create_user(
        email=email, password=PASSWORD, role=User.Role.ADMIN,
        full_name='System Administrator', username=email,
    )


def house(owner, name, **kw):
    kw.setdefault('address', '1 Road')
    kw.setdefault('barangay', 'Sapilang')
    kw.setdefault('status', BoardingHouse.Status.APPROVED)
    return BoardingHouse.objects.create(owner=owner, name=name, **kw)


class ExplorationTestBase(TestCase):
    def setUp(self):
        cache.clear()   # the landing/browse pages cache HTML; never inherit it


class ProfileEditKeepsDisplayNameTests(ExplorationTestBase):
    """Changing one field on Edit Profile must not erase the others.

    Registration only ever writes `full_name`; nothing in the app populates
    `first_name`/`last_name`. Both profile edit forms recomputed `full_name` as
    f"{first_name} {last_name}" on every save, so a user who opened Edit Profile
    to change their phone number came back to a blank name. Because
    `User.display_name` reads `full_name`, every other user then saw the
    account's email address or login handle in its place -- on the landlord's
    bookings table, in inquiry threads, and in the accept confirmation.
    """

    def setUp(self):
        super().setUp()
        self.student = student('wipe-s@example.com', 'Demo Student')
        self.landlord = landlord('wipe-l@example.com', 'Elena Villaflor')

    def _post_edit(self, user, first='', last='', phone='09171234567'):
        return self.client.post('/profile/edit/', {
            'first_name': first,
            'last_name': last,
            'email': user.email,
            'phone_number': phone,
        })

    def test_student_phone_only_edit_keeps_the_name(self):
        self.client.force_login(self.student)
        r = self._post_edit(self.student)
        self.assertEqual(r.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.full_name, 'Demo Student')
        self.assertEqual(self.student.display_name, 'Demo Student')
        # The field the user actually came to change must still save.
        self.assertEqual(self.student.phone_number, '09171234567')

    def test_landlord_phone_only_edit_keeps_the_name(self):
        self.client.force_login(self.landlord)
        self.assertEqual(self._post_edit(self.landlord).status_code, 302)
        self.landlord.refresh_from_db()
        self.assertEqual(self.landlord.full_name, 'Elena Villaflor')

    def test_typing_a_real_name_still_updates_full_name(self):
        self.client.force_login(self.student)
        self._post_edit(self.student, first='Ana', last='Reyes')
        self.student.refresh_from_db()
        self.assertEqual(self.student.full_name, 'Ana Reyes')

    def test_repeated_saves_do_not_erode_the_name(self):
        self.client.force_login(self.landlord)
        self._post_edit(self.landlord)
        self._post_edit(self.landlord, phone='09170000000')
        self.landlord.refresh_from_db()
        self.assertEqual(self.landlord.full_name, 'Elena Villaflor')

    def test_landlords_booking_table_shows_the_name_not_the_email(self):
        """The downstream symptom that made the wipe visible to a landlord."""
        h = house(self.landlord, 'Name Retention House')
        room = Room.objects.create(boarding_house=h, room_type='Single',
                                   monthly_rate=1500, capacity=1)
        Booking.objects.create(student=self.student, room=room,
                               status=Booking.Status.CONFIRMED)
        self.client.force_login(self.landlord)
        self._post_edit(self.landlord)
        content = self.client.get('/landlords/bookings/').content.decode()
        self.assertIn('Demo Student', content)


class CrossRoleRedirectLoopTests(ExplorationTestBase):
    """A signed-in user who walks into another role's area must land on a page.

    Django's `user_passes_test` bounces a signed-in user who lacks the role to
    LOGIN_URL?next=<the page they were just denied>. The login views then
    honoured that `next` for an already-authenticated visitor, sending them
    straight back to the denied page: an unbounded redirect loop that ended in
    the browser's ERR_TOO_MANY_REDIRECTS error rather than any page at all.
    """

    CASES = [
        ('student', '/landlords/dashboard/', '/students/dashboard/'),
        ('student', '/landlords/bookings/', '/students/dashboard/'),
        ('student', '/admin/dashboard/', '/students/dashboard/'),
        ('student', '/admin/settings/', '/students/dashboard/'),
        ('landlord', '/students/dashboard/', '/landlords/dashboard/'),
        ('landlord', '/students/bookings/', '/landlords/dashboard/'),
        ('landlord', '/admin/analytics/', '/landlords/dashboard/'),
        ('admin', '/students/inquiries/', '/admin/dashboard/'),
        ('admin', '/landlords/dashboard/', '/admin/dashboard/'),
    ]

    def _sign_in(self, role):
        # A fresh account per call: `email` is unique, so re-using it inside a
        # subTest raises inside the test's atomic block and every later query
        # in that test dies with TransactionManagementError.
        self._seq = getattr(self, '_seq', 0) + 1
        email = f'loop-{role}-{self._seq}@example.com'
        makers = {'student': student, 'landlord': landlord, 'admin': admin}
        user = makers[role](email)
        self.client.force_login(user)
        return user

    def test_cross_role_urls_settle_instead_of_looping(self):
        for role, denied, home in self.CASES:
            with self.subTest(role=role, denied=denied):
                self._sign_in(role)
                path, hops, landed = denied, 0, None
                # Walk the chain by hand with a hard hop cap: a redirect loop
                # shows up as the cap being reached, never as a final 200.
                while hops < 8:
                    hops += 1
                    r = self.client.get(path)
                    if r.status_code in (301, 302, 303, 307, 308):
                        path = r.headers['Location']
                        continue
                    landed = (r.status_code, path)
                    break
                self.assertIsNotNone(
                    landed, f'{role} -> {denied} never stopped redirecting')
                self.assertEqual(landed[0], 200, f'{role} -> {denied} ended at {landed}')
                self.assertIn(landed[1], (denied, home),
                              f'{role} -> {denied} landed somewhere unexpected')

    def test_login_page_for_a_signed_in_user_lands_on_a_real_page(self):
        self._sign_in('student')
        r = self.client.get('/accounts/login/?next=/admin/dashboard/')
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('next=', r.headers['Location'])
        self.assertEqual(r.headers['Location'], '/students/dashboard/')

    def test_split_login_pages_behave_the_same_way(self):
        for path in ('/students/login/', '/landlords/login/', '/admin/login/'):
            with self.subTest(path=path):
                self._sign_in('student')
                r = self.client.get(path)
                self.assertEqual(r.status_code, 302, f'{path} rendered for a signed-in user')
                self.assertNotIn('next=', r.headers['Location'])
                # Whatever it chose, it must be a page this role can open.
                self.assertEqual(self.client.get(r.headers['Location']).status_code, 200)

    def test_anonymous_user_is_still_sent_to_the_login_page(self):
        r = self.client.get('/students/dashboard/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r.headers['Location'])


class LandlordInquiryCardTests(ExplorationTestBase):
    """The inquiry queue is where a landlord chooses who rents from them.

    Every card used to be plain text: the student's name, falling back to
    their email address; a bold "Room:" label glued to the house and room in
    one run of prose; and a truncated message. Nothing showed who was asking
    or which room they were asking about, while the sibling bookings table
    and the admin student list both drew an avatar for the same person.
    """

    def setUp(self):
        super().setUp()
        self.landlord = landlord('card-l@example.com')
        self.student = student('card-s@example.com')
        h = house(self.landlord, 'Card Test House')
        self.room = Room.objects.create(boarding_house=h, room_type='Single Room',
                                        monthly_rate=1500, capacity=2)
        Inquiry.objects.create(student=self.student, room=self.room,
                               message_text='Is this room still free?')
        self.client.force_login(self.landlord)

    def _content(self):
        r = self.client.get('/landlords/inquiries/')
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_card_shows_the_student_avatar_and_handle(self):
        content = self._content()
        self.assertIn('inq-avatar', content, 'no avatar on the inquiry card')
        self.assertIn('Ana Reyes', content)
        self.assertIn('card-s@example.com', content)

    def test_card_shows_the_room_with_its_price(self):
        content = self._content()
        self.assertIn('inq-room-thumb', content, 'no room visual on the card')
        self.assertIn('Card Test House', content)
        # floatformat:0 -- a whole-number DecimalField stores 1500, not 1500.00,
        # so it renders without a thousands separator here.
        self.assertIn('1500', content)

    def test_card_never_prints_a_template_comment(self):
        """`{# ... #}` is single-line in Django; a multi-line one is emitted as
        literal text, so the reader sees the comment."""
        content = self._content()
        self.assertNotIn('{#', content)
        self.assertNotIn('{% comment %}', content)

    def test_empty_queue_still_offers_a_way_forward(self):
        Inquiry.objects.all().delete()
        content = self._content()
        self.assertIn('No inquiries yet', content)
        self.assertIn('Add a Boarding House', content)
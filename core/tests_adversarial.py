"""ADVERSARIAL SUITE -- "how will the system destroy itself?"

Written for the instructor's Build -> Test -> Find -> Fix -> Test-again loop.

Philosophy: every test here is an ATTACK. It does not ask "does the feature
work?"; it asks "what happens when someone hammers, duplicates, or starves
this code path?" A test that passes means the system survived the attack.

Categories
----------
WRONG OUTPUT      numbers/labels the user sees must match what the system did
DUPLICATE DATA    the same real-world thing must not appear or exist twice
HIGH VOLUME       response must stay bounded as users/traffic scale up
NETWORK FAILURE   the system must degrade gracefully, not leak or 500
"""
import threading

from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase

from .models import (
    Amenity,
    Barangay,
    BoardingHouse,
    Booking,
    Inquiry,
    Room,
    User,
)

PASSWORD = 'Adversary123'
CARD_LIMIT = 200  # houses created in volume tests


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def landlord(email):
    return User.objects.create_user(
        email=email, password=PASSWORD, role=User.Role.LANDLORD,
        full_name='Landlord', username=email,
    )


def student(email):
    return User.objects.create_user(
        email=email, password=PASSWORD, role=User.Role.STUDENT,
        full_name='Student', username=email,
    )


def house(owner, name, **kw):
    kw.setdefault('address', '1 Road')
    kw.setdefault('barangay', 'Sapilang')
    kw.setdefault('status', BoardingHouse.Status.APPROVED)
    return BoardingHouse.objects.create(owner=owner, name=name, **kw)


def card_count(response, name):
    """How many times a house name appears in the rendered grid."""
    return response.content.decode('utf-8').count(name)


class AdversarialTestBase(TestCase):
    def setUp(self):
        cache.clear()   # the landing/browse pages cache HTML; never inherit it


# ==========================================================================
# 1. WRONG OUTPUT
# ==========================================================================
class WrongOutputPriceTests(AdversarialTestBase):
    """ATTACK: make the card show a price the student cannot actually pay."""

    def setUp(self):
        super().setUp()
        self.landlord = landlord('wo-price@example.com')
        self.house = house(self.landlord, 'Cheap Label House')

    def test_card_price_ignores_filters_the_user_applied(self):
        """Filter says 'at least 5000'; a 500-peso room must not be advertised."""
        Room.objects.create(boarding_house=self.house, room_type='Tiny',
                            monthly_rate=500, capacity=1, is_available=True)
        Room.objects.create(boarding_house=self.house, room_type='Big',
                            monthly_rate=9000, capacity=1, is_available=True)
        response = self.client.get('/listings/?price_min=5000')
        self.assertEqual(response.status_code, 200)
        card = response.context['houses'][0]
        self.assertGreaterEqual(
            card.min_price, 5000,
            f'Card advertises P{card.min_price} while the student filtered '
            f'for rooms of at least P5000.',
        )

    def test_card_price_comes_from_a_room_nobody_can_book(self):
        """A de-listed (inactive) room must not set the advertised 'from' price."""
        Room.objects.create(boarding_house=self.house, room_type='Hidden',
                            monthly_rate=100, capacity=1, is_active=False,
                            is_available=True)
        Room.objects.create(boarding_house=self.house, room_type='Real',
                            monthly_rate=5000, capacity=1, is_active=True,
                            is_available=True)
        response = self.client.get('/listings/')
        card = response.context['houses'][0]
        self.assertEqual(
            card.min_price, 5000,
            f'Card advertises P{card.min_price} from an inactive room that is '
            f'not bookable anywhere on the site.',
        )

    def test_price_max_filter_does_not_advertise_cheaper_than_shown(self):
        Room.objects.create(boarding_house=self.house, room_type='A',
                            monthly_rate=500, capacity=1, is_available=True)
        Room.objects.create(boarding_house=self.house, room_type='B',
                            monthly_rate=9000, capacity=1, is_available=True)
        response = self.client.get('/listings/?price_max=1000')
        card = response.context['houses'][0]
        self.assertLessEqual(card.min_price, 1000)


class WrongOutputAvailabilityTests(AdversarialTestBase):
    """ATTACK: make the 'rooms available' badge lie about the search."""

    def setUp(self):
        super().setUp()
        self.landlord = landlord('wo-avail@example.com')
        self.house = house(self.landlord, 'Tier House')
        self.cheap = Room.objects.create(
            boarding_house=self.house, room_type='Bed', monthly_rate=1000,
            capacity=1, is_available=True)
        self.dear = Room.objects.create(
            boarding_house=self.house, room_type='Suite', monthly_rate=9000,
            capacity=1, is_available=True)

    def test_available_count_must_match_the_price_filter(self):
        response = self.client.get('/listings/?price_max=2000')
        card = response.context['houses'][0]
        self.assertEqual(
            card.available_rooms_count, 1,
            f'Badge says {card.available_rooms_count} rooms available but only '
            f'1 room fits the P2000 cap the student applied.',
        )

    def test_full_room_is_not_counted_as_available(self):
        Room.objects.create(boarding_house=self.house, room_type='Full', monthly_rate=1200,
                            capacity=1, is_available=True)
        full = Room.objects.get(room_type='Full')
        Booking.objects.create(student=student('wo-s-full@example.com'), room=full,
                               status=Booking.Status.CONFIRMED)
        response = self.client.get('/listings/')
        card = response.context['houses'][0]
        self.assertEqual(card.available_rooms_count, 2,
                         'A room booked to capacity is being advertised as available.')

    def test_landlord_detail_occupied_count_matches_confirmed_bookings(self):
        Booking.objects.create(student=student('wo-s2@example.com'), room=self.cheap,
                               status=Booking.Status.CONFIRMED)
        self.client.force_login(self.landlord)
        response = self.client.get(
            f'/landlords/boarding-houses/{self.house.pk}/')
        self.assertEqual(response.context['occupied_count'], 1)
        self.assertEqual(response.context['available_count'], 1)


class WrongOutputSortTests(AdversarialTestBase):
    """ATTACK: 'Lowest price first' must actually be sorted."""

    def setUp(self):
        super().setUp()
        self.landlord = landlord('wo-sort@example.com')
        self.cheap_house = house(self.landlord, 'AAA Cheap')
        self.dear_house = house(self.landlord, 'ZZZ Dear')
        Room.objects.create(boarding_house=self.cheap_house, room_type='S',
                            monthly_rate=1000, capacity=1)
        Room.objects.create(boarding_house=self.dear_house, room_type='S',
                            monthly_rate=9000, capacity=1)

    def test_lowest_price_sort_is_actually_ascending(self):
        response = self.client.get('/listings/?sort=lowest_price')
        prices = [h.min_price for h in response.context['houses']]
        self.assertEqual(
            prices, sorted(prices),
            f'House cards are not in ascending price order: {prices}',
        )
        self.assertEqual(len(prices), 2, f'Expected 2 houses, got {prices}')

    def test_newest_sort_is_stable_and_unique(self):
        response = self.client.get('/listings/?sort=newest')
        names = [h.name for h in response.context['houses']]
        self.assertEqual(len(names), len(set(names)), f'Duplicates: {names}')


class WrongOutputBookingTests(AdversarialTestBase):
    """ATTACK: create a booking on a room/house that is not sellable."""

    def setUp(self):
        super().setUp()
        self.landlord = landlord('wo-book@example.com')
        self.house = house(self.landlord, 'Pending House',
                           status=BoardingHouse.Status.PENDING)
        self.room = Room.objects.create(
            boarding_house=self.house, room_type='S', monthly_rate=2000,
            capacity=2, is_available=True)
        self.s1 = student('wo-b-s1@example.com')
        self.inq = Inquiry.objects.create(student=self.s1, room=self.room,
                                          message_text='hi')

    def test_cannot_accept_a_student_into_a_rejected_listing(self):
        """Admin rejects the house; the landlord must not keep selling it."""
        self.house.status = BoardingHouse.Status.REJECTED
        self.house.save(update_fields=['status'])
        self.client.force_login(self.landlord)
        self.client.post(f'/landlords/inquiries/{self.inq.pk}/accept/')
        self.assertEqual(
            Booking.objects.filter(room=self.room,
                                   status=Booking.Status.CONFIRMED).count(), 0,
            'A confirmed booking was created for a REJECTED listing that '
            'students cannot even see.',
        )

    def test_cannot_accept_into_a_deactivated_room(self):
        self.house.status = BoardingHouse.Status.APPROVED
        self.house.save(update_fields=['status'])
        self.room.is_active = False
        self.room.save(update_fields=['is_active'])
        self.client.force_login(self.landlord)
        self.client.post(f'/landlords/inquiries/{self.inq.pk}/accept/')
        self.assertEqual(
            Booking.objects.filter(room=self.room,
                                   status=Booking.Status.CONFIRMED).count(), 0,
            'Accepted a student into a room the landlord had switched off.',
        )


# ==========================================================================
# 2. DUPLICATE DATA
# ==========================================================================
class DuplicateCardTests(AdversarialTestBase):
    """ATTACK: make one boarding house appear many times in the grid."""

    def setUp(self):
        super().setUp()
        self.landlord = landlord('dup-card@example.com')
        self.house = house(self.landlord, 'Fanout House')
        for rate in (3000, 3500, 4000):
            Room.objects.create(boarding_house=self.house, room_type='Single',
                                monthly_rate=rate, capacity=1,
                                is_available=True)

    def test_lowest_price_sort_does_not_duplicate_the_card(self):
        response = self.client.get('/listings/?sort=lowest_price')
        self.assertEqual(
            card_count(response, 'Fanout House'), 1,
            'One house rendered as 3 cards because it has 3 rooms.',
        )

    def test_search_page_does_not_duplicate_the_card(self):
        response = self.client.get('/search/?sort=lowest_price')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(card_count(response, 'Fanout House'), 1,
                         'Search page fan-out: one house, several cards.')

    def test_room_type_filter_does_not_duplicate_the_card(self):
        response = self.client.get('/listings/?room_type=Single')
        self.assertEqual(card_count(response, 'Fanout House'), 1)

    def test_amenity_filter_does_not_duplicate_the_card(self):
        wifi = Amenity.objects.create(name='Adversarial WiFi')
        for room in self.house.rooms.all():
            room.amenities.add(wifi)
        response = self.client.get('/listings/?amenities=Adversarial+WiFi')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(card_count(response, 'Fanout House'), 1)

    def test_stacked_filters_do_not_duplicate_the_card(self):
        response = self.client.get(
            '/listings/?room_type=Single&price_min=2500&price_max=5000'
            '&barangay=Sapilang&sort=lowest_price')
        self.assertEqual(card_count(response, 'Fanout House'), 1)

    def test_decorated_list_has_no_repeat_objects(self):
        response = self.client.get('/listings/?sort=lowest_price')
        pks = [h.pk for h in response.context['houses']]
        self.assertEqual(len(pks), len(set(pks)), f'Duplicate house pks: {pks}')


class DuplicateRecordTests(AdversarialTestBase):
    """ATTACK: write the same record twice."""

    def setUp(self):
        super().setUp()
        self.landlord = landlord('dup-rec@example.com')
        self.house = house(self.landlord, 'Dup Record House')
        self.room = Room.objects.create(boarding_house=self.house, room_type='S',
                                        monthly_rate=2000, capacity=1)
        self.s1 = student('dup-s1@example.com')

    def test_double_inquiry_makes_one_conversation(self):
        self.client.force_login(self.s1)
        for _ in range(3):
            self.client.post(f'/inquiries/send/{self.room.pk}/',
                             {'message_text': 'Please, is this free?'})
        self.assertEqual(
            Inquiry.objects.filter(student=self.s1, room=self.room).count(), 1,
            'Student created several parallel conversations about one room.',
        )

    def test_get_on_inquiry_form_creates_nothing(self):
        self.client.force_login(self.s1)
        self.client.get(f'/inquiries/send/{self.room.pk}/')
        self.assertEqual(Inquiry.objects.count(), 0,
                         'Simply opening the inquiry page created an inquiry.')

    def test_double_accept_makes_one_booking(self):
        self.client.force_login(self.landlord)
        for _ in range(3):
            self.client.post(f'/inquiries/send/{self.room.pk}/')
        inq = Inquiry.objects.create(student=self.s1, room=self.room,
                                     message_text='me')
        for _ in range(3):
            self.client.post(f'/landlords/inquiries/{inq.pk}/accept/')
        self.assertEqual(
            Booking.objects.filter(student=self.s1, room=self.room,
                                   status=Booking.Status.CONFIRMED).count(), 1,
            'Repeated Accept clicks created duplicate confirmed bookings.',
        )

    def test_barangay_names_stay_unique(self):
        Barangay.objects.create(name='Unique Ward')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Barangay.objects.create(name='Unique Ward')

    def test_duplicate_registration_is_refused(self):
        payload = {
            'username': 'dupreg', 'full_name': 'Dup Reg',
            'email': 'dupreg@example.com', 'student_id': '241-0000-1',
            'program': 'CIS', 'password1': 'StrongPass123',
            'password2': 'StrongPass123',
        }
        from .forms import StudentRegistrationForm
        self.assertTrue(StudentRegistrationForm(data=payload).is_valid())
        self.client.post('/students/register/', payload)
        second = StudentRegistrationForm(data=payload)
        self.assertFalse(second.is_valid(),
                         'The same email/student ID was accepted twice.')


# ==========================================================================
# 3. HIGH VOLUME  (what happens when the whole campus shows up at once)
# ==========================================================================
class HighVolumeQueryBudgetTests(AdversarialTestBase):
    """ATTACK: spend a user's request budget on N+1 queries."""

    def setUp(self):
        super().setUp()
        self.landlord = landlord('hv-q@example.com')
        self.house = house(self.landlord, 'Many Room House')
        self.rooms = [
            Room.objects.create(boarding_house=self.house, room_type=f'R{i}',
                                monthly_rate=1000 + i, capacity=1,
                                is_available=True)
            for i in range(12)
        ]

    def test_detail_page_query_count_is_flat_in_room_count(self):
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(f'/listings/{self.house.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertLess(
            len(ctx.captured_queries), 15,
            f'{len(ctx.captured_queries)} queries for a 12-room detail page '
            f'(one availability COUNT per room). Room count should not drive '
            f'the query count.',
        )

    def test_listing_page_query_count_is_bounded(self):
        from django.test.utils import CaptureQueriesContext
        for i in range(10):
            h = house(self.landlord, f'Bulk House {i}')
            Room.objects.create(boarding_house=h, room_type='S',
                                monthly_rate=1500, capacity=1)
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/listings/')
        self.assertEqual(response.status_code, 200)
        self.assertLess(
            len(ctx.captured_queries), 25,
            f'{len(ctx.captured_queries)} queries for an 11-house browse page.',
        )

    def test_browse_query_count_does_not_grow_with_the_catalogue(self):
        """ATTACK: add rooms and houses, watch the per-request cost climb.

        This is the property that decides whether the system survives a
        campus-wide surge: a browse request must cost the same whether the
        catalogue holds 1 house or 100.
        """
        from django.test.utils import CaptureQueriesContext

        def browse_cost():
            cache.clear()
            with CaptureQueriesContext(connection) as ctx:
                response = self.client.get('/listings/')
            self.assertEqual(response.status_code, 200)
            return len(ctx.captured_queries)

        baseline = browse_cost()
        for i in range(8):
            extra = house(self.landlord, f'Growing House {i}')
            for j in range(3):
                Room.objects.create(boarding_house=extra, room_type=f'T{j}',
                                    monthly_rate=900 + j, capacity=1)
        grown = browse_cost()
        self.assertLessEqual(
            grown, baseline + 2,
            f'Browse cost scaled with the catalogue: {baseline} queries for 1 '
            f'house, {grown} queries for 9 houses (one page shows 12).',
        )

    def test_landlord_detail_query_count_is_bounded(self):
        from django.test.utils import CaptureQueriesContext
        self.client.force_login(self.landlord)
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(
                f'/landlords/boarding-houses/{self.house.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertLess(
            len(ctx.captured_queries), 20,
            f'{len(ctx.captured_queries)} queries on the landlord property page.',
        )


class HighVolumePaginationTests(AdversarialTestBase):
    """ATTACK: one browse request must not render the entire table."""

    @classmethod
    def setUpTestData(cls):
        owner = landlord('hv-page@example.com')
        for i in range(30):
            h = house(owner, f'Page House {i:02d}')
            Room.objects.create(boarding_house=h, room_type='S',
                                monthly_rate=1000, capacity=1)

    def test_browse_page_is_paginated(self):
        page1 = self.client.get('/listings/')
        page2 = self.client.get('/listings/?page=2')
        self.assertEqual(page1.status_code, 200)
        first = {h.pk for h in page1.context['houses']}
        self.assertLess(
            len(first), 30,
            f'Browse page rendered all 30 houses in one response '
            f'({len(first)} cards). No pagination on the hottest page.',
        )
        second = {h.pk for h in page2.context['houses']}
        self.assertTrue(second, '?page=2 returned nothing.')
        self.assertFalse(first & second, 'Page 1 and page 2 overlap.')


class HighVolumeThrottleTests(AdversarialTestBase):
    """ATTACK: starve legitimate users behind the campus NAT / proxy IP."""

    def setUp(self):
        super().setUp()
        self.users = [student(f'hv-nat-{i}@example.com') for i in range(6)]

    def test_one_ip_burst_from_many_users_is_not_throttled(self):
        """Six different students on campus wifi share one public IP.

        A per-IP write budget means a normal class behind NAT starts getting
        429s while a scripted abuser on a second IP gets a fresh allowance.
        """
        statuses = []
        for i in range(130):
            u = self.users[i % len(self.users)]
            self.client.force_login(u)
            response = self.client.post(
                '/profile/edit/', {'first_name': 'A', 'last_name': 'B'},
            )
            statuses.append(response.status_code)
        throttled = [s for s in statuses if s == 429]
        self.assertEqual(
            throttled, [],
            f'{len(throttled)} legitimate requests were rejected with 429 '
            f'because unrelated users share one IP.',
        )

    @staticmethod
    def _stub_request(user, ip):
        """Minimal request object for driving the throttle helper directly."""
        request = type('Req', (), {})()
        request.user = user
        request.META = {'REMOTE_ADDR': ip}
        return request

    def test_a_single_abuser_is_still_throttled(self):
        """Fixing NAT starvation must not remove the protection itself."""
        from core.views import _throttle_generic
        abuser = self._stub_request(self.users[0], '10.0.0.1')
        rejected = [
            _throttle_generic(abuser, scope='abuse', per_minute=5)
            for _ in range(10)
        ]
        self.assertIn(True, rejected,
                      'One caller hammering one endpoint is never rate-limited.')

    def test_budget_is_per_caller_not_per_ip(self):
        """Two students on the same campus IP must not share one allowance."""
        from core.views import _throttle_generic
        first = self._stub_request(self.users[0], '10.0.0.1')
        second = self._stub_request(self.users[1], '10.0.0.1')
        for _ in range(10):
            _throttle_generic(first, scope='nat', per_minute=5)
        self.assertFalse(
            _throttle_generic(second, scope='nat', per_minute=5),
            'User B inherited user A\u2019s exhausted budget on the shared IP.',
        )

    def test_login_failure_counter_counts_every_attempt(self):
        """ATTACK: fire failed logins in parallel and count the losses.

        A get -> +1 -> set counter loses updates when threads interleave, so
        a brute-force burst can be undercounted and never trip the lockout.
        Every attempt must land in the counter.
        """
        from core.views import _lockout_state, _record_login_failure
        cache.clear()
        request = type('R', (), {
            'POST': {'username': 'victim@example.com'},
            'META': {'REMOTE_ADDR': '10.0.0.9'},
        })()
        per_thread, n_threads = 25, 4

        def hammer():
            for _ in range(per_thread):
                _record_login_failure(request)

        threads = [threading.Thread(target=hammer) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        locked, fails, _until = _lockout_state(request)
        self.assertEqual(
            fails, per_thread * n_threads,
            f'{per_thread * n_threads} failed logins were recorded as {fails}: '
            f'the lockout counter loses increments under concurrency.',
        )
        self.assertTrue(locked, 'A burst of failures never locked the account.')


class HighVolumeCacheTests(AdversarialTestBase):
    """ATTACK: rely on a cache that disappears when the server scales out."""

    def test_cache_backend_cannot_fail_under_concurrency(self):
        """A file-based cache looks like the obvious way to share state between
        workers, but on Windows several threads reading the same cache file
        raise PermissionError and every warm page becomes HTTP 500.

        Measured: swapping to FileBasedCache produced 21 x HTTP 500 in an
        1800-request load test of /listings/ -- a cache meant to absorb a
        stampede was taking the site down during one.
        """
        from django.conf import settings
        backend = settings.CACHES['default']['BACKEND'].lower()
        self.assertNotIn(
            'filebased', backend,
            'FileBasedCache raises PermissionError under concurrent threads on '
            'Windows; use LocMemCache (single process) or a real shared cache.',
        )

    def test_locmem_is_only_safe_because_the_server_is_single_process(self):
        """LocMemCache is shared by every THREAD but not by every PROCESS, so
        the production launcher must not fork workers: if it did, the login
        lockout and the write throttle would silently split per worker.
        """
        from django.conf import settings
        launcher = (settings.BASE_DIR / 'Run Production Server.py').read_text(
            encoding='utf-8')
        self.assertIn('threads=', launcher)
        self.assertNotIn('processes=', launcher)

    def test_page_cache_failure_never_returns_500(self):
        """ATTACK: break the cache backend and hammer the cached pages.

        The landing and browse pages are cached. If the cache backend raises
        (disk full, file locked, Redis down) the site must fall back to
        rendering normally, not 500 for every visitor at once.
        """
        from unittest import mock
        target = 'django.core.cache.backends.locmem.LocMemCache'
        with mock.patch(f'{target}.get', side_effect=RuntimeError('cache down')), \
                mock.patch(f'{target}.set', side_effect=RuntimeError('cache down')), \
                mock.patch(f'{target}.delete', side_effect=RuntimeError('cache down')):
            landing = self.client.get('/')
            browse = self.client.get('/listings/')
        self.assertEqual(landing.status_code, 200,
                         'A cache outage turned the landing page into a 500.')
        self.assertEqual(browse.status_code, 200,
                         'A cache outage turned the browse page into a 500.')

    def test_approving_a_listing_shows_up_immediately(self):
        """ATTACK: warm the cached browse page, then approve a listing.

        A cached page with no invalidation keeps showing the old world: the
        admin approves a house and it stays invisible while students browse.
        """
        admin = User.objects.create_user(
            email='cache-admin@example.com', password=PASSWORD,
            role=User.Role.ADMIN, username='cache-admin@example.com',
        )
        owner = landlord('cache-l@example.com')
        pending = house(owner, 'Freshly Approved House',
                        status=BoardingHouse.Status.PENDING, is_active=False)
        Room.objects.create(boarding_house=pending, room_type='S',
                            monthly_rate=1200, capacity=1)

        # Warm the cache the way a real visitor would.
        warm = self.client.get('/listings/')
        self.assertNotIn(b'Freshly Approved House', warm.content)
        self.client.get('/')                      # warm the landing cache too

        self.client.force_login(admin)
        self.client.post(f'/admin/listings/{pending.pk}/approve/')
        self.client.logout()   # the landing page redirects signed-in users

        after = self.client.get('/listings/')
        self.assertIn(
            b'Freshly Approved House', after.content,
            'An approved listing is still missing from the cached browse page.',
        )
        landing = self.client.get('/')
        self.assertEqual(landing.status_code, 200)
        self.assertIn(b'Freshly Approved House', landing.content,
                      'The cached landing page kept showing the old listings.')

    def test_adding_a_barangay_shows_up_immediately(self):
        """ATTACK: warm the cached browse page, then add a barangay.

        The student filter is rendered inside that cached HTML, so an admin's
        new barangay stayed invisible to logged-out students until the cache
        expired — the page looked broken right after saving.
        """
        admin = User.objects.create_user(
            email='barangay-admin@example.com', password=PASSWORD,
            role=User.Role.ADMIN, username='barangay-admin@example.com',
        )
        warm = self.client.get('/listings/')
        self.assertNotIn(b'New Cache Ward', warm.content)

        self.client.force_login(admin)
        response = self.client.post(
            '/admin/barangays/',
            {'name': 'New Cache Ward', 'distance_from_campus': '1.5 km'},
        )
        self.assertEqual(response.status_code, 302)
        self.client.logout()

        after = self.client.get('/listings/')
        self.assertIn(
            b'New Cache Ward', after.content,
            'A new barangay is still missing from the cached student filter.',
        )


class AcceptRaceTests(TransactionTestCase):
    """ATTACK: two landlords (or double click) claim the last bed at once.

    Real concurrency: two threads, one barrier, both POST Accept for one
    capacity-1 room. The database must end with exactly ONE confirmed booking.
    """

    def setUp(self):
        cache.clear()
        self.landlord = landlord('race-l@example.com')
        self.house = house(self.landlord, 'Race House')
        self.room = Room.objects.create(boarding_house=self.house, room_type='S',
                                        monthly_rate=2000, capacity=1,
                                        is_available=True)
        self.s1 = student('race-s1@example.com')
        self.s2 = student('race-s2@example.com')
        self.i1 = Inquiry.objects.create(student=self.s1, room=self.room,
                                         message_text='a')
        self.i2 = Inquiry.objects.create(student=self.s2, room=self.room,
                                         message_text='b')

    def test_simultaneous_accepts_cannot_overbook_the_last_bed(self):
        if connection.vendor == 'sqlite':
            self.skipTest('SQLite has no row locks; production runs MariaDB.')

        barrier = threading.Barrier(2)
        statuses = []

        def accept(inquiry_pk, username):
            connection.close()
            client = Client()
            client.force_login(User.objects.get(username=username))
            try:
                barrier.wait(timeout=10)
                response = client.post(
                    f'/landlords/inquiries/{inquiry_pk}/accept/')
                statuses.append(response.status_code)
            finally:
                connection.close()

        threads = [
            threading.Thread(target=accept, args=(self.i1.pk,
                                                  self.landlord.username)),
            threading.Thread(target=accept, args=(self.i2.pk,
                                                  self.landlord.username)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)

        confirmed = Booking.objects.filter(
            room=self.room, status=Booking.Status.CONFIRMED).count()
        self.assertEqual(
            confirmed, 1,
            f'OVERBOOKING: capacity-1 room ended with {confirmed} confirmed '
            f'bookings after simultaneous accepts (statuses={statuses}).',
        )
        self.assertEqual(self.room.occupied_count, 1)


# ==========================================================================
# 4. NETWORK FAILURE
# ==========================================================================
class RenderedTemplateIntegrityTests(AdversarialTestBase):
    """ATTACK: leak template source onto the page.

    `{# ... #}` is a SINGLE-LINE comment in Django. Written across several
    lines it is not a comment at all -- the whole block is printed verbatim
    into the HTML. That is how '{# The pager lives inside the fragment ... }'
    ended up visible under the browse grid.
    """

    def _assert_clean(self, url):
        body = self.client.get(url).content.decode('utf-8')
        for marker in ('{#', '#}'):
            self.assertNotIn(
                marker, body,
                f'Raw template comment syntax {marker!r} leaked onto {url}.',
            )

    def test_public_pages_have_no_raw_template_syntax(self):
        for url in ('/', '/listings/', '/search/', '/accounts/login/',
                    '/students/login/', '/landlords/login/',
                    '/students/register/', '/admin/login/'):
            with self.subTest(url=url):
                self._assert_clean(url)

    def test_authenticated_pages_have_no_raw_template_syntax(self):
        owner = landlord('integrity-l@example.com')
        h = house(owner, 'Integrity House')
        room = Room.objects.create(boarding_house=h, room_type='Single',
                                   monthly_rate=1500, capacity=1)
        stu = student('integrity-s@example.com')
        Inquiry.objects.create(student=stu, room=room, message_text='hello')

        self.client.force_login(owner)
        for url in (f'/listings/{h.pk}/', '/landlords/dashboard/',
                    '/landlords/inquiries/',
                    f'/landlords/boarding-houses/{h.pk}/',
                    f'/landlords/rooms/{room.pk}/edit/',
                    f'/landlords/boarding-houses/{h.pk}/rooms/add/',
                    '/profile/', '/profile/edit/'):
            with self.subTest(url=url):
                response = self.client.get(url)
                if response.status_code != 200:
                    continue   # non-200 routes are covered by the smoke tests
                body = response.content.decode('utf-8')
                for marker in ('{#', '#}'):
                    self.assertNotIn(marker, body,
                                     f'{marker!r} leaked onto {url}')


class NetworkAssetTests(AdversarialTestBase):
    """ATTACK: make every page load re-download assets, or leak files."""

    def test_static_asset_supports_conditional_get(self):
        """No 304 means every page view re-downloads the whole design system."""
        response = self.client.get('/static/core/css/Design%20Tokens.css')
        self.assertEqual(response.status_code, 200)
        last_modified = response.headers.get('Last-Modified')
        self.assertIsNotNone(
            last_modified,
            'Static CSS is served without Last-Modified: browsers cannot '
            'revalidate, so every navigation re-downloads it.',
        )
        again = self.client.get('/static/core/css/Design%20Tokens.css',
                                HTTP_IF_MODIFIED_SINCE=last_modified)
        self.assertEqual(
            again.status_code, 304,
            'Conditional GET returned 200 instead of 304: no client caching.',
        )

    def test_media_path_traversal_is_blocked(self):
        for path in ('/media/../myproject/settings.py',
                     '/media/..%2f..%2fmyproject%2fsettings.py',
                     '/static/../myproject/settings.py'):
            response = self.client.get(path)
            self.assertIn(
                response.status_code, (301, 400, 403, 404),
                f'{path} answered {response.status_code} instead of refusing.',
            )
            self.assertNotIn(b'SECRET_KEY', response.content)

    def test_listing_with_a_missing_photo_still_renders(self):
        """Disk full / file deleted out-of-band must not break the page."""
        owner = landlord('net-img@example.com')
        broken = house(owner, 'Broken Photo House')
        broken.image = 'boarding_images/does-not-exist.jpg'
        broken.save(update_fields=['image'])
        Room.objects.create(boarding_house=broken, room_type='S',
                            monthly_rate=1000, capacity=1)
        response = self.client.get('/listings/')
        self.assertEqual(response.status_code, 200)
        detail = self.client.get(f'/listings/{broken.pk}/')
        self.assertEqual(detail.status_code, 200,
                         'A row pointing at a deleted image file 500s the page.')

    def test_missing_static_asset_returns_404_not_500(self):
        response = self.client.get('/static/core/images/definitely-gone.png')
        self.assertEqual(response.status_code, 404)


class NetworkDegradationTests(AdversarialTestBase):
    """ATTACK: yank the database out from under a live request."""

    def test_home_survives_database_outage(self):
        from unittest import mock
        from django.db import OperationalError
        cache.clear()
        with mock.patch('django.db.backends.utils.CursorWrapper.execute',
                        side_effect=OperationalError('db gone')):
            response = self.client.get('/')
        self.assertIn(response.status_code, (200, 503),
                      f'DB outage produced {response.status_code} on the '
                      f'landing page instead of a graceful response.')

    def test_health_liveness_never_touches_the_database(self):
        from unittest import mock
        from django.db import OperationalError
        with mock.patch('django.db.backends.utils.CursorWrapper.execute',
                        side_effect=OperationalError('db gone')):
            response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200,
                         'Liveness probe fails when the DB is down: it would '
                         'report the process as dead and trigger a restart loop.')

    def test_inquiry_json_endpoint_never_returns_html_on_error(self):
        """The polling JS calls r.json(); an HTML error body breaks the UI."""
        owner = landlord('net-json@example.com')
        h = house(owner, 'JSON House')
        room = Room.objects.create(boarding_house=h, room_type='S',
                                   monthly_rate=1000, capacity=1)
        s = student('net-json-s@example.com')
        inq = Inquiry.objects.create(student=s, room=room, message_text='x')
        self.client.force_login(s)
        response = self.client.get(f'/inquiries/{inq.pk}/messages/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response['Content-Type'])
        stranger = student('net-json-x@example.com')
        self.client.force_login(stranger)
        denied = self.client.get(f'/inquiries/{inq.pk}/messages/')
        self.assertEqual(denied.status_code, 403)
        self.assertIn('application/json', denied['Content-Type'],
                      'Unauthorised poll returns HTML, which crashes the '
                      'inquiry thread polling code.')


# --------------------------------------------------------------------------
# ROOM UPLOAD CAP -- HIGH VOLUME
# --------------------------------------------------------------------------
class RoomPhotoUploadCapTests(TestCase):
    """RoomForm.photo is a plain form field, not a model field on Room.

    Django's ModelForm validation never touches it, so the RoomPhoto model
    validators (validate_image_size) never ran on this write path and an
    oversized image was accepted all the way to disk. These tests lock the
    cap in place so it cannot silently regress.
    """

    def _oversized_jpeg(self):
        import io as _io
        from PIL import Image as _Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = _io.BytesIO()
        _Image.new('RGB', (10, 10), (120, 30, 30)).save(buf, 'JPEG')
        upload = SimpleUploadedFile('big.jpg', buf.getvalue(),
                                    content_type='image/jpeg')
        # Valid image bytes, but reported as 17 MB -- Pillow never opens it.
        upload.size = 17 * 1024 * 1024
        return upload

    def test_oversized_room_photo_is_rejected(self):
        from .forms import RoomForm
        form = RoomForm(
            {'room_type': 'Studio', 'monthly_rate': 1000, 'capacity': 1},
            {'photo': self._oversized_jpeg()},
        )
        self.assertFalse(form.is_valid(), '17 MB room photo was accepted.')
        self.assertIn('photo', form.errors)

    def test_small_room_photo_still_accepted(self):
        import io as _io
        from PIL import Image as _Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .forms import RoomForm
        buf = _io.BytesIO()
        _Image.new('RGB', (10, 10), (120, 30, 30)).save(buf, 'JPEG')
        form = RoomForm(
            {'room_type': 'Studio', 'monthly_rate': 1000, 'capacity': 1},
            {'photo': SimpleUploadedFile('ok.jpg', buf.getvalue(),
                                         content_type='image/jpeg')},
        )
        self.assertTrue(form.is_valid(), dict(form.errors))

    def test_room_photo_is_optional(self):
        from .forms import RoomForm
        form = RoomForm(
            {'room_type': 'Studio', 'monthly_rate': 1000, 'capacity': 1}, {},
        )
        self.assertTrue(form.is_valid(), dict(form.errors))

    def test_room_create_endpoint_is_rate_limited(self):
        """Flooding room-create must stop creating rooms.

        Asserted on the ROW COUNT, not the status code: the accepted path and
        the throttled path both redirect (302), so a status-only test passes
        even when the throttle never fires.
        """
        import io as _io
        from PIL import Image as _Image
        from django.core.cache import cache
        from django.core.files.uploadedfile import SimpleUploadedFile
        cache.clear()
        owner = landlord('roomcap-l@example.com')
        h = house(owner, 'Throttle House')
        buf = _io.BytesIO()
        _Image.new('RGB', (8, 8), (10, 120, 60)).save(buf, 'JPEG')
        raw = buf.getvalue()
        self.client.force_login(owner)
        url = f'/landlords/boarding-houses/{h.pk}/rooms/add/'
        data = {'room_type': 'Studio', 'monthly_rate': 1500, 'capacity': 1}

        before = Room.objects.filter(boarding_house=h).count()
        created = []
        for i in range(26):
            self.client.post(url, {**data, 'photo': SimpleUploadedFile(
                f'r{i}.jpg', raw, content_type='image/jpeg')})
            after = Room.objects.filter(boarding_house=h).count()
            created.append(after > before)
            before = after
        cache.clear()

        self.assertEqual(created[:20], [True] * 20,
                         'the first 20 uploads in a minute should be accepted')
        self.assertEqual(created[20:], [False] * 6,
                         'uploads past the per-minute cap must be shed')


# --------------------------------------------------------------------------
# PAGE IDENTITY -- WRONG OUTPUT
# --------------------------------------------------------------------------
class RoomFormPageTitleTests(TestCase):
    """room_form.html renders {{ title }}, but room_create/room_edit used to
    pass no title, so both pages shipped a literally empty <title></title>.
    Django renders undefined variables as empty strings rather than raising,
    so this shipped silently.
    """

    def setUp(self):
        self.owner = landlord('roomtitle-l@example.com')
        self.h = house(self.owner, 'Title House')
        self.room = Room.objects.create(boarding_house=self.h,
                                        room_type='S', monthly_rate=1000,
                                        capacity=1)
        self.client.force_login(self.owner)

    def test_add_room_page_has_non_empty_title(self):
        r = self.client.get(f'/landlords/boarding-houses/{self.h.pk}/rooms/add/')
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertIn('<title>Add New Room</title>', content)
        self.assertNotIn('<title></title>', content)

    def test_edit_room_page_has_non_empty_title(self):
        r = self.client.get(f'/landlords/rooms/{self.room.pk}/edit/')
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertIn('<title>Edit Room</title>', content)
        self.assertNotIn('<title></title>', content)

    def test_room_form_pages_have_exactly_one_h1(self):
        for url in (f'/landlords/boarding-houses/{self.h.pk}/rooms/add/',
                    f'/landlords/rooms/{self.room.pk}/edit/'):
            content = self.client.get(url).content.decode()
            self.assertEqual(content.count('<h1'), 1,
                             f'{url} should have exactly one <h1>')


class PublicNameDisplayTests(TestCase):
    """Public pages used {{ user.get_full_name|default:user.username }}.

    Registration only ever collects full_name, so first_name/last_name are
    empty for every account and get_full_name() returns '' -- which meant the
    template silently fell back to the login handle. display_name reads the
    populated full_name column instead.
    """

    def setUp(self):
        self.owner = landlord('ident-l@example.com')
        self.owner.full_name = 'Elena Villaflor'
        self.owner.save()
        self.h = house(self.owner, 'Identity House')
        self.room = Room.objects.create(boarding_house=self.h, room_type='S',
                                        monthly_rate=1000, capacity=1)
        # user_profile is @login_required; a student is the audience that
        # matters here (students browse landlord cards before applying).
        self.client.force_login(student('ident-s@example.com'))

    def test_public_profile_shows_real_name_not_username(self):
        r = self.client.get(f'/users/{self.owner.pk}/')
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertIn('Elena Villaflor', content)
        self.assertNotIn('ident-l', content.split('<title>')[1].split('</title>')[0])

    def test_listing_owner_chip_shows_real_name(self):
        # /listings/<pk>/ is boarding_detail, so the pk is the HOUSE id, not
        # the room id -- passing a room pk 404s whenever ids diverge.
        r = self.client.get(f'/listings/{self.h.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Elena Villaflor', r.content.decode())

    def test_display_name_prefers_full_name(self):
        self.assertEqual(self.owner.display_name, 'Elena Villaflor')

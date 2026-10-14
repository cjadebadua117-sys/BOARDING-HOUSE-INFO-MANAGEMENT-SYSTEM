from django.test import TestCase

from .forms import StudentRegistrationForm
from .models import AdminActionLog, BoardingHouse, Booking, LandlordRating, Room, User


class StudentRegistrationFlowTests(TestCase):
    def test_registration_rejects_invalid_email_and_student_id(self):
        form = StudentRegistrationForm(data={
            'username': 'juan',
            'full_name': 'Juan dela Cruz',
            'email': 'not-an-email',
            'student_id': '24102731',
            'program': 'CIS',
            'password1': 'StrongPass123',
            'password2': 'StrongPass123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn('Student ID must be in the format 241-0273-1.', form.errors['student_id'])

    def test_duplicate_email_and_student_id_are_rejected(self):
        User.objects.create_user(
            email='existing@gmail.com',
            password='SecurePass123',
            role=User.Role.STUDENT,
            full_name='Existing Student',
            student_id='241-0273-1',
            username='existing@gmail.com',
        )

        form = StudentRegistrationForm(data={
            'username': 'another',
            'full_name': 'Another Student',
            'email': 'existing@gmail.com',
            'student_id': '241-0273-1',
            'program': 'CIS',
            'password1': 'StrongPass123',
            'password2': 'StrongPass123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('A student account with this email address already exists.', form.errors['email'])
        self.assertTrue(
            any('already exists' in err for err in form.errors.get('student_id', [])),
            f'Expected duplicate student ID error, got: {form.errors.get("student_id")}',
        )


class BrowsePageTests(TestCase):
    def test_browse_page_renders_filter_labels_and_barangay_filter(self):
        house = BoardingHouse.objects.create(
            owner=User.objects.create_user(email='owner@gmail.com', password='OwnerPass123', role=User.Role.LANDLORD, full_name='Owner', username='owner@gmail.com'),
            name='Warm Home',
            address='123 Main Street',
            barangay='Naguilian',
            status=BoardingHouse.Status.APPROVED,
            description='A cozy place for students',
        )
        Room.objects.create(boarding_house=house, room_type='Single', monthly_rate=2500, capacity=1, is_available=True)

        response = self.client.get('/listings/?barangay=Naguilian')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Price min')
        self.assertContains(response, 'Price max')
        self.assertContains(response, 'Room type')
        self.assertContains(response, 'Barangay')
        self.assertContains(response, 'Amenities')


class ListingPriceValidationTests(TestCase):
    """Listing forms must reject non-positive prices and invalid capacities."""

    def setUp(self):
        self.landlord = User.objects.create_user(
            email='landlord@gmail.com',
            password='LandlordPass123',
            role=User.Role.LANDLORD,
            full_name='Landlord',
            username='landlord@gmail.com',
        )

    def test_house_rejects_negative_price(self):
        from .forms import BoardingHouseForm
        form = BoardingHouseForm(data={
            'name': 'Cheap House',
            'address': 'Somewhere',
            'barangay': 'Sapilang',
            'price': '-9999',
            'gender_allowed': 'both',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('price', form.errors)

    def test_room_rejects_negative_rate_and_zero_capacity(self):
        from .forms import RoomForm
        house = BoardingHouse.objects.create(
            owner=self.landlord,
            name='Rate Test House',
            address='Somewhere',
            barangay='Sapilang',
            status=BoardingHouse.Status.APPROVED,
        )
        form = RoomForm(data={
            'room_type': 'Bedspace',
            'monthly_rate': '-500',
            'capacity': '0',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('monthly_rate', form.errors)
        self.assertIn('capacity', form.errors)


class LandlordRatingTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='student@gmail.com', email='student@gmail.com',
            password='StudentPass123', role=User.Role.STUDENT,
        )
        self.other_student = User.objects.create_user(
            username='other@gmail.com', email='other@gmail.com',
            password='OtherPass123', role=User.Role.STUDENT,
        )
        self.landlord = User.objects.create_user(
            username='landlord-rating@gmail.com', email='landlord-rating@gmail.com',
            password='LandlordPass123', role=User.Role.LANDLORD,
        )
        house = BoardingHouse.objects.create(
            owner=self.landlord, name='Rating House', address='Main Street',
            barangay='Sapilang', status=BoardingHouse.Status.APPROVED,
        )
        room = Room.objects.create(
            boarding_house=house, room_type='Single', monthly_rate=2500, capacity=1,
        )
        self.booking = Booking.objects.create(
            student=self.student, room=room, status=Booking.Status.CONFIRMED,
        )

    def test_student_with_confirmed_booking_can_rate_once(self):
        self.client.login(username='student@gmail.com', password='StudentPass123')
        response = self.client.post(
            f'/users/{self.landlord.pk}/rate/',
            {'rating': 5, 'comment': 'Helpful and responsive.'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/users/{self.landlord.pk}/')
        self.assertEqual(LandlordRating.objects.get().rating, 5)
        duplicate = self.client.post(
            f'/users/{self.landlord.pk}/rate/', {'rating': 4},
        )
        self.assertEqual(duplicate.status_code, 302)
        self.assertEqual(duplicate.url, f'/users/{self.landlord.pk}/')
        self.assertEqual(LandlordRating.objects.count(), 1)

    def test_student_without_confirmed_booking_cannot_rate(self):
        self.client.login(username='other@gmail.com', password='OtherPass123')
        response = self.client.post(
            f'/users/{self.landlord.pk}/rate/', {'rating': 5},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/users/{self.landlord.pk}/')
        self.assertFalse(LandlordRating.objects.exists())

    def test_landlord_cannot_submit_rating(self):
        self.client.login(username='landlord-rating@gmail.com', password='LandlordPass123')
        response = self.client.post(
            f'/users/{self.landlord.pk}/rate/', {'rating': 5},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(LandlordRating.objects.exists())


class RatingsPagesTests(TestCase):
    """Admin 'Ratings' overview and landlord 'My Ratings' pages."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin@gmail.com', email='admin@gmail.com',
            password='AdminPass123', role=User.Role.ADMIN,
        )
        self.student = User.objects.create_user(
            username='ratings-page-student@gmail.com', email='ratings-page-student@gmail.com',
            password='StudentPass123', role=User.Role.STUDENT,
            full_name='Rina Santos',
        )
        self.landlord = User.objects.create_user(
            username='ratings-page-landlord@gmail.com', email='ratings-page-landlord@gmail.com',
            password='LandlordPass123', role=User.Role.LANDLORD,
            full_name='Juan Dela Cruz',
        )
        self.other_landlord = User.objects.create_user(
            username='other-landlord@gmail.com', email='other-landlord@gmail.com',
            password='OtherLandlordPass123', role=User.Role.LANDLORD,
        )
        house = BoardingHouse.objects.create(
            owner=self.landlord, name='Ratings Page House', address='Main Street',
            barangay='Sapilang', status=BoardingHouse.Status.APPROVED,
        )
        room = Room.objects.create(
            boarding_house=house, room_type='Single', monthly_rate=2500, capacity=1,
        )
        self.booking = Booking.objects.create(
            student=self.student, room=room, status=Booking.Status.CONFIRMED,
        )
        LandlordRating.objects.create(
            student=self.student, landlord=self.landlord, booking=self.booking,
            rating=5, comment='Great place, kind landlord.',
        )
        LandlordRating.objects.create(
            student=self.student,
            landlord=self.other_landlord,
            booking=Booking.objects.create(
                student=self.student,
                room=Room.objects.create(
                    boarding_house=BoardingHouse.objects.create(
                        owner=self.other_landlord, name='Other House', address='Second Street',
                        barangay='Sapilang', status=BoardingHouse.Status.APPROVED,
                    ),
                    room_type='Double', monthly_rate=3500, capacity=2,
                ),
                status=Booking.Status.CONFIRMED,
            ),
            rating=3, comment='',
        )

    def test_admin_ratings_page_requires_admin(self):
        response = self.client.get('/admin/ratings/')
        self.assertEqual(response.status_code, 302)  # anonymous -> login
        self.client.login(username='ratings-page-landlord@gmail.com', password='LandlordPass123')
        response = self.client.get('/admin/ratings/')
        self.assertEqual(response.status_code, 302)  # landlord -> not allowed
        self.client.login(username='admin@gmail.com', password='AdminPass123')
        response = self.client.get('/admin/ratings/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ratings Page House')

    def test_admin_ratings_page_stats_and_filter(self):
        self.client.login(username='admin@gmail.com', password='AdminPass123')
        response = self.client.get('/admin/ratings/')
        self.assertEqual(response.context['rating_count'], 2)
        self.assertEqual(response.context['comment_count'], 1)
        self.assertEqual(response.context['distribution'][5], 1)
        self.assertEqual(response.context['distribution'][3], 1)
        filtered = self.client.get('/admin/ratings/?stars=5')
        self.assertEqual(len(filtered.context['ratings']), 1)
        searched = self.client.get('/admin/ratings/?search=rina')
        self.assertEqual(len(searched.context['ratings']), 2)  # same student rated both

    def test_landlord_my_ratings_page_requires_landlord(self):
        response = self.client.get('/landlords/ratings/')
        self.assertEqual(response.status_code, 302)  # anonymous -> login
        self.client.login(username='admin@gmail.com', password='AdminPass123')
        response = self.client.get('/landlords/ratings/')
        self.assertEqual(response.status_code, 302)  # admin -> not allowed
        self.client.login(username='ratings-page-landlord@gmail.com', password='LandlordPass123')
        response = self.client.get('/landlords/ratings/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rina Santos')
        self.assertNotContains(response, 'Other House')  # only own ratings

    def test_landlord_my_ratings_stats_and_filter(self):
        self.client.login(username='ratings-page-landlord@gmail.com', password='LandlordPass123')
        response = self.client.get('/landlords/ratings/')
        self.assertEqual(response.context['rating_count'], 1)
        self.assertEqual(response.context['average_rating'], 5)
        empty_filter = self.client.get('/landlords/ratings/?stars=1')
        self.assertEqual(len(empty_filter.context['ratings']), 0)
        self.assertContains(empty_filter, 'No 1-star ratings yet.')


class SecurityHardeningTests(TestCase):
    """Covers the instructor-requested hardening round."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email='root@gmail.com', password='RootPass123', role=User.Role.ADMIN,
            full_name='Root Admin', username='root@gmail.com', is_staff=True,
        )
        self.landlord = User.objects.create_user(
            email='landlord@gmail.com', password='LandlordPass123', role=User.Role.LANDLORD,
            full_name='Test Landlord', username='landlord@gmail.com',
        )
        self.student = User.objects.create_user(
            email='student@gmail.com', password='StudentPass123', role=User.Role.STUDENT,
            full_name='Test Student', username='student@gmail.com',
        )
        self.other_student = User.objects.create_user(
            email='other@gmail.com', password='StudentPass123', role=User.Role.STUDENT,
            full_name='Other Student', username='other@gmail.com',
        )

    def _login(self, user, password):
        self.client.login(username=user.username, password=password)

    def test_student_cannot_open_other_student_profile(self):
        """IDOR fix: student A gets 404 on student B's profile."""
        self._login(self.student, 'StudentPass123')
        response = self.client.get(f'/users/{self.other_student.pk}/')
        self.assertEqual(response.status_code, 404)

    def test_landlord_profile_is_viewable_and_own_profile_too(self):
        self._login(self.student, 'StudentPass123')
        self.assertEqual(self.client.get(f'/users/{self.landlord.pk}/').status_code, 200)
        self.assertEqual(self.client.get(f'/users/{self.student.pk}/').status_code, 200)

    def test_health_deep_check_requires_staff(self):
        self.assertEqual(self.client.get('/health/?deep=1').status_code, 404)
        self.assertEqual(self.client.get('/health/').status_code, 200)  # liveness stays public
        self._login(self.admin, 'RootPass123')
        self.assertIn(self.client.get('/health/?deep=1').status_code, (200, 503))

    def test_honeypot_sits_at_admin_root(self):
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Log in')
        probe = self.client.post('/admin/', {'username': 'boss', 'password': 'wrong'})
        self.assertEqual(probe.status_code, 200)
        self.assertTrue(AdminActionLog.objects.filter(action='honeypot_probe').exists())

    def test_account_lockout_after_15_failures(self):
        from django.core.cache import cache
        cache.clear()
        from core.views import _lockout_state, _record_login_failure
        request = type('R', (), {'POST': {'username': 'student@gmail.com'},
                                 'META': {'REMOTE_ADDR': '1.2.3.4'}})()
        for _ in range(15):
            _record_login_failure(request)
        locked, fails, until = _lockout_state(request)
        self.assertTrue(locked)
        self.assertGreaterEqual(fails, 15)
        self.assertIsNotNone(until)

    def test_security_headers_present(self):
        response = self.client.get('/accounts/login/')
        self.assertIn('Content-Security-Policy', response.headers)
        self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
        self.assertEqual(response.headers['Referrer-Policy'], 'strict-origin-when-cross-origin')
        self.assertIn('Permissions-Policy', response.headers)

    def test_admin_ip_allowlist_blocks_foreign_ip(self):
        from django.test import override_settings
        self._login(self.admin, 'RootPass123')
        with override_settings(ADMIN_IP_ALLOWLIST=['10.9.9.9']):
            response = self.client.get('/admin/dashboard/', REMOTE_ADDR='1.2.3.4')
            self.assertEqual(response.status_code, 404)

    def test_audit_log_written_for_profile_update(self):
        from django.core.cache import cache
        cache.clear()
        self._login(self.student, 'StudentPass123')
        response = self.client.post('/profile/edit/', data={
            'first_name': 'Updated', 'last_name': 'Student',
        })
        self.assertEqual(response.status_code, 302)  # redirect back to profile
        self.assertTrue(AdminActionLog.objects.filter(action='profile_updated', actor=self.student).exists())

    def test_inquiry_subject_is_length_clamped(self):
        """A 100KB 'subject' cannot reach the database (model max_length 255)."""
        from django.core.cache import cache
        cache.clear()
        house = BoardingHouse.objects.create(
            owner=self.landlord, name='Clamp House', address='1 Road',
            barangay='Naguilian', status=BoardingHouse.Status.APPROVED,
        )
        room = Room.objects.create(
            boarding_house=house, room_type='Single', monthly_rate=2000,
            capacity=2, is_available=True,
        )
        self._login(self.student, 'StudentPass123')
        response = self.client.post(f'/inquiries/send/{room.pk}/', data={
            'subject': 'S' * 100_000,
            'message_text': 'Hello, is this room available?',
        })
        self.assertEqual(response.status_code, 302)
        inquiry = self.student.inquiries.order_by('-id').first()
        self.assertIsNotNone(inquiry)
        self.assertLessEqual(len(inquiry.subject), 255)


class AllPagesSmokeTest(TestCase):
    """Regression net for 'broken pages': every route renders for the right
    role with a populated database, no 500s or template errors, and all
    {% static %} assets referenced by rendered pages actually resolve."""

    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user(
            email='s@example.com', password='SmokePass123',
            role=User.Role.STUDENT, full_name='Smoke Student', username='s@example.com',
        )
        cls.landlord = User.objects.create_user(
            email='l@example.com', password='SmokePass123',
            role=User.Role.LANDLORD, full_name='Smoke Landlord', username='l@example.com',
        )
        cls.admin = User.objects.create_user(
            email='a@example.com', password='SmokePass123',
            role=User.Role.ADMIN, full_name='Smoke Admin', username='a@example.com',
        )
        cls.house = BoardingHouse.objects.create(
            owner=cls.landlord, name='Smoke House', address='1 Test Road',
            barangay='Naguilian', status=BoardingHouse.Status.APPROVED,
        )
        cls.room = Room.objects.create(
            boarding_house=cls.house, room_type='Single', monthly_rate=2000,
            capacity=2, is_available=True,
        )

    def _assert_renders(self, url, client=None):
        client = client or self.client
        response = client.get(url)
        self.assertEqual(
            response.status_code, 200,
            f'GET {url} returned {response.status_code} (expected 200)',
        )
        return response

    def _assert_assets_resolve(self, response, url):
        """Extract {% static %}-produced URLs from the HTML and fetch each one."""
        html = response.content.decode('utf-8')
        import re
        urls = set(re.findall(r'(?:src|href)="(/static/[^"]+)"', html))
        for asset_url in sorted(urls):
            asset_response = self.client.get(asset_url)
            self.assertEqual(
                asset_response.status_code, 200,
                f'Page {url} references missing static asset: {asset_url}',
            )

    def test_public_pages_render(self):
        for url in [
            '/', '/listings/', '/listings/{}/'.format(self.house.pk),
            '/listing/{}/'.format(self.house.pk), '/search/',
            '/accounts/login/', '/students/login/', '/landlords/login/',
            '/students/register/', '/admin/login/', '/password-reset/',
            '/health/',
        ]:
            with self.subTest(url=url):
                self._assert_renders(url)

    def test_removed_chat_route_redirects_home(self):
        """Chat was removed; the old /chat/ bookmark must redirect, not 404."""
        response = self.client.get('/chat/')
        self.assertEqual(response.status_code, 302)

    def test_student_pages_render(self):
        self.client.force_login(self.student)
        for url in [
            '/students/dashboard/', '/listings/', '/listings/{}/'.format(self.house.pk),
            '/students/inquiries/', '/students/bookings/', '/profile/', '/profile/edit/',
            '/profile/change-password/', '/search/',
            '/users/{}/'.format(self.landlord.pk), '/users/{}/'.format(self.student.pk),
        ]:
            with self.subTest(url=url):
                response = self._assert_renders(url)
                self._assert_assets_resolve(response, url)

    def test_landlord_pages_render(self):
        self.client.force_login(self.landlord)
        h = self.house.pk
        for url in [
            '/landlords/dashboard/', '/landlords/boarding-houses/',
            '/landlords/boarding-houses/{}/'.format(h),
            '/landlords/boarding-houses/{}/edit/'.format(h),
            '/landlords/boarding-houses/{}/rooms/add/'.format(h),
            '/landlords/inquiries/', '/landlords/bookings/', '/landlords/ratings/',
            '/profile/', '/profile/edit/',
            '/users/{}/'.format(self.landlord.pk),  # own profile (role badge regression)
        ]:
            with self.subTest(url=url):
                response = self._assert_renders(url)
                self._assert_assets_resolve(response, url)

    def test_landlord_cannot_open_another_students_private_profile(self):
        """IDOR guard: landlords may open landlord profiles and their own —
        never a student's private data."""
        self.client.force_login(self.landlord)
        response = self.client.get('/users/{}/'.format(self.student.pk))
        self.assertEqual(response.status_code, 404)

    def test_admin_pages_render(self):
        self.client.force_login(self.admin)
        for url in [
            '/admin/dashboard/', '/admin/analytics/', '/admin/ratings/',
            '/admin/landlords/', '/admin/landlords/{}/'.format(self.landlord.pk),
            '/admin/landlords/{}/edit/'.format(self.landlord.pk), '/admin/students/',
            '/admin/landlords/add/', '/admin/listings/pending/', '/admin/barangays/',
            '/admin/settings/', '/admin/reports/', '/profile/',
        ]:
            with self.subTest(url=url):
                self._assert_renders(url)

    def test_landlord_own_profile_shows_landlord_role_badge(self):
        """Regression: user_profile rendered 'Student' for a landlord viewing
        their own profile because viewed_is_landlord was hardcoded False."""
        self.client.force_login(self.landlord)
        response = self.client.get('/users/{}/'.format(self.landlord.pk))
        self.assertContains(response, '>Landlord</span>')

    def test_profile_page_default_avatar_asset_exists(self):
        """Regression: profile.html referenced images/default-avatar.png which
        never existed — a 404 asset in dev and a 500 in production."""
        from django.contrib.staticfiles import finders
        self.assertIsNotNone(finders.find('core/images/default-avatar.png'))
        self.client.force_login(self.student)
        response = self.client.get('/profile/')
        self.assertContains(response, 'core/images/default-avatar.png')
        self._assert_assets_resolve(response, '/profile/')

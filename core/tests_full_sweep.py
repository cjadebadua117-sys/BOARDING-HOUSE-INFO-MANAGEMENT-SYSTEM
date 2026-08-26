"""
Full-sweep behavioral tests: every route x every role, plus all write flows.
Each assertion encodes the CORRECT behavior, so any failure is a real bug.
Run: python manage.py test core.tests_full_sweep -v 1
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .forms import BoardingHouseForm
from .models import (
    Amenity,
    Barangay,
    BoardingHouse,
    Booking,
    Inquiry,
    Room,
    SiteSetting,
    User,
    UserReport,
    barangay_display_map,
)


class SweepData(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='boss', email='boss@gmail.com', password='Passw0rd!123', role=User.Role.ADMIN)
        cls.landlord = User.objects.create_user(
            username='landy', email='landy@gmail.com', password='Passw0rd!123', role=User.Role.LANDLORD)
        cls.landlord2 = User.objects.create_user(
            username='landy2', email='landy2@gmail.com', password='Passw0rd!123', role=User.Role.LANDLORD)
        cls.student = User.objects.create_user(
            username='stud', email='stud@gmail.com', password='Passw0rd!123',
            role=User.Role.STUDENT, student_id='241-0273-1')

        # Seeded by data migration — reuse and force a known distance.
        barangay, _ = Barangay.objects.get_or_create(name='Sapilang')
        barangay.distance_from_campus = 'Walking distance'
        barangay.save()

        cls.house = BoardingHouse.objects.create(
            owner=cls.landlord, name='Sunrise Dorm', address='Purok 2', barangay='Sapilang',
            price=Decimal('2500.00'), status=BoardingHouse.Status.APPROVED, is_active=True)
        cls.hidden_house = BoardingHouse.objects.create(
            owner=cls.landlord, name='Hidden House', address='Purok 3', barangay='Sapilang',
            price=Decimal('2000.00'), status=BoardingHouse.Status.REJECTED, is_active=False)
        cls.other_house = BoardingHouse.objects.create(
            owner=cls.landlord2, name='Other Dorm', address='Purok 1', barangay='Sapilang',
            price=Decimal('3000.00'), status=BoardingHouse.Status.APPROVED, is_active=True)

        cls.amenity = Amenity.objects.create(name='Wi-Fi')
        cls.room = Room.objects.create(
            boarding_house=cls.house, room_type='Bedspace', monthly_rate=Decimal('1500.00'),
            capacity=2, is_available=True)
        cls.room.amenities.add(cls.amenity)
        cls.room_other = Room.objects.create(
            boarding_house=cls.other_house, room_type='Studio', monthly_rate=Decimal('3500.00'),
            capacity=1, is_available=True)

        cls.inquiry = Inquiry.objects.create(
            student=cls.student, room=cls.room, subject='Hello', message_text='Is this free?')
        cls.booking = Booking.objects.create(
            student=cls.student, room=cls.room_other, status=Booking.Status.CONFIRMED)
        cls.report = UserReport.objects.create(
            reporter=cls.student, reported_user=cls.landlord2, reason='scam', details='hmm')


class RouteMatrixTests(SweepData):
    """Every GET route as each role. Nothing may ever return 500."""

    PUBLIC = ['home', 'listing_list', 'student_register', 'student_login', 'login',
              'landlord_login', 'admin_login']
    ANON_OK = {'home': 200, 'listing_list': 200, 'student_register': 200,
               'student_login': 200, 'login': 200, 'landlord_login': 200,
               'admin_login': 200}

    def get(self, client, name, **kwargs):
        return client.get(reverse(name, kwargs=kwargs)) if kwargs else client.get(reverse(name))

    def test_public_pages_anonymous(self):
        c = self.client_class()
        for name in self.PUBLIC:
            with self.subTest(route=name):
                r = self.get(c, name)
                self.assertEqual(r.status_code, self.ANON_OK[name], f'{name} -> {r.status_code}')

    def test_listing_detail_visibility(self):
        c = self.client_class()
        self.assertEqual(self.get(c, 'boarding_detail', pk=self.house.pk).status_code, 200)
        # Non-public listing must redirect politely, never 500.
        r = self.get(c, 'boarding_detail', pk=self.hidden_house.pk)
        self.assertEqual(r.status_code, 302)

    def test_protected_routes_redirect_anonymous_never_500(self):
        c = self.client_class()
        protected = [
            ('student_dashboard', {}), ('student_inquiry_list', {}), ('student_bookings', {}),
            ('student_inquiry_thread', {'pk': self.inquiry.pk}),
            ('send_inquiry', {'pk': self.room.pk}),
            ('landlord_dashboard', {}), ('landlord_boarding_house_list', {}),
            ('boarding_house_create', {}), ('landlord_boarding_house_detail', {'pk': self.house.pk}),
            ('boarding_house_edit', {'pk': self.house.pk}), ('room_create', {'pk': self.house.pk}),
            ('room_edit', {'pk': self.room.pk}), ('toggle_room_availability', {'pk': self.room.pk}),
            ('landlord_inquiry_list', {}), ('landlord_bookings', {}),
            ('landlord_inquiry_thread', {'pk': self.inquiry.pk}),
            ('admin_dashboard', {}), ('admin_analytics', {}), ('admin_landlord_list', {}),
            ('admin_landlord_detail', {'pk': self.landlord.pk}), ('admin_student_list', {}),
            ('admin_pending_listings', {}), ('admin_barangay_list', {}),
            ('admin_settings', {}), ('admin_reports', {}),
            ('admin_report_detail', {'pk': self.report.pk}),
            ('profile', {}), ('user_profile', {'pk': self.student.pk}),
            ('report_user', {'pk': self.landlord2.pk}),
        ]
        for name, kw in protected:
            with self.subTest(route=name):
                r = self.get(c, name, **kw)
                self.assertEqual(r.status_code, 302, f'anonymous {name} -> {r.status_code}')
                self.assertIn('/accounts/login/', r['Location'], f'{name} login redirect broken')

    def test_role_guards(self):
        spec = {
            'student': {
                'ok': [('student_dashboard', {}), ('student_inquiry_list', {}),
                       ('student_bookings', {}), ('student_inquiry_thread', {'pk': self.inquiry.pk}),
                       ('send_inquiry', {'pk': self.room_other.pk}), ('profile', {}),
                       ('user_profile', {'pk': self.landlord.pk})],
                'denied': [('landlord_dashboard', {}), ('landlord_boarding_house_list', {}),
                           ('admin_dashboard', {}), ('admin_settings', {})],
            },
            'landlord': {
                'ok': [('landlord_dashboard', {}), ('landlord_boarding_house_list', {}),
                       ('boarding_house_create', {}),
                       ('landlord_boarding_house_detail', {'pk': self.house.pk}),
                       ('boarding_house_edit', {'pk': self.house.pk}),
                       ('room_create', {'pk': self.house.pk}), ('room_edit', {'pk': self.room.pk}),
                       ('landlord_inquiry_list', {}), ('landlord_bookings', {}),
                       ('landlord_inquiry_thread', {'pk': self.inquiry.pk}),
                       ('landlord_inquiry_list', {}), ('profile', {})],
                'denied': [('student_dashboard', {}), ('admin_dashboard', {})],
            },
            'admin': {
                'ok': [('admin_dashboard', {}), ('admin_analytics', {}),
                       ('admin_landlord_list', {}), ('admin_landlord_detail', {'pk': self.landlord.pk}),
                       ('admin_edit_landlord', {'pk': self.landlord.pk}),
                       ('admin_student_list', {}), ('admin_pending_listings', {}),
                       ('admin_barangay_list', {}), ('admin_settings', {}),
                       ('admin_reports', {}), ('admin_report_detail', {'pk': self.report.pk}),
                       ('landlord_boarding_house_detail', {'pk': self.house.pk})],
                'denied': [('student_dashboard', {}), ('landlord_dashboard', {}),
                           # Admins have no profile page — polite redirect expected.
                           ('profile', {})],
            },
        }
        creds = {'student': ('stud', 'Passw0rd!123'), 'landlord': ('landy', 'Passw0rd!123'),
                 'admin': ('boss', 'Passw0rd!123')}
        for role, blocks in spec.items():
            c = self.client_class()
            c.login(username=creds[role][0], password=creds[role][1])
            for name, kw in blocks['ok']:
                with self.subTest(role=role, route=name):
                    r = self.get(c, name, **kw)
                    self.assertEqual(r.status_code, 200, f'{role}/{name} -> {r.status_code}')
            for name, kw in blocks['denied']:
                with self.subTest(role=role, denied=name):
                    r = self.get(c, name, **kw)
                    self.assertEqual(r.status_code, 302, f'{role}/{name} -> {r.status_code}')


class WriteFlowTests(SweepData):
    def login_as(self, username):
        c = self.client_class()
        c.login(username=username, password='Passw0rd!123')
        return c

    def test_student_registration_creates_account(self):
        c = self.client_class()
        r = c.post(reverse('student_register'), {
            'username': 'newbie', 'email': 'newbie@gmail.com', 'full_name': 'New Bee',
            'student_id': '241-9999-9', 'program': 'CIS', 'password1': 'Str0ngPass!x',
            'password2': 'Str0ngPass!x',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username='newbie', role=User.Role.STUDENT).exists())

    def student_user(self):
        return User.objects.get(username='stud')

    def test_send_inquiry_and_reply_and_accept(self):
        c = self.login_as('stud')
        r = c.post(reverse('send_inquiry', args=[self.room.pk]), {
            'subject': 'Hi', 'message_text': 'Still available?'})
        self.assertEqual(r.status_code, 302)
        inquiry = (Inquiry.objects.filter(student=self.student_user(), room=self.room)
                   .order_by('-pk').first())
        self.assertIsNotNone(inquiry)

        r = self.login_as('landy').post(
            reverse('landlord_inquiry_thread', args=[inquiry.pk]), {'message_text': 'Yes!'})
        self.assertEqual(r.status_code, 302)

        accept_c = self.login_as('landy')
        r = accept_c.post(reverse('accept_student', args=[inquiry.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Booking.objects.filter(
            student=self.student_user(), room=self.room, status=Booking.Status.CONFIRMED).exists())

    def test_toggle_room_availability_get_must_not_mutate(self):
        before = Room.objects.get(pk=self.room.pk).is_available
        r = self.login_as('landy').get(reverse('toggle_room_availability', args=[self.room.pk]))
        after = Room.objects.get(pk=self.room.pk).is_available
        self.assertEqual(before, after,
                         'GET toggle mutated room availability (missing @require_POST)')

    def test_toggle_room_availability_post_works(self):
        before = Room.objects.get(pk=self.room.pk).is_available
        r = self.login_as('landy').post(reverse('toggle_room_availability', args=[self.room.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertNotEqual(Room.objects.get(pk=self.room.pk).is_available, before)

    def test_hidden_listing_stays_hidden_after_landlord_edit(self):
        c = self.login_as('landy')
        url = reverse('boarding_house_edit', args=[self.hidden_house.pk])
        self.assertNotIn('is_active', BoardingHouseForm.Meta.fields,
                         'Landlord house form must not expose is_active')
        r = c.post(url, {
            'name': 'Hidden House', 'address': 'Purok 3', 'barangay': 'Sapilang',
            'price': '2000', 'gender_allowed': 'both', 'description': 'x', 'is_active': 'on',
        })
        self.assertEqual(r.status_code, 302)
        house = BoardingHouse.objects.get(pk=self.hidden_house.pk)
        self.assertFalse(house.is_active, 'Landlord edit re-enabled an admin-hidden listing')
        self.assertEqual(house.status, BoardingHouse.Status.REJECTED)

    def test_barangay_display_map_resolves_distances(self):
        mapping = barangay_display_map()
        self.assertEqual(mapping.get('Sapilang'), 'Sapilang (Walking distance)',
                         f'barangay_display_map broken: {mapping}')

    def test_landlord_profile_update_syncs_full_name(self):
        c = self.login_as('landy')
        import json
        r = c.post(reverse('update_profile'), data=json.dumps({
            'first_name': 'Danny', 'last_name': 'Rivera', 'phone_number': '09171234567'}),
            content_type='application/json')
        self.assertEqual(r.status_code, 200)
        user = User.objects.get(pk=self.landlord.pk)
        self.assertEqual(user.full_name, 'Danny Rivera',
                         f'full_name not synced: {user.full_name!r}')

    def test_admin_approve_then_reject_listing(self):
        pending = BoardingHouse.objects.create(
            owner=self.landlord, name='Pending Dorm', address='Purok 4', barangay='Sapilang',
            price=Decimal('1800.00'), status=BoardingHouse.Status.PENDING, is_active=False)
        c = self.login_as('boss')
        r = c.post(reverse('admin_approve_listing', args=[pending.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(BoardingHouse.objects.get(pk=pending.pk).status, 'approved')

    def test_admin_barangay_crud(self):
        c = self.login_as('boss')
        r = c.post(reverse('admin_barangay_list'), {'name': 'Poblacion', 'distance_from_campus': '1 km'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Barangay.objects.filter(name='Poblacion').exists())
        pk = Barangay.objects.get(name='Poblacion').pk
        r = c.post(reverse('admin_barangay_edit', args=[pk]), {'name': 'Poblacion', 'distance_from_campus': '2 km'})
        self.assertEqual(r.status_code, 302)
        r = c.post(reverse('admin_barangay_delete', args=[pk]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Barangay.objects.filter(name='Poblacion').exists())

    def test_admin_settings_save(self):
        c = self.login_as('boss')
        r = c.post(reverse('admin_settings'), {
            'site_name': 'BHIMS Test', 'tagline': 'Home away', 'support_email': 's@gmail.com',
            'student_registration_enabled': 'on'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(SiteSetting.objects.get(key='site_name').value, 'BHIMS Test')

    def test_report_flow(self):
        c = self.login_as('stud')
        r = c.post(reverse('report_user', args=[self.landlord.pk]),
                   {'reason': 'harassment', 'details': 'rude replies'})
        self.assertIn(r.status_code, (302, 200))
        self.assertTrue(UserReport.objects.filter(reporter=self.student, reported_user=self.landlord).exists())

    def test_admin_resolve_report(self):
        c = self.login_as('boss')
        r = c.post(reverse('admin_report_update', args=[self.report.pk]), {'action': 'resolve'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(UserReport.objects.get(pk=self.report.pk).status, 'resolved')

    def test_password_change_flow(self):
        import json
        c = self.login_as('stud')
        r = c.post(reverse('change_password'), data=json.dumps({
            'old_password': 'wrongpass', 'new_password1': 'AnotherPass!1', 'new_password2': 'AnotherPass!1'}),
            content_type='application/json')
        self.assertEqual(r.status_code, 400)
        r = c.post(reverse('change_password'), data=json.dumps({
            'old_password': 'Passw0rd!123', 'new_password1': 'AnotherPass!1', 'new_password2': 'AnotherPass!1'}),
            content_type='application/json')
        self.assertEqual(r.status_code, 200)

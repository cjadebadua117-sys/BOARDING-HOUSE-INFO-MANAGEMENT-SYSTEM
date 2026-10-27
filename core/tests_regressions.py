"""Regression tests for the defects found while preparing the final project.

Each class exists because a specific defect was reproduced first; the docstring
says what the defect was, so a future change that reintroduces it fails here
with an explanation instead of silently shipping.

Reported in .audit/AUDIT_REPORT.md (H1, H3, M1, M2, M3) plus two notes from the
same pass (closed-thread messaging, the accept message outside the transaction).
"""

import json
import pathlib
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Amenity,
    Barangay,
    BoardingHouse,
    Booking,
    Inquiry,
    InquiryMessage,
    LandlordRating,
    Room,
    SiteSetting,
    User,
)


def make_user(email, role, password='StrongPass123'):
    return User.objects.create_user(
        username=email, email=email, password=password, role=role,
    )


def make_house(landlord, name, status=BoardingHouse.Status.APPROVED, barangay='Sapilang'):
    house = BoardingHouse.objects.create(
        owner=landlord, name=name, address='Main Street', barangay=barangay,
        status=status,
    )
    return house


def make_room(house, room_type='Single', monthly_rate=2500, capacity=1):
    return Room.objects.create(
        boarding_house=house, room_type=room_type,
        monthly_rate=monthly_rate, capacity=capacity,
    )


class SearchResultsCountTests(TestCase):
    """H3: `listings` is a Page, so `listings.count` rendered as blank and the
    heading read "Result Found" on the search page."""

    def setUp(self):
        self.landlord = make_user('search-landlord@gmail.com', User.Role.LANDLORD)
        for i in range(2):
            house = make_house(self.landlord, f'Search House {i}')
            make_room(house)

    def test_search_heading_shows_the_real_count(self):
        response = self.client.get('/search/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2 Results Found')
        self.assertNotContains(response, ' Result Found')

    def test_single_result_is_not_pluralised(self):
        BoardingHouse.objects.filter(name='Search House 1').delete()
        response = self.client.get('/search/')
        self.assertContains(response, '1 Result Found')


class LandlordStudentProfileAccessTests(TestCase):
    """M1: the inquiry thread links the student's name and avatar, but
    user_profile 404'd for the landlord — the only broken internal link on the
    site, and it sat in the middle of the system's main flow."""

    def setUp(self):
        self.landlord = make_user('profile-landlord@gmail.com', User.Role.LANDLORD)
        self.other_landlord = make_user('profile-other-landlord@gmail.com', User.Role.LANDLORD)
        self.student = make_user('profile-student@gmail.com', User.Role.STUDENT)
        self.other_student = make_user('profile-other-student@gmail.com', User.Role.STUDENT)

        self.house = make_house(self.landlord, 'Profile House')
        make_house(self.other_landlord, 'Unrelated House')
        self.room = make_room(self.house)
        self.inquiry = Inquiry.objects.create(
            student=self.student, room=self.room, message_text='Is this room free?',
        )

    def test_landlord_can_open_the_student_they_are_negotiating_with(self):
        self.client.login(username='profile-landlord@gmail.com', password='StrongPass123')
        response = self.client.get(f'/users/{self.student.pk}/')
        self.assertEqual(response.status_code, 200)

    def test_unrelated_landlord_still_gets_404(self):
        self.client.login(username='profile-other-landlord@gmail.com', password='StrongPass123')
        response = self.client.get(f'/users/{self.student.pk}/')
        self.assertEqual(response.status_code, 404)

    def test_a_booking_also_grants_access(self):
        Inquiry.objects.all().delete()
        Booking.objects.create(
            student=self.student, room=self.room, status=Booking.Status.CONFIRMED,
        )
        self.client.login(username='profile-landlord@gmail.com', password='StrongPass123')
        self.assertEqual(self.client.get(f'/users/{self.student.pk}/').status_code, 200)

    def test_student_to_student_privacy_is_unchanged(self):
        self.client.login(username='profile-other-student@gmail.com', password='StrongPass123')
        response = self.client.get(f'/users/{self.student.pk}/')
        self.assertEqual(response.status_code, 404)


class RejectedInquiryGetSafetyTests(TestCase):
    """H1: a plain GET deleted a REJECTED inquiry and every message in it —
    reproducible by revisiting an old link, and reachable by any prefetch or
    crawler. Replacing the thread is now POST-only and explicit."""

    def setUp(self):
        self.landlord = make_user('reject-landlord@gmail.com', User.Role.LANDLORD)
        self.student = make_user('reject-student@gmail.com', User.Role.STUDENT)
        self.house = make_house(self.landlord, 'Reject House')
        self.room = make_room(self.house)
        self.inquiry = Inquiry.objects.create(
            student=self.student, room=self.room, status=Inquiry.Status.REJECTED,
            message_text='Original message',
        )
        InquiryMessage.objects.create(
            inquiry=self.inquiry, sender=self.student, message_text='Any updates?',
        )
        self.client.login(username='reject-student@gmail.com', password='StrongPass123')
        self.url = reverse('send_inquiry', args=[self.room.pk])

    def test_get_shows_the_form_and_deletes_nothing(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Inquiry.objects.filter(pk=self.inquiry.pk).exists())
        self.assertEqual(InquiryMessage.objects.filter(inquiry=self.inquiry).count(), 1)

    def test_post_without_confirmation_keeps_the_thread(self):
        response = self.client.post(self.url, {'message_text': 'Trying again'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inquiry.objects.filter(room=self.room, student=self.student).count(), 1)
        self.assertTrue(Inquiry.objects.filter(pk=self.inquiry.pk).exists())

    def test_confirmed_post_replaces_the_declined_thread(self):
        response = self.client.post(
            self.url, {'message_text': 'Trying again', 'reapply': '1'},
        )
        self.assertEqual(response.status_code, 302)
        inquiries = Inquiry.objects.filter(room=self.room, student=self.student)
        self.assertEqual(inquiries.count(), 1)
        fresh = inquiries.get()
        self.assertNotEqual(fresh.pk, self.inquiry.pk)
        self.assertEqual(fresh.message_text, 'Trying again')
        self.assertEqual(fresh.status, Inquiry.Status.PENDING)
        self.assertFalse(InquiryMessage.objects.filter(inquiry=self.inquiry).exists())


class RatingBookingDeterminismTests(TestCase):
    """M2: the rating was attached to `Booking.objects.filter(...).first()` with
    no ordering, so with two confirmed rooms under one landlord the rating
    could land on a different property each time."""

    def setUp(self):
        self.landlord = make_user('rating-landlord@gmail.com', User.Role.LANDLORD)
        self.student = make_user('rating-student@gmail.com', User.Role.STUDENT)
        self.first_house = make_house(self.landlord, 'First House')
        self.second_house = make_house(self.landlord, 'Second House')
        self.first_room = make_room(self.first_house, capacity=2)
        self.second_room = make_room(self.second_house, capacity=2)
        self.older_booking = Booking.objects.create(
            student=self.student, room=self.first_room, status=Booking.Status.CONFIRMED,
            confirmed_at=timezone.now() - timedelta(days=30),
        )
        self.newer_booking = Booking.objects.create(
            student=self.student, room=self.second_room, status=Booking.Status.CONFIRMED,
            confirmed_at=timezone.now(),
        )

    def test_rating_attaches_to_the_earliest_confirmed_booking(self):
        self.client.login(username='rating-student@gmail.com', password='StrongPass123')
        self.client.post(f'/users/{self.landlord.pk}/rate/', {'rating': 5})
        rating = LandlordRating.objects.get()
        self.assertEqual(rating.booking_id, self.older_booking.pk)


class SearchPaginationOrderTests(TestCase):
    """M3: search paginated an unordered queryset, so a visitor paging through
    results could see one listing twice and miss another."""

    def setUp(self):
        self.landlord = make_user('page-landlord@gmail.com', User.Role.LANDLORD)
        self.houses = []
        for i in range(15):
            house = make_house(self.landlord, f'Paged House {i:02d}')
            make_room(house)
            self.houses.append(house)

    def test_pages_do_not_overlap_and_come_in_a_stable_order(self):
        first = self.client.get('/search/')
        second = self.client.get('/search/?page=2')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        page1 = [h.pk for h in first.context['listings']]
        page2 = [h.pk for h in second.context['listings']]
        self.assertEqual(len(page1), 12)
        self.assertEqual(len(page2), 3)
        self.assertEqual(set(page1) & set(page2), set(), 'a house appeared on two pages')
        self.assertEqual(set(page1) | set(page2), {h.pk for h in self.houses})

        repeat = self.client.get('/search/')
        self.assertEqual([h.pk for h in repeat.context['listings']], page1)


class TemplateCommentSyntaxTests(TestCase):
    """Django strips `{# ... #}` only when it opens and closes on the SAME line.
    A multi-line one is printed verbatim into the page — it happened twice while
    this project was being prepared (both times it dumped template text and
    example markup into the visitor's view, and the browser-side integrity test
    only caught the page it happened to visit). This scans every template in the
    repository instead.
    """

    def test_no_multiline_hash_comment_in_any_template(self):
        template_dir = pathlib.Path(settings.BASE_DIR) / 'core' / 'templates'
        offenders = []
        for path in sorted(template_dir.rglob('*.html')):
            text = path.read_text(encoding='utf-8', errors='replace')
            for number, line in enumerate(text.splitlines(), 1):
                opened = line.find('{#')
                if opened != -1 and '#}' not in line[opened:]:
                    offenders.append(f'{path.relative_to(template_dir)}:{number}')
        self.assertEqual(
            offenders, [],
            'These {# #} comments span lines, so Django will print them into the '
            f'page as text: {offenders}. Use {{% comment %}} ... {{% endcomment %}}.',
        )


class SearchFilterContractTests(TestCase):
    """The search page's sidebar was wired to a different API than the view
    implements: `q`, `min_price`, `max_price` and `min_rooms` were read by
    nobody, amenity checkboxes sent ids where the view parsed names, the sort
    values were not accepted choices (an invalid form made the view drop EVERY
    filter, so a sorted page silently showed everything), and the barangay
    dropdown rendered empty options because the view passes names while the
    template asked for objects.

    These tests drive the view with exactly the parameter names the template
    now renders, so the two cannot drift apart again.
    """

    def setUp(self):
        self.landlord = make_user('filter-landlord@gmail.com', User.Role.LANDLORD)
        self.cctv = Amenity.objects.create(name='CCTV')

        self.alpha = make_house(self.landlord, 'Alpha Boarding', barangay='Sapilang')
        alpha_single = make_room(self.alpha, room_type='Single', monthly_rate=2000)
        alpha_single.amenities.add(self.cctv)
        make_room(self.alpha, room_type='Double', monthly_rate=3000)

        self.beta = make_house(self.landlord, 'Beta Lodge', barangay='Cabaroan')
        make_room(self.beta, room_type='Bedspace', monthly_rate=1500)

        self.gamma = make_house(self.landlord, 'Gamma Home', barangay='Sapilang')
        gamma_studio = make_room(self.gamma, room_type='Studio', monthly_rate=5000)
        gamma_studio.amenities.add(self.cctv)

        self.delta = make_house(self.landlord, 'Delta Dorm', barangay='Casiaman')
        for _ in range(3):
            make_room(self.delta, room_type='Single', monthly_rate=2500)

    def _result_ids(self, **params):
        response = self.client.get('/search/', params)
        self.assertEqual(response.status_code, 200, f'params={params}')
        return {house.pk for house in response.context['listings']}

    def test_free_text_search_matches_the_listing_and_its_room_types(self):
        self.assertEqual(self._result_ids(q='Alpha'), {self.alpha.pk})
        self.assertEqual(self._result_ids(q='Bedspace'), {self.beta.pk})

    def test_price_range_uses_the_names_the_page_renders(self):
        self.assertEqual(
            self._result_ids(price_min='2000', price_max='2600'),
            {self.alpha.pk, self.delta.pk},
        )

    def test_min_rooms_counts_only_rooms_that_can_be_booked(self):
        self.assertEqual(self._result_ids(min_rooms='2'), {self.alpha.pk, self.delta.pk})

        # Book out both of Alpha's rooms and it drops out of "2 or more open".
        student = make_user('filter-student@gmail.com', User.Role.STUDENT)
        for room in self.alpha.rooms.all():
            Booking.objects.create(student=student, room=room, status=Booking.Status.CONFIRMED)
        self.assertEqual(self._result_ids(min_rooms='2'), {self.delta.pk})

    def test_min_rooms_handles_a_house_with_mixed_room_states(self):
        # The first version grouped the count by the per-room booking count, so
        # a house with one booked-out room and one free room produced two rows
        # and MariaDB answered the live page with a 500:
        # (1242, 'Subquery returns more than 1 row').
        student = make_user('mixed-student@gmail.com', User.Role.STUDENT)
        alpha_rooms = list(self.alpha.rooms.all())
        Booking.objects.create(
            student=student, room=alpha_rooms[0], status=Booking.Status.CONFIRMED,
        )
        self.assertEqual(
            self._result_ids(min_rooms='1'),
            {self.alpha.pk, self.beta.pk, self.gamma.pk, self.delta.pk},
        )
        self.assertEqual(self._result_ids(min_rooms='2'), {self.delta.pk})

    def test_amenity_checkboxes_filter_by_name_and_can_be_combined(self):
        self.assertEqual(self._result_ids(amenities='CCTV'), {self.alpha.pk, self.gamma.pk})
        self.assertEqual(
            self.client.get('/search/', {'amenities': ['CCTV', 'No Such Amenity']}).status_code,
            200,
        )

    def test_barangay_option_values_are_names_and_actually_filter(self):
        response = self.client.get('/search/')
        self.assertContains(response, 'value="Sapilang"')
        self.assertNotContains(response, 'value="" ></option>')
        self.assertEqual(self._result_ids(barangay='Sapilang'), {self.alpha.pk, self.gamma.pk})

    def test_accepted_sort_value_does_not_silently_drop_the_other_filters(self):
        # Before: sort=price_low was not a valid choice, the form went invalid,
        # and the view returned every house as if nothing had been asked for.
        self.assertEqual(
            self._result_ids(barangay='Sapilang', sort='lowest_price'),
            {self.alpha.pk, self.gamma.pk},
        )


class InquiryStatusFollowsActivityTests(TestCase):
    """N1: a CLOSED thread accepted new messages while still claiming to be
    closed, so the landlord's queue disagreed with the conversation."""

    def setUp(self):
        self.landlord = make_user('status-landlord@gmail.com', User.Role.LANDLORD)
        self.student = make_user('status-student@gmail.com', User.Role.STUDENT)
        self.house = make_house(self.landlord, 'Status House')
        self.room = make_room(self.house)
        self.client.login(username='status-student@gmail.com', password='StrongPass123')

    def _post_message(self, status):
        inquiry = Inquiry.objects.create(
            student=self.student, room=self.room, status=status,
            message_text='Hello',
        )
        response = self.client.post(
            reverse('student_inquiry_thread', args=[inquiry.pk]),
            {'message_text': 'Following up'},
        )
        self.assertEqual(response.status_code, 302)
        inquiry.refresh_from_db()
        return inquiry

    def test_message_reopens_a_closed_thread(self):
        inquiry = self._post_message(Inquiry.Status.CLOSED)
        self.assertEqual(inquiry.status, Inquiry.Status.OPEN)
        self.assertEqual(inquiry.messages.count(), 1)

    def test_message_reopens_a_declined_thread(self):
        inquiry = self._post_message(Inquiry.Status.REJECTED)
        self.assertEqual(inquiry.status, Inquiry.Status.OPEN)


class AcceptFlowAtomicityTests(TestCase):
    """N2: the system message was written outside the booking transaction, so a
    failure between the two could leave a confirmed booking the student was
    never told about."""

    def setUp(self):
        self.landlord = make_user('accept-landlord@gmail.com', User.Role.LANDLORD)
        self.student = make_user('accept-student@gmail.com', User.Role.STUDENT)
        self.house = make_house(self.landlord, 'Accept House')
        self.room = make_room(self.house)
        self.inquiry = Inquiry.objects.create(
            student=self.student, room=self.room, message_text='Can I rent this?',
        )

    def test_accept_writes_the_booking_and_the_message_together(self):
        self.client.login(username='accept-landlord@gmail.com', password='StrongPass123')
        response = self.client.post(reverse('accept_student', args=[self.inquiry.pk]))
        self.assertEqual(response.status_code, 302)

        booking = Booking.objects.get(student=self.student, room=self.room)
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.inquiry.refresh_from_db()
        self.assertEqual(self.inquiry.status, Inquiry.Status.CLOSED)
        self.assertTrue(
            self.inquiry.messages.filter(message_text__startswith='System:').exists(),
            'a confirmed booking must always carry its system message',
        )


class BarangayDropdownTests(TestCase):
    """The landlord's barangay dropdown must offer only the six default
    barangays; anything else has to be added by an admin first."""

    ALLOWED = {'Arosip', 'Cabaroan', 'Casiaman', 'Salincob', 'Sapilang', 'Say-oan'}

    def test_only_the_six_defaults_are_seeded(self):
        self.assertEqual(
            set(Barangay.objects.values_list('name', flat=True)), self.ALLOWED,
        )

    def test_dropdown_matches_the_barangay_table(self):
        from .forms import BoardingHouseForm
        choices = {c[0] for c in BoardingHouseForm().fields['barangay'].choices}
        self.assertEqual(choices, self.ALLOWED)

    def test_admin_added_barangay_appears(self):
        from .forms import BoardingHouseForm
        Barangay.objects.create(name='New Ward', distance_from_campus='1 km')
        choices = {c[0] for c in BoardingHouseForm().fields['barangay'].choices}
        self.assertIn('New Ward', choices)


class StudentBarangayFilterTests(TestCase):
    """The student's barangay filters come from Admin -> Edit Barangays only.

    A house's `barangay` is free text, so building the dropdown from the
    houses' own values (as the browse and search views used to, alongside the
    admin list) offered students barangays the admin had never added and could
    not manage — old demo rows still carried names such as "Poblacion".
    """

    ALLOWED = {'Arosip', 'Cabaroan', 'Casiaman', 'Salincob', 'Sapilang', 'Say-oan'}

    def setUp(self):
        self.landlord = make_user('student-filter-landlord@gmail.com', User.Role.LANDLORD)
        make_room(make_house(self.landlord, 'Official Home', barangay='Sapilang'))
        # A row left over from before this barangay was removed from the table.
        make_room(make_house(self.landlord, 'Legacy Home', barangay='Legacy Ward'))

    def test_browse_filter_offers_only_admin_barangays(self):
        response = self.client.get('/listings/?sort=newest')
        self.assertContains(response, 'value="Sapilang"')
        self.assertNotContains(response, 'value="Legacy Ward"')
        self.assertEqual(
            {v for v, _label in response.context['form'].fields['barangay'].choices} - {''},
            self.ALLOWED,
        )

    def test_search_filter_offers_only_admin_barangays(self):
        response = self.client.get('/search/')
        self.assertContains(response, 'value="Sapilang"')
        self.assertNotContains(response, 'value="Legacy Ward"')
        self.assertEqual(
            {v for v, _label in response.context['form'].fields['barangay'].choices} - {''},
            self.ALLOWED,
        )

    def test_admin_added_barangay_appears_in_both_filters(self):
        Barangay.objects.create(name='New Ward', distance_from_campus='1 km')
        for url in ('/listings/?sort=newest', '/search/'):
            response = self.client.get(url)
            self.assertContains(response, 'value="New Ward"', msg_prefix=url)

    def test_filters_fall_back_to_the_six_when_the_table_is_empty(self):
        Barangay.objects.all().delete()
        for url in ('/listings/?sort=newest', '/search/'):
            response = self.client.get(url)
            for name in self.ALLOWED:
                self.assertContains(response, f'value="{name}"', msg_prefix=url)


class BarangayActiveListingCountTests(TestCase):
    """Admin -> Edit Barangays showed 0 active listings for "poblacion" while
    the student's Poblacion filter returned a house.

    The count grouped by the listing's exact string, but a listing may hold
    "Poblacion" while the admin typed "poblacion" — the database compares
    those as equal, so the student filter found the house while the admin
    table's exact dict lookup missed it. The count also included approved
    houses that students never see (no bookable room), so Casiaman/Sapilang
    read higher than the browse page. Both roles must answer the same question.
    """

    def setUp(self):
        self.admin = make_user('barangay-count-admin@gmail.com', User.Role.ADMIN)
        self.landlord = make_user('barangay-count-landlord@gmail.com', User.Role.LANDLORD)
        self.poblacion = Barangay.objects.create(
            name='poblacion', distance_from_campus='3.5 km',
        )
        self.house = make_house(self.landlord, 'Poblacion Home', barangay='Poblacion')
        make_room(self.house)

    def _admin_counts(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin_barangay_list'))
        self.assertEqual(response.status_code, 200)
        return {barangay.name: count for barangay, count in response.context['barangay_data']}

    def _student_result_ids(self, **params):
        self.client.logout()
        response = self.client.get('/listings/', params)
        self.assertEqual(response.status_code, 200)
        return {house.pk for house in response.context['houses']}

    def test_count_matches_the_student_filter_when_only_the_case_differs(self):
        self.assertEqual(
            self._student_result_ids(barangay='poblacion'), {self.house.pk},
        )
        self.assertEqual(self._admin_counts()['poblacion'], 1)

    def test_house_students_cannot_see_is_not_counted(self):
        self.house.rooms.update(is_available=False)
        self.assertEqual(self._student_result_ids(barangay='poblacion'), set())
        self.assertEqual(self._admin_counts()['poblacion'], 0)

    def test_listing_shows_the_admin_distance_label_despite_its_casing(self):
        self.assertEqual(self.house.barangay_display, 'poblacion (3.5 km)')


class InquiryNewBadgeTests(TestCase):
    """The 'NEW' chip must appear for BOTH sides when there is activity they
    have not opened yet, and clear once the thread is read."""

    def setUp(self):
        self.landlord = make_user('badge-landlord@gmail.com', User.Role.LANDLORD)
        self.student = make_user('badge-student@gmail.com', User.Role.STUDENT)
        self.house = make_house(self.landlord, 'Badge House')
        self.room = make_room(self.house)
        self.inquiry = Inquiry.objects.create(
            student=self.student, room=self.room, message_text='Is this room free?',
        )

    def test_landlord_list_flags_a_new_unopened_inquiry(self):
        self.client.login(username='badge-landlord@gmail.com', password='StrongPass123')
        response = self.client.get(reverse('landlord_inquiry_list'))
        self.assertContains(response, 'new-chip')

        # Opening the thread clears the chip on the next list load.
        self.client.get(reverse('landlord_inquiry_thread', args=[self.inquiry.pk]))
        response = self.client.get(reverse('landlord_inquiry_list'))
        self.assertNotContains(response, 'new-chip')

    def test_student_list_flags_a_landlord_reply_then_clears(self):
        # Student has read their own opening message.
        self.client.login(username='badge-student@gmail.com', password='StrongPass123')
        self.client.get(reverse('student_inquiry_thread', args=[self.inquiry.pk]))
        response = self.client.get(reverse('student_inquiry_list'))
        self.assertNotContains(response, 'new-chip')

        # Landlord replies — the student list must now show NEW.
        InquiryMessage.objects.create(
            inquiry=self.inquiry, sender=self.landlord, message_text='Yes it is.',
        )
        response = self.client.get(reverse('student_inquiry_list'))
        self.assertContains(response, 'new-chip')

        # Once the student opens the thread the chip clears again.
        self.client.get(reverse('student_inquiry_thread', args=[self.inquiry.pk]))
        response = self.client.get(reverse('student_inquiry_list'))
        self.assertNotContains(response, 'new-chip')


class ProfileSaveEndpointTests(TestCase):
    """The profile page's Save Changes button posted JSON to /profile/ itself,
    which only renders HTML, so every save died with
    "Unexpected token '<', \"<!DOCTYPE \"... is not valid JSON". The JSON view
    existed but had no URL, and landlords had no bio field to save at all."""

    def setUp(self):
        self.landlord = make_user('save-landlord@gmail.com', User.Role.LANDLORD)
        self.student = make_user('save-student@gmail.com', User.Role.STUDENT)

    def _post(self, user, payload):
        self.client.login(username=user.email, password='StrongPass123')
        return self.client.post(
            reverse('update_profile'),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_update_profile_url_is_json_not_html(self):
        response = self._post(self.student, {
            'first_name': 'Sam', 'last_name': 'Cruz',
            'phone_number': '09170001111', 'bio': 'Third-year CS student.',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'].split(';')[0], 'application/json')
        self.assertTrue(response.json()['success'])

    def test_landlord_can_save_a_bio(self):
        response = self._post(self.landlord, {
            'first_name': 'Liza', 'last_name': 'Reyes',
            'phone_number': '09096631300', 'bio': "I'm build different",
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.landlord.refresh_from_db()
        self.assertEqual(self.landlord.bio, "I'm build different")
        self.assertEqual(response.json()['profile']['bio'], "I'm build different")

    def test_student_can_save_a_bio(self):
        response = self._post(self.student, {
            'first_name': 'Sam', 'last_name': 'Cruz',
            'phone_number': '09170001111', 'bio': 'Looking for a dorm near CIS.',
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.student.refresh_from_db()
        self.assertEqual(self.student.bio, 'Looking for a dorm near CIS.')
        # The client redraws the profile title from this payload, so it needs a
        # name fallback for users without a first name.
        self.assertEqual(
            response.json()['profile']['username'], self.student.username,
        )

    def test_landlord_form_exposes_the_bio_field(self):
        self.client.login(username=self.landlord.email, password='StrongPass123')
        response = self.client.get(reverse('profile'))
        self.assertContains(response, 'id_bio')

    def test_clear_bio_empties_it_without_the_rest_of_the_form(self):
        self.student.bio = 'Old bio'
        self.student.save(update_fields=['bio'])
        response = self._post(self.student, {'clear_bio': True})
        self.assertEqual(response.status_code, 200, response.content)
        self.student.refresh_from_db()
        self.assertEqual(self.student.bio, '')

    def test_invalid_payload_returns_json_errors(self):
        # bio is capped at 300 characters by the model/form.
        response = self._post(self.student, {'bio': 'x' * 301})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertIn('bio', response.json()['errors'])


class StudentRegistrationToggleTests(TestCase):
    """Admin -> System Settings -> Allow student registration.

    The switch is inside a form whose Save button writes it, so flipping it
    and reloading without Save looked like it had turned itself back on. And
    the stored value only guarded the POST: the browse and login pages kept
    inviting students to "Create account", then refused them after the whole
    form was filled in.
    """

    PAYLOAD = {
        'username': 'toggle-new', 'full_name': 'Toggle New',
        'email': 'toggle-new@example.com', 'student_id': '241-1111-1',
        'program': 'CIS', 'password1': 'StrongPass123',
        'password2': 'StrongPass123',
    }
    CHECKED = (
        'name="student_registration_enabled" class="form-check-input" '
        'id="id_student_registration_enabled" checked'
    )

    def setUp(self):
        # The default browse page is cached; a stale copy from another test
        # must not decide what this one sees.
        cache.clear()
        self.admin = make_user('toggle-admin@gmail.com', User.Role.ADMIN)

    def _set(self, enabled):
        SiteSetting.objects.update_or_create(
            key='student_registration_enabled',
            defaults={'value': '1' if enabled else '0'},
        )

    def _admin_post(self, enabled):
        self.client.force_login(self.admin)
        data = {
            'site_name': 'BHIMS',
            'tagline': 'Your Home Away From Home, Near NLUC',
            'support_email': '',
        }
        if enabled:
            data['student_registration_enabled'] = 'on'
        response = self.client.post(reverse('admin_settings'), data)
        self.assertEqual(response.status_code, 302)

    def test_open_by_default_and_creates_an_account(self):
        page = self.client.get(reverse('student_register'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'data-sheet="signup"')

        response = self.client.post(reverse('student_register'), self.PAYLOAD)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='toggle-new').exists())

    def test_off_blocks_the_signup_route_and_post(self):
        self._set(False)
        page = self.client.get(reverse('student_register'))
        self.assertRedirects(
            page, reverse('home'), fetch_redirect_response=False,
        )
        response = self.client.post(reverse('student_register'), self.PAYLOAD)
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False,
        )
        self.assertFalse(
            User.objects.filter(username='toggle-new').exists(),
            'A disabled registration page still created an account.',
        )

    def test_off_removes_every_signup_invitation(self):
        self._set(False)
        login_page = self.client.get(reverse('student_login'))
        self.assertEqual(login_page.status_code, 200)
        self.assertContains(login_page, 'Student access closed')
        self.assertNotContains(login_page, 'data-sheet="signup"')
        self.assertNotContains(login_page, 'action="/students/register/"')
        # The sign-in form is closed as well, not just the signup sheet.
        self.assertNotContains(login_page, 'name="password"')

        # A stale ?mode=signup link must not leave both sheets hidden.
        stale = self.client.get(reverse('student_login') + '?mode=signup')
        self.assertContains(stale, 'data-mode="signin"')
        self.assertNotContains(stale, 'data-sheet="signup"')

        browse = self.client.get('/listings/')
        self.assertNotContains(browse, '/students/register/')

    def test_on_shows_the_signup_invitation(self):
        self._set(True)
        login_page = self.client.get(reverse('student_login'))
        self.assertContains(login_page, 'Create account')
        self.assertContains(login_page, 'data-sheet="signup"')
        self.assertContains(login_page, 'name="password"')
        browse = self.client.get('/listings/')
        self.assertContains(browse, '/students/register/')

    def test_off_blocks_a_correct_student_password(self):
        student = make_user('toggle-student@example.com', User.Role.STUDENT)
        self._set(False)
        for url in (reverse('login'), reverse('student_login')):
            client = self.client_class()
            response = client.post(
                url, {'username': student.username, 'password': 'StrongPass123'},
            )
            self.assertEqual(response.status_code, 200, url)
            self.assertIsNone(
                client.session.get('_auth_user_id'),
                f'{url} opened a student session while access was off.',
            )
            self.assertContains(
                response, 'Student sign-in is currently disabled', msg_prefix=url,
            )

    def test_on_allows_student_sign_in(self):
        student = make_user('toggle-open@example.com', User.Role.STUDENT)
        self._set(True)
        response = self.client.post(
            reverse('login'),
            {'username': student.username, 'password': 'StrongPass123'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get('_auth_user_id'), str(student.pk))

    def test_off_ends_an_existing_student_session(self):
        student = make_user('toggle-session@example.com', User.Role.STUDENT)
        self.client.force_login(student)
        self._set(False)
        response = self.client.get(reverse('student_dashboard'))
        self.assertRedirects(
            response, reverse('student_login'), fetch_redirect_response=False,
        )
        self.assertIsNone(self.client.session.get('_auth_user_id'))

    def test_admin_sign_in_keeps_working_when_student_access_is_off(self):
        self._set(False)
        response = self.client.post(
            reverse('admin_login'),
            {'username': self.admin.username, 'password': 'StrongPass123'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get('_auth_user_id'), str(self.admin.pk))

    def test_saving_the_toggle_refreshes_the_cached_browse_page(self):
        self._set(True)
        warm = self.client.get('/listings/')
        self.assertContains(warm, '/students/register/')

        self._admin_post(False)
        self.client.logout()
        after = self.client.get('/listings/')
        self.assertNotContains(
            after, '/students/register/',
            msg_prefix='The cached browse page still invited students to register.',
        )

    def test_admin_save_persists_off_and_on(self):
        self.client.force_login(self.admin)
        page = self.client.get(reverse('admin_settings'))
        self.assertContains(page, self.CHECKED)

        self._admin_post(False)
        self.assertEqual(
            SiteSetting.objects.get(key='student_registration_enabled').value,
            '0',
        )
        page = self.client.get(reverse('admin_settings'))
        self.assertNotContains(page, self.CHECKED)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('student_register')).status_code, 302)

        self._admin_post(True)
        self.assertEqual(
            SiteSetting.objects.get(key='student_registration_enabled').value,
            '1',
        )
        page = self.client.get(reverse('admin_settings'))
        self.assertContains(page, self.CHECKED)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('student_register')).status_code, 200)

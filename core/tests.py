from django.test import TestCase

from .forms import StudentRegistrationForm
from .models import BoardingHouse, Booking, LandlordRating, Room, User


class StudentRegistrationFlowTests(TestCase):
    def test_registration_rejects_invalid_gmail_and_student_id(self):
        form = StudentRegistrationForm(data={
            'username': 'juan',
            'full_name': 'Juan dela Cruz',
            'email': 'juan@yahoo.com',
            'student_id': '24102731',
            'program': 'CIS',
            'password1': 'StrongPass123',
            'password2': 'StrongPass123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('Please register with a valid Gmail address that ends in @gmail.com.', form.errors['email'])
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
        self.assertIn('A student account with this Gmail address already exists.', form.errors['email'])
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

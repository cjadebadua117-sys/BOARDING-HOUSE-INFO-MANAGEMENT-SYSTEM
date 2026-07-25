from django.test import TestCase

from .forms import StudentRegistrationForm
from .models import BoardingHouse, Room, User


class StudentRegistrationFlowTests(TestCase):
    def test_registration_rejects_invalid_gmail_and_student_id(self):
        form = StudentRegistrationForm(data={
            'full_name': 'Juan dela Cruz',
            'email': 'juan@yahoo.com',
            'student_id': '24102731',
            'program': 'BSIT',
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
            'full_name': 'Another Student',
            'email': 'existing@gmail.com',
            'student_id': '241-0273-1',
            'program': 'BSIT',
            'password1': 'StrongPass123',
            'password2': 'StrongPass123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('A student account with this Gmail address already exists.', form.errors['email'])
        self.assertIn('This Student ID is already registered.', form.errors['student_id'])


class BrowsePageTests(TestCase):
    def test_browse_page_renders_filter_labels_and_barangay_filter(self):
        house = BoardingHouse.objects.create(
            owner=User.objects.create_user(email='owner@gmail.com', password='OwnerPass123', role=User.Role.LANDLORD, full_name='Owner', username='owner@gmail.com'),
            name='Warm Home',
            address='123 Main Street',
            barangay='Naguilian',
            description='A cozy place for students',
        )
        Room.objects.create(boarding_house=house, room_type='Single', price=2500, capacity=1, is_available=True)

        response = self.client.get('/listings/?barangay=Naguilian')
        self.assertContains(response, 'Price Range')
        self.assertContains(response, 'Room Type')
        self.assertContains(response, 'Amenities')
        self.assertContains(response, 'Barangay')

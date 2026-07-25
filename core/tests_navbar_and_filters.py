
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.hashers import make_password
from core.models import User, Amenity, BoardingHouse, Room

class NavbarAndFilterTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            username='student_test',
            email='student@test.com',
            password='password',
            role='student',
            is_active=True
        )
        self.landlord = User.objects.create_user(
            username='landlord_test',
            email='landlord@test.com',
            password='password',
            role='landlord',
            is_active=True,
            is_verified=True
        )
        self.admin = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='password',
            role='admin',
            is_active=True,
            is_staff=True,
            is_superuser=True
        )

        # Create Amenities
        self.wifi = Amenity.objects.create(name='Wi-Fi')
        self.ac = Amenity.objects.create(name='Air Conditioning')
        self.kitchen = Amenity.objects.create(name='Shared Kitchen')

        # Create Boarding House
        self.bh1 = BoardingHouse.objects.create(
            owner=self.landlord,
            name='Test House 1',
            address='123 Test St.',
            barangay='Poblacion',
            city='Test City',
            description='A test boarding house.'
        )
        
        self.bh2 = BoardingHouse.objects.create(
            owner=self.landlord,
            name='Test House 2',
            address='456 Sample Ave.',
            barangay='San Jose',
            city='Test City',
            description='Another test boarding house.'
        )

        # Create Rooms
        self.room1 = Room.objects.create(
            boarding_house=self.bh1,
            room_type='Single',
            price=5000.00,
            description='A single room.'
        )
        self.room1.amenities.add(self.wifi, self.ac)

        self.room2 = Room.objects.create(
            boarding_house=self.bh2,
            room_type='Double',
            price=3500.00,
            description='A double room.'
        )
        self.room2.amenities.add(self.kitchen)
        
        self.room3 = Room.objects.create(
            boarding_house=self.bh1,
            room_type='Single',
            price=5500.00,
            description='An expensive single room.'
        )
        self.room3.amenities.add(self.wifi)

    def test_navbar_logged_out(self):
        response = self.client.get(reverse('listing_list'))
        self.assertContains(response, 'Browse')
        self.assertContains(response, 'Student Login')
        self.assertContains(response, 'Landlord Login')
        self.assertContains(response, 'Sign Up')

    def test_navbar_student(self):
        self.client.login(username='student_test', password='password')
        response = self.client.get(reverse('listing_list'))
        self.assertContains(response, 'Browse')
        self.assertContains(response, 'My Profile')
        self.assertContains(response, 'My Inquiries')
        self.assertContains(response, 'Logout')

    def test_navbar_landlord(self):
        self.client.login(username='landlord_test', password='password')
        response = self.client.get(reverse('landlord_dashboard'))
        self.assertContains(response, 'Dashboard')
        self.assertContains(response, 'My Boarding Houses')
        self.assertContains(response, 'Inquiries')
        self.assertContains(response, 'Logout')

    def test_navbar_admin(self):
        self.client.login(username='admin_test', password='password')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertContains(response, 'Admin Dashboard')
        self.assertContains(response, 'Landlord Accounts')
        self.assertContains(response, 'Analytics')
        self.assertContains(response, 'Logout')

    def test_filter_price(self):
        response = self.client.get(reverse('listing_list'), {'price_min': 4000, 'price_max': 5200})
        self.assertContains(response, 'Test House 1')
        self.assertNotContains(response, 'Test House 2')

    def test_filter_room_type(self):
        response = self.client.get(reverse('listing_list'), {'room_type': 'Double'})
        self.assertContains(response, 'Test House 2')
        self.assertNotContains(response, 'Test House 1')

    def test_filter_amenities(self):
        response = self.client.get(reverse('listing_list'), {'amenities': [self.ac.id]})
        self.assertContains(response, 'Test House 1')
        self.assertNotContains(response, 'Test House 2')

    def test_filter_barangay(self):
        response = self.client.get(reverse('listing_list'), {'barangay': 'San Jose'})
        self.assertContains(response, 'Test House 2')
        self.assertNotContains(response, 'Test House 1')

    def test_sort_lowest_price(self):
        response = self.client.get(reverse('listing_list'), {'sort': 'lowest_price'})
        # The first result should be Test House 2 because it has the cheapest room
        self.assertIn(self.bh2, response.context['houses'])
        self.assertLess(response.context['houses'].first().rooms.first().price, self.bh1.rooms.first().price)

    def test_sort_newest(self):
        response = self.client.get(reverse('listing_list'), {'sort': 'newest'})
        # The first result should be Test House 2 because it was created last
        self.assertEqual(response.context['houses'].first(), self.bh2)
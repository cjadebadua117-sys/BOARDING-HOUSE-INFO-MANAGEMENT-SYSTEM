
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.contrib.auth.hashers import make_password
from core.models import User, Amenity, BoardingHouse, Room

def seed_data():
    # Clean up existing data
    User.objects.all().delete()
    Amenity.objects.all().delete()
    BoardingHouse.objects.all().delete()
    Room.objects.all().delete()

    # Create Users
    student = User.objects.create(
        username='student_test',
        email='student@test.com',
        password=make_password('password'),
        role='student',
        is_active=True
    )

    landlord = User.objects.create(
        username='landlord_test',
        email='landlord@test.com',
        password=make_password('password'),
        role='landlord',
        is_active=True,
        is_verified=True
    )

    admin = User.objects.create(
        username='admin_test',
        email='admin@test.com',
        password=make_password('password'),
        role='admin',
        is_active=True,
        is_staff=True,
        is_superuser=True
    )

    print("Users created.")

    # Create Amenities
    wifi = Amenity.objects.create(name='Wi-Fi')
    ac = Amenity.objects.create(name='Air Conditioning')
    kitchen = Amenity.objects.create(name='Shared Kitchen')
    
    print("Amenities created.")

    # Create Boarding House
    bh1 = BoardingHouse.objects.create(
        owner=landlord,
        name='Test House 1',
        address='123 Test St.',
        barangay='Poblacion',
        city='Test City',
        description='A test boarding house.'
    )
    
    bh2 = BoardingHouse.objects.create(
        owner=landlord,
        name='Test House 2',
        address='456 Sample Ave.',
        barangay='San Jose',
        city='Test City',
        description='Another test boarding house.'
    )

    print("Boarding Houses created.")

    # Create Rooms
    room1 = Room.objects.create(
        boarding_house=bh1,
        room_type='Single',
        price=5000.00,
        description='A single room.'
    )
    room1.amenities.add(wifi, ac)

    room2 = Room.objects.create(
        boarding_house=bh2,
        room_type='Double',
        price=3500.00,
        description='A double room.'
    )
    room2.amenities.add(kitchen)
    
    room3 = Room.objects.create(
        boarding_house=bh1,
        room_type='Single',
        price=5500.00,
        description='An expensive single room.'
    )
    room3.amenities.add(wifi)


    print("Rooms created.")
    print("Database seeding complete.")

if __name__ == '__main__':
    seed_data()
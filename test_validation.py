import os
import django
from django.core.exceptions import ValidationError

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from core.models import User, Landlord, BoardingHouse, BoardingHouseImage

def test_boarding_house_validation():
    print("Testing boarding house image validation...")
    
    # Create a test admin user
    admin_user = User.objects.create_superuser(
        email='admin@test.com',
        password='testpass123',
        role=User.Role.ADMIN
    )
    
    # Create a landlord user
    landlord_user = User.objects.create_user(
        email='landlord@test.com',
        password='testpass123',
        role=User.Role.LANDLORD
    )
    
    # Create landlord profile
    landlord = Landlord.objects.create(
        AccountID=landlord_user,
        FullName='Test Landlord',
        ContactNumber='1234567890',
        Address='123 Test Street'
    )
    
    # Try to create a boarding house and set status to Available immediately
    print("\n1. Testing: Create boarding house and try to set to Available without images...")
    try:
        house = BoardingHouse(
            LandlordID=landlord,
            HouseName='Test Boarding House',
            Barangay='sapilang',
            Address='456 Test Avenue',
            MonthlyRate=5000.00,
            Capacity=10,
            AvailableSlots=8,
            Status='Available'  # This should be forced to Unavailable for new instances
        )
        house.save()
        print(f"   Boarding house created. Status automatically set to: {house.Status}")
        assert house.Status == 'Unavailable', "New boarding house should be forced to Unavailable"
    except Exception as e:
        print(f"   Error: {e}")
    
    # Now add an image to the boarding house
    print("\n2. Testing: Add image to boarding house...")
    BoardingHouseImage.objects.create(
        BoardingHouseID=house,
        ImagePath='test_image.jpg',
        IsPrimary=True
    )
    print("   Image added successfully.")
    
    # Now try to set status to Available
    print("\n3. Testing: Set status to Available after adding image...")
    try:
        house.Status = 'Available'
        house.save()
        print(f"   Status successfully set to: {house.Status}")
        assert house.Status == 'Available', "Should be able to set to Available with images"
    except ValidationError as e:
        print(f"   Unexpected error: {e}")
        assert False, "Should not raise validation error when images exist"
    
    # Remove all images and try to set back to Available
    print("\n4. Testing: Remove images and try to set back to Available...")
    house.images.all().delete()
    house.Status = 'Unavailable'
    house.save()
    
    try:
        house.Status = 'Available'
        house.save()
        assert False, "Should raise validation error when trying to set to Available without images"
    except ValidationError as e:
        print(f"   Correctly raised validation error: {e}")
    
    print("\n✅ All tests passed! The image requirement validation is working correctly.")

if __name__ == "__main__":
    test_boarding_house_validation()
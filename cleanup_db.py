import django
django.setup()
from django.db import connection

with connection.cursor() as cursor:
    # Delete core migration record to force re-apply
    cursor.execute("DELETE FROM django_migrations WHERE app = 'core'")
    print("Deleted core migration record")
    
    # Drop all old core tables
    tables = [
        'core_room_amenities', 'core_roomphoto', 'core_amenity',
        'core_inquirymessage', 'core_inquiry', 'core_room',
        'core_boardinghouse', 'core_user_groups', 'core_user_user_permissions',
        'core_user'
    ]
    for table in tables:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"Dropped {table}")
        except Exception as e:
            print(f"Error dropping {table}: {e}")

print("Database cleanup complete!")
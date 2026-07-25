import django
django.setup()
from django.db import connection

with connection.cursor() as cursor:
    # Delete all migration records
    cursor.execute("DELETE FROM django_migrations WHERE app IN ('core', 'admin', 'auth', 'contenttypes', 'sessions')")
    print("Cleared all migration records")
    
    # Drop all tables to start fresh
    tables_to_drop = [
        'core_room_amenities', 'core_roomphoto', 'core_amenity',
        'core_inquirymessage', 'core_inquiry', 'core_room',
        'core_boardinghouse', 'core_user_groups', 'core_user_user_permissions',
        'core_user', 'auth_group_permissions', 'auth_permission', 'auth_group',
        'django_admin_log', 'django_content_type', 'django_session'
    ]
    for table in tables_to_drop:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"Dropped {table}")
        except Exception as e:
            print(f"Error dropping {table}: {e}")

print("Full database reset complete!")
import os
import django
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
try:
    django.setup()
except Exception as e:
    print('Django setup failed:', e)
    sys.exit(1)
from django.db import connection
print('--- DESCRIBE tbl_accounts ---')
with connection.cursor() as c:
    try:
        c.execute('DESCRIBE tbl_accounts;')
    except Exception as e:
        print('DESCRIBE failed:', repr(e))
        sys.exit(1)
    rows = c.fetchall()
    for r in rows:
        print(r)

print('\n--- CREATE TEST USER ---')
from core.models import User
try:
    existing = User.objects.filter(username='tmp_mig_test').first()
    if existing:
        existing.delete()
    u = User.objects.create_user(username='tmp_mig_test', email='tmp_mig_test@example.com', password='Password123!')
    u.phone_number = '09171234567'
    u.bio = 'migration check'
    u.save()
    print('Created user id:', u.pk)
    print('phone_number:', u.phone_number)
    print('bio:', u.bio)
except Exception as e:
    print('User creation failed:', repr(e))
    sys.exit(1)
print('\nOK')

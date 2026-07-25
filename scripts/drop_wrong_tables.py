"""
Drop legacy incorrect tbl_ tables and remove core migration records.
Run from project root with the virtualenv Python.
"""
import os
import django
import sys

# Ensure project root is on sys.path so 'myproject' can be imported
project_root = os.path.dirname(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.db import connections

conn = connections['default']
cur = conn.cursor()
wrong_tables = [
    'tbl_accounts',
    'tbl_accounts_groups',
    'tbl_accounts_user_permissions',
    'tbl_adminlogs',
    'tbl_boardinghouse_images',
    'tbl_boardinghouses',
    'tbl_bookings',
    'tbl_landlords',
    'tbl_students',
]

for table in wrong_tables:
    try:
        cur.execute(f"DROP TABLE IF EXISTS `{table}`")
        print('Dropped', table)
    except Exception as e:
        print('Failed to drop', table, e)

# Remove core entries from django_migrations so Django will create fresh migrations
try:
    cur.execute("DELETE FROM django_migrations WHERE app='core'")
    print('Cleared core migration records')
except Exception as e:
    print('Failed to clear django_migrations for core', e)

cur.close()
conn.close()
print('Done')

import os, sys
project_root = os.path.dirname(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
import django
django.setup()
from django.db import connections
conn = connections['default']
cur = conn.cursor()
remaining = ['tbl_accounts','tbl_boardinghouses','tbl_landlords']
for table in remaining:
    print('\nForeign keys referencing', table)
    cur.execute("""
        SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE REFERENCED_TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME = %s
    """, [table])
    rows = cur.fetchall()
    if not rows:
        print(' None')
    else:
        for r in rows:
            print(' ', r)
cur.close()
conn.close()

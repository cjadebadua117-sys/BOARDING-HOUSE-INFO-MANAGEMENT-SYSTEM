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

# Find and drop foreign keys that reference the remaining tbl_ tables
cur.execute("""
    SELECT TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE REFERENCED_TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IN ('tbl_accounts','tbl_boardinghouses','tbl_landlords')
""")
rows = cur.fetchall()
for table_name, constraint_name, ref_table in rows:
    try:
        cur.execute(f"ALTER TABLE `{table_name}` DROP FOREIGN KEY `{constraint_name}`")
        print(f'Dropped FK {constraint_name} on {table_name} referencing {ref_table}')
    except Exception as e:
        print('Failed to drop FK', constraint_name, 'on', table_name, e)

# Now drop the remaining tables
to_drop = ['tbl_boardinghouses','tbl_landlords','tbl_accounts']
for t in to_drop:
    try:
        cur.execute(f"DROP TABLE IF EXISTS `{t}`")
        print('Dropped', t)
    except Exception as e:
        print('Failed to drop', t, e)

# Just in case, clear core migrations again
try:
    cur.execute("DELETE FROM django_migrations WHERE app='core'")
    print('Cleared core migration records')
except Exception as e:
    print('Failed to clear django_migrations for core', e)

cur.close()
conn.close()
print('Done')

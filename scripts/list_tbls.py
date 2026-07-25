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
cur.execute("SHOW TABLES LIKE 'tbl_%'")
rows = cur.fetchall()
if not rows:
    print('No tbl_ tables found')
else:
    for r in rows:
        print(r[0])
cur.close()
conn.close()

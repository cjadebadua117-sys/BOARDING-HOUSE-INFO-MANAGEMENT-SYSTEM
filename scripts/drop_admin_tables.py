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
try:
    cur.execute('DROP TABLE IF EXISTS django_admin_log')
    print('Dropped django_admin_log')
except Exception as e:
    print('Failed to drop django_admin_log', e)
cur.close()
conn.close()

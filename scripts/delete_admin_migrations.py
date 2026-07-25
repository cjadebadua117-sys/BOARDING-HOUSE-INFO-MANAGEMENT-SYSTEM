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
cur.execute("DELETE FROM django_migrations WHERE app='admin'")
print('Deleted admin migrations rows')
cur.close()
conn.close()

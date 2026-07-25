import MySQLdb
import sys

try:
    conn = MySQLdb.connect(host='127.0.0.1', port=3306, user='root', passwd='', db='boarding_house_system')
except Exception as e:
    print('CONNECT_ERR', repr(e))
    sys.exit(1)

cur = conn.cursor()
cur.execute('SHOW DATABASES')
print('DATABASES:')
for row in cur.fetchall():
    print('-', row[0])

cur.execute('SHOW TABLES')
print('TABLES:')
for row in cur.fetchall():
    print('-', row[0])

try:
    cur.execute("SELECT app, name, applied FROM django_migrations WHERE app='core'")
    rows = cur.fetchall()
    print('CORE MIGRATIONS:')
    if rows:
        for r in rows:
            print('-', r)
    else:
        print('(none)')
except Exception as e:
    print('MIGRATION_QUERY_ERR', repr(e))

cur.close()
conn.close()

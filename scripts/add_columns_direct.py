import MySQLdb
import sys

config = dict(host='127.0.0.1', user='root', passwd='', db='boarding_house_system', charset='utf8mb4')
try:
    conn = MySQLdb.connect(**config)
except Exception as e:
    print('DB connect failed:', repr(e))
    sys.exit(1)
cur = conn.cursor()
columns = [
    ('phone_number', 'VARCHAR(30)'),
    ('profile_picture', 'VARCHAR(100)'),
    ('bio', 'TEXT')
]
for name, typ in columns:
    cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s", ('boarding_house_system', 'tbl_accounts', name))
    exists = cur.fetchone()[0]
    if exists:
        print(f'Column {name} already exists')
    else:
        try:
            cur.execute(f'ALTER TABLE tbl_accounts ADD COLUMN {name} {typ} NULL')
            print('Added column', name)
        except Exception as e:
            print('Failed to add', name, repr(e))
conn.commit()
cur.close()
conn.close()

#!/usr/bin/env python
"""Drop all tables from the database"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute('SET FOREIGN_KEY_CHECKS=0')
    cursor.execute('SELECT table_name FROM information_schema.tables WHERE table_schema="boarding_house_system"')
    tables = cursor.fetchall()
    for table in tables:
        print(f'Dropping table: {table[0]}')
        cursor.execute(f'DROP TABLE IF EXISTS {table[0]}')
    cursor.execute('SET FOREIGN_KEY_CHECKS=1')
    print('All tables dropped successfully')

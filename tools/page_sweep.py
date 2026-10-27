"""Temporary audit script: request every page as each role and report status."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.test import Client
from core.models import User, BoardingHouse, Room

admin = User.objects.get(username='newadmin123')
landlord = User.objects.get(username='newlandlord456')
student = User.objects.get(username='newstudent789')

house_owned = BoardingHouse.objects.filter(owner=landlord).first()
house_any = BoardingHouse.objects.filter(status='approved').first()
room_owned = Room.objects.filter(boarding_house__owner=landlord).first()
room_any = Room.objects.first()
student_any = User.objects.filter(role='student').exclude(pk=student.pk).first()
landlord_any = User.objects.filter(role='landlord').exclude(pk=landlord.pk).first()

public_urls = [
    '/', '/listings/', '/search/', '/health/',
    '/students/register/', '/students/login/', '/accounts/login/',
    '/landlords/login/', '/landlords/register/', '/admin/login/',
    f'/listings/{house_any.pk}/' if house_any else None,
    f'/users/{landlord_any.pk}/' if landlord_any else None,
]

student_urls = [
    '/students/dashboard/', '/students/inquiries/', '/students/bookings/',
    '/profile/', '/profile/edit/', '/profile/change-password/',
    '/listings/', '/search/',
    f'/listings/{house_any.pk}/' if house_any else None,
    f'/users/{landlord_any.pk}/' if landlord_any else None,
]

landlord_urls = [
    '/landlords/dashboard/', '/landlords/boarding-houses/',
    '/landlords/boarding-houses/add/', '/landlords/inquiries/',
    '/landlords/bookings/', '/landlords/ratings/',
    '/profile/', '/profile/edit/', '/profile/change-password/',
    '/listings/',
    f'/landlords/boarding-houses/{house_owned.pk}/' if house_owned else None,
    f'/landlords/boarding-houses/{house_owned.pk}/edit/' if house_owned else None,
    f'/landlords/boarding-houses/{house_owned.pk}/rooms/add/' if house_owned else None,
    f'/landlords/rooms/{room_owned.pk}/edit/' if room_owned else None,
    f'/users/{student_any.pk}/' if student_any else None,
]

admin_urls = [
    '/admin/dashboard/', '/admin/analytics/', '/admin/ratings/',
    '/admin/landlords/', '/admin/students/', '/admin/listings/pending/',
    '/admin/barangays/', '/admin/settings/', '/admin/reports/',
    '/admin/landlords/add/', '/profile/',
    f'/admin/landlords/{landlord.pk}/',
    f'/admin/landlords/{landlord.pk}/edit/',
    f'/admin/landlords/{landlord.pk}/toggle/' if False else None,
    f'/landlords/boarding-houses/{house_owned.pk}/' if house_owned else None,
]

def run(label, urls, user=None):
    c = Client()
    if user is not None:
        c.force_login(user)
    print(f'\n=== {label} ===')
    for url in urls:
        if not url:
            continue
        try:
            r = c.get(url)
            code = r.status_code
            note = ''
            if code in (301, 302):
                note = f' -> {r.headers.get("Location", "")}'
            print(f'{code} {url}{note}')
        except Exception as exc:  # noqa: BLE001 - audit script wants every failure
            print(f'EXC {url}: {type(exc).__name__}: {exc}')

run('PUBLIC', public_urls)
run('STUDENT', student_urls, student)
run('LANDLORD', landlord_urls, landlord)
run('ADMIN', admin_urls, admin)

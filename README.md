# BHIMS — Boarding House Information Management System

A web system for **DMMMSU–NLUC Bacnotan** students to find, inquire about, and book
boarding houses near campus. Landlords post listings, admins moderate them, and
students browse and book safely.

## Tech Stack

- **Python 3.14 / Django 6.0**
- **MySQL / MariaDB** (XAMPP) via `mysqlclient`
- **Bootstrap 5 + custom glassmorphism design system**

## Features by Role

| Role | Capabilities |
|---|---|
| Student | Register, browse/filter listings (barangay, price, amenities), send inquiries, chat with landlords, get confirmed bookings |
| Landlord | Register, manage boarding houses & rooms (photos, rates, capacity, amenities), reply to inquiries, accept students |
| Admin | Approve/reject listings, manage landlords/students/barangays, view analytics, edit site settings |

## Setup (XAMPP)

1. Start **Apache/MySQL** in XAMPP and create the database:
   ```sql
   CREATE DATABASE boarding_house_system;
   ```
2. Create a virtual environment and install dependencies:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Apply migrations:
   ```powershell
   python manage.py migrate
   ```
4. Create an admin account:
   ```powershell
   python manage.py createsuperuser
   ```
5. Run the server:
   ```powershell
   python manage.py runserver
   ```
6. Open <http://127.0.0.1:8000/>

## Environment Variables (optional)

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Secret key for production (dev fallback exists) |
| `DJANGO_DEBUG` | Set `0` to disable debug mode |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts for production |
| `DJANGO_EMAIL_BACKEND` | e.g. `django.core.mail.backends.smtp.EmailBackend` |
| `DJANGO_EMAIL_HOST` / `_PORT` / `_USER` / `_PASSWORD` | SMTP credentials for real password-reset emails |

## Database Note

XAMPP ships MariaDB **10.4**, while Django 6 officially requires 10.5+. The
custom backend in `myproject/mysql_backend/` lowers that gate because BHIMS only
uses basic SQL features. For production, upgrade MariaDB and remove the override.

## Tests

```powershell
python manage.py test core
```

## Project Layout

```
core/            Main app: models, views, forms, templates, static files
myproject/       Project settings & URL config (incl. MariaDB compat backend)
media/           User-uploaded images (profile pictures, room photos)
scripts/         Utility scripts
```

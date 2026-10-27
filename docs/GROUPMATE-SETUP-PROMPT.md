# Freebuff prompt for a groupmate — set up BHIMS on your laptop

Paste the block below into Freebuff on your own machine. It is written to be
self-contained: the agent has not seen the rest of the conversation.

---

Set up this BHIMS Django project so it runs on my laptop, then prove it runs.

**1. Find and sync the repo.** It is the clone of
`https://github.com/cjadebadua117-sys/BOARDING-HOUSE-INFO-MANAGEMENT-SYSTEM.git`
— ask me for the folder if you cannot find it. The repository's history was
rewritten, so a normal `git pull` will fail on my clone. Sync it with:

```
git fetch origin
git reset --hard origin/master
```

If I have local changes I want to keep, stop and tell me instead of discarding
them. Do not commit or push anything.

**2. Environment.** Django 6 needs Python 3.12 or newer.

```
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

If `mysqlclient` fails to build, report the exact error to me rather than
swapping in a different package.

**3. Database server.** XAMPP must be running — MySQL at least, and confirm
something is listening on `127.0.0.1:3306`. In MariaDB create the database if it
does not exist:

```sql
CREATE DATABASE boarding_house_information_management_system;
```

If there is no `.env`, copy `.env.example` to `.env` and set
`DJANGO_DB_NAME=boarding_house_information_management_system` (XAMPP's `root`
user has an empty password unless I changed it).

Then apply the schema:

```
python manage.py migrate
```

**4. Images (only if I hand you `bhims-media-*.zip`).** The project's uploaded
photos live in `media/` at the project root and are git-ignored, so a fresh
clone has none. The archive stores its paths *without* a `media/` prefix, so
extract it into a folder called `media` beside `manage.py`:

```powershell
Expand-Archive -Path bhims-media-<stamp>.zip -DestinationPath media -Force
```

Afterwards `media/boarding_images/`, `media/room_photos/` and
`media/profile_pictures/` must exist. Without this the site still runs, but
listings show a "No photo yet" placeholder and any images the database points
at render broken — so do this **before** seeding or importing.

**5. Get data into it.** Default — build a demo database, no personal data:

```
python manage.py seed_demo_listings
python manage.py createsuperuser
```

Only if I hand you an encrypted dump (`bhims-share-*.sql.enc`), do this instead:
decrypt it with the password I give you —

```
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in <file>.enc -out bhims-share.sql
```

— import that `.sql` into `boarding_house_information_management_system`
(phpMyAdmin or the `mysql` client), then run `python manage.py migrate` again to
apply any migrations newer than the dump.

**6. Prove it works.** Start the server and load it:

```
python manage.py runserver
```

Open <http://127.0.0.1:8000/> and confirm the home page renders and sign-in
works. Then tell me: the exact commands you ran, every error you hit, and
whether the site actually loaded — not just whether the commands exited 0.

---

## Prerequisites on your laptop

- **XAMPP** installed, with MySQL started.
- **Python 3.12+** and **Git** on PATH.
- Only if importing the real dump: **Git for Windows** (for `openssl`) and the
  `.enc` file plus its password.

## Demo logins after seeding

`demo_landlord` / `DemoLandlord2026!` — and the seeded student accounts follow
the same pattern (`demo_student01`, etc.).

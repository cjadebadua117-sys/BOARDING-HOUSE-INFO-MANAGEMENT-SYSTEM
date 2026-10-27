# Getting the updated BHIMS on your laptop

For classmates who need to run the latest version of
[BOARDING-HOUSE-INFO-MANAGEMENT-SYSTEM](https://github.com/cjadebadua117-sys/BOARDING-HOUSE-INFO-MANAGEMENT-SYSTEM).

Time: about 10 minutes the first time, under 2 minutes for later updates.
Everything below is Windows PowerShell; the commands are the same on macOS/Linux
with `source venv/bin/activate` instead of the `.\venv\Scripts\activate` line.

---

## 0. What you need (once)

| Tool | Check | Notes |
|---|---|---|
| Git | `git --version` | <https://git-scm.com/download/win> |
| Python **3.12 or newer** | `python --version` | Django 6 refuses anything older. Tick "Add Python to PATH" when installing. |
| XAMPP | MySQL runs in the XAMPP Control Panel | The database lives here. |
| Repo access | the GitHub link opens for you | If it 404s, ask CJ to add you as a collaborator. |

---

## 1A. First time — clone the project

```powershell
cd $HOME\Desktop
git clone https://github.com/cjadebadua117-sys/BOARDING-HOUSE-INFO-MANAGEMENT-SYSTEM.git
cd BOARDING-HOUSE-INFO-MANAGEMENT-SYSTEM
```

## 1B. You already have a copy — pull the update

```powershell
cd path\to\BOARDING-HOUSE-INFO-MANAGEMENT-SYSTEM
git status
git pull origin master
```

`git status` must not list files you edited by hand. If it does, either commit
them or throw them away with `git restore <file>` — otherwise the pull stops
with a conflict. **Do not** run `git reset --hard` unless you are sure you want
to lose your own edits.

After pulling, stop the running server (Ctrl+C), start it again, and hard-refresh
the browser (**Ctrl+F5**) — Django reloads Python automatically but the browser
keeps the old CSS.

---

## 2. Database (only when it is not set up yet)

1. Open **XAMPP Control Panel** → **Start** MySQL (Apache is not needed).
2. Go to <http://localhost/phpmyadmin> → **New** → database name:

   ```
   boarding_house_information_management_system
   ```

   Collation `utf8mb4_general_ci` is fine.

If you changed the MySQL root password, copy `.env.example` to `.env` and fill
in `DJANGO_DB_USER` / `DJANGO_DB_PASSWORD`. With a stock XAMPP install you can
skip `.env` entirely — the defaults (`root`, no password) already work.

---

## 3. Install and prepare (first time, and after any update that changes dependencies)

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
```

`migrate` is safe to run every time; it only applies what is missing.

Want sample data instead of an empty site? This creates three demo landlords,
fifteen demo students, bookings, ratings and twelve listings (with the façade
photos the repo ships):

```powershell
python manage.py seed_demo_listings
```

It adds its own barangays and amenities, so it works on a fresh database. It
prints *"No room photos found"* on a fresh clone — that is expected: the room
photos live in `media/`, which is not in the repository, so the cards fall back
to the façade images that are.

Create your own admin account:

```powershell
python manage.py createsuperuser
```

That account already gets the `admin` role (the custom user manager sets it), so
it works on both `/admin/login/` (BHIMS dashboard) and `/django-admin/` (plain
Django admin). Students and landlords who register through the site cannot reach
any admin page.

---

## 4. Run it

```powershell
.\venv\Scripts\activate
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

Press **Ctrl+C** in the terminal to stop it. If port 8000 is busy, use
`python manage.py runserver 8001`.

### Demo accounts from the seed command

| Role | Username | Password |
|---|---|---|
| Landlord | `demo_landlord`, `demo_landlord_2`, `demo_landlord_3` | `DemoLandlord2026!` |
| Student | `demo_student01` … `demo_student15` | `DemoStudent2026!` |
| Admin | the superuser you created | your own |

Sign-in pages: students `/students/login/`, landlords `/landlords/login/`,
admin `/admin/login/`. Django's own admin is at `/django-admin/`.

---

## 5. Prove the update actually arrived

```powershell
git log --oneline --grep="profile card"
```

It must print one line — the commit *"Keep profile card text inside the card on
narrow phones"* (`97a8971`). Nothing printed means the pull did not happen (run
`git pull origin master`). `git log -1 --oneline` shows the newest commit, which
may be newer than that one if the project moved on.

Then check the change itself:

1. Sign in as a student, open **My Profile**.
2. Press **F12** → click the phone/tablet icon (Ctrl+Shift+M) → pick **320 px**.
3. The labels and values (Full Name, Email Address, Student ID…) must stay
   **inside** the glass card. Before the update they ran about 15 px past its
   right edge.

---

## Common problems

| Message | Cause and fix |
|---|---|
| `Can't connect to server on '127.0.0.1' (10061)` | MySQL is not running — start it in XAMPP. |
| `Unknown database 'boarding_house_information_management_system'` | Create it in phpMyAdmin (step 2). |
| `Access denied for user 'root'@'localhost'` | You set a root password — put it in `.env` as `DJANGO_DB_PASSWORD`. |
| `no such table: core_...` | Run `python manage.py migrate` inside the activated venv. |
| `error: Microsoft Visual C++ 14.0 or greater is required` (while installing `mysqlclient`) | Install "Build Tools for Visual Studio", or use the pure-Python driver: `pip install PyMySQL`, then add `import pymysql` + `pymysql.install_as_MySQLdb()` as the first lines of `myproject/__init__.py`. |
| `Error: That port is already in use.` | Another server is running, or use `python manage.py runserver 8001`. |
| `'python' is not recognized` | Python is not on PATH — reinstall and tick "Add Python to PATH", or use `py -3.12` instead of `python`. |
| The page loads but looks unstyled, or the profile card still overflows | Hard refresh: **Ctrl+F5**. The browser caches CSS. |
| `git pull` says "Your local changes would be overwritten" | You edited tracked files. `git status`, then `git restore <file>` to discard your edit, or commit it first. |

---

## What to never commit

`.env`, `venv/`, `media/`, `db.sqlite3`, `backups/` — all of them are already in
`.gitignore` for a reason (secrets, 67 MB of photos, local machine paths).
If `git status` shows any of them, something is wrong; do not `git add .`.

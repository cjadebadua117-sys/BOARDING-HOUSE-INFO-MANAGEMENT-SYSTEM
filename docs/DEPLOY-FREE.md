# Deploying BHIMS for free

Goal: a public URL, Django + MariaDB, no monthly cost, no credit card.

## Will it survive closing the laptop?

| Setup | Laptop off | URL | Where the data lives |
|---|---|---|---|
| Cloudflare quick tunnel | **site goes down** | random, new on every run | your local XAMPP |
| Alwaysdata free plan | **stays up 24/7** | `<account>.alwaysdata.net` | MariaDB on their server |

Only the second one is hosting. The tunnel forwards requests to `127.0.0.1` on
this machine, so sleep, shutdown or a dropped connection takes the site offline.
A host runs the WSGI app and the database itself, which is what makes the site
independent of whether this laptop is on.

## Recommendation: Alwaysdata free plan

> **Updated 18 Oct 2026 — card required.** Alwaysdata's registration page now
> forces **credit or debit card validation** ("you must validate a credit or
> debit card" / "will not be charged any fees") before the account is created.
> The plan is still 0 €/month, but it is **not usable without a card**. The only
> no-card option in this repo is the Cloudflare tunnel in the next section —
> temporary, but free and account-free. The rest of this guide applies only if
> you (or someone helping you) have a card.

Alwaysdata is the only mainstream host where **Django, MariaDB and SSH are all
bundled on the free plan**. It is a full PaaS account, not a trial: 0 €/month,
"available for life" per their offers page.

What the free plan gives you (verified against Alwaysdata's own docs, Oct 2026):

| | Free plan |
|---|---|
| Disk | **1 GB SSD**, shared by code + databases + mail |
| Database | **MariaDB (MySQL-compatible)** included |
| Python | **3.14 / 3.13 / 3.12** — Django 6 needs 3.12+, so this works |
| Web server | uWSGI (WSGI app, no gunicorn needed) |
| SSH | Yes, on all plans |
| Address | `<account>.alwaysdata.net` — **custom domains need a paid plan** |
| Resources | 256 MB RAM, ¼ CPU |
| Backups | 3 days |
| Catch | Free accounts are suspended after **120 days without sign-in** (under 1 year old) |
| Card | **Required at signup** (validated, never charged) — see the note above |

This project's footprint: 14 MB collected static + 67 MB media + ~6 MB code +
a few MB of database ≈ **90 MB of the 1 GB**, so it fits comfortably.

Sources: [offers page](https://www.alwaysdata.com/en/offers/),
[Alwaysdata public cloud pricing](https://help.alwaysdata.com/en/docs/admin-billing/billing/public-cloud-prices/),
[Python configuration](https://help.alwaysdata.com/en/docs/web-hosting/languages/python/configuration/),
[MariaDB docs](https://help.alwaysdata.com/en/docs/web-hosting/databases/mariadb/),
[free-plan suspension rules](https://help.alwaysdata.com/en/docs/admin-billing/profile/suspension/).

The project is already shaped for this: `DEBUG` defaults to off, WhiteNoise
takes over static files when `DJANGO_WHITENOISE=1`, secrets come from env vars
or `.env`, and `myproject/urls.py` serves `/media/`. Production mode was booted
locally and verified (hashed static, gzip, media, all pages 200) before writing
this guide.

## Demo only: instant public URL from this laptop (no account)

A Cloudflare quick tunnel exposes the local production server on a public HTTPS
address with no signup. The address changes every time it starts and dies with
the process, so after a reboot you do **not** reopen the old link — you start a
new one:

```
double-click  start-public-demo.bat
```

That is the whole routine: it checks MySQL, starts the tunnel, waits for the new
`https://<random>.trycloudflare.com`, starts the production server wired to that
hostname, prints the address and copies it to the clipboard (it is also saved in
`.audit/public-url.txt`). Leave the window open while the site is live; Ctrl+C
or closing it takes the site down.

Under the hood (`tools/Start Public Demo.py`) it runs the same two pieces by
hand, in this order — the tunnel must exist first, because its random hostname
has to be in Django's allowlists before any POST works:

```bash
# 1. download once (~55 MB)
curl -L -o .audit/cloudflared.exe \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe

# 2. start the tunnel (it prints https://<random>.trycloudflare.com)
./.audit/cloudflared.exe tunnel --url http://127.0.0.1:8099 --no-autoupdate

# 3. in a second terminal: production server on :8099, using that hostname
DJANGO_DEBUG=0 DJANGO_WHITENOISE=1 \
DJANGO_ALLOWED_HOSTS="<random>.trycloudflare.com,127.0.0.1,localhost" \
DJANGO_CSRF_TRUSTED_ORIGINS="https://<random>.trycloudflare.com" \
BHIMS_PORT=8099 ./venv/Scripts/python.exe "Run Production Server.py"
```

Trade-offs: the URL is random and dies with the process, the PC must stay awake
and online, and everything (including the login pages) is public. Django's
`ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` must contain the tunnel host or every
POST fails with 403. Use this for demos, not as the permanent home.

## One-command deploy (recommended)

`tools/Deploy to Alwaysdata.py` performs everything from step 3 down over plain
SSH. You do the four things that need your login, once, in the admin panel:

1. Create the free account at <https://www.alwaysdata.com/en/offers/>.
2. **Databases → MariaDB → add a database**, plus a user, then grant that user
   access to the database. Note the host, database name, user and password.
3. **Advanced → Environments → add Python 3.13** (3.12+ all work; Django 6 needs
   3.12 minimum).
4. **Web → Sites → add a site**:

   | Field | Value |
   |---|---|
   | Type | Python WSGI |
   | Addresses | `<account>.alwaysdata.net` |
   | Working directory | `~/bhims` |
   | WSGI file | `myproject/wsgi.py` |
   | Virtualenv | `~/venv` |

   Add the site last: it points at `~/venv`, which the script creates. If the
   panel refuses a path that does not exist yet, run the script once (it will
   report that the URL is not answering yet), add the site, then re-run with
   `--skip-db --skip-media`.

Then, from the project folder:

```bash
venv\Scripts\python.exe "tools\Deploy to Alwaysdata.py" --account <account>
```

It asks for the database name/user/password once and remembers them in
`.deploy/config.json` (git-ignored, because it holds the password). After that it:

1. dumps the XAMPP database with `mysqldump` into `.deploy/bhims.sql`;
2. uploads `manage.py`, `requirements.txt`, `myproject/` and `core/` as a 3 MB
   archive (the 50 MB of drafts, diagrams and logs in this repo stay here);
3. creates `~/venv` on the server and installs `requirements.txt`, falling back
   to the pure-Python `PyMySQL` driver if `mysqlclient` will not compile;
4. imports the dump (it contains no `CREATE DATABASE`, so it lands in the
   database from step 2) and extracts the 61 MB photo archive into `media/`;
5. writes `~/bhims/.env` with `DEBUG=0`, WhiteNoise, HTTPS hardening and a fresh
   `SECRET_KEY` (never this laptop's key), then `chmod 600`;
6. runs `migrate` and `collectstatic`;
7. fetches the public URL and prints the status of `/`, `/listings/`,
   `/students/login/` and a hashed CSS file.

Dry run, and later code-only redeploys:

```bash
venv\Scripts\python.exe "tools\Deploy to Alwaysdata.py" --dry-run
venv\Scripts\python.exe "tools\Deploy to Alwaysdata.py" --skip-db --skip-media
```

If the first load redirects in a loop, the host is not sending
`X-Forwarded-Proto`; the script says so and the fix is `DJANGO_HTTPS=0` in
`~/bhims/.env` (everything else keeps working; the cookies just stop being
marked `Secure`).

The manual steps below are the same sequence done by hand — useful if SSH is
blocked on your network, or if a step needs debugging.

## Manual walkthrough (every step, by hand)

### 1. Account + database

1. Sign up at <https://www.alwaysdata.com/en/offers/> (free / Public Cloud).
2. Admin panel → **Databases → MariaDB → Add a database**. Create the database
   and a user, then grant that user access to it.
3. Copy the **host, port, database name, user and password shown on that page**.
   (Alwaysdata shows the exact values per account under Databases → MySQL; do
   not guess the hostname.)

### 2. Python environment

Admin panel → **Advanced → Environments → Add**: pick Python **3.13**, name it
`bhims`. This creates the interpreter your site will use.

### 3. Upload the code

Use SSH (`ssh <account>@ssh-<account>.alwaysdata.net`) or the web file manager.
Git Bash on Windows has `scp` but usually no `rsync`, so copy only the four
things the app needs:

```bash
ssh <account>@ssh-<account>.alwaysdata.net 'mkdir -p ~/bhims'
scp -r manage.py requirements.txt myproject core \
    <account>@ssh-<account>.alwaysdata.net:~/bhims/
```

Do **not** upload `.env`, `media/`, `static/`, `logs/`, `docs/` or `.git` — the
first two arrive in step 5, static is regenerated on the server, and the rest is
local-only material that would eat the 1 GB quota.

### 4. Install dependencies

```bash
cd ~/bhims
python -m venv ~/venv
~/venv/bin/pip install -r requirements.txt
```

`mysqlclient` compiles against MariaDB headers. If that build fails, use the
pure-Python driver instead:

```bash
~/venv/bin/pip install PyMySQL
```

and add this as the first two lines of `myproject/__init__.py`:

```python
import pymysql
pymysql.install_as_MySQLdb()
```

### 5. Import the database and upload photos

On Windows, dump your XAMPP database (MariaDB → MariaDB, so the dump imports
cleanly):

```bash
"C:\xampp\mysql\bin\mysqldump.exe" -u root -p \
  --default-character-set=utf8mb4 \
  boarding_house_information_management_system > bhims.sql
```

Upload and import it:

```bash
scp bhims.sql <account>@ssh-<account>.alwaysdata.net:~/
ssh <account>@ssh-<account>.alwaysdata.net
mysql -h <DB_HOST> -u <DB_USER> -p <DB_NAME> < ~/bhims.sql
```

Then push the uploaded photos (61 MB compressed, also without `rsync`):

```bash
tar -czf bhims-media.tar.gz -C media .
scp bhims-media.tar.gz <account>@ssh-<account>.alwaysdata.net:~/
ssh <account>@ssh-<account>.alwaysdata.net \
    'tar -xzf ~/bhims-media.tar.gz -C ~/bhims/media && rm ~/bhims-media.tar.gz'
rm bhims-media.tar.gz
```

### 6. Create the site

Admin panel → **Web → Sites → Add a site**:

| Field | Value |
|---|---|
| Type | **Python WSGI** |
| Addresses | `<account>.alwaysdata.net` |
| Working directory | `~/bhims` |
| WSGI file | `myproject/wsgi.py` |
| Virtualenv | `~/venv` |

HTTPS on the `.alwaysdata.net` address is provisioned automatically.

### 7. Environment variables

Create `~/bhims/.env` over SSH (`chmod 600`) — `settings.py` already reads this
file, and it is git-ignored. Using a file (not just the panel) matters because
`manage.py` commands run over SSH do not see the site panel's variables.

```ini
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<paste 64 random characters>
DJANGO_ALLOWED_HOSTS=<account>.alwaysdata.net
DJANGO_CSRF_TRUSTED_ORIGINS=https://<account>.alwaysdata.net
DJANGO_HTTPS=1
DJANGO_WHITENOISE=1
DJANGO_DB_NAME=<from step 1>
DJANGO_DB_USER=<from step 1>
DJANGO_DB_PASSWORD=<from step 1>
DJANGO_DB_HOST=<from step 1>
DJANGO_DB_PORT=3306
```

Generate a key with `python -c "import secrets;print(secrets.token_urlsafe(64))"`.
Never upload your laptop's `.env`: a different `SECRET_KEY` on the server is
correct, it only invalidates old sessions.

`DJANGO_HTTPS=1` switches on `SECURE_SSL_REDIRECT`, secure cookies, HSTS and the
`X-Forwarded-Proto` header. If the first load shows a redirect loop, Alwaysdata
is not sending that header — drop `DJANGO_HTTPS=1` and keep plain HTTP until you
confirm; everything else keeps working.

### 8. Migrate and collect static

```bash
cd ~/bhims
~/venv/bin/python manage.py migrate
~/venv/bin/python manage.py collectstatic --noinput
~/venv/bin/python manage.py createsuperuser
```

### 9. Verify (do not skip)

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://<account>.alwaysdata.net/
curl -s https://<account>.alwaysdata.net/ | grep -o '/static/[^"]*\.css' | head -1
```

Then in a browser: landing page renders with styling, a listing photo loads
(`/media/...`), student + landlord + admin logins work with real accounts, the
student dashboard shows the inquiries you had locally, and the admin dashboard
shows correct counts. If static 404s, `collectstatic` did not run with
`DJANGO_WHITENOISE=1`.

## Keeping the live site in step with this laptop

- **Code changed here:** `venv\Scripts\python.exe "tools\Deploy to Alwaysdata.py"
  --skip-db --skip-media` (re-uploads 3 MB and re-runs migrate + collectstatic).
- **Data changed here** (new rooms, inquiries, users): run the script with no
  flags; it re-dumps the database and re-imports it. The import replaces rows
  in the live database, so anything created *on the live site* between deploys
  is lost — tell users before you refresh, or stop editing locally and treat the
  server as the source of truth.
- **Photos:** included in the same run; `--skip-media` leaves the existing ones.

## What "free" costs you

- No custom domain — the URL is `<account>.alwaysdata.net`.
- The URL is fixed and the site answers while this laptop is off, asleep or
  offline — that is the whole point of moving it off the tunnel.
- 256 MB RAM / ¼ CPU: fine for a class demo, not for hundreds of concurrent users.
- Free tier is for personal projects; a public production service is against the
  spirit of the plan.
- Sign in to the panel at least every ~120 days or the account is suspended.
- No email sending out of the box; password-reset emails need an SMTP provider
  (e.g. a free transactional-email tier) and the `DJANGO_EMAIL_*` variables.

## Alternatives, and why they are not the default

| Option | Verdict |
|---|---|
| **Oracle Cloud Always Free VM** | Genuinely free forever and the only free route to your own domain, but signup requires a **card**, and you administer nginx + gunicorn + MariaDB + TLS yourself. 2 OCPU / 12 GB ARM, 200 GB disk. Best if you want a real `.com`-style URL and don't mind Linux admin. |
| **Render free** | No free MySQL. Free managed DB is **PostgreSQL and expires 30 days after creation**; free web services sleep after 15 min with ~1 min cold start. Would need a MySQL→Postgres migration *and* a new DB every month. |
| **PythonAnywhere free** | **MySQL is no longer included for accounts created after Jan 2026** (moved to the Developer tier), 512 MB disk, web apps expire after a month unused. Would force SQLite. |
| **Vercel / Netlify** | Serverless front-end hosts; they cannot run a long-lived Django process or a MySQL server. |

## Rollback

Nothing here touches your local setup. Keep the XAMPP database and `media/`
folder as the source of truth; to refresh the live site, re-dump the DB and
re-run steps 5 and 8 (or just run the deploy script again).

To take the site down, delete the site entry in **Web → Sites**; to remove
everything including the database, delete the Alwaysdata account. Neither
action affects this laptop.

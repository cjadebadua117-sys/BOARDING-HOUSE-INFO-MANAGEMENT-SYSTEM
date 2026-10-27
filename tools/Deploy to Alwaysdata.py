r"""BHIMS deployer — puts the site on Alwaysdata's free plan and leaves it there.

Why this exists
---------------
`cloudflared` only *forwards* to this laptop, so the site dies the moment the
machine sleeps.  A real host runs the WSGI app itself, keeps MariaDB on its own
disk, and answers 24/7 whether the laptop is on or off.  This script does the
whole move: dump the XAMPP database, upload the code, build the virtualenv,
import the data, upload the photos, write the server-side .env, migrate,
collectstatic, then check the public URL.

What you must do by hand (once — only you can, it needs your email):
    1. Create the free account at https://www.alwaysdata.com/en/offers/
    2. Panel -> Databases -> MariaDB -> add a database + a user, and grant it
       access to the database.  Note the host/user/password it shows.
    3. Panel -> Advanced -> Environments -> add a Python 3.13 environment.
    4. Panel -> Web -> Sites -> add a site:
           type              Python WSGI
           addresses         <account>.alwaysdata.net
           working directory ~/bhims
           WSGI file         myproject/wsgi.py
           virtualenv        ~/venv
       (Creating the site last is deliberate: it needs ~/venv, which this
       script creates.)

Usage (from the project root):
    venv\\Scripts\\python.exe "tools\\Deploy to Alwaysdata.py" --account myschool
    venv\\Scripts\\python.exe "tools\\Deploy to Alwaysdata.py"            # reuse saved answers
    venv\\Scripts\\python.exe "tools\\Deploy to Alwaysdata.py" --dry-run
    venv\\Scripts\\python.exe "tools\\Deploy to Alwaysdata.py" --skip-db --skip-media

Answers are remembered in .deploy/config.json (git-ignored, because it holds the
database password) so a later code-only redeploy is one command.

Deleting the account is the undo button: nothing on this laptop is modified
except .deploy/ (dumps and archives) and, optionally, .gitignore.
"""
import argparse
import getpass
import json
import os
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEPLOY_DIR = BASE_DIR / '.deploy'
CONFIG_PATH = DEPLOY_DIR / 'config.json'

# Exactly what the server needs to run. An allowlist, not a denylist: the repo
# folder also holds 50 MB of audits, diagrams, exports and .docx drafts, and a
# 1 GB free quota cannot afford to carry them.
DEPLOY_FILES = ('manage.py', 'requirements.txt', 'myproject', 'core')
IGNORED_NAMES = {'__pycache__', '.DS_Store', 'Thumbs.db', '.env', '.env.example'}
IGNORED_SUFFIXES = {'.pyc', '.pyo'}

MYSQLDUMP_CANDIDATES = [
    Path(r'C:\xampp\mysql\bin\mysqldump.exe'),
    Path('C:/Program Files/MySQL/MySQL Server 8.0/bin/mysqldump.exe'),
]

DRY_RUN = False


# --------------------------------------------------------------------------- #
# plumbing
# --------------------------------------------------------------------------- #
def say(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def warn(msg):
    print(f'!! {msg}', flush=True)


def run(cmd, *, stdin_text=None, stdin_file=None, check=True, quiet=False):
    """Run a command, streaming its output. Returns the exit code."""
    if DRY_RUN:
        shown = ' '.join(str(c) for c in cmd)
        print(f'    (dry-run) {shown}')
        if stdin_text:
            for line in stdin_text.strip().splitlines():
                print(f'              | {line}')
        return 0
    kwargs = {}
    if stdin_text is not None:
        kwargs['input'] = stdin_text
        kwargs['text'] = True
    elif stdin_file is not None:
        kwargs['stdin'] = open(stdin_file, 'rb')
    try:
        result = subprocess.run(cmd, capture_output=quiet, **kwargs)
    finally:
        if stdin_file is not None:
            kwargs['stdin'].close()
    if check and result.returncode != 0:
        raise SystemExit(f'!! command failed ({result.returncode}): {" ".join(str(c) for c in cmd)}')
    return result.returncode


def ssh(script, check=True):
    """Run a bash script on the server. One process, so quoting never bites."""
    cmd = [
        'ssh', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=20',
        CFG['ssh_host'], 'bash', '-s',
    ]
    return run(cmd, stdin_text=script, check=check)


def scp(local, remote, check=True):
    cmd = [
        'scp', '-q', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=20',
        str(local), f'{CFG["ssh_host"]}:{remote}',
    ]
    return run(cmd, check=check)


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #
CFG = {}


def load_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            warn(f'{CONFIG_PATH.name} is unreadable — asking again.')
    return {}


def save_config(cfg):
    DEPLOY_DIR.mkdir(exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass  # Windows: best effort only
    say(f'answers saved to .deploy/{CONFIG_PATH.name} (git-ignored)')


def ask(label, key, args, secret=False):
    """args value > saved config > interactive prompt."""
    value = getattr(args, key, None)
    if value:
        return value
    if CFG.get(key):
        return CFG[key]
    default = CFG.get(key)
    while True:
        if secret:
            value = getpass.getpass(f'{label}: ')
        else:
            suffix = f' [{default}]' if default else ''
            value = input(f'{label}{suffix}: ').strip() or (default or '')
        if value:
            return value
        print('   required.')


def resolve(args):
    CFG.update(load_config())
    account = ask('Alwaysdata account name', 'account', args)

    CFG['account'] = account
    CFG['ssh_host'] = (
        args.ssh_host or CFG.get('ssh_host') or f'{account}@ssh-{account}.alwaysdata.net'
    )
    CFG['site_host'] = args.site_host or CFG.get('site_host') or f'{account}.alwaysdata.net'
    CFG['db_name'] = ask('Database name (panel -> Databases)', 'db_name', args)
    CFG['db_user'] = ask('Database user', 'db_user', args)
    CFG['db_password'] = ask('Database password', 'db_password', args, secret=True)
    CFG['db_host'] = (
        args.db_host or CFG.get('db_host') or f'mysql-{account}.alwaysdata.net'
    )
    CFG['db_port'] = args.db_port or CFG.get('db_port') or '3306'
    CFG['python'] = args.python or CFG.get('python') or 'python3.13'
    CFG['remote_dir'] = CFG.get('remote_dir') or f'/home/{account}/bhims'
    if not DRY_RUN:
        save_config(dict(CFG))


# --------------------------------------------------------------------------- #
# steps
# --------------------------------------------------------------------------- #
def local_db_settings():
    """Read the XAMPP credentials from .env / defaults, same as the app does."""
    values = {}
    env_path = BASE_DIR / '.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                values[key.strip()] = value.strip()
    return {
        'name': values.get('DJANGO_DB_NAME', 'boarding_house_information_management_system'),
        'user': values.get('DJANGO_DB_USER', 'root'),
        'password': values.get('DJANGO_DB_PASSWORD', ''),
        'host': values.get('DJANGO_DB_HOST', '127.0.0.1'),
        'port': values.get('DJANGO_DB_PORT', '3306'),
    }


def dump_database():
    exe = next((c for c in MYSQLDUMP_CANDIDATES if c.exists()), None)
    if not exe and not shutil.which('mysqldump'):
        raise SystemExit('!! mysqldump.exe not found — install XAMPP MySQL or add mysqldump to PATH.')
    exe = str(exe or 'mysqldump')

    db = local_db_settings()
    out = DEPLOY_DIR / 'bhims.sql'
    DEPLOY_DIR.mkdir(exist_ok=True)
    say(f'dumping local database "{db["name"]}" ...')

    cmd = [
        exe, f'--host={db["host"]}', f'--port={db["port"]}', f'--user={db["user"]}',
        '--single-transaction', '--quick', '--routines', '--triggers',
        '--default-character-set=utf8mb4', db['name'],
    ]
    env = os.environ.copy()
    if db['password']:
        env['MYSQL_PWD'] = db['password']  # keeps it out of the process list
    if DRY_RUN:
        print(f'    (dry-run) {" ".join(cmd)} > .deploy/bhims.sql')
        return out

    with open(out, 'wb') as fh:
        result = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, env=env)
    if result.returncode != 0:
        message = result.stderr.decode(errors='ignore').strip()[:400]
        raise SystemExit(f'!! mysqldump failed: {message}\n   Is XAMPP MySQL running?')
    say(f'database dumped -> .deploy/bhims.sql ({out.stat().st_size // 1024} KB)')
    return out


def archive_tree(source, out, include=None, label='code'):
    """tar.gz of `include` entries inside `source` (or all of it).

    Portable by design: Windows bins have no rsync, but tar + scp always exist.
    """
    source = Path(source)
    out.parent.mkdir(parents=True, exist_ok=True)
    roots = [source / name for name in (include or ('.',))]
    missing = [str(root.relative_to(source)) for root in roots if not root.exists()]
    if missing:
        raise SystemExit(f'!! not found, cannot deploy: {missing}')

    files = []
    for root in roots:
        if root.is_file():
            files.append(root)
            continue
        files.extend(p for p in root.rglob('*') if p.is_file())
    files = [
        p for p in files
        if not any(part in IGNORED_NAMES for part in p.relative_to(source).parts)
        and p.suffix not in IGNORED_SUFFIXES
    ]

    say(f'packing {label} ({len(files)} files) ...')
    if DRY_RUN:
        print(f'    (dry-run) tar -> .deploy/{out.name}')
        return out
    with tarfile.open(out, 'w:gz') as tar:
        for path in files:
            tar.add(path, arcname=str(path.relative_to(source)))
    say(f'{label} packed: {out.stat().st_size // 1024} KB')
    return out


def remote_prepare(code_tar):
    say('uploading code + building the virtualenv on the server ...')
    scp(code_tar, '~/bhims-code.tar.gz')
    python_candidates = ' '.join(
        dict.fromkeys([CFG['python'], 'python3.13', 'python3.12', 'python3'])
    )
    script = f"""
set -euo pipefail
mkdir -p "$HOME/bhims" "$HOME/bhims/media"
tar -xzf "$HOME/bhims-code.tar.gz" -C "$HOME/bhims"
rm -f "$HOME/bhims-code.tar.gz"

# Pick any interpreter >= 3.12 (Django 6 requirement), preferring the one the
# account environment provides.
pick_python() {{
  for c in {python_candidates}; do
    command -v "$c" >/dev/null 2>&1 || continue
    v=$("$c" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null) || continue
    case "$v" in
      3.1[2-9]|3.[2-9][0-9]) echo "$c"; return 0 ;;
    esac
  done
  return 1
}}
PY=$(pick_python) || {{
  echo "!! No Python 3.12+ found. Panel -> Advanced -> Environments -> add Python 3.13, then re-run."
  exit 1
}}
echo "using $($PY --version 2>&1)"
if [ ! -x "$HOME/venv/bin/python" ]; then
  "$PY" -m venv "$HOME/venv"
fi
"$HOME/venv/bin/python" -c 'import sys; print("server python:", sys.version.split()[0])'

"$HOME/venv/bin/pip" install --upgrade pip -q
if ! "$HOME/venv/bin/pip" install -q -r "$HOME/bhims/requirements.txt"; then
  echo "!! mysqlclient build failed - falling back to the pure-Python driver"
  "$HOME/venv/bin/pip" install -q PyMySQL
  if ! grep -q pymysql "$HOME/bhims/myproject/__init__.py" 2>/dev/null; then
    printf 'import pymysql\\npymysql.install_as_MySQLdb()\\n\\n' \\
      | cat - "$HOME/bhims/myproject/__init__.py" > "$HOME/bhims/myproject/__init__.py.new"
    mv "$HOME/bhims/myproject/__init__.py.new" "$HOME/bhims/myproject/__init__.py"
  fi
fi
"$HOME/venv/bin/python" -c 'import django; print("django", django.get_version())'
"""
    ssh(script)


def upload_database(sql_path):
    say('importing the database on the server ...')
    scp(sql_path, '~/bhims.sql')
    cnf = DEPLOY_DIR / '.my.cnf'
    cnf.write_text(
        '[client]\n'
        f'user={CFG["db_user"]}\n'
        f'password={CFG["db_password"]}\n'
        f'host={CFG["db_host"]}\n'
        f'port={CFG["db_port"]}\n',
        encoding='utf-8',
    )
    scp(cnf, '~/.bhims-mysql.cnf')
    cnf.unlink(missing_ok=True)  # keep the password out of the repo folder
    script = f"""
set -euo pipefail
chmod 600 "$HOME/.bhims-mysql.cnf"
mysql --defaults-extra-file="$HOME/.bhims-mysql.cnf" {CFG['db_name']} < "$HOME/bhims.sql"
rm -f "$HOME/bhims.sql" "$HOME/.bhims-mysql.cnf"
echo "database imported"
"""
    ssh(script)


def upload_media():
    media = BASE_DIR / 'media'
    if not media.exists() or not any(media.iterdir()):
        warn('media/ is empty — nothing to upload.')
        return
    tar_path = ARCHIVE_DIR / 'bhims-media.tar.gz'
    archive_tree(media, tar_path, label='photos')
    say('uploading photos ...')
    scp(tar_path, '~/bhims-media.tar.gz')
    ssh(
        'set -euo pipefail\n'
        'tar -xzf "$HOME/bhims-media.tar.gz" -C "$HOME/bhims/media"\n'
        'rm -f "$HOME/bhims-media.tar.gz"\n'
        'echo "media extracted: $(find "$HOME/bhims/media" -type f | wc -l) files"\n'
    )
    if not DRY_RUN:
        tar_path.unlink(missing_ok=True)


def write_env_file():
    say('writing the server-side .env ...')
    env_path = DEPLOY_DIR / '.env.remote'
    env_path.write_text(
        '# Generated by tools/Deploy to Alwaysdata.py - do not commit.\n'
        'DJANGO_DEBUG=0\n'
        f'DJANGO_SECRET_KEY={secrets.token_urlsafe(64)}\n'
        f'DJANGO_ALLOWED_HOSTS={CFG["site_host"]},localhost,127.0.0.1\n'
        f'DJANGO_CSRF_TRUSTED_ORIGINS=https://{CFG["site_host"]}\n'
        'DJANGO_HTTPS=1\n'
        'DJANGO_WHITENOISE=1\n'
        f'DJANGO_DB_NAME={CFG["db_name"]}\n'
        f'DJANGO_DB_USER={CFG["db_user"]}\n'
        f'DJANGO_DB_PASSWORD={CFG["db_password"]}\n'
        f'DJANGO_DB_HOST={CFG["db_host"]}\n'
        f'DJANGO_DB_PORT={CFG["db_port"]}\n',
        encoding='utf-8',
    )
    scp(env_path, '~/bhims/.env')
    env_path.unlink(missing_ok=True)
    ssh('chmod 600 "$HOME/bhims/.env" && echo ".env written (600)"')


def migrate():
    say('running migrations + collectstatic ...')
    ssh(f"""
set -euo pipefail
cd "$HOME/bhims"
"$HOME/venv/bin/python" manage.py migrate --noinput
"$HOME/venv/bin/python" manage.py collectstatic --noinput
echo "static files: $(find "$HOME/bhims/static" -type f 2>/dev/null | wc -l)"
""")


def http_status(url):
    request = urllib.request.Request(url, method='GET', headers={'User-Agent': 'bhims-deploy/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.status, response.read(20000).decode('utf-8', 'ignore')
    except urllib.error.HTTPError as exc:
        return exc.code, ''
    except Exception as exc:  # network, TLS, DNS, redirect loop
        return None, str(exc)


def verify():
    """Fetch the real URL. A 301/302 instead of 200 means HTTPS detection is wrong."""
    base = f'https://{CFG["site_host"]}'
    say(f'checking {base} ...')
    if DRY_RUN:
        print(f'    (dry-run) GET {base}/')
        return True

    status, body = None, ''
    for attempt in range(1, 4):
        status, body = http_status(f'{base}/')
        if status == 200:
            break
        say(f'   attempt {attempt}: {status or "no answer"} - the site may still be starting')
        if attempt < 3:
            time.sleep(5)

    if status != 200:
        if status in (301, 302, 307, 308):
            warn('the site redirects forever: the host is not sending X-Forwarded-Proto.')
            warn(f'set DJANGO_HTTPS=0 in the .env on the server and reload {base}/')
        else:
            warn(f'{base} answered {status or "nothing"}')
        return False

    checks = {'/': 200, '/listings/': None, '/students/login/': None}
    for path in ('/listings/', '/students/login/'):
        checks[path] = http_status(base + path)[0]

    asset = next(
        (chunk.split('"')[0] for chunk in body.split('href="')[1:]
         if chunk.startswith('/static/') and chunk.split('"')[0].endswith('.css')),
        None,
    )
    if asset:
        checks[asset] = http_status(base + asset)[0]

    say('pages: ' + ', '.join(f'{k} -> {v}' for k, v in checks.items()))
    return all(v == 200 for v in checks.values())


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def parse_args():
    parser = argparse.ArgumentParser(description="Deploy BHIMS to Alwaysdata's free plan.")
    parser.add_argument('--account', help='Alwaysdata account name (e.g. myschool)')
    parser.add_argument('--ssh-host', help='default: <account>@ssh-<account>.alwaysdata.net')
    parser.add_argument('--site-host', help='default: <account>.alwaysdata.net')
    parser.add_argument('--db-name')
    parser.add_argument('--db-user')
    parser.add_argument('--db-password')
    parser.add_argument('--db-host', help='default: mysql-<account>.alwaysdata.net')
    parser.add_argument('--db-port', default='3306')
    parser.add_argument('--python', default='python3.13', help='remote interpreter for the venv')
    parser.add_argument('--skip-db', action='store_true', help='keep the server database as-is')
    parser.add_argument('--skip-media', action='store_true', help='do not re-upload photos')
    parser.add_argument('--dry-run', action='store_true', help='print every step, touch nothing')
    parser.add_argument('--forget', action='store_true', help='ignore saved answers')
    return parser.parse_args()


def main():
    global DRY_RUN
    args = parse_args()
    DRY_RUN = args.dry_run
    if args.forget and CONFIG_PATH.exists():
        CONFIG_PATH.unlink()

    if DRY_RUN:
        say('DRY RUN - nothing is uploaded, the server is not touched.')
    resolve(args)
    ARCHIVE_DIR.mkdir(exist_ok=True)

    say(f'target: {CFG["ssh_host"]}  ->  https://{CFG["site_host"]}')
    sql = None if args.skip_db else dump_database()
    code_tar = archive_tree(BASE_DIR, ARCHIVE_DIR / 'bhims-code.tar.gz', DEPLOY_FILES, 'code')

    remote_prepare(code_tar)
    if sql:
        upload_database(sql)
    if not args.skip_media:
        upload_media()
    write_env_file()
    migrate()

    ok = verify()
    if DRY_RUN:
        print('\n   dry run finished: the steps above are what a real run would execute.')
        return 0
    if ok:
        print()
        say(f'LIVE: https://{CFG["site_host"]}')
        print('   The server keeps running when this laptop is off - that is the point.')
        print('   Redeploy code only:  --skip-db --skip-media')
    else:
        warn('the deploy ran, but the URL did not answer 200 yet.')
        print('   Most likely the Alwaysdata site entry is missing or still starting:')
        print(f'   panel -> Web -> Sites -> Python WSGI, WSGI file myproject/wsgi.py,')
        print(f'   working directory {CFG["remote_dir"]}, virtualenv ~/venv,')
        print(f'   address {CFG["site_host"]}.  Re-run with --skip-db --skip-media.')
        print('   Still redirecting in a loop? Set DJANGO_HTTPS=0 in ~/bhims/.env.')

    if not DRY_RUN:
        for leftover in ARCHIVE_DIR.glob('*.tar.gz'):
            leftover.unlink(missing_ok=True)
        if sql:
            sql.unlink(missing_ok=True)
    return 0


ARCHIVE_DIR = DEPLOY_DIR

if __name__ == '__main__':
    sys.exit(main())

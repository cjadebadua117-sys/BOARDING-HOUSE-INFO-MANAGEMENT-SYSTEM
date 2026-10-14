r"""BHIMS backup tool — database + uploaded media.

Usage (from the project root):
    venv\\Scripts\\python.exe "tools\\Database Backup.py"

Creates ./backups/bhims-db-YYYYMMDD-HHMM.sql and
        ./backups/bhims-media-YYYYMMDD-HHMM.zip

Schedule it daily with Windows Task Scheduler:
    schtasks /Create /TN "BHIMS backup" /SC DAILY /ST 02:00 /TR ^
      "C:\path\to\venv\Scripts\python.exe" "C:\path\to\tools\Database Backup.py"

Credentials come from the environment (.env is loaded), so no password is
ever written to disk in the command line or the archive.
"""
import os
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BASE_DIR / 'backups'


def _load_env():
    env_path = BASE_DIR / '.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())


def backup_database():
    name = os.environ.get('DJANGO_DB_NAME', 'boarding_house_system')
    user = os.environ.get('DJANGO_DB_USER', 'root')
    password = os.environ.get('DJANGO_DB_PASSWORD', '')
    host = os.environ.get('DJANGO_DB_HOST', '127.0.0.1')
    port = os.environ.get('DJANGO_DB_PORT', '3306')
    stamp = datetime.now().strftime('%Y%m%d-%H%M')
    out = BACKUP_DIR / f'bhims-db-{stamp}.sql'

    candidates = [
        Path(r'C:\xampp\mysql\bin\mysqldump.exe'),
        Path('C:/Program Files/MySQL/MySQL Server 8.0/bin/mysqldump.exe'),
    ]
    exe = next((c for c in candidates if c.exists()), None)
    if not exe:
        print('!! mysqldump.exe not found — skipped the database dump.')
        return None

    cmd = [
        str(exe), f'--host={host}', f'--port={port}', f'--user={user}',
        '--single-transaction', '--routines', '--triggers', name,
    ]
    env = os.environ.copy()
    if password:
        # Pass via MYSQL_PWD so the password never appears in the process list.
        env['MYSQL_PWD'] = password
    with open(out, 'w', encoding='utf-8') as fh:
        result = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, env=env)
    if result.returncode != 0:
        print(f'!! mysqldump failed: {result.stderr.decode(errors="ignore")[:300]}')
        return None
    print(f'[ok] database -> {out.name} ({out.stat().st_size // 1024} KB)')
    return out


def backup_media():
    media = BASE_DIR / 'media'
    if not media.exists():
        print('!! media/ not found — skipped.')
        return None
    stamp = datetime.now().strftime('%Y%m%d-%H%M')
    out = BACKUP_DIR / f'bhims-media-{stamp}.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in media.rglob('*'):
            if path.is_file():
                zf.write(path, path.relative_to(media))
    print(f'[ok] media    -> {out.name} ({out.stat().st_size // 1024} KB)')
    return out


def main():
    BACKUP_DIR.mkdir(exist_ok=True)
    _load_env()
    print('BHIMS backup starting...')
    backup_database()
    backup_media()
    print('Done. Backups live in ./backups/ (add it to .gitignore).')


if __name__ == '__main__':
    sys.exit(main())

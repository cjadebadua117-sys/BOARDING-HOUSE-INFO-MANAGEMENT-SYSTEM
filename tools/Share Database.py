r"""BHIMS share tool - dump the database and lock it with a password.

Usage (from the project root):
    venv\Scripts\python.exe "tools\Share Database.py"

Writes, into ./backups/:
    bhims-share-YYYYMMDD-HHMM.sql       the plain dump (keep this one to yourself)
    bhims-share-YYYYMMDD-HHMM.sql.enc   the same dump, AES-256 encrypted

The password is typed at the prompt (twice) and is never written to disk, to the
command line, or to your shell history. Send the .enc file and the password over
TWO DIFFERENT channels - e.g. the file by Google Drive/email and the password by
SMS or in person.

The dump is produced with the same credentials as tools/Database Backup.py:
they come from .env (or the environment), so no password ever appears in the
command line. Only "tools/Database Backup.py" and this file need mysqldump.exe,
which ships with XAMPP at C:\xampp\mysql\bin\mysqldump.exe.

The person you send it to restores it like this (they need OpenSSL, which comes
with Git for Windows):

    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 ^
      -in bhims-share-YYYYMMDD-HHMM.sql.enc -out bhims-share.sql

then, in phpMyAdmin:

    CREATE DATABASE boarding_house_information_management_system;
    -- select that database, then Import -> bhims-share.sql
"""
import getpass
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BASE_DIR / 'backups'

# Cipher settings, shared with the recipient's decrypt command below. Changing
# them here means changing the documented command too.
CIPHER = 'aes-256-cbc'
ITER = '200000'


def _load_env():
    env_path = BASE_DIR / '.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())


def _mysqldump_exe():
    candidates = [
        Path(r'C:\xampp\mysql\bin\mysqldump.exe'),
        Path('C:/Program Files/MySQL/MySQL Server 8.0/bin/mysqldump.exe'),
    ]
    return next((c for c in candidates if c.exists()), None)


def dump_database(stamp):
    """Run mysqldump into ./backups/ and return the path, or None on failure."""
    name = os.environ.get('DJANGO_DB_NAME', 'boarding_house_system')
    user = os.environ.get('DJANGO_DB_USER', 'root')
    password = os.environ.get('DJANGO_DB_PASSWORD', '')
    host = os.environ.get('DJANGO_DB_HOST', '127.0.0.1')
    port = os.environ.get('DJANGO_DB_PORT', '3306')

    exe = _mysqldump_exe()
    if not exe:
        print('!! mysqldump.exe not found - is XAMPP installed?')
        return None

    out = BACKUP_DIR / f'bhims-share-{stamp}.sql'
    cmd = [
        str(exe), f'--host={host}', f'--port={port}', f'--user={user}',
        '--single-transaction', '--routines', '--triggers', name,
    ]
    env = os.environ.copy()
    if password:
        env['MYSQL_PWD'] = password  # keeps the password out of the process list
    with open(out, 'w', encoding='utf-8') as fh:
        result = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, env=env)
    if result.returncode != 0:
        print(f'!! mysqldump failed: {result.stderr.decode(errors="ignore")[:300]}')
        return None
    print(f'[ok] dump     -> {out.name} ({out.stat().st_size // 1024} KB)')
    return out


def encrypt(src, password):
    """Encrypt src with OpenSSL AES-256 into src + '.enc'."""
    dst = src.with_suffix(src.suffix + '.enc')
    cmd = [
        'openssl', 'enc', f'-{CIPHER}', '-pbkdf2', '-iter', ITER, '-salt',
        '-in', str(src), '-out', str(dst), '-pass', 'stdin',
    ]
    try:
        result = subprocess.run(cmd, input=(password + '\n').encode(), stderr=subprocess.PIPE)
    except FileNotFoundError:
        print('!! openssl not found on PATH. Install Git for Windows, or encrypt the')
        print('   .sql yourself with 7-Zip (AES-256) before sending it.')
        return None
    if result.returncode != 0:
        print(f'!! openssl failed: {result.stderr.decode(errors="ignore")[:300]}')
        return None
    print(f'[ok] locked   -> {dst.name} ({dst.stat().st_size // 1024} KB)')
    return dst


def read_password():
    """Password from the environment (for scripts) or typed twice at a prompt."""
    env_pw = os.environ.get('BHIMS_SHARE_PASSWORD')
    if env_pw:
        return env_pw
    first = getpass.getpass('Password for the archive: ')
    if not first:
        print('!! empty password - refusing to encrypt with no protection.')
        return None
    if first != getpass.getpass('Repeat the password: '):
        print('!! the two passwords did not match.')
        return None
    return first


def main():
    BACKUP_DIR.mkdir(exist_ok=True)
    _load_env()

    stamp = datetime.now().strftime('%Y%m%d-%H%M')
    print('BHIMS share: dumping the database...')
    plain = dump_database(stamp)
    if not plain or not plain.exists() or plain.stat().st_size == 0:
        print('!! nothing to share - the dump is empty or missing.')
        return 1

    password = read_password()
    if not password:
        return 1

    locked = encrypt(plain, password)
    if not locked:
        return 1

    print()
    print('Send these to your classmate, by two different channels:')
    print(f'  1. the file     {locked.name}')
    print('  2. the password (SMS, in person - never with the file)')
    print()
    print('They decrypt it with:')
    print(f'  openssl enc -d -{CIPHER} -pbkdf2 -iter {ITER} '
          f'-in {locked.name} -out bhims-share.sql')
    print('then import bhims-share.sql into a database named in the dump.')
    print()
    print(f'The plain {plain.name} is unencrypted and stays on this machine only.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

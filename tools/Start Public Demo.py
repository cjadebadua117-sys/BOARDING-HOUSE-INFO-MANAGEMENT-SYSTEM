r"""Start the public demo: Cloudflare tunnel + Django production server.

After a reboot the laptop has nothing running, and the old trycloudflare.com
address is gone (quick tunnels are random and die with the process). This
script puts the whole stack back up in one step and prints the new address:

    venv\Scripts\python.exe "tools\Start Public Demo.py"
    start-public-demo.bat            (double-click equivalent)

What it does:
1. checks that MySQL is running (the app cannot serve anything without it);
2. clears a stale server off the port;
3. starts cloudflared, waits for its new https://<random>.trycloudflare.com;
4. starts "Run Production Server.py" with DEBUG off, WhiteNoise on, and that
   hostname in DJANGO_ALLOWED_HOSTS / DJANGO_CSRF_TRUSTED_ORIGINS;
5. waits for HTTP 200 through the tunnel and prints the URL (also saved to
   .audit/public-url.txt and copied to the clipboard).

It keeps running until Ctrl+C, which stops both processes. Nothing is installed
and no account is needed; the trade-off is that the address is temporary and
only exists while this window stays open.

This is for demos. For a URL that survives closing the laptop, see
docs/DEPLOY-FREE.md (Alwaysdata free plan).
"""
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
AUDIT = BASE_DIR / '.audit'
CLOUDFLARED = AUDIT / 'cloudflared.exe'
TUNNEL_LOG = AUDIT / 'tunnel.log'
SERVER_LOG = AUDIT / 'server.log'
URL_FILE = AUDIT / 'public-url.txt'
CLOUDFLARED_URL = ('https://github.com/cloudflare/cloudflared/releases/latest/'
                   'download/cloudflared-windows-amd64.exe')
URL_PATTERN = re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com')
PREFERRED_PORT = 8099

# XAMPP's own MySQL, started without a console window so the demo needs only
# this one double-click. It is left running on exit: it belongs to the user,
# not to this script.
XAMPP_MYSQLD = Path('C:/xampp/mysql/bin/mysqld.exe')
XAMPP_MY_INI = Path('C:/xampp/mysql/bin/my.ini')


def say(message=''):
    print(message, flush=True)


def mysql_running(host='127.0.0.1', port=3306, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def free_port(start=PREFERRED_PORT, tries=12):
    """First port in the range nothing is listening on."""
    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('127.0.0.1', port))
            except OSError:
                continue
            return port
    raise SystemExit(f'!! no free port in {start}-{start + tries}')


def start_mysql(deadline=25):
    """Wake XAMPP's MySQL if it is not already listening."""
    if mysql_running():
        say('  mysql     already running')
        return True
    if not (XAMPP_MYSQLD.exists() and XAMPP_MY_INI.exists()):
        return False
    say('  mysql     starting it for you ...')
    flags = 0
    if os.name == 'nt':
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(
            [str(XAMPP_MYSQLD), f'--defaults-file={XAMPP_MY_INI}', '--standalone'],
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        say(f'  mysql     could not start: {exc}')
        return False
    end = time.time() + deadline
    while time.time() < end:
        if mysql_running(timeout=1.0):
            say('  mysql     up')
            return True
        time.sleep(0.7)
    return False


def ensure_cloudflared():
    if CLOUDFLARED.exists():
        return
    say('  cloudflared is missing, downloading it once (~55 MB) ...')
    import urllib.request as request
    AUDIT.mkdir(exist_ok=True)
    with request.urlopen(CLOUDFLARED_URL, timeout=180) as response, open(CLOUDFLARED, 'wb') as out:
        shutil.copyfileobj(response, out)


def read_url(deadline=40):
    end = time.time() + deadline
    while time.time() < end:
        if TUNNEL_LOG.exists():
            found = URL_PATTERN.search(TUNNEL_LOG.read_text(encoding='utf-8', errors='ignore'))
            if found:
                return found.group(0)
        time.sleep(0.5)
    return None


def http_status(url, timeout=4):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status
    except Exception:
        return None


def flush_dns():
    """A brand-new tunnel host is often cached as IPv6-only by home routers."""
    if os.name == 'nt' and shutil.which('ipconfig'):
        subprocess.run(['ipconfig', '/flushdns'], capture_output=True, check=False)


def wait_public(url, deadline=30):
    end = time.time() + deadline
    flushed = False
    while time.time() < end:
        if http_status(url, timeout=10) == 200:
            return True
        if not flushed:
            flush_dns()
            flushed = True
        time.sleep(2)
    return False


def wait_ready(port, deadline=45):
    end = time.time() + deadline
    while time.time() < end:
        if http_status(f'http://127.0.0.1:{port}/') == 200:
            return True
        time.sleep(0.7)
    return False


def stop(process):
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()


def main():
    AUDIT.mkdir(exist_ok=True)
    say('BHIMS public demo')
    say('=' * 60)

    if not start_mysql():
        say('!! MySQL is not answering on 127.0.0.1:3306 and could not be started.')
        say('   Open XAMPP Control Panel -> Start MySQL, then run this again.')
        return 1

    ensure_cloudflared()
    port = free_port()
    host_tag = f'127.0.0.1:{port}'
    say(f'  port      {host_tag}')

    TUNNEL_LOG.write_text('', encoding='utf-8')
    SERVER_LOG.write_text('', encoding='utf-8')

    tunnel = subprocess.Popen(
        [str(CLOUDFLARED), 'tunnel', '--url', f'http://{host_tag}', '--no-autoupdate'],
        stdout=open(TUNNEL_LOG, 'w', encoding='utf-8'),
        stderr=subprocess.STDOUT,
        cwd=str(BASE_DIR),
    )
    say('  tunnel    starting ...')
    public_url = read_url()
    if not public_url:
        stop(tunnel)
        say('!! cloudflared did not produce a URL. Last lines of .audit/tunnel.log:')
        say('\n'.join(TUNNEL_LOG.read_text(encoding='utf-8', errors='ignore').strip().splitlines()[-5:]))
        return 1
    host = public_url.split('://', 1)[1]
    say(f'  tunnel    {public_url}')

    env = os.environ.copy()
    env.update({
        'DJANGO_DEBUG': '0',
        'DJANGO_WHITENOISE': '1',
        'DJANGO_ALLOWED_HOSTS': f'{host},127.0.0.1,localhost',
        'DJANGO_CSRF_TRUSTED_ORIGINS': public_url,
        'BHIMS_PORT': str(port),
        'BHIMS_WORKERS': env.get('BHIMS_WORKERS', '16'),
    })
    server = subprocess.Popen(
        [PYTHON, str(BASE_DIR / 'Run Production Server.py')],
        env=env,
        cwd=str(BASE_DIR),
        stdout=open(SERVER_LOG, 'w', encoding='utf-8'),
        stderr=subprocess.STDOUT,
    )
    say('  server    starting (collectstatic runs first) ...')

    if not wait_ready(port):
        stop(server)
        stop(tunnel)
        say('!! the server did not answer on 127.0.0.1:%d. Last lines of .audit/server.log:' % port)
        say('\n'.join(SERVER_LOG.read_text(encoding='utf-8', errors='ignore').strip().splitlines()[-10:]))
        return 1

    through_tunnel = wait_public(public_url)
    URL_FILE.write_text(public_url + '\n', encoding='utf-8')
    if shutil.which('clip'):
        subprocess.run('clip', input=public_url, text=True, shell=True, check=False)

    say('')
    say('=' * 60)
    say(f'  LIVE  {public_url}')
    say('=' * 60)
    say('  copied to clipboard, saved in .audit/public-url.txt')
    say(f'  public check: {"200 OK" if through_tunnel else "not answering yet - open the link anyway, DNS can lag a minute"}')
    say('  Ctrl+C here stops the site. Closing this window also stops it.')
    say('')

    try:
        while True:
            if server.poll() is not None:
                say(f'!! the server exited (code {server.returncode}). See .audit/server.log')
                break
            if tunnel.poll() is not None:
                say(f'!! the tunnel exited (code {tunnel.returncode}). See .audit/tunnel.log')
                break
            time.sleep(2)
    except KeyboardInterrupt:
        say('\n  stopping ...')
    finally:
        stop(server)
        stop(tunnel)
    say('  stopped. (the URL is dead now, as expected)')
    return 0


if __name__ == '__main__':
    sys.exit(main())

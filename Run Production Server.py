"""
BHIMS production launcher — run this instead of `manage.py runserver`
when many users will use the system at the same time.

    venv\\Scripts\\python.exe "Run Production Server.py"

What it does:
1. Runs `collectstatic` so WhiteNoise can serve compressed, cache-friendly
   static files without touching Python for each request.
2. Starts Waitress: a real production WSGI server with 16 worker threads
   (the dev `runserver` is single-process and is NOT built for load).
3. Serves the site on http://127.0.0.1:8000/ exactly like runserver does.

Enable hardening (recommended while serving many users):
    set DJANGO_DEBUG=0 && venv\\Scripts\\python.exe "Run Production Server.py"
"""
import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MANAGE = os.path.join(BASE_DIR, 'manage.py')
PYTHON = sys.executable


def main():
    # Production defaults: DEBUG off, WhiteNoise on. These MUST be set before
    # collectstatic runs, because the manifest storage (and the hashed file
    # names plus staticfiles.json manifest it writes) is only active while
    # DJANGO_WHITENOISE=1. Collecting first with the default storage left the
    # app asking for a manifest nobody had written.
    os.environ.setdefault('DJANGO_DEBUG', '0')
    os.environ['DJANGO_WHITENOISE'] = '1'

    print('[BHIMS] Collecting static files (compressed for fast serving)...')
    subprocess.run([PYTHON, MANAGE, 'collectstatic', '--noinput'], check=True)

    from waitress import serve
    from myproject.wsgi import application

    # Worker threads. Measured with "tools/Load Test.py":
    #   32 threads, 500 concurrent users -> 197 ConnectionRefusedError (4.4%)
    #   96 threads, 500 concurrent users -> 0 failures, 4464/4464 requests OK
    # The accept queue drains only as fast as idle worker threads are
    # available; too few threads and Windows starts refusing connections
    # during a campus-opening stampede. Override with BHIMS_WORKERS.
    #
    # Keep this at or below (MariaDB max_connections - a healthy margin):
    # Django holds one persistent connection per active thread
    # (CONN_MAX_AGE=60), and XAMPP's MariaDB ships with max_connections=151.
    threads = int(os.environ.get('BHIMS_WORKERS', '96'))
    port = int(os.environ.get('BHIMS_PORT', '8000'))

    print(f'[BHIMS] Production server starting on http://127.0.0.1:{port}/ '
          f'with {threads} worker threads. Press Ctrl+C to stop.')
    serve(
        application,
        host='127.0.0.1',
        port=port,
        threads=threads,
        # Backlog: how many connections may sit waiting to be accepted during
        # a burst (e.g. 500 students hitting refresh at 8:00 AM). Default is
        # small; 2048 absorbs campus-opening stampedes on Windows.
        backlog=2048,
        #connection_limit: max simultaneous open sockets. Real users hold
        # keep-alive connections open while reading the page; the default
        # (100) actively refuses everyone beyond it — fatal with hundreds
        # of concurrent visitors.
        connection_limit=2000,
        channel_timeout=120,
        max_request_body_size=64 * 1024 * 1024,
    )


if __name__ == '__main__':
    main()

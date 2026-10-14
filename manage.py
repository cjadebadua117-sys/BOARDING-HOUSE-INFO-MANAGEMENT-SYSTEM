#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import socket
import sys


# Django's runserver hardcodes this default; it is NOT configurable from
# settings or the environment. If Django ever changes it, change it here too,
# or this guard will check a different port than the one Django binds.
DJANGO_RUNSERVER_DEFAULT_PORT = 8000


def _port_in_use(port, host):
    """True when something is ALREADY listening on this address.

    Connecting is the honest test: it is what the browser will do, and on
    Windows a bind() with SO_REUSEADDR succeeds even when the port is taken,
    so binding success cannot be used to detect a clash.

    Any failure here answers False. A broken probe must never stop the server
    from starting -- Django's own binding logic still has the final say.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(0.5)
    try:
        return probe.connect_ex((host, port)) == 0
    except (OSError, UnicodeError):
        return False
    finally:
        probe.close()


def _guard_runserver_port(argv):
    """Refuse to start on a port another app already owns.

    Without this, `manage.py runserver` on Windows binds the port anyway
    (SO_REUSEADDR), prints "Starting development server", and then serves
    NOTHING -- every request goes to the app that was there first. It fails
    silently, which looks like a broken site rather than a port clash.

    Only `runserver` is guarded; every other command is untouched.
    """
    if len(argv) < 2 or argv[1] not in ('runserver', 'runserver_plus'):
        return

    host, port = '127.0.0.1', DJANGO_RUNSERVER_DEFAULT_PORT
    args = argv[2:]
    # Django accepts `runserver 127.0.0.1:8000` as ONE argument, not two, so the
    # host and port have to be split out of a single token here.
    if args and not args[0].startswith('-'):
        positional = args[0]
        args = args[1:]
        if ':' in positional:
            host, _, raw_port = positional.rpartition(':')
            try:
                port = int(raw_port)
            except ValueError:
                sys.stderr.write(f'  ERROR: "{positional}" is not a valid host:port.\n\n')
                sys.exit(1)
        else:
            host = positional
    for i, token in enumerate(args):
        if token in ('--port', '-p') and i + 1 < len(args):
            port = int(args[i + 1])
        elif token.startswith('--port='):
            port = int(token.split('=', 1)[1])

    if not _port_in_use(port, host):
        return

    sys.stderr.write(
        f"\n"
        f"  STOP: port {port} on {host} is already in use by another program.\n"
        f"\n"
        f"  BHIMS did NOT start. On Windows, starting anyway would bind the same\n"
        f"  port and then serve nothing, because the other program keeps every\n"
        f"  request -- the site would just look broken.\n"
        f"\n"
        f"  Find what is holding it:\n"
        f"    netstat -ano | findstr :{port}\n"
        f"  Then either stop it, or start BHIMS somewhere else:\n"
        f"    python manage.py runserver {host}:8010\n\n"
    )
    sys.exit(1)


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    _guard_runserver_port(sys.argv)
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

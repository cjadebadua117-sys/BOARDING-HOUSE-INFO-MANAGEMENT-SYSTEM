"""BHIMS load test — simulates many concurrent users across several client
processes (the way real traffic arrives from many devices).

Usage:
    python "tools/Load Test.py" 500          # 500 users, 8 client processes
    LT_PROCS=12 python "tools/Load Test.py" 500

Each simulated user does 3 rounds of: landing -> listings -> login page,
reusing one keep-alive connection (like a real browser tab).
"""
import http.client
import json
import os
import sys
import threading
import time
from collections import Counter
from urllib.parse import urlparse

# Point the tool at any instance: LT_BASE=http://127.0.0.1:8010
BASE = os.environ.get('LT_BASE', 'http://127.0.0.1:8000')
ROUNDS = 3
PATHS = ['/', '/listings/', '/accounts/login/']
TIMEOUT = 25

_url = urlparse(BASE)
_HOST, _PORT = _url.hostname, _url.port or 80
_tls = threading.local()

latencies = []
codes = Counter()
failures = Counter()
res_lock = threading.Lock()


def _conn():
    """One keep-alive connection per thread, reused like a real browser."""
    c = getattr(_tls, 'conn', None)
    if c is None:
        c = http.client.HTTPConnection(_HOST, _PORT, timeout=TIMEOUT)
        _tls.conn = c
    return c


def fetch(path):
    for attempt in (1, 2):
        c = _conn()
        try:
            c.request('GET', path, headers={'User-Agent': 'loadtest/1.0',
                                            'Connection': 'keep-alive'})
            r = c.getresponse()
            r.read()
            return r.status
        except Exception:
            try:
                c.close()
            except Exception:
                pass
            _tls.conn = http.client.HTTPConnection(_HOST, _PORT, timeout=TIMEOUT)
            if attempt == 2:
                raise


THINK_SECONDS = float(os.environ.get('LT_THINK', '0'))  # human pause between pages


def user_workflow():
    for _ in range(ROUNDS):
        for path in PATHS:
            if THINK_SECONDS:
                time.sleep(THINK_SECONDS * (0.5 + (id(path) % 100) / 100.0))
            t0 = time.perf_counter()
            try:
                code = fetch(path)
            except Exception as e:
                code = f'ERR:{type(e).__name__}'
            dt = (time.perf_counter() - t0) * 1000
            with res_lock:
                codes[code] += 1
                latencies.append(dt)
                if isinstance(code, str) or code >= 500:
                    failures[code] += 1


def run_group(n_users):
    threads = [threading.Thread(target=user_workflow, daemon=True) for _ in range(n_users)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(280)
    return {
        'latencies': sorted(latencies),
        'codes': dict(codes),
        'failures': dict(failures),
    }


if os.environ.get('LT_CHILD') == '1':
    print(json.dumps(run_group(int(sys.argv[1]))))
    sys.exit(0)


def percentile(sorted_list, pct):
    if not sorted_list:
        return 0
    return sorted_list[min(int(len(sorted_list) * pct), len(sorted_list) - 1)]


def main():
    from subprocess import Popen, PIPE

    n_users = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    n_procs = int(os.environ.get('LT_PROCS', '8'))
    per_proc = max(1, n_users // n_procs)

    print(f'Load test: {n_users} users ({n_procs} client processes x {per_proc}) '
          f'x {ROUNDS} rounds x {len(PATHS)} pages...', flush=True)
    t0 = time.perf_counter()
    procs = [
        Popen([sys.executable, os.path.abspath(__file__), str(per_proc)],
              env={**os.environ, 'LT_CHILD': '1'}, stdout=PIPE)
        for _ in range(n_procs)
    ]
    all_lat, merged_codes, merged_fail = [], Counter(), Counter()
    for pr in procs:
        out, _ = pr.communicate(300)
        try:
            data = json.loads(out.decode().strip().splitlines()[-1])
        except Exception:
            continue
        all_lat += data['latencies']
        merged_codes.update({k: v for k, v in data['codes'].items()})
        merged_fail.update({k: v for k, v in data['failures'].items()})
    wall = time.perf_counter() - t0

    all_lat.sort()
    n = len(all_lat)
    print(json.dumps({
        'users': n_users,
        'requests': n,
        'wall_seconds': round(wall, 1),
        'rps': round(n / wall, 1) if wall else 0,
        'p50_ms': round(percentile(all_lat, 0.50), 1),
        'p90_ms': round(percentile(all_lat, 0.90), 1),
        'p99_ms': round(percentile(all_lat, 0.99), 1),
        'status_codes': {str(k): v for k, v in merged_codes.items()},
        'failures': {str(k): v for k, v in merged_fail.items()},
    }, indent=1))


if __name__ == '__main__':
    main()

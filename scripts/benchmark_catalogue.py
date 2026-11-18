"""Measure catalogue load time (non-functional requirement: list page < 2 s with >= 30 books; risk R-06).

Local (in-process, server render time only):
    python scripts/benchmark_catalogue.py
Against a running or hosted site (full HTTP round trip):
    python scripts/benchmark_catalogue.py --url https://your-app.onrender.com
"""
import argparse
import os
import statistics
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PATHS = [
    "/",                                      # US-03 page 1, newest first
    "/?page=3",                               # US-03 last page
    "/?q=the",                                # US-05 search
    "/?category=1",                           # US-17 category filter
    "/?min_price=50000&max_price=300000",     # US-18 price range
    "/?q=a&category=1&min_price=50000&max_price=300000&page=1",  # combined criteria
    "/books/1",                               # US-04 details
]
LIMIT_MS = 2000


def run(fetch, rounds):
    rows = []
    for path in PATHS:
        fetch(path)  # warm-up
        samples = []
        for _ in range(rounds):
            t0 = time.perf_counter()
            status = fetch(path)
            samples.append((time.perf_counter() - t0) * 1000)
        samples.sort()
        p95 = samples[max(0, int(round(0.95 * len(samples))) - 1)]
        rows.append((path, status, statistics.median(samples), p95, samples[-1]))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="Base URL of a running site; omit to test in-process")
    ap.add_argument("--rounds", type=int, default=30)
    args = ap.parse_args()

    if args.url:
        base = args.url.rstrip("/")

        def fetch(path):
            with urllib.request.urlopen(base + path, timeout=30) as r:
                r.read()
                return r.status
        where = base
    else:
        from bookstore import create_app
        tmp = tempfile.mkdtemp()
        app = create_app({"TESTING": True, "DATABASE": os.path.join(tmp, "bench.sqlite3"),
                          "UPLOAD_FOLDER": os.path.join(tmp, "uploads")})
        client = app.test_client()

        def fetch(path):
            return client.get(path).status_code
        where = "in-process Flask test client (32 seeded books)"

    rows = run(fetch, args.rounds)
    print(f"Catalogue load time - {where}, {args.rounds} requests per page")
    print(f"{'Page':58} {'HTTP':>4} {'median':>9} {'p95':>9} {'max':>9}")
    worst = 0
    for path, status, med, p95, mx in rows:
        worst = max(worst, mx)
        print(f"{path:58} {status:>4} {med:8.1f}ms {p95:8.1f}ms {mx:8.1f}ms")
    verdict = "PASS" if worst < LIMIT_MS else "FAIL"
    print(f"Slowest request: {worst:.1f} ms -> {verdict} (limit {LIMIT_MS} ms)")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

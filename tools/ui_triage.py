"""Triage a ui_audit.py JSON report, defaulting to MOBILE renders.

Usage:
    ./venv/Scripts/python.exe tools/ui_triage.py .audit/MOBILE-AFTER.json [mobile|desktop|all]

The text report buries findings; this prints only what actually needs fixing on
a phone, grouped by kind so a single shared cause (one component used on many
pages) is obvious instead of looking like dozens of unrelated bugs.
"""
import json
import sys
from collections import Counter, defaultdict

path = sys.argv[1] if len(sys.argv) > 1 else ".audit/MOBILE-NOW.json"
only = sys.argv[2] if len(sys.argv) > 2 else "mobile"
pages = json.load(open(path, encoding="utf-8"))

rows = defaultdict(list)          # kind -> [(page, theme, detail)]
counts = Counter()

for p in pages:
    if only != "all" and p.get("viewport") != only:
        continue
    pr = p.get("probe") or {}
    tag = f"{p['page']}/{p['theme']}"

    if p.get("status") != 200:
        rows["status != 200"].append((tag, p.get("note", "")[:80]))

    ov = pr.get("overflow")
    if ov:
        rows["horizontal overflow"].append((tag, json.dumps(ov)[:150]))

    for it in pr.get("contrast") or []:
        rows["contrast"].append((tag, json.dumps(it)[:150]))
    for it in pr.get("tapTargets") or []:
        rows["tap target < 44px"].append((tag, json.dumps(it)[:170]))
    for it in pr.get("unlabeled") or []:
        rows["unlabeled control"].append((tag, json.dumps(it)[:150]))
    for it in pr.get("brokenImages") or []:
        rows["broken image"].append((tag, json.dumps(it)[:150]))
    for it in pr.get("duplicateIds") or []:
        rows["duplicate id"].append((tag, json.dumps(it)[:120]))
    if p.get("console_errors"):
        rows["console error"].append((tag, json.dumps(p["console_errors"])[:150]))
    if p.get("failed_requests"):
        rows["failed request"].append((tag, json.dumps(p["failed_requests"])[:150]))

    for k, v in (pr.items()):
        if isinstance(v, list) and v:
            counts[k] += len(v)

print(f"viewport={only}   renders={sum(1 for p in pages if p.get('viewport')==only)}\n")
if not rows:
    print("NO PROBLEMS FOUND")
    raise SystemExit(0)

order = ["status != 200", "horizontal overflow", "contrast", "tap target < 44px",
         "unlabeled control", "broken image", "duplicate id",
         "console error", "failed request"]
grand = 0
for k in order:
    items = rows.get(k) or []
    if not items:
        continue
    pages_hit = sorted({t for t, _ in items})
    print(f"### {k}  — {len(items)} findings on {len(pages_hit)} pages")
    print(f"    pages: {', '.join(pages_hit)}")
    for t, d in items[:6]:
        print(f"      - {t}: {d}")
    if len(items) > 6:
        print(f"      ... +{len(items)-6} more")
    print()
    grand += len(items)

print("TOTAL findings:", grand)
print("\nprobe field totals:", dict(counts))
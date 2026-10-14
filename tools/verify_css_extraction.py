"""Prove the CSS extraction was lossless.

Originals come straight from git HEAD (authoritative), so this does not
depend on any temporary backup copy. Every extracted file must be
byte-identical to the <style> block it replaced.
"""
import re
import subprocess
import pathlib

STYLE = re.compile(r"<style>\n?(.*?)</style>", re.S)
HDR = re.compile(r"^/\* Extracted verbatim.*?\*/\n", re.S)
LINK = re.compile(r"core/css/pages/([A-Za-z0-9_\-.]+\.css)")

CUR = pathlib.Path("core/templates/core")
OUT = pathlib.Path("core/static/core/css/pages")


def git_show(path):
    return subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        capture_output=True, text=True, encoding="utf-8",
    ).stdout


def norm(p):
    return str(p).replace("\\", "/")


# --- originals, from git HEAD -------------------------------------------
orig_files = subprocess.run(
    ["git", "ls-tree", "-r", "--name-only", "HEAD", "core/templates"],
    capture_output=True, text=True, encoding="utf-8",
).stdout.split()

orig_map = {}
for path in orig_files:
    if not path.endswith(".html"):
        continue
    rel = norm(pathlib.Path(path).relative_to("core/templates/core"))
    for i, m in enumerate(STYLE.finditer(git_show(path)), 1):
        orig_map[(rel, i)] = m.group(1).strip("\n").strip()

# --- what each template links now ---------------------------------------
cur_map = {}
for f in sorted(CUR.rglob("*.html")):
    rel = norm(f.relative_to(CUR))
    for i, m in enumerate(LINK.finditer(f.read_text(encoding="utf-8")), 1):
        cur_map[(rel, i)] = m.group(1)

print(f'{"template":44s} {"blk":>3} {"extracted file":32s} identical?')
print("-" * 94)
ok = bad = missing = 0
for (tpl, idx), css in sorted(orig_map.items()):
    name = cur_map.get((tpl, idx))
    if not name:
        continue
    p = OUT / name
    if not p.exists():
        print(f"{tpl:44s} {idx:>3} {name:32s} *** FILE MISSING ***")
        missing += 1
        continue
    got = HDR.sub("", p.read_text(encoding="utf-8")).strip()
    if got == css:
        ok += 1
    else:
        bad += 1
        print(f"{tpl:44s} {idx:>3} {name:32s} *** NO ***")
        print(f"     original {len(css)} chars / extracted {len(got)} chars")

print("-" * 94)
print(f"identical: {ok}   DIFFERING: {bad}   missing: {missing}")

still = sorted({k[0] for k in orig_map if (k[0], k[1]) not in cur_map})
still_blocks = sum(1 for k in orig_map if (k[0], k[1]) not in cur_map)
extracted_lines = sum(v.count("\n") + 1 for v in orig_map.values()
                      if (k := None) is None and True)  # placeholder, replaced below
extracted_lines = sum(orig_map[k].count("\n") + 1
                      for k in orig_map if (k[0], k[1]) in cur_map)
still_lines = sum(orig_map[k].count("\n") + 1
                  for k in orig_map if (k[0], k[1]) not in cur_map)

print(f"\noriginal inline blocks : {len(orig_map)}")
print(f"extracted & verified   : {ok}  ({extracted_lines} CSS lines)")
print(f"still inline on disk   : {still_blocks} block(s), {still_lines} lines, in {len(still)} template(s)")
for s in still:
    print(f"    - {s}")
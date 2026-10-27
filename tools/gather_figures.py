import os, re, zipfile, shutil, struct

ROOT = r"C:\Users\Admin\Desktop\BOARDING HOUSE INFO MANAGEMENT SYSTEMS"
OUT = os.path.join(ROOT, "tools", "verify_out", "figures")
os.makedirs(OUT, exist_ok=True)

def png_size(p):
    with open(p, "rb") as f:
        d = f.read(33)
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", d[16:24])
    return w, h

# ---- 1. extract midterm figures in document order ----
src = r"C:\Users\Admin\Documents\Downloads\BHIMS_MIDTERM_PROJECT_humanized.docx"
z = zipfile.ZipFile(src)
rels = z.read("word/_rels/document.xml.rels").decode("utf8")
relmap = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
doc = z.read("word/document.xml").decode("utf8")
order = []
for m in re.finditer(r'r:embed="([^"]+)"', doc):
    t = relmap.get(m.group(1), "")
    if t and t not in order:
        order.append(t)
print("=== MIDTERM FIGURE ORDER ===")
for i, t in enumerate(order, 1):
    name = os.path.basename(t)
    data = z.read("word/" + t)
    dst = os.path.join(OUT, f"midterm_fig{i}_{name}")
    with open(dst, "wb") as f:
        f.write(data)
    print(f"Fig {i}: {t}  {png_size(dst)}")

print("\n=== BUILT DIAGRAMS ===")
d = os.path.join(ROOT, "docs", "final-project", "diagrams")
for f in sorted(os.listdir(d)):
    if f.endswith(".png"):
        print(f"{f}: {png_size(os.path.join(d, f))}")

print("\n=== MIDTERM DIAGRAMS (docs/diagrams) ===")
d2 = os.path.join(ROOT, "docs", "diagrams")
for f in sorted(os.listdir(d2)):
    if f.endswith(".png"):
        print(f"{f}: {png_size(os.path.join(d2, f))}")

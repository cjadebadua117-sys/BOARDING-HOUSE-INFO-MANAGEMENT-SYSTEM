"""Build a white, line-art version of the DMMMSU seal for use as a watermark.

The stock seal is full colour on transparency. Flattening it to a silhouette in
CSS (brightness(0) invert(1)) merges its white interior with its thick green
ring, so it renders as one scalloped blob rather than a seal.

Here every near-white pixel is punched out to transparent and everything that
remains is painted white. The result keeps alpha only where the original had
ink, so it reads as white line art over any background.

Run once; writes core/static/core/images/dmmmsu-seal-mono.png. The original
dmmmsu-seal.png is never modified.
"""
import os

from PIL import Image

SRC = "core/static/core/images/dmmmsu-seal.png"
DST = "core/static/core/images/dmmmsu-seal-mono.png"

# Anything at least this bright is treated as paper rather than ink. The seal's
# yellow rings are the darkest non-white it contains, so the threshold only has
# to separate white from "not white".
PAPER = 232

src = Image.open(SRC).convert("RGBA")
w, h = src.size
in_px = src.load()

out = Image.new("RGBA", (w, h), (255, 255, 255, 0))
out_px = out.load()

kept = 0
for y in range(h):
    for x in range(w):
        r, g, b, a = in_px[x, y]
        if a == 0:
            continue
        # Soften the threshold across a small band so anti-aliased edges fade
        # instead of turning into hard jaggies.
        lo = min(r, g, b)
        if lo >= PAPER:
            continue
        if lo > PAPER - 40:
            alpha = int(a * (PAPER - lo) / 40)
        else:
            alpha = a
        if alpha:
            out_px[x, y] = (255, 255, 255, alpha)
            kept += 1

out.save(DST)

total = sum(1 for y in range(h) for x in range(w) if in_px[x, y][3] > 0)
print(f"wrote {DST}  {w}x{h}")
print(f"ink pixels kept: {kept}  (of {total} opaque in source)")
print(f"size: {os.path.getsize(DST)} bytes  (source {os.path.getsize(SRC)} bytes)")

# Sanity check: the result must actually be mostly transparent, otherwise it is
# another opaque block waiting to look like a smudge.
opaque = sum(1 for y in range(h) for x in range(w) if out_px[x, y][3] > 200)
print(f"opaque share of output: {opaque/(w*h):.1%}  (source was {total/(w*h):.1%})")
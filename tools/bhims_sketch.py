#!/usr/bin/env python3
"""
BHIMS — Boarding House Information Management System
Low-fidelity pencil-sketch style system diagram.

Hand-drawn aesthetic: slightly wobbly lines, cross-hatch fills, paper
texture, coffee-stain circles, margin doodles. One big sketch sheet.
"""
from PIL import Image, ImageDraw, ImageFont
import math, random

random.seed(7)  # reproducible sketch, not a raster photo

W, H = 1600, 2200
PAPER = (248, 242, 228)          # warm off-white paper
INK    = (46,  40,  34)           # graphite pencil
RED    = (188, 72, 47)           # red ink accent
BLUE   = (60,  84,  120)         # blue ink accent
GREEN  = (90,  120, 80)          # green accent
FENCE_ROWS = 6                   # cross-hatch density

img = Image.new("RGB", (W, H), PAPER)
d = ImageDraw.Draw(img, "RGBA")

# ---------- paper grain + faint coffee rings ----------
px = img.load()
for _ in range(9000):
    x = random.randint(0, W-1)
    y = random.randint(0, H-1)
    r = random.randint(0, 5)
    v = random.randint(-18, 18)
    for yy in range(max(0,y-r), min(H,y+r+1)):
        for xx in range(max(0,x-r), min(W,x+r+1)):
            if (xx-x)**2 + (yy-y)**2 <= r*r:
                a, b, c = px[xx, yy]
                px[xx, yy] = (max(0,min(255,a+v)),
                               max(0,min(255,b+v)),
                               max(0,min(255,c+v)))
for _ in range(4):
    cx = random.randint(200, W-200)
    cy = random.randint(200, H-200)
    rr = random.randint(120, 260)
    for ang in range(0, 360, 3):
        r = rr * math.sqrt(random.random())
        x = int(cx + r*math.cos(math.radians(ang)))
        y = int(cy + r*math.sin(math.radians(ang)))
        if 0 <= x < W and 0 <= y < H:
            a,b,c = px[x,y]
            px[x,y] = (min(255,a+6), min(255,b+4), min(255,c+2))

# ---------- helpers: wobbly paths ----------
def _wobble(p0, p1, amp=2.2, steps=None):
    dx = float(p1[0]-p0[0])
    dy = float(p1[1]-p0[1])
    dist = math.hypot(dx, dy)
    steps = steps or max(2, int(dist/6))
    pts = [(int(p0[0]), int(p0[1]))]
    for i in range(1, steps):
        t = i/steps
        basex = p0[0]+dx*t
        basey = p0[1]+dy*t
        wx = random.uniform(-amp, amp)
        wy = random.uniform(-amp, amp)
        pts.append((int(basex+wx), int(basey+wy)))
    pts.append((int(p1[0]), int(p1[1])))
    return pts

def pencil_line(p0, p1, color=INK, width=2, amp=2.2):
    d.line(_wobble(p0, p1, amp=amp), fill=color, width=int(width), joint="curve")  # _wobble now returns int tuples

def pencil_rect(corner, size, color=INK, width=2, amp=2.6, fill=None):
    x, y = corner
    w, h = size
    # build edges individually for control
    e1 = _wobble((x,y), (x+w,y), amp=amp)
    e2 = _wobble((x+w,y), (x+w,y+h), amp=amp)
    e3 = _wobble((x+w,y+h), (x,y+h), amp=amp)
    e4 = _wobble((x,y+h), (x,y), amp=amp)
    if fill:
        d.polygon([(x,y),(x+w,y),(x+w,y+h),(x,y+h)], fill=fill)
    for e in (e1,e2,e3,e4):
        int_e = [(int(p[0]), int(p[1])) for p in e]
        d.line(int_e, fill=color, width=int(width), joint="curve")

def crosshatch_box(corner, size, color=INK, width=1, spacing=7):
    x, y = corner
    w, h = size
    for i in range(0, int(w+math.hypot(w,h)), spacing):
        base_x = x - h*0.4
        p0 = (base_x + i, y)
        p1 = (base_x + i + h, y + h)
        d.line(_wobble(p0, p1, amp=0.9, steps=max(2,int(math.hypot(h,h)/5))),
               fill=color, width=width)
    for i in range(0, int(h+math.hypot(w,h)), spacing):
        base_x = x - h*0.4
        p0 = (base_x + i, y)
        p1 = (base_x + i - h, y + h)
        d.line(_wobble(p0, p1, amp=0.9, steps=max(2,int(math.hypot(h,h)/5))),
               fill=color, width=width)

def stipple(corner, size, color=INK, r=1.4, count=40):
    x, y = corner
    w, h = size
    for _ in range(count):
        sx = random.uniform(x, x+w)
        sy = random.uniform(y, y+h)
        d.ellipse([sx-r, sy-r, sx+r, sy+r], fill=color)

def sketch_text(cxy, text, *, color=INK, size=13, font=None, jitter=1.1):
    x, y = cxy
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            d.text((x+dx*random.uniform(-0.4,0.4),
                    y+dy*random.uniform(-0.4,0.4)),
                   text, font=font, fill=color+(70,))
    d.text((x, y), text, font=font, fill=color)

def try_font(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/local/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/DejaVuSans.ttf",
]
F_TITLE   = try_font(FONT_PATHS, 26)
F_SUB     = try_font(FONT_PATHS, 15)
F_LABEL   = try_font(FONT_PATHS, 13)
F_SMALL   = try_font(FONT_PATHS, 11)
F_HUGE    = try_font(FONT_PATHS, 42)

# =========================================================
# BORDER + TITLE BLOCK  (pencil frame on the sheet)
# =========================================================
inset = 42
pencil_rect((inset, inset), (W-2*inset, H-2*inset),
            color=INK, width=3, amp=4.2)
d.line(_wobble((inset+8, inset+8),(W-inset-8, inset+8)),
       fill=INK, width=1, joint="curve")
sketch_text((inset+18, inset+10),
            "BHIMS  —  Boarding House Information Management System",
            color=INK, size=24, font=F_TITLE)
sketch_text((inset+22, inset+44),
            "System sketch (low-fidelity) — student / landlord / administrator",
            color=BLUE, size=13, font=F_SUB)

# red accent corner boxing
for (cx1,cy1,cx2,cy2) in [
    (inset+10, inset+10, inset+34, inset+34),
    (W-inset-10, inset+10, W-inset-34, inset+34),
    (inset+10, H-inset-10, inset+34, H-inset-34),
    (W-inset-10, H-inset-10, W-inset-34, H-inset-34),
]:
    d.ellipse([min(cx1,cx2),min(cy1,cy2),max(cx1,cx2),max(cy1,cy2)], outline=RED, width=3)

# =========================================================
# CENTER: THE SYSTEM (cloud-ish blob)
# =========================================================
sys_cx, sys_cy = W//2, H//2 - 60
sys_rx, sys_ry = 300, 150

# wobbly oval blob
def wobbly_ellipse(cx, cy, rx, ry, *, color=INK, width=3, amp=4.0, steps=70):
    pts = []
    for i in range(steps+1):
        ang = 2*math.pi*i/steps
        rr = 1 + random.uniform(-amp/100.0, amp/100.0)
        x = int(cx + rx*rr*math.cos(ang) + random.uniform(-1.5,1.5))
        y = int(cy + ry*rr*math.sin(ang) + random.uniform(-1.5,1.5))
        pts.append((x,y))
    d.line(pts, fill=color, width=width, joint="curve")

def wobbly_ellipse_fill(cx, cy, rx, ry, fill, *, stroke=INK, sw=3, amp=4.0):
    pts = []
    for i in range(70+1):
        ang = 2*math.pi*i/70
        rr = 1 + random.uniform(-amp/100.0, amp/100.0)
        x = int(cx + rx*rr*math.cos(ang) + random.uniform(-1.5,1.5))
        y = int(cy + ry*rr*math.sin(ang) + random.uniform(-1.5,1.5))
        pts.append((x,y))
    d.line(pts + [tuple(int(v) for v in pts[0])], fill=stroke, width=int(sw), joint="curve")

# shaded system blob
for offset in range(0, 9):
    wobbly_ellipse(sys_cx, sys_cy, sys_rx+offset*3, sys_ry+offset*3,
                   color=(150,150,150,20+offset*4), width=1, amp=5.0)
wobbly_ellipse_fill(sys_cx, sys_cy, sys_rx, sys_ry,
                    fill=(255,255,255,24), stroke=INK, sw=3.5, amp=5.0)

sketch_text((sys_cx-150, sys_cy-44),
            "BOARDING HOUSE", color=INK, size=24, font=F_SUB)
sketch_text((sys_cx-130, sys_cy-20),
            "INFORMATION", color=INK, size=24, font=F_SUB)
sketch_text((sys_cx-150, sys_cy+4),
            "MANAGEMENT SYSTEM", color=INK, size=24, font=F_SUB)
sketch_text((sys_cx-46, sys_cy+30),
            "(BHIMS)", color=BLUE, size=15, font=F_SMALL)

# little system doodle: wifi-style signals inside
for i,(r,wid,off) in enumerate([(30,2,0),(52,2,-9),(74,2,-18)]):
    cx = sys_cx + off
    cy = sys_cy - 58
    d.line(_wobble((cx-r,cy),(cx+r,cy)), fill=BLUE, width=wid, joint="curve")
    d.line(_wobble((cx-r-3,cy-6),(cx+r+3,cy-6)), fill=BLUE, width=wid, joint="curve")

# crosshatch the system lightly to read as a "box being drawn"
crosshatch_box((sys_cx-sys_rx, sys_cy-sys_ry),
               (sys_rx*2, sys_ry*2),
               color=(120,120,120,40), width=1, spacing=14)

# =========================================================
# THREE ACTORS  (rounded user blobs, top & bottom)
# =================================================
def actor_blob(cx, cy, rx, ry, label_lines, accent=RED):
    wobbly_ellipse_fill(cx, cy, rx, ry, fill=(255,255,255,6),
                        stroke=accent, sw=3, amp=4.0)
    crosshatch_box((cx-rx, cy-ry), (rx*2, ry*2),
                   color=(accent[0],accent[1],accent[2],40), width=1, spacing=10)
    lh = 16
    total_h = lh*(len(label_lines)-1)
    y0 = cy - total_h//2
    x0 = cx - 90
    for i,ln in enumerate(label_lines):
        w = d.textlength(ln, font=F_LABEL)
        sketch_text((cx - w/2 + random.uniform(-0.6,0.6),
                     y0 + i*lh + random.uniform(-0.6,0.6)),
                    ln, color=INK, size=13, font=F_LABEL)

# STUDENT  (top-left-ish)
sx, sy = W//2 - 420, sys_cy - 300
pencil_line((sys_cx - sys_rx + 10, sys_cy - sys_ry + 10),
            (sx, sy+38), color=INK, width=2, amp=2.2)
actor_blob(sx, sy, 95, 72,
           ["STUDENT", "(searcher,", "booker, rater)"],
           accent=RED)

# LANDLORD (top-right-ish)
lx, ly = W//2 + 420, sys_cy - 300
pencil_line((sys_cx + sys_rx - 10, sys_cy - sys_ry + 10),
            (lx, ly+38), color=INK, width=2, amp=2.2)
actor_blob(lx, ly, 100, 74,
           ["LANDLORD", "(posts houses,", "replies,", "accepts/declines,", "gets rated)"],
           accent=BLUE)

# ADMINISTRATOR (bottom center, bigger)
ax, ay = sys_cx, sys_cy + 330
pencil_line((sys_cx, sys_cy + sys_ry - 10), (ax, ay-46),
            color=INK, width=2, amp=2.2)
actor_blob(ax, ay, 120, 92,
           ["ADMINISTRATOR", "(approves listings,", "manages accounts,", "barangays & settings,",
            "resolves reports,", "sees analytics)"],
           accent=GREEN)

# small arrowheads on the actor lines
def arrowhead(base, tip, color=INK, size=10):
    tipx = int(tip[0])
    tipy = int(tip[1])
    basex = int(base[0])
    basey = int(base[1])
    dx = float(tipx) - float(basex)
    dy = float(tipy) - float(basey)
    L = math.hypot(dx,dy) or 1.0
    ux = dx/L
    uy = dy/L
    px = -uy
    py = ux
    hw = float(size)
    pts = [
        (tipx, tipy),
        (int(tipx-ux*hw+px*hw*0.5), int(tipy-uy*hw+py*hw*0.5)),
        (int(tipx-ux*hw-px*hw*0.5), int(tipy-uy*hw-py*hw*0.5)),
    ]
    p0 = (int(pts[0][0]), int(pts[0][1]))
    p1 = (int(pts[1][0]), int(pts[1][1]))
    p2 = (int(pts[2][0]), int(pts[2][1]))
    d.line([(p0[0],p0[1]),(p1[0],p1[1])], fill=color, width=1)
    d.line([(p0[0],p0[1]),(p2[0],p2[1])], fill=color, width=1)

arrowhead((sx, sy+38), (sys_cx-sys_rx+20, sys_cy-sys_ry+16))
arrowhead((lx, ly+38), (sys_cx+sys_rx-20, sys_cy-sys_ry+16))
arrowhead((sys_cx, sys_cy+sys_ry-14), (ax, ay-52))

# =========================================================
# EIGHT DATA STORES  (bottom strip: open-ended folders)
# =================================================
store_y = H - 360
stores = [
    ("D1", "USERS  (accounts,", "roles, sessions)"),
    ("D2", "HOUSES & ROOMS", "(listings, availability)"),
    ("D3", "AMENITIES", "& BARANGAYS"),
    ("D4", "INQUIRIES", "& MESSAGES"),
    ("D5", "BOOKINGS", "(confirmed / pending)"),
    ("D6", "LANDLORD", "RATINGS"),
    ("D7", "USER REPORTS", "(pending/resolved)"),
    ("D8", "AUDIT LOG", "& SETTINGS"),
]
n = len(stores)
margin = 70
gap = (W - 2*margin - n*8) // (n+1)
box_w = (W - 2*margin - gap*(n+1)) // n
box_h = 108
# pair them so we can draw slightly different widths for wrapped labels
widths = []
for i in range(n):
    three = stores[i]
    longest = max(d.textlength(t, font=F_SMALL) for t in three)
    widths.append(max(box_w, int(longest+22)))

x = margin
for i,(tag, *lines) in enumerate(stores):
    w = widths[i]
    # folder-ish shape
    pencil_rect((x, store_y-12), (w, box_h), color=BLUE, width=2.2, amp=3.0,
                fill=(214,224,240,16))
    # folder tab
    d.line(_wobble((x, store_y-12), (x+14, store_y-22), amp=1.6),
           fill=BLUE, width=2)
    d.line(_wobble((x+14, store_y-22), (x+w-2, store_y-22), amp=1.6),
           fill=BLUE, width=2)
    d.line(_wobble((x+w-2, store_y-22), (x+w, store_y-12), amp=1.6),
           fill=BLUE, width=2)
    # label
    lx = x + w/2
    for j,ln in enumerate(lines):
        wtxt = d.textlength(ln, font=F_SMALL)
        sketch_text((lx - wtxt/2 + random.uniform(-0.5,0.5),
                     store_y + 6 + j*13 + random.uniform(-0.5,0.5)),
                    ln, color=INK, size=11, font=F_SMALL)
    # left D-tag in blue
    stipple((x+5, store_y+box_h-18), (w-10, 16), color=BLUE, r=1.6, count=14)
    sketch_text((x+w/2, store_y+box_h-4),
                tag, color=BLUE, size=12, font=F_SMALL)
    x += w + gap

# connecting dashed lines from stores up to the system
for i in range(n):
    x = margin + sum(widths[:i]) + i*gap + widths[i]/2
    y0 = store_y - 12
    y1 = sys_cy + sys_ry - 6
    ax_ = x
    av = random.uniform(0.35,0.6)
    pts = []
    ys = y1
    for step in range(0, int(y1-y0), 18):
        t = step/(y1-y0)
        px = x + math.sin(t*math.pi*1.3)*8
        if step % 2 == 0:
            pts.append((px, y0+step+9))
        else:
            pts.append((px, y0+step+9))
    # dashed doodle line
    segs = []
    k = 0
    for yy in range(y0, y1, 12):
        segs.append((x + math.sin((yy-y0)/80.0)*7,
                     yy))
        k += 1
    segs.append((x + math.sin((y1-y0)/80.0)*7, y1))
    # render as dashed
    for a,b in zip(segs[::2], segs[1::2]):
        d.line(_wobble(a,b,amp=1.4), fill=(60,84,120,110), width=1.4, joint="curve")

# =========================================================
# EIGHT PROCESS BUMBLEBEES  (the 8 numbered modules)
# around the center, arranged in a ring
# =================================================
modules = [
    ("1.0", "User & Account\nManagement"),
    ("2.0", "Boarding House &\nRoom Management"),
    ("3.0", "Search &\nAvailability"),
    ("4.0", "Inquiry &\nMessaging"),
    ("5.0", "Booking\nManagement"),
    ("6.0", "Rating &\nReview"),
    ("7.0", "User\nReporting"),
    ("8.0", "Administration &\nAnalytics"),
]
R = 340
for i,(tag,lines) in enumerate(modules):
    ang = 2*math.pi*i/8 - math.pi/2
    cx = sys_cx + R*math.cos(ang)
    cy = sys_cy + R*math.sin(ang)
    r = 78
    wobbly_ellipse_fill(cx, cy, r, r*0.82, fill=(255,255,255,18),
                         stroke=INK, sw=2.4, amp=3.4)
    crosshatch_box((cx-r, cy-r*0.82), (r*2, r*1.64),
                   color=(80,80,80,26), width=1, spacing=8)
    lx = cx
    for j,ln in enumerate(lines.split("\n")):
        wtxt = d.textlength(ln, font=F_SMALL)
        sketch_text((lx - wtxt/2 + random.uniform(-0.5,0.5),
                     cy - 9 + j*13 + random.uniform(-0.5,0.5)),
                    ln, color=INK, size=11, font=F_SMALL)
    # big number badge
    bw = d.textlength(tag, font=F_HUGE) + 24
    bh = 56
    bx = cx - bw/2
    by = cy - r*0.82 - bh - 6
    pencil_rect((bx, by), (bw, bh), color=RED, width=2.4, amp=2.6,
                fill=(255,220,210,20))
    wtxt = d.textlength(tag, font=F_HUGE)
    sketch_text((cx - wtxt/2 + random.uniform(-0.6,0.6),
                 by + (bh-20)/2 + random.uniform(-0.6,0.6)),
                tag, color=RED, size=30, font=F_HUGE)
    # tiny connector from module -> system
    pencil_line((cx, cy-r*0.82 if math.cos(ang)>=0 else cy+r*0.82),
                (sys_cx + (sys_rx-10)*math.cos(ang),
                 sys_cy + (sys_ry-10)*math.sin(ang)),
                color=(60,84,120), width=1.4, amp=1.6)

# =========================================================
# FLOW ARROWS between actors and modules  (sketchy)
# =================================================
def flow_arrow(p0, p1, color=INK, width=2.0, amp=2.4, label=None):
    pencil_line(p0, p1, color=color, width=width, amp=amp)
    # arrowhead
    tipx = int(p1[0])
    tipy = int(p1[1])
    dx = float(p1[0]-p0[0])
    dy = float(p1[1]-p0[1])
    L = math.hypot(dx,dy) or 1.0
    ux = dx/L
    uy = dy/L
    px = -uy
    py = ux
    sz = 9.0
    basex = tipx-ux*sz
    basey = tipy-uy*sz
    p_tip = (tipx, tipy)
    p_a = (int(basex+px*sz*0.55), int(basey+py*sz*0.55))
    p_b = (int(basex-px*sz*0.55), int(basey-py*sz*0.55))
    d.line([p_tip, p_a], fill=color, width=1)
    d.line([p_tip, p_b], fill=color, width=1)
    if label:
        mx = (p0[0]+p1[0])/2 + random.uniform(-6,6)
        my = (p0[1]+p1[1])/2 + random.uniform(-6,6) - 12
        sketch_text((mx - d.textlength(label, font=F_SMALL)/2,
                     my),
                    label, color=color, size=10, font=F_SMALL)

# STUDENT -> (3.0, 4.0, 7.0-ish)
flow_arrow((sx, sy+40),
           (sys_cx + R*math.cos(2*math.pi*2/8 - math.pi/2),
            sys_cy + R*math.sin(2*math.pi*2/8 - math.pi/2)+50),
           color=RED, width=2.2, label="search / inquiry / report")
flow_arrow((sx, sy+90),
           (sys_cx + R*math.cos(2*math.pi*5/8 - math.pi/2),
            sys_cy + R*math.sin(2*math.pi*5/8 - math.pi/2)-30),
           color=RED, width=1.8, label="rate landlord")

# LANDLORD -> (2.0, 4.0, 5.0-ish)
flow_arrow((lx, ly+40),
           (sys_cx + R*math.cos(2*math.pi*1/8 - math.pi/2),
            sys_cy + R*math.sin(2*math.pi*1/8 - math.pi/2)+50),
           color=BLUE, width=2.2, label="post / edit listings")
flow_arrow((lx, ly+90),
           (sys_cx + R*math.cos(2*math.pi*3/8 - math.pi/2),
            sys_cy + R*math.sin(2*math.pi*3/8 - math.pi/2)-20),
           color=BLUE, width=1.9, label="reply + accept/decline")

# ADMIN -> (1.0, 7.0, 8.0-ish) from bottom blob
flow_arrow((ax, ay-30),
           (sys_cx + R*math.cos(2*math.pi*0/8 - math.pi/2),
            sys_cy + R*math.sin(2*math.pi*0/8 - math.pi/2)+30),
           color=GREEN, width=2.2, label="accounts / settings")
flow_arrow((ax, ay-8),
           (sys_cx + R*math.cos(2*math.pi*6/8 - math.pi/2),
            sys_cy + R*math.sin(2*math.pi*6/8 - math.pi/2)-10),
           color=GREEN, width=1.9, label="resolve reports")
flow_arrow((ax, ay+20),
           (sys_cx + R*math.cos(2*math.pi*7/8 - math.pi/2),
            sys_cy + R*math.sin(2*math.pi*7/8 - math.pi/2)+10),
           color=GREEN, width=1.9, label="approve / analytics")

# =========================================================
# CAPACITY GUARD doodle (DB lock icon near 5.0)
# =================================================
lock_cx = int(sys_cx + R*math.cos(2*math.pi*4/8 - math.pi/2))
lock_cy = int(sys_cy + R*math.sin(2*math.pi*4/8 - math.pi/2))
d.ellipse([lock_cx-16, lock_cy-28, lock_cx+16, lock_cy-4],
          outline=INK, width=2)
d.line(_wobble((lock_cx-11, lock_cy-10), (lock_cx+11, lock_cy-10)),
       fill=INK, width=2)
d.ellipse([lock_cx-7, lock_cy-10, lock_cx+7, lock_cy+4],
          outline=INK, width=2)
sketch_text((lock_cx+22, lock_cy-30),
            "row-locked accept", color=INK, size=10, font=F_SMALL)

# =========================================================
# LEGEND (bottom-left corner)
# =================================================
leg_x, leg_y = 70, H-150
pencil_rect((leg_x-12, leg_y-12), (560, 122), color=INK, width=2, amp=2.4,
            fill=(255,255,255,14))
sketch_text((leg_x, leg_y-4),
            "legend", color=INK, size=13, font=F_LABEL)
items = [
    (RED,   "Student flows (search, book, rate, report)"),
    (BLUE,  "Landlord flows (listings, replies, decisions)"),
    (GREEN, "Administrator flows (approve, manage, resolve)"),
    (INK,   "Data stores D1–D8  /  modules 1.0–8.0"),
]
for i,(c,t) in enumerate(items):
    yy = leg_y + 14 + i*20
    d.ellipse([leg_x, yy-5, leg_x+12, yy+7], fill=c)
    sketch_text((leg_x+20, yy-7), t, color=INK, size=11, font=F_SMALL)

# =========================================================
# MARGIN DOODLES: tiny houses, beds, stars, question marks
# =================================================
def tiny_house(cx, cy, scale=1.0, color=INK):
    s = float(scale)
    ix = int(cx)
    iy = int(cy)
    # roof triangle
    d.line(_wobble((ix-int(18*s), iy+int(6*s)), (ix, iy-int(22*s)), amp=1.0),
           fill=color, width=2)
    d.line(_wobble((ix, iy-int(22*s)), (ix+int(18*s), iy+int(6*s)), amp=1.0),
           fill=color, width=2)
    # body
    d.line(_wobble((ix-int(15*s), iy+int(6*s)), (ix+int(15*s), iy+int(6*s)), amp=1.0),
           fill=color, width=2)
    d.line(_wobble((ix-int(15*s), iy+int(6*s)), (ix-int(15*s), iy+int(30*s)), amp=1.0),
           fill=color, width=2)
    d.line(_wobble((ix+int(15*s), iy+int(6*s)), (ix+int(15*s), iy+int(30*s)), amp=1.0),
           fill=color, width=2)
    d.line(_wobble((ix-int(15*s), iy+int(30*s)), (ix+int(15*s), iy+int(30*s)), amp=1.0),
           fill=color, width=2)

def tiny_bed(cx, cy, scale=1.0, color=INK):
    s=float(scale)
    ix=int(cx)
    iy=int(cy)
    d.line(_wobble((ix-int(16*s), iy), (ix+int(16*s), iy), amp=1.0),
           fill=color, width=2)
    d.line(_wobble((ix-int(16*s), iy+int(4*s)), (ix+int(16*s), iy+int(4*s)), amp=1.0),
           fill=color, width=2)
    d.line(_wobble((ix-int(16*s), iy), (ix-int(16*s), iy+int(4*s)), amp=1.0),
           fill=color, width=2)
    d.line(_wobble((ix+int(16*s), iy), (ix+int(16*s), iy+int(4*s)), amp=1.0),
           fill=color, width=2)
    # pillow
    d.ellipse([ix-int(9*s), iy-int(3*s), ix-int(4*s), iy+int(2*s)], fill=color)
    # blanket lines
    for yy in range(1,4):
        d.line(_wobble((ix-int(14*s), iy+int(yy*s)), (ix+int(14*s), iy+int(yy*s)),
                        amp=0.5), fill=color, width=1)

def star(cx, cy, n=5, r_out=9, r_in=4, color=RED, w=2.0):
    ix=int(cx)
    iy=int(cy)
    pts=[]
    for i in range(n*2):
        r = r_out if i%2==0 else r_in
        ang = math.pi/2 + math.pi*i/n + random.uniform(-0.06,0.06)
        pts.append((int(ix+r*math.cos(ang)), int(iy+r*math.sin(ang))))
    d.line(pts+[pts[0]], fill=color, width=int(w), joint="curve")

def question_mark(cx, cy, color=INK, size=11):
    ix=int(cx)
    iy=int(cy)
    d.line(_wobble((ix-7, iy+8), (ix-7, iy-2), amp=0.7),
           fill=color, width=int(size))
    d.line(_wobble((ix-8, iy+5), (ix-2, iy-4), amp=0.7),
           fill=color, width=int(size))
    d.line(_wobble((ix-2, iy-4), (ix+4, iy+3), amp=0.7),
           fill=color, width=int(size))
    d.ellipse([ix+4, iy-4, ix+7, iy-1], outline=color, width=int(size))

# sprinkle tiny houses near landlord
for i in range(8):
    tx = random.randint(W//2+300, W-120)
    ty = random.randint(60, 240)
    tiny_house(tx, ty, scale=random.uniform(0.6,1.1),
               color=(120,150,200, random.randint(80,150)))

# sprinkle tiny beds near student
for i in range(7):
    tx = random.randint(120, W//2-300)
    ty = random.randint(60, 240)
    tiny_bed(tx, ty, scale=random.uniform(0.6,1.1),
             color=(200,150,120, random.randint(80,150)))

# stars near rating module
rating_cx, rating_cy = sys_cx + R*math.cos(2*math.pi*5/8 - math.pi/2), \
                        sys_cy + R*math.sin(2*math.pi*5/8 - math.pi/2)
for i in range(5):
    star(rating_cx + random.randint(-30,30)*1,
         rating_cy + 70 + i*14,
         r_out=random.randint(5,8), r_in=random.randint(2,3),
         color=RED)
# question marks near search
search_cx, search_cy = sys_cx + R*math.cos(2*math.pi*2/8 - math.pi/2), \
                        sys_cy + R*math.sin(2*math.pi*2/8 - math.pi/2)
for i in range(4):
    question_mark(search_cx + random.randint(-40,40),
                  search_cy - 50 - i*16, color=BLUE)

# footer: sheet number + date handwritten-style
sketch_text((W-inset-380, H-inset-36),
            "Sheet 1 of 1   ·   sketch — not a UI mockup",
            color=(120,120,120), size=12, font=F_SMALL)
sketch_text((W-inset-380, H-inset-16),
            "BHIMS · DMMMSU–NLUC · 8 data stores, 8 processes, 3 actors",
            color=(120,120,120), size=11, font=F_SMALL)

# -------------------------------------------------
out = "BHIMS_system_sketch_lowfidelity.png"
img.save(out, dpi=(150,150))
print("saved", out, img.size)

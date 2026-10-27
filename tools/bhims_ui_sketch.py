#!/usr/bin/env python3
"""
BHIMS — Boarding House Information Management System
Low-fidelity UI sketch (pencil style).

Hand-drawn sheets of the real app chrome and key screens, taken from the actual
templates in core/templates/core/. This is a paper notebook of wireframes, not
the polished UI and not the system-flow diagram.

Sheet 1 - chrome: topbar/navbar, sidebar nav, public footer
Sheet 2 - landing / home (hero, trust bar, features, featured carousel, CTA)
Sheet 3 - browse listings (filter card, results grid, skeleton, pager)
Sheet 4 - boarding house detail (hero photos, rooms, summary sidebar, inquiry CTA)
Sheet 5 - student flows: inquiries list, inquiry thread, send inquiry, my bookings
Sheet 6 - landlord flows: my boarding houses, inquiry list, accept/decline, my ratings
Sheet 7 - admin flows: dashboard, pending listings approve/reject, manage landlords/students,
         reports resolve/dismiss, barangays, analytics, settings
Sheet 8 - auth: sign-in / sign-up split card, remember me, forgot password, lockout banner
"""

from PIL import Image, ImageDraw, ImageFont
import math, random

random.seed(13)

W, H = 1700, 2500
PAPER = (250, 244, 228)
INK   = (46, 40, 34)
RED   = (188, 72, 47)
BLUE  = (60, 84, 120)
GREEN = (90, 120, 80)
TEAL  = (28, 90, 76)
GOLD  = (178, 136, 50)
FENCE = 6

img = Image.new("RGB", (W, H), PAPER)
_real_d = ImageDraw.Draw(img)
px = img.load()

def _ci(o):
    if isinstance(o, tuple):
        return tuple(_ci(x) for x in o)
    if isinstance(o, list):
        return [_ci(x) for x in o]
    if isinstance(o, float):
        return int(o)
    if isinstance(o, int):
        return o
    return o

class DE:
    def __getattr__(self, name):
        f = getattr(_real_d, name)
        def coerced(*a, **kw):
            return f(*(_ci(x) for x in a), **{k:_ci(v) for k,v in kw.items()})
        return coerced
d = DE()

# ---------- paper grain ----------
for _ in range(11000):
    x = random.randint(0, W-1); y = random.randint(0, H-1)
    r = random.randint(0, 5); v = random.randint(-16, 16)
    for yy in range(max(0,y-r), min(H,y+r+1)):
        for xx in range(max(0,x-r), min(W,x+r+1)):
            if (xx-x)**2 + (yy-y)**2 <= r*r:
                a,b,c = px[xx,yy]
                px[xx,yy] = (max(0,min(255,a+v)), max(0,min(255,b+v)), max(0,min(255,c+v)))

for _ in range(5):
    cx = random.randint(150, W-150); cy = random.randint(150, H-150)
    rr = random.randint(110, 260)
    for ang in range(0, 360, 3):
        r = rr * math.sqrt(random.random())
        x = int(cx + r*math.cos(math.radians(ang)))
        y = int(cy + r*math.sin(math.radians(ang)))
        if 0 <= x < W and 0 <= y < H:
            a,b,c = px[x,y]
            px[x,y] = (min(255,a+6), min(255,b+5), min(255,c+3))

# ---------- fonts ----------
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/local/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/DejaVuSans.ttf",
]
def tf(pat, sz):
    for p in pat:
        try: return ImageFont.truetype(p, sz)
        except Exception: continue
    return ImageFont.load_default()
F_TITLE = tf(FONT_PATHS, 26)
F_SUB   = tf(FONT_PATHS, 15)
F_LABEL = tf(FONT_PATHS, 13)
F_SMALL = tf(FONT_PATHS, 11)
F_HUGE  = tf(FONT_PATHS, 42)
F_NOTE  = tf(FONT_PATHS, 10)

# ---------- helpers ----------
def _w(p0,p1,amp=2.2,steps=None):
    dx=float(p1[0]-p0[0]); dy=float(p1[1]-p0[1]); dist=math.hypot(dx,dy)
    steps=steps or max(2,int(dist/6))
    pts=[(int(p0[0]),int(p0[1]))]
    for i in range(1,steps):
        t=i/steps; bx=p0[0]+dx*t; by=p0[1]+dy*t
        pts.append((int(bx+random.uniform(-amp,amp)), int(by+random.uniform(-amp,amp))))
    pts.append((int(p1[0]),int(p1[1])))
    return pts

def pl(p0,p1,color=INK,width=2,amp=2.2):
    d.line(_w(p0,p1,amp=amp), fill=color, width=width, joint="curve")

def pr(corner,size,color=INK,width=2,amp=2.6,fill=None):
    x,y=corner; w,h=size
    e1=_w((x,y),(x+w,y),amp=amp); e2=_w((x+w,y),(x+w,y+h),amp=amp)
    e3=_w((x+w,y+h),(x,y+h),amp=amp); e4=_w((x,y+h),(x,y),amp=amp)
    if fill: d.polygon([(x,y),(x+w,y),(x+w,y+h),(x,y+h)], fill=fill)
    for e in (e1,e2,e3,e4):
        d.line([(int(p[0]),int(p[1])) for p in e], fill=color, width=int(width), joint="curve")

def ch(corner,size,color=INK,width=1,spacing=7):
    x,y=corner; w,h=size
    for i in range(0,int(w+math.hypot(w,h)),spacing):
        p0=(x - h*0.4 + i, y); p1=(x - h*0.4 + i + h, y + h)
        d.line(_w(p0,p1,amp=0.9,steps=max(2,int(h/5))), fill=color, width=width)
    for i in range(0,int(h+math.hypot(w,h)),spacing):
        p0=(x - h*0.4 + i, y); p1=(x - h*0.4 + i - h, y + h)
        d.line(_w(p0,p1,amp=0.9,steps=max(2,int(h/5))), fill=color, width=width)

def sp(corner,size,color=INK,r=1.4,count=40):
    x,y=corner; w,h=size
    for _ in range(count):
        sx=random.uniform(x,x+w); sy=random.uniform(y,y+h)
        d.ellipse([sx-r,sy-r,sx+r,sy+r], fill=color)

def st(cxy,text,*,color=INK,size=13,font=None,jitter=1.1):
    x,y=cxy
    for dx in (-1,0,1):
        for dy in (-1,0,1):
            if dx==0 and dy==0: continue
            d.text((x+dx*random.uniform(-0.4,0.4), y+dy*random.uniform(-0.4,0.4)),
                   text, font=font, fill=color+(70,))
    d.text((x,y), text, font=font, fill=color)

def sl(sz=13,color=INK):
    # simple underline-style textbox with optional label
    return sz

# =========================================================
# SHEET FRAME: big notebook grid, title strip at top
# =========================================================
inset = 40
pr((inset,inset),(W-2*inset, H-2*inset), color=INK, width=3, amp=4.0)
pl((inset+10,inset+10),(W-inset-10,inset+10), INK, width=1)
st((inset+18,inset+10), "BHIMS — UI sketch (low-fidelity)", color=INK, size=24, font=F_TITLE)
st((inset+22,inset+44), "paper notebook of the real screens — from core/templates/  ·  not a mockup, not the polished UI", color=BLUE, size=13, font=F_SUB)

for (cx1,cy1,cx2,cy2) in [
    (inset+10,inset+10,inset+34,inset+34),
    (W-inset-10,inset+10,W-inset-34,inset+34),
    (inset+10,H-inset-10,inset+34,H-inset-34),
    (W-inset-10,H-inset-10,W-inset-34,H-inset-34),
]:
    d.ellipse([min(cx1,cx2),min(cy1,cy2),max(cx1,cx2),max(cy1,cy2)], outline=RED, width=3)

# page numbers bottom-right
st((W-inset-260, H-inset-34), "8 sketch sheets  ·  BHIMS  ·  DMMMSU–NLUC", color=(120,120,120), size=12, font=F_SMALL)
st((W-inset-260, H-inset-14), "UI notebook — chrome, landing, browse, detail, student, landlord, admin, auth", color=(120,120,120), size=11, font=F_SMALL)

# =========================================================
# SHEET 1 — CHROME  (topbar / navbar, sidebar, footer)
# =================================================
x0,y0 = inset+30, inset+120
w,h = W-2*inset-60, 300
pr((x0,y0),(w,h), color=INK, width=2.4, amp=3.0, fill=(255,255,255,14))
st((x0+14,y0+8), "SHEET 1 — app chrome", color=TEAL, size=13, font=F_LABEL)
st((x0+150,y0+8), "navbar · sidebar · footer", color=(120,120,120), size=11, font=F_SMALL)

# ---- topbar ----
tb_x, tb_y, tb_w, tb_h = x0+20, y0+40, w-40, 58
pr((tb_x,tb_y),(tb_w,tb_h), color=INK, width=2.2, amp=2.4, fill=(238,242,247,22))
# hamburger icon (hamburger lines)
for i in range(3):
    pl((tb_x+10, tb_y+12+i*10), (tb_x+34, tb_y+12+i*10), color=(0,0,0), width=2, amp=0.8)
# brand mark + wordmark
d.ellipse([tb_x+44, tb_y+12, tb_x+68, tb_y+36], outline=INK, width=2)
st((tb_x+74, tb_y+20), "BHIMS", color=INK, size=14, font=F_LABEL)
st((tb_x+112, tb_y+20), "Boarding House Information Management System", color=(120,120,120), size=9, font=F_SMALL)
# right side: sign in, landlord, theme toggle
pl((tb_x+tb_w-220, tb_y+12), (tb_x+tb_w-150, tb_y+12), color=INK, width=2, amp=0.8)
pl((tb_x+tb_w-220, tb_y+30), (tb_x+tb_w-150, tb_y+30), color=INK, width=2, amp=0.8)
st((tb_x+tb_w-228, tb_y+8), "Sign in", color=INK, size=11, font=F_SMALL)
st((tb_x+tb_w-158, tb_y+8), "Landlord", color=INK, size=11, font=F_SMALL)
# theme toggle moon/sun
d.ellipse([tb_x+tb_w-90, tb_y+14, tb_x+tb_w-50, tb_y+34], outline=INK, width=2)
d.ellipse([tb_x+tb_w-82, tb_y+18, tb_x+tb_w-56, tb_y+32], fill=INK)

# ---- sidebar (collapsible rail) ----
sb_x, sb_y, sb_w, sb_h = x0+20, y0+118, 200, 178
pr((sb_x,sb_y),(sb_w,sb_h), color=INK, width=2.2, amp=2.4, fill=(238,242,247,22))
# sidebar header: close X
pl((sb_x+10, sb_y+10), (sb_x+30, sb_y+30), color=INK, width=2, amp=0.8)
pl((sb_x+10, sb_y+30), (sb_x+30, sb_y+10), color=INK, width=2, amp=0.8)
st((sb_x+38, sb_y+18), "Menu", color=INK, size=11, font=F_SMALL)
# nav links (student role shown)
links = [
    ("Dashboard", "grid-1x2"),
    ("Browse Listings", "house-door"),
    ("My Inquiries NEW", "chat-dots"),
    ("My Bookings", "patch-check"),
    ("My Profile", "person-circle"),
]
ly = sb_y+34
for label, icon in links:
    d.ellipse([sb_x+12, ly, sb_x+28, ly+14], outline=INK, width=2)
    pl((sb_x+36, ly+6), (sb_x+36, ly+12), INK, width=2, amp=0.6)
    pl((sb_x+36, ly+12), (sb_x+42, ly+12), INK, width=2, amp=0.6)
    st((sb_x+46, ly+1), label, color=INK, size=10, font=F_SMALL)
    ly += 22

# NEW chip doodle
d.ellipse([sb_x+sb_w-44, sb_y+74, sb_x+sb_w-20, sb_y+90], outline=RED, width=2, fill=(255,220,210,20))
st((sb_x+sb_w-40, sb_y+78), "NEW", color=RED, size=9, font=F_SMALL)

# profile card bottom of sidebar
pc_y = sb_y+sb_h-40
d.ellipse([sb_x+14, pc_y, sb_x+36, pc_y+22], outline=INK, width=2)
st((sb_x+42, pc_y+4), "J. Layco", color=INK, size=10, font=F_SMALL)
st((sb_x+42, pc_y+14), "student", color=(120,120,120), size=9, font=F_SMALL)
pl((sb_x+14, pc_y+30), (sb_x+36, pc_y+30), color=INK, width=2, amp=0.8)

# ---- footer (small strip) ----
ft_y = y0+h-30
pr((x0,ft_y),(w,22), color=INK, width=1.8, amp=2.0, fill=(238,242,247,22))
st((x0+12, ft_y+6), "BHIMS · DMMMSU–NLUC, Bacnotan", color=(120,120,120), size=9, font=F_SMALL)
st((x0+w-120, ft_y+6), "Student portal · Landlord portal", color=(120,120,120), size=9, font=F_SMALL)
# small doodles: lamp, building
d.ellipse([int(x0+200), int(ft_y+7), int(x0+212), int(ft_y+15)], outline=INK, width=1)
d.line(_w((int(x0+206),int(ft_y+15)),(int(x0+206),int(ft_y+20))), INK, width=1)
d.line(_w((int(x0+130),int(ft_y+20)),(int(x0+170),int(ft_y+20))), INK, width=1)
d.line(_w((int(x0+130),int(ft_y+20)),(int(x0+130),int(ft_y+12))), INK, width=1)
d.line(_w((int(x0+170),int(ft_y+20)),(int(x0+170),int(ft_y+12))), INK, width=1)

# =========================================================
# SHEET 2 — LANDING / HOME
# =================================================
x0,y0 = inset+30, y0+h+50
w,h = W-2*inset-60, 520
pr((x0,y0),(w,h), color=INK, width=2.4, amp=3.0, fill=(255,255,255,14))
st((x0+14,y0+8), "SHEET 2 — landing / home", color=TEAL, size=13, font=F_LABEL)
st((x0+200,y0+8), "hero · trust bar · features · featured carousel · CTA", color=(120,120,120), size=11, font=F_SMALL)

# hero band (photo caption overlay)
hh_x, hh_y, hh_w, hh_h = x0+20, y0+40, w-40, 168
pr((hh_x,hh_y),(hh_w,hh_h), color=INK, width=2.2, amp=2.4, fill=(241,246,251,22))
# campus photo chunk
d.rectangle([hh_x+20, hh_y+20, hh_x+hh_w-20, hh_y+hh_h-20], fill=(224,232,240,60))
pl((hh_x+20,hh_y+20),(hh_x+hh_w-20,hh_y+20), INK, width=1, amp=1.2)
# caption pill
d.ellipse([hh_x+hh_w-200, hh_y+hh_h-30, hh_x+hh_w-40, hh_y+hh_h-8], outline=INK, width=2, fill=(10,22,38,80))
st((hh_x+hh_w-180, hh_y+hh_h-24), "DMMMSU–NLUC Campus · Bacnotan, La Union", color=(255,255,255), size=9, font=F_SMALL)
# kicker pill
d.ellipse([hh_x+40, hh_y+16, hh_x+170, hh_y+32], outline=INK, width=1.6, fill=(255,255,255,90))
st((hh_x+60, hh_y+19), "NLUC Bacnotan Student Housing", color=(60,70,80), size=9, font=F_SMALL)
st((hh_x+190, hh_y+60), "Find Your Place. Feel at Home.", color=INK, size=22, font=F_SUB)
st((hh_x+200, hh_y+98), "Verified boarding houses around DMMMSU–NLUC Bacnotan — prices, barangays,", color=(80,80,80), size=11, font=F_SMALL)
st((hh_x+200, hh_y+112), "and a direct line to the landlord.", color=(80,80,80), size=11, font=F_SMALL)
# two buttons: student sign in / landlord sign in
pr((hh_x+190, hh_y+132), (150,32), color=TEAL, width=2.2, amp=2.0, fill=(20,86,60,40))
st((hh_x+192, hh_y+136), "Student sign in", color=(255,255,255), size=11, font=F_SMALL)
pr((hh_x+352, hh_y+132), (150,32), color=INK, width=1.8, amp=2.0, fill=(255,255,255,40))
st((hh_x+355, hh_y+136), "Landlord sign in", color=TEAL, size=11, font=F_SMALL)

# floating glass chips over hero
for i,(lx,ly,t1,t2) in enumerate([(hh_x+hh_w-260, hh_y+60,"Admin-verified", "houses only"),
                                  (hh_x+60, hh_y+40,"Direct chat", "with landlords")]):
    d.ellipse([lx,ly,lx+120,ly+36], outline=BLUE, width=1.6, fill=(255,255,255,70))
    st((lx+10, ly+10), t1, color=INK, size=10, font=F_SMALL)
    st((lx+10, ly+22), t2, color=(80,80,80), size=9, font=F_SMALL)

# trust bar
tb_x, tb_y = x0+20, hh_y+hh_h+14
pr((tb_x,tb_y),(w-40,54), color=INK, width=1.8, amp=2.0, fill=(238,242,247,22))
for i,(big,small) in enumerate([("Verified","Admin-reviewed houses"),
                                 ("Direct chat","Message landlords in-app"),
                                 ("Campus-near","Barangays around NLUC")]):
    bx = tb_x+14 + i*((w-40-28)//3)
    st((bx, tb_y+8), big, color=TEAL, size=12, font=F_LABEL)
    st((bx, tb_y+24), small, color=(100,100,100), size=9, font=F_SMALL)

# features grid (3 cards)
fx, fy = x0+20, tb_y+72
fw, fh = (w-40-20)//3, 132
for i,(title,icon) in enumerate([("Browse Listings","card-list"),
                                  ("Connect Directly","chat-dots"),
                                  ("Curated Listings","patch-check")]):
    cx = fx + i*(fw+10)
    pr((cx,fy),(fw,fh), color=INK, width=1.8, amp=2.0, fill=(245,248,252,18))
    d.ellipse([cx+fw/2-20, fy+10, cx+fw/2+20, fy+34], outline=TEAL, width=2, fill=(20,86,60,30))
    st((cx+fw/2-14, fy+16), icon, color=TEAL, size=12, font=F_SMALL)
    st((cx+fw/2-40, fy+44), title, color=INK, size=12, font=F_LABEL)
    st((cx+10, fy+62), "Filter by barangay, rent, and room type. See what's actually open before you walk over.", color=(100,100,100), size=8.5, font=F_SMALL)
    st((cx+10, fy+74), "Message the landlord in the app. Ask about vacancies, visiting hours,", color=(100,100,100), size=8.5, font=F_SMALL)
    st((cx+10, fy+86), "and house rules without sharing your number first.", color=(100,100,100), size=8.5, font=F_SMALL)
    st((cx+10, fy+98), "Listings go through admin review before they show up. You're looking at", color=(100,100,100), size=8.5, font=F_SMALL)
    st((cx+10, fy+110), "houses that made it past that check.", color=(100,100,100), size=8.5, font=F_SMALL)

# featured carousel strip
cx0, cy0 = x0+20, fy+fh+16
cw, chh = w-40, 56
pr((cx0,cy0),(cw,chh), color=INK, width=1.8, amp=2.0, fill=(255,255,255,18))
# three cards in a row
ccw = (cw-20-20)//3
for i in range(3):
    cxx = cx0+10 + i*(ccw+10)
    pr((cxx,cy0+6),(ccw-4,44), color=INK, width=1.6, amp=1.8, fill=(255,255,255,20))
    d.rectangle([cxx+4, cy0+10, cxx+ccw-8, cy0+44], fill=(224,232,240,70))
    st((cxx+8, cy0+14), "₱2,400", color=TEAL, size=11, font=F_LABEL)
    st((cxx+8, cy0+26), "Illacandia Student Home", color=INK, size=9, font=F_SMALL)
    st((cxx+8, cy0+36), "Sapilang (Walking distance) · 1 open", color=(100,100,100), size=8, font=F_SMALL)
    # open badge
    st((cxx+ccw-40, cy0+10), "1 open", color=TEAL, size=8, font=F_SMALL)
# arrows
for ax in (cx0+6, cx0+cw-14):
    d.ellipse([ax, cy0+chh/2-10, ax+20, cy0+chh/2+10], outline=INK, width=2, fill=(255,255,255,40))
    d.line([tuple(int(v) for v in (ax+10, cy0+chh/2)), tuple(int(v) for v in (ax+10, cy0+chh/2-6)), tuple(int(v) for v in (ax+10, cy0+chh/2+6))], fill=INK, width=2)
st((cx0+cw/2-40, cy0+chh+6), "sliding row · admin-verified houses", color=(120,120,120), size=9, font=F_SMALL)

# CTA band
cta_x, cta_y = x0+20, cy0+chh+24
pr((cta_x,cta_y),(cw,48), color=TEAL, width=2.2, amp=2.4, fill=(20,86,60,30))
st((cta_x+20, cta_y+12), "Your next room is a few taps away", color=(255,255,255), size=13, font=F_LABEL)
st((cta_x+20, cta_y+26), "Browse verified listings for free, message landlords directly, and book your stay.", color=(220,235,225), size=9, font=F_SMALL)
pr((cta_x+cw-170, cta_y+6), (150,34), color=(255,255,255,60), width=2, amp=1.6)
st((cta_x+cw-168, cta_y+10), "Student sign in", color=(255,255,255), size=10, font=F_SMALL)
pr((cta_x+cw-330, cta_y+6), (150,34), color=(255,255,255,30), width=2, amp=1.6)
st((cta_x+cw-328, cta_y+10), "Landlord sign in", color=(255,255,255), size=10, font=F_SMALL)

# =========================================================
# SHEET 3 — BROWSE LISTINGS
# =================================================
x0,y0 = inset+30, cta_y+chh+60
w,h = W-2*inset-60, 300
pr((x0,y0),(w,h), color=INK, width=2.4, amp=3.0, fill=(255,255,255,14))
st((x0+14,y0+8), "SHEET 3 — browse listings", color=TEAL, size=13, font=F_LABEL)
st((x0+200,y0+8), "filter card · results grid · skeleton · pager", color=(120,120,120), size=11, font=F_SMALL)

# page header
ph_x, ph_y = x0+20, y0+40
pr((ph_x,ph_y),(w-40,60), color=INK, width=1.8, amp=2.0, fill=(245,248,252,18))
st((ph_x+14, ph_y+8), "Browse", color=TEAL, size=11, font=F_SMALL)
st((ph_x+14, ph_y+22), "Boarding houses near NLUC", color=INK, size=17, font=F_SUB)
st((ph_x+14, ph_y+44), "Hi Jade. Filter by rent and barangay, then message the landlord from the listing.", color=(100,100,100), size=10, font=F_SMALL)
st((ph_x+w-40-120, ph_y+44), "My Inquiries NEW", color=TEAL, size=10, font=F_SMALL)

# filter card (details)
fc_x, fc_y = ph_x, ph_y+72
fc_w, fc_h = (w-40-20)//2-6, 200
pr((fc_x,fc_y),(fc_w,fc_h), color=BLUE, width=2.0, amp=2.0, fill=(238,243,250,20))
st((fc_x+12, fc_y+10), "Filter listings", color=INK, size=11, font=F_LABEL)
st((fc_x+fc_w-70, fc_y+10), "Reset", color=TEAL, size=10, font=F_SMALL)
for i,(label,placeholder) in enumerate([("Price min","₱0"),
                                         ("Price max","₱10,000"),
                                         ("Room type","Any"),
                                         ("Barangay","Any"),
                                         ("Amenities","comma list"),
                                         ("Sort","newest")]):
    ly = fc_y+30 + i*24
    st((fc_x+12, ly), label, color=(80,80,80), size=9, font=F_SMALL)
    d.line(_w((fc_x+90,ly),(fc_x+fc_w-16,ly),amp=0.6), fill=(180,180,180), width=1)
    st((fc_x+fc_w-40, ly), placeholder, color=(140,140,140), size=9, font=F_SMALL)
st((fc_x+12, fc_y+fc_h-22), "Apply filters", color=TEAL, size=10, font=F_SMALL)
st((fc_x+12, fc_y+fc_h-34), "Filters apply as you type.", color=(120,120,120), size=9, font=F_SMALL)

# results grid
rg_x, rg_y = fc_x+fc_w+16, fc_y
rg_w, rg_h = w-40-(fc_w+16)-10, fc_h
pr((rg_x,rg_y),(rg_w,rg_h), color=INK, width=1.8, amp=2.0, fill=(255,255,255,16))
st((rg_x+10, rg_y+6), "6 boarding houses found", color=TEAL, size=10, font=F_SMALL)
# grid of 2x3 cards
ccw2 = (rg_w-20-20)//2
for i in range(6):
    rxx = rg_x+10 + (i%2)*(ccw2+10)
    ryy = rg_y+24 + (i//2)*((rg_h-30)//3)
    pr((rxx,ryy),(ccw2-4, (rg_h-30)//3-6), color=INK, width=1.4, amp=1.6, fill=(255,255,255,18))
    st((rxx+6, ryy+4), "₱1,800", color=TEAL, size=10, font=F_SMALL)
    st((rxx+6, ryy+12), "Sunrise Boarding", color=INK, size=9, font=F_SMALL)
    st((rxx+6, ryy+22), "Arosip (2.5 km)", color=(100,100,100), size=8, font=F_SMALL)
    st((rxx+6, ryy+32), "1 open · ₱1,800 / month", color=(120,120,120), size=8, font=F_SMALL)

# skeleton row overlay (loading state)
sk_x, sk_y = rg_x+10, rg_y+rg_h-44
for i in range(2):
    sxx = sk_x + i*(ccw2+10)
    d.rectangle([sxx, sk_y, sxx+ccw2-4, sk_y+30], fill=(200,206,214,70))
    for j in range(4):
        d.line(_w((sxx+6,sk_y+4+j*6),(sxx+ccw2-12,sk_y+4+j*6),amp=0.5), fill=(180,186,194), width=1)

# pager strip
pg_x, pg_y = rg_x+10, rg_y+rg_h-12
d.line(_w((pg_x,pg_y),(rg_x+rg_w-10,pg_y)), INK, width=1)
st((pg_x, pg_y-8), "← prev   1 2 3   next →", color=(100,100,100), size=9, font=F_SMALL)

# =========================================================
# SHEET 4 — BOARDING HOUSE DETAIL
# =================================================
x0,y0 = inset+30, pg_y+14
w,h = W-2*inset-60, 410
pr((x0,y0),(w,h), color=INK, width=2.4, amp=3.0, fill=(255,255,255,14))
st((x0+14,y0+8), "SHEET 4 — boarding house detail", color=TEAL, size=13, font=F_LABEL)
st((x0+260,y0+8), "hero photos · rooms · summary sidebar · inquiry CTA", color=(120,120,120), size=11, font=F_SMALL)

# hero photo strip (5 photos)
hp_x, hp_y, hp_w, hp_h = x0+20, y0+40, w-40, 118
pr((hp_x,hp_y),(hp_w,hp_h), color=INK, width=1.8, amp=2.0, fill=(224,232,240,30))
for i in range(5):
    pxx = hp_x+10 + i*((hp_w-20)//5)
    pww = (hp_w-20)//5-4
    d.rectangle([pxx, hp_y+8, pxx+pww, hp_y+hp_h-8], fill=(214,222,232,80))
    # doodle of a bed
    tiny_bed(pxx+pww/2, hp_y+hp_h/2, scale=0.8, color=(80,80,80))
    if i == 0:
        d.ellipse([pxx+4, hp_y+18, pxx+18, hp_y+36], outline=TEAL, width=1.6, fill=(20,86,60,30))
        st((pxx+2, hp_y+18), "1/5", color=(255,255,255), size=8, font=F_SMALL)
# back link
st((hp_x+10, hp_y+hp_h+8), "← All listings", color=TEAL, size=11, font=F_SMALL)

# layout: copy left, summary sidebar right
lc_x, lc_y, lc_w = hp_x, hp_y+hp_h+30, (w-40-16)//2
ls_x, ls_y, ls_w = lc_x+lc_w+10, lc_y, w-40-lc_w-10

# copy
pr((lc_x,lc_y),(lc_w, h-(lc_y-y0)-14), color=INK, width=1.8, amp=2.0, fill=(255,255,255,16))
st((lc_x+10, lc_y+8), "Illacandia Student Home", color=INK, size=16, font=F_SUB)
st((lc_x+10, lc_y+30), "J. Layco", color=TEAL, size=11, font=F_SMALL)
st((lc_x+10, lc_y+44), "Rooms", color=INK, size=12, font=F_LABEL)
for i,(name,cap,fill,price) in enumerate([("Standard Room", "1", "0/1 filled", "₱2,400"),
                                           ("Double Room", "2", "1/2 filled", "₱3,200")]):
    ry = lc_y+60 + i*78
    pr((lc_x+10,ry),(lc_w-20,68), color=INK, width=1.6, amp=1.8, fill=(252,254,256,24))
    d.rectangle([lc_x+14, ry+8, lc_x+34, ry+40], fill=(224,232,240,90))
    st((lc_x+40, ry+6), name, color=INK, size=11, font=F_LABEL)
    st((lc_x+40, ry+18), "1 beds · Standard", color=(100,100,100), size=9, font=F_SMALL)
    st((lc_x+40, ry+28), "0/1 filled", color=(120,120,120), size=9, font=F_SMALL)
    st((lc_x+40, ry+38), price, color=TEAL, size=11, font=F_LABEL)
    # amenities tags
    for j,am in enumerate(["Wi-Fi","Water","Fan"]):
        st((lc_x+40+j*50, ry+50), f" {am} ", color=(120,120,120), size=8, font=F_SMALL)
    # inquire CTA
    pr((lc_x+lc_w-120, ry+30), (104,26), color=TEAL, width=2.0, amp=1.6)
    st((lc_x+lc_w-118, ry+34), "Inquire about this room", color=(255,255,255), size=9, font=F_SMALL)

# summary sidebar
pr((ls_x,ls_y),(ls_w, h-(ls_y-y0)-14), color=INK, width=1.8, amp=2.0, fill=(245,248,252,24))
st((ls_x+10, ls_y+8), "Illacandia Student Home", color=INK, size=12, font=F_SUB)
st((ls_x+10, ls_y+28), "Sapilang (Walking distance), Bacnotan", color=TEAL, size=10, font=F_SMALL)
for i,(dt,vl) in enumerate([("From","₱2,400 / month"),
                             ("Who can stay","Both (Male & Female)"),
                             ("Open rooms","1 available")]):
    ry = ls_y+50 + i*30
    st((ls_x+10, ry), dt, color=(100,100,100), size=10, font=F_SMALL)
    st((ls_x+ls_w-10, ry), vl, color=INK, size=10, font=F_SMALL)
pr((ls_x+10, ls_y+ls_w+10), (ls_w-20,30), color=TEAL, width=2.0, amp=1.6)
st((ls_x+14, ls_y+ls_w+14), "Message landlord", color=(255,255,255), size=10, font=F_SMALL)

# =========================================================
# SHEET 5 — STUDENT FLOWS: inquiries list · thread · send inquiry · bookings
# =================================================
x0,y0 = inset+30, ls_y+h-14+40
w,h = W-2*inset-60, 640
pr((x0,y0),(w,h), color=INK, width=2.4, amp=3.0, fill=(255,255,255,14))
st((x0+14,y0+8), "SHEET 5 — student flows", color=TEAL, size=13, font=F_LABEL)
st((x0+240,y0+8), "inquiries list · inquiry thread · send inquiry · my bookings", color=(120,120,120), size=11, font=F_SMALL)

# 2x2 grid of four mini-sheets
gw = (w-30)//2; gh = (h-40)//2
def mini_sheet(cx,cy,tw,th,title,accent):
    pr((cx,cy),(tw,th), color=accent, width=2.0, amp=2.2, fill=(255,255,255,16))
    st((cx+10,cy+8), title, color=accent, size=11, font=F_LABEL)
    return cx+8, cy+26, tw-16, th-34

s1x,s1y,s1w,s1h = mini_sheet(x0+10,y0+10,gw,gh,"My Inquiries (NEW badge)", TEAL)
s2x,s2y,s2w,s2h = mini_sheet(x0+10+gw+10,y0+10,gw,gh,"Inquiry Thread", BLUE)
s3x,s3y,s3w,s3h = mini_sheet(x0+10,y0+gh+10,gw,gh,"Send Inquiry", GOLD)
s4x,s4y,s4w,s4h = mini_sheet(x0+10+gw+10,y0+gh+10,gw,gh,"My Bookings", GREEN)

# ---- My Inquiries ----
ix,iy,iw,ih = s1x,s1y,s1w,s1h
pl(_w((ix,iy),(ix+iw,iy)), fill=INK, width=1.4, amp=0.8)
st((ix,iy-8), "Inquiries from landlords", color=TEAL, size=10, font=F_SMALL)
for i,(house,room,new) in enumerate([("Illacandia Student Home","Standard Room",True),
                                       ("Sunrise Boarding","Double Room",False),
                                       ("River View Home","Standard Room",True)]):
    ry = iy+4 + i*40
    pr((ix,ry),(iw,34), color=INK, width=1.4, amp=1.6, fill=(255,255,255,18))
    st((ix+8, ry+4), house, color=INK, size=10, font=F_SMALL)
    st((ix+8, ry+14), room, color=(100,100,100), size=9, font=F_SMALL)
    st((ix+iw-60, ry+8), "NEW", color=RED, size=9, font=F_SMALL) if new else st((ix+iw-60, ry+8), "read", color=(120,120,120), size=9, font=F_SMALL)
    pl(_w((ix+iw-10,ry+6),(ix+iw-10,ry+26)), fill=INK, width=1.4, amp=0.5)

# ---- Inquiry Thread ----
tx,ty,tw,th = s2x,s2y,s2w,s2h
st((tx,ty-8), "Chat with landlord (J. Layco)", color=BLUE, size=10, font=F_SMALL)
# messages bubbles
for i,(who,text,side) in enumerate([("Landlord","Hi! Available starting June.", "left"),
                                     ("Student","Can I see it this weekend?", "right"),
                                     ("Landlord","Saturday afternoon works.", "left")]):
    my = ty+4 + i*44
    if side=="left":
        pr((tx+8,my),(tw*0.6,30), color=BLUE, width=1.6, amp=1.8)
        st((tx+12, my+6), who, color=TEAL, size=9, font=F_SMALL)
        st((tx+12, my+16), text, color=INK, size=9, font=F_SMALL)
    else:
        pr((tx+tw*0.4,my),(tw*0.5-8,30), color=TEAL, width=1.6, amp=1.8)
        st((tx+tw*0.4+8, my+6), text, color=INK, size=9, font=F_SMALL)
# input row
pr((tx+8,ty+th-40),(tw-16,30), color=INK, width=1.4, amp=1.6)
pl(_w((tx+14,ty+th-22),(tx+tw-20,ty+th-22)), fill=INK, width=1.2, amp=0.6)
st((tx+tw-30, ty+th-24), "Send", color=TEAL, size=9, font=F_SMALL)

# ---- Send Inquiry ----
ssx,ssy,ssw,ssh = s3x,s3y,s3w,s3h
for i,(label,placeholder) in enumerate([("Room","Standard Room · ₱2,400"),
                                         ("Subject","About availability"),
                                         ("Message","Is the room still open?")]):
    sy = ssy+8 + i*50
    st((ssx, sy), label, color=(100,100,100), size=9, font=F_SMALL)
    d.line([_w((ssx+70,sy),(ssx+ssw-12,sy),amp=0.6)], fill=(180,180,180), width=1)
    st((ssx+ssw-90, sy), placeholder, color=(140,140,140), size=9, font=F_SMALL)
pr((ssx,ssy+ssh-40),(ssw-16,30), color=TEAL, width=2.0, amp=1.6)
st((ssx+ssw-90, ssy+ssh-34), "Send Inquiry", color=(255,255,255), size=10, font=F_SMALL)

# ---- My Bookings ----
bsx,bsy,bsw,bsh = s4x,s4y,s4w,s4h
st((bsx,bsh-8), "Confirmed bookings", color=GREEN, size=10, font=F_SMALL)
for i,(house,room,status) in enumerate([("Illacandia Student Home","Standard Room","Confirmed"),
                                         ("Sunrise Boarding","Double Room","Confirmed")]):
    by = bsy+8 + i*40
    pr((bsx,by),(bsw,34), color=INK, width=1.4, amp=1.6, fill=(255,255,255,18))
    st((bsx+8, by+4), house, color=INK, size=10, font=F_SMALL)
    st((bsx+8, by+14), room, color=(100,100,100), size=9, font=F_SMALL)
    d.ellipse([bsx+bsw-44, by+8, bsx+bsw-16, by+24], outline=GREEN, width=2, fill=(90,120,80,20))
    st((bsx+bsw-38, by+12), "confirmed", color=GREEN, size=8, font=F_SMALL)

# =========================================================
# SHEET 6 — LANDLORD FLOWS: my boarding houses · inquiry list · accept/decline · ratings
# =================================================
x0,y0 = inset+30, bsy+bsh+14
w,h = W-2*inset-60, 330
pr((x0,y0),(w,h), color=INK, width=2.4, amp=3.0, fill=(255,255,255,14))
st((x0+14,y0+8), "SHEET 6 — landlord flows", color=TEAL, size=13, font=F_LABEL)
st((x0+240,y0+8), "my boarding houses · inquiry list · accept/decline · my ratings", color=(120,120,120), size=11, font=F_SMALL)

# 2x2 again
gw = (w-30)//2; gh = (h-40)//2
def mini2(cx,cy,tw,th,title,accent):
    pr((cx,cy),(tw,th), color=accent, width=2.0, amp=2.2, fill=(255,255,255,16))
    st((cx+10,cy+8), title, color=accent, size=11, font=F_LABEL)
    return cx+8, cy+26, tw-16, th-34

l1x,l1y,l1w,l1h = mini2(x0+10,y0+10,gw,gh,"My Boarding Houses", TEAL)
l2x,l2y,l2w,l2h = mini2(x0+10+gw+10,y0+10,gw,gh,"Inquiries", BLUE)
l3x,l3y,l3w,l3h = mini2(x0+10,y0+gh+10,gw,gh,"Accept / Decline", GOLD)
l4x,l4y,l4w,l4h = mini2(x0+10+gw+10,y0+gh+10,gw,gh,"My Ratings", GREEN)

# My Boarding Houses
for i,(house,status) in enumerate([("Illacandia Student Home","approved"),
                                    ("Sunrise Boarding","pending")]):
    ry = l1y+6 + i*40
    pr((l1x,ry),(l1w,32), color=INK, width=1.4, amp=1.6, fill=(255,255,255,18))
    st((l1x+8, ry+4), house, color=INK, size=10, font=F_SMALL)
    if status=="approved":
        d.ellipse([l1x+l1w-44, ry+6, l1x+l1w-16, ry+22], outline=TEAL, width=2, fill=(20,86,60,20))
        st((l1x+l1w-42, ry+10), "verified", color=TEAL, size=8, font=F_SMALL)
    else:
        st((l1x+l1w-40, ry+10), "pending", color=GOLD, size=8, font=F_SMALL)

# Inquiries (with NEW chip)
for i,(student,message) in enumerate([("J. Layco","Is the room still open?"),
                                       ("M. Bayubay","Can I visit Saturday?")]):
    ry = l2y+6 + i*40
    pr((l2x,ry),(l2w,32), color=INK, width=1.4, amp=1.6, fill=(255,255,255,18))
    st((l2x+8, ry+4), student, color=INK, size=10, font=F_SMALL)
    st((l2x+8, ry+16), message, color=(100,100,100), size=8, font=F_SMALL)
    d.ellipse([l2x+l2w-44, ry+6, l2x+l2w-16, ry+22], outline=RED, width=2, fill=(255,220,210,20))
    st((l2x+l2w-42, ry+10), "NEW", color=RED, size=8, font=F_SMALL)

# Accept / Decline
st((l3x,l3y-8), "Inquiry #2 (Illacandia · Standard Room)", color=BLUE, size=9, font=F_SMALL)
pr((l3x,l3y),(l3w,l3h-8), color=INK, width=1.4, amp=1.6, fill=(255,255,255,18))
st((l3x+8, l3y+6), "Student: J. Layco", color=INK, size=9, font=F_SMALL)
st((l3x+8, l3y+16), "Request: ₱2,400 / month · move-in June", color=(100,100,100), size=8, font=F_SMALL)
st((l3x+8, l3y+26), "Message: Is the room still open?", color=(100,100,100), size=8, font=F_SMALL)
# two buttons
pr((l3x+8, l3y+40),(l3w//2-12,28), color=TEAL, width=2.0, amp=1.6)
st((l3x+10, l3y+44), "Accept", color=(255,255,255), size=10, font=F_SMALL)
pr((l3x+l3w//2+4, l3y+40),(l3w//2-12,28), color=RED, width=2.0, amp=1.6)
st((l3x+l3w//2+6, l3y+44), "Decline", color=(255,255,255), size=10, font=F_SMALL)
st((l3x+8, l3y+l3h-16), "row-locked accept · one booking per inquiry", color=(120,120,120), size=8, font=F_SMALL)

# My Ratings
st((l4x,l4y-8), "Ratings received (average 4.2 / 5)", color=GREEN, size=9, font=F_SMALL)
for i,(student,rating) in enumerate([("J. Layco","★★★★☆ 4.2"),("M. Bayubay","★★★★★ 5.0")]):
    ry = l4y+6 + i*40
    pr((l4x,ry),(l4w,32), color=INK, width=1.4, amp=1.6, fill=(255,255,255,18))
    st((l4x+8, ry+4), student, color=INK, size=10, font=F_SMALL)
    st((l4x+8, ry+16), rating, color=GOLD, size=10, font=F_SMALL)
# average bar
for i in range(5):
    st((l4x+12+i*18, l4y+l4h-14), "★", color=GOLD if i<4 else (120,120,120), size=10, font=F_SMALL)
st((l4x+12, l4y+l4h-4), "4.2 avg · 2 reviews", color=(120,120,120), size=8, font=F_SMALL)

# =========================================================
# SHEET 7 — ADMIN FLOWS: dashboard · pending listings · manage landlords/students ·
#             reports · barangays · analytics · settings
# =================================================
x0,y0 = inset+30, y0+h+40
w,h = W-2*inset-60, 560
pr((x0,y0),(w,h), color=INK, width=2.4, amp=3.0, fill=(255,255,255,14))
st((x0+14,y0+8), "SHEET 7 — admin flows", color=GREEN, size=13, font=F_LABEL)
st((x0+220,y0+8), "dashboard · pending listings · manage landlords/students · reports · barangays · analytics · settings", color=(120,120,120), size=11, font=F_SMALL)

# top dashboard strip with stat cards
sdx,sdy,sdw,sdh = x0+20, y0+40, w-40, 80
pr((sdx,sdy),(sdw,sdh), color=INK, width=1.8, amp=2.0, fill=(238,242,247,22))
st((sdx+10, sdy+6), "Admin Dashboard", color=GREEN, size=14, font=F_SUB)
for i,(big,label) in enumerate([("12","Listings"),("48","Bookings"),("4.3★","Avg rating"),("3","Reports")]):
    cx = sdx+10 + i*((sdw-20)//4)
    st((cx, sdy+34), big, color=TEAL, size=20, font=F_SUB)
    st((cx, sdy+56), label, color=(100,100,100), size=10, font=F_SMALL)
# audit trail doodle
st((sdx+sdw-150, sdy+34), "last action: approved listing #7", color=(120,120,120), size=9, font=F_SMALL)

# 2x3 grid of admin sub-screens
agw = ((w-40-20)//2); agh = ((sdh+80))//3
def asheet(cx,cy,tw,th,title,accent,contents):
    pr((cx,cy),(tw,th), color=accent, width=1.8, amp=2.0, fill=(255,255,255,14))
    st((cx+8,cy+6), title, color=accent, size=10, font=F_LABEL)
    return cx+8, cy+22, tw-16, th-28

a1x,a1y,a1w,a1h = asheet(x0+20, sdy+sdh+10, agw, agh, "Pending Listings — approve / reject", TEAL,
                          [("Illacandia Student Home","₱2,400","approved"),
                           ("New House","₱3,000","pending")])
a2x,a2y,a2w,a2h = asheet(x0+20+agw+10, sdy+sdh+10, agw, agh, "Manage Landlords", BLUE,
                          [("create / edit / deactivate","landlord ID · account status")])
a3x,a3y,a3w,a3h = asheet(x0+20, sdy+sdh+10+agh+10, agw, agh, "Manage Students", BLUE,
                          [("create / edit / deactivate","program · status")])
a4x,a4y,a4w,a4h = asheet(x0+20+agw+10, sdy+sdh+10+agh+10, agw, agh, "User Reports — resolve / dismiss", GOLD,
                          [("Report #3","harassment","pending"),
                           ("Report #1","fake_listing","resolved")])
a5x,a5y,a5w,a5h = asheet(x0+20, sdy+sdh+10+2*(agh+10), agw, agh, "Edit Barangays", BLUE,
                          [("Arosip · 2.5 km","Sapilang · Walking distance","Salincob · 3.2 km")])
a6x,a6y,a6w,a6h = asheet(x0+20+agw+10, sdy+sdh+10+2*(agh+10), agw, agh, "Analytics · Settings", GREEN,
                          [("occupancy · ratings · reports","barangay list · site settings")])

# pending listings content
for i,(house,price,status) in enumerate(a1x,a1y,a1w,a1h):
    pass
for i,(house,price,status) in enumerate([("Illacandia Student Home","₱2,400","approved"),
                                          ("New House","₱3,000","pending")]):
    ry = a1y+6 + i*36
    pr((a1x,ry),(a1w,28), color=INK, width=1.4, amp=1.6, fill=(255,255,255,18))
    st((a1x+8, ry+4), house, color=INK, size=9, font=F_SMALL)
    st((a1x+8, ry+16), price, color=TEAL, size=9, font=F_SMALL)
    if status=="approved":
        st((a1x+a1w-50, ry+6), "APPROVED", color=TEAL, size=8, font=F_SMALL)
    else:
        st((a1x+a1w-50, ry+6), "PENDING", color=GOLD, size=8, font=F_SMALL)
    # approve/reject buttons
    pr((a1x+a1w-150, ry+2), (60,22), color=TEAL, width=1.8, amp=1.4)
    st((a1x+a1w-148, ry+6), "Approve", color=(255,255,255), size=8, font=F_SMALL)
    pr((a1x+a1w-86, ry+2), (60,22), color=RED, width=1.8, amp=1.4)
    st((a1x+a1w-84, ry+6), "Reject", color=(255,255,255), size=8, font=F_SMALL)

# reports content
for i,(rep,reason,status) in enumerate([("Report #3","harassment","pending"),
                                         ("Report #1","fake_listing","resolved")]):
    ry = a4y+6 + i*36
    pr((a4x,ry),(a4w,28), color=INK, width=1.4, amp=1.6, fill=(255,255,255,18))
    st((a4x+8, ry+4), rep, color=INK, size=9, font=F_SMALL)
    st((a4x+8, ry+16), reason, color=(100,100,100), size=8, font=F_SMALL)
    if status=="pending":
        st((a4x+a4w-56, ry+6), "PENDING", color=GOLD, size=8, font=F_SMALL)
    else:
        st((a4x+a4w-64, ry+6), "RESOLVED", color=GREEN, size=8, font=F_SMALL)
    pr((a4x+a4w-150, ry+2), (60,22), color=TEAL, width=1.8, amp=1.4)
    st((a4x+a4w-148, ry+6), "Resolve", color=(255,255,255), size=8, font=F_SMALL)
    pr((a4x+a4w-86, ry+2), (60,22), color=(120,120,120), width=1.8, amp=1.4)
    st((a4x+a4w-84, ry+6), "Dismiss", color=(255,255,255), size=8, font=F_SMALL)

# barangays content
for i,bn in enumerate(["Arosip · 2.5 km","Sapilang · Walking distance","Salincob · 3.2 km"]):
    ry = a5y+6 + i*26
    pr((a5x,ry),(a5w,20), color=INK, width=1.4, amp=1.4, fill=(255,255,255,18))
    st((a5x+8, ry+4), bn, color=INK, size=9, font=F_SMALL)

# analytics content
st((a6x+8, a6y+6), "occupancy · ratings · reports", color=GREEN, size=9, font=F_SMALL)
st((a6x+8, a6y+20), "barangay list · site settings", color=(100,100,100), size=9, font=F_SMALL)
for i in range(4):
    st((a6x+8, a6y+36+i*22), "─" * 20, color=(160,160,160), size=9, font=F_SMALL)

# =========================================================
# SHEET 8 — AUTH: sign-in / sign-up split, remember me, forgot password, lockout
# =================================================
x0,y0 = inset+30, y0+h+40
w,h = W-2*inset-60, 320
pr((x0,y0),(w,h), color=INK, width=2.4, amp=3.0, fill=(255,255,255,14))
st((x0+14,y0+8), "SHEET 8 — auth: sign-in / sign-up", color=TEAL, size=13, font=F_LABEL)
st((x0+280,y0+8), "split card · email/username · password · remember me · forgot password · lockout banner", color=(120,120,120), size=11, font=F_SMALL)

# split card: sign in left, sign up right
asx,asy,asw,ash = x0+20, y0+40, (w-40)//2, 240
pr((asx,asy),(asw,ash), color=INK, width=2.0, amp=2.2, fill=(255,255,255,16))
pr((asx+asw+10,asy),(asw,ash), color=INK, width=2.0, amp=2.2, fill=(255,255,255,16))

# sign in half
st((asx+asx+8, asy+8), "Sign in", color=TEAL, size=12, font=F_LABEL)
for i,(label,placeholder) in enumerate([("Email / username","you@nluc.edu"),
                                         ("Password","••••••••")]):
    sy = asy+30 + i*34
    st((asx+10, sy), label, color=(100,100,100), size=9, font=F_SMALL)
    d.line([_w((asx+100,sy),(asx+asw-12,sy),amp=0.6)], fill=(180,180,180), width=1)
    st((asx+asw-90, sy), placeholder, color=(140,140,140), size=9, font=F_SMALL)
pr((asx+10, asy+ash-44),(asw-20,30), color=TEAL, width=2.0, amp=1.6)
st((asx+14, asy+ash-40), "Sign in", color=(255,255,255), size=10, font=F_SMALL)
# remember me + forgot password row
sy = asy+ash-82
d.ellipse([asx+12, sy, asx+24, sy+12], outline=INK, width=1.6)
st((asx+28, sy+2), "Remember Me", color=INK, size=9, font=F_SMALL)
st((asx+asw-90, sy+2), "Forgot Password?", color=TEAL, size=9, font=F_SMALL)

# sign up half
st((asx+asw+10+8, asy+8), "Create account", color=TEAL, size=12, font=F_LABEL)
for i,(label,placeholder) in enumerate([("Email","you@nluc.edu"),
                                         ("Password","••••••••"),
                                         ("Confirm password","••••••••"),
                                         ("Program","College of Education"),
                                         ("Full name","Jade Badua")]):
    sy = asy+30 + i*34
    st((asx+asw+10+10, sy), label, color=(100,100,100), size=9, font=F_SMALL)
    d.line([_w((asx+asw+10+90,sy),(asx+asw+asw-12,sy),amp=0.6)], fill=(180,180,180), width=1)
    st((asx+asw+asw-90, sy), placeholder, color=(140,140,140), size=9, font=F_SMALL)
pr((asx+asw+10+10, asy+ash-44),(asw-20,30), color=TEAL, width=2.0, amp=1.6)
st((asx+asw+10+14, asy+ash-40), "Create account", color=(255,255,255), size=10, font=F_SMALL)

# lockout banner (top of card)
lb_x, lb_y = asx, asy-30
pr((lb_x,lb_y),(asw+asw+10,24), color=RED, width=2.0, amp=2.0, fill=(255,220,210,30))
st((lb_x+10, lb_y+4), "Too many failed attempts — this account is locked for about 30 minutes.", color=RED, size=9, font=F_SMALL)

# footer note
st((x0+10, y0+h-22), "Sheets are pencil-sketch wireframes of the real BHIMS UI chrome and key screens, drawn from core/templates/core/.", color=(120,120,120), size=10, font=F_SMALL)
st((x0+10, y0+h-6), "Not a mockup and not the polished UI — the actual app carries navbar, sidebar, glass cards, carousel, and role-aware dashboards.", color=(120,120,120), size=10, font=F_SMALL)


def tiny_bed(cx, cy, scale=1.0, color=INK):
    s=float(scale)
    ix=int(cx); iy=int(cy)
    d.line(_w((ix-int(16*s),iy),(ix+int(16*s),iy)), INK, width=2)
    d.line(_w((ix-int(16*s),iy+int(4*s)),(ix+int(16*s),iy+int(4*s))), INK, width=2)
    d.line(_w((ix-int(16*s),iy),(ix-int(16*s),iy+int(4*s))), INK, width=2)
    d.line(_w((ix+int(16*s),iy),(ix+int(16*s),iy+int(4*s))), INK, width=2)
    d.ellipse([ix-int(9*s), iy-int(3*s), ix-int(4*s), iy+int(2*s)], fill=color)
    for yy in range(1,4):
        d.line(_w((ix-int(14*s), iy+int(yy*s)), (ix+int(14*s), iy+int(yy*s)), amp=0.5), INK, width=1)

def tiny_house(cx, cy, scale=1.0, color=INK):
    s=float(scale)
    ix=int(cx); iy=int(cy)
    d.line(_w((ix-int(18*s), iy+int(6*s)), (ix, iy-int(22*s))), INK, width=2)
    d.line(_w((ix, iy-int(22*s)), (ix+int(18*s), iy+int(6*s))), INK, width=2)
    d.line(_w((ix-int(15*s), iy+int(6*s)), (ix+int(15*s), iy+int(6*s))), INK, width=2)
    d.line(_w((ix-int(15*s), iy+int(6*s)), (ix-int(15*s), iy+int(30*s))), INK, width=2)
    d.line(_w((ix+int(15*s), iy+int(6*s)), (ix+int(15*s), iy+int(30*s))), INK, width=2)
    d.line(_w((ix-int(15*s), iy+int(30*s)), (ix+int(15*s), iy+int(30*s))), INK, width=2)

def question_mark(cx, cy, color=INK, size=11):
    ix=int(cx); iy=int(cy)
    d.line(_w((ix-7, iy+8), (ix-7, iy-2)), color=INK, width=int(size))
    d.line(_w((ix-8, iy+5), (ix-2, iy-4)), color=INK, width=int(size))
    d.line(_w((ix-2, iy-4), (ix+4, iy+3)), color=INK, width=int(size))
    d.ellipse([ix+4, iy-4, ix+7, iy-1], outline=color, width=int(size))

# tiny doodles around the edge
for i in range(12):
    dx=random.randint(inset+30, W-inset-30)
    dy=random.randint(inset+30, H-inset-30)
    if random.random()<0.33:
        tiny_house(dx,dy,scale=random.uniform(0.5,0.9),color=(120,120,120,90))
    elif random.random()<0.66:
        tiny_bed(dx,dy,scale=random.uniform(0.5,0.9),color=(120,120,120,90))
    else:
        question_mark(dx,dy,color=(120,120,120),size=8)

out = "BHIMS_UI_sketch_lowfidelity.png"
img.save(out, dpi=(150,150))
print("saved", out, img.size)

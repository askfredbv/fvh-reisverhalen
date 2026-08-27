# Render de 3 artikel-schema's als propere PNG's (Pillow, supersampled).
from PIL import Image, ImageDraw, ImageFont
import os

OUT = r"C:\claude\fvh.com\exports\bouwen-met-data-beeld"
os.makedirs(OUT, exist_ok=True)
FONTS = r"C:\Windows\Fonts"
SS = 3  # supersample

INK   = (34, 34, 34)
SUB   = (120, 120, 120)
LINE  = (90, 90, 90)
BOXBD = (205, 205, 205)
BOXBG = (248, 248, 248)
ACC   = (42, 111, 176)
ACCBG = (233, 242, 250)
WHITE = (255, 255, 255)

def P(v): return int(v * SS)
def F(name, sz): return ImageFont.truetype(os.path.join(FONTS, name), int(sz * SS))

ARIALB = "arialbd.ttf"
SEGOE  = "segoeui.ttf"
CONSOLA= "consola.ttf"

def new(w, h):
    img = Image.new("RGB", (P(w), P(h)), WHITE)
    return img, ImageDraw.Draw(img)

def finish(img, w, h, name):
    img = img.resize((w, h), Image.LANCZOS)
    path = os.path.join(OUT, name)
    img.save(path)
    print("WROTE", path, img.size)

def text(d, x, y, s, font, fill=INK, anchor="mm"):
    d.text((P(x), P(y)), s, font=font, fill=fill, anchor=anchor)

def box(d, cx, cy, w, h, items, bg=BOXBG, bd=BOXBD, radius=14):
    # items: list of (string, fontname, size, fill)
    x0, y0 = P(cx - w/2), P(cy - h/2)
    x1, y1 = P(cx + w/2), P(cy + h/2)
    d.rounded_rectangle([x0, y0, x1, y1], radius=P(radius), fill=bg, outline=bd, width=P(1.4))
    # vertical stack centered
    fonts = [F(fn, sz) for (_, fn, sz, _) in items]
    heights = []
    for f in fonts:
        asc, desc = f.getmetrics()
        heights.append(asc + desc)
    gap = P(5)
    total = sum(heights) + gap * (len(items) - 1)
    yy = P(cy) - total / 2
    for (s, fn, sz, fill), f, hh in zip(items, fonts, heights):
        d.text((P(cx), yy + hh / 2), s, font=f, fill=fill, anchor="mm")
        yy += hh + gap

def varrow(d, x, y1, y2, color=LINE):
    d.line([(P(x), P(y1)), (P(x), P(y2))], fill=color, width=P(1.6))
    s = P(6)
    d.polygon([(P(x) - s, P(y2) - s), (P(x) + s, P(y2) - s), (P(x), P(y2))], fill=color)

def harrow(d, x1, x2, y, color=LINE):
    d.line([(P(x1), P(y)), (P(x2), P(y))], fill=color, width=P(1.6))
    s = P(6)
    d.polygon([(P(x2) - s, P(y) - s), (P(x2) - s, P(y) + s), (P(x2), P(y))], fill=color)

def title(d, cx, y, s):
    text(d, cx, y, s, F(ARIALB, 19), INK, anchor="mm")

# ---------- Schema A: van 64.142 foto's naar 21 reizen ----------
def schema_a():
    W, H = 1000, 620
    img, d = new(W, H)
    title(d, W/2, 46, "Van 64.142 foto's naar 21 reizen")
    # two input boxes
    bw, bh = 380, 96
    lx, rx = 270, 730
    ty = 150
    box(d, lx, ty, bw, bh, [
        ("Foto's", ARIALB, 17, INK),
        ("64.142 stuks · 289 GB · 1907 mappen", SEGOE, 12.5, INK),
        ("inhoud zonder structuur", SEGOE, 11.5, SUB),
    ])
    box(d, rx, ty, bw, bh, [
        ("Google Maps-tijdlijn", ARIALB, 17, INK),
        ("via Google Takeout, sinds 2015", SEGOE, 12.5, INK),
        ("structuur zonder inhoud", SEGOE, 11.5, SUB),
    ])
    # join node
    jy = 320
    box(d, W/2, jy, 380, 64, [
        ("gekoppeld op de tijd", ARIALB, 15, ACC),
        ("timestamp + GPS, gematcht op de tijdlijn", SEGOE, 12, INK),
    ], bg=ACCBG, bd=ACC)
    # arrows inputs -> join
    varrow(d, lx, ty + bh/2, jy - 32 - 6)
    varrow(d, rx, ty + bh/2, jy - 32 - 6)
    d.line([(P(lx), P(jy-32-6)), (P(rx), P(jy-32-6))], fill=LINE, width=P(1.6))  # not used visually; keep simple
    # 21 reizen
    ry = 450
    box(d, W/2, ry, 360, 70, [
        ("21 reizen", ARIALB, 17, INK),
        ("elk met een begin- en einddatum", SEGOE, 12.5, INK),
    ])
    varrow(d, W/2, jy + 32, ry - 35 - 6)
    # per reis -> lokale map
    py = 560
    box(d, W/2, py, 420, 56, [
        ("per reis → één lokale map met foto's", SEGOE, 13.5, INK),
    ])
    varrow(d, W/2, ry + 35, py - 28 - 6)
    finish(img, W, H, "schema-1-naar-21-reizen.png")

# ---------- Schema B: de machine, vier stappen ----------
def schema_b():
    W, H = 1000, 720
    img, d = new(W, H)
    title(d, W/2, 46, "De machine: vier stappen, alles lokaal")
    steps = [
        ("1 · Indexeren", "foto's → photos.csv  (sha1, datum, GPS)"),
        ("2 · Bekijken", "Gemma 4 12B → vision.csv  (caption, scène, bordtekst)"),
        ("3 · Samenvoegen", "+ tijdlijn + reviews → manifest.csv"),
        ("4 · Contactblad", "thumbnails + vinkjes → contactsheet.html"),
    ]
    bw, bh = 560, 78
    y = 150
    dy = 118
    cx = W/2
    for i, (t, sub) in enumerate(steps):
        box(d, cx, y, bw, bh, [
            (t, ARIALB, 16, INK),
            (sub, SEGOE, 12.5, INK),
        ])
        if i < len(steps) - 1:
            varrow(d, cx, y + bh/2, y + dy - bh/2 - 6)
        y += dy
    # final selectie
    varrow(d, cx, y - dy + bh/2, y - dy/2 + 4 - 6 + 14)
    box(d, cx, y - dy/2 + 18, 300, 52, [
        ("mijn selectie", ARIALB, 15, ACC),
    ], bg=ACCBG, bd=ACC)
    text(d, W/2, H - 28, "alles lokaal · Python · sha1-cache (onderbreken = gratis)",
         F(SEGOE, 12), SUB, anchor="mm")
    finish(img, W, H, "schema-2-de-machine.png")

# ---------- Schema C: van losse metadata naar een tijdslijn ----------
def schema_c():
    W, H = 1000, 560
    img, d = new(W, H)
    title(d, W/2, 46, "Van losse metadata naar een tijdslijn")
    rows = [
        ("timestamp", "groepeer per dag"),
        ("GPS × tijdlijn", "plaats  (ook zónder GPS)"),
        ("≤ 90 s, zelfde plek", "vermoedelijk duplicaat: markeer er één"),
        ("review-bezoekdatum", "aan de juiste dag"),
    ]
    lw, rw, bh = 300, 430, 56
    lx, rx = 250, 690
    y = 130
    dy = 78
    for left, right in rows:
        box(d, lx, y, lw, bh, [(left, SEGOE, 13.5, INK)])
        harrow(d, lx + lw/2 + 4, rx - rw/2 - 4, y)
        box(d, rx, y, rw, bh, [(right, SEGOE, 13.5, INK)], bg=WHITE, bd=BOXBD)
        y += dy
    # converge down to result
    yb = y + 6
    box(d, W/2, yb + 24, 470, 56, [
        ("dag per dag: waar, wat, en soms waarom", ARIALB, 14, ACC),
    ], bg=ACCBG, bd=ACC)
    varrow(d, W/2, y - dy + bh/2, yb + 24 - 28 - 6)
    finish(img, W, H, "schema-3-naar-tijdslijn.png")

schema_a()
schema_b()
schema_c()
print("done")

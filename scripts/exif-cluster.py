#!/usr/bin/env python3
"""EXIF-cluster — the local 'data layer' for the travel pipeline (NO LLM).

Buckets a trip's photo folder PER DAY (matched to the timeline) and, where the
photo still carries EXIF GPS, labels it with the nearest place Frederik reviewed.
Output = a per-day manifest the writer scans to pick ~10 hero shots per article.

Usage:  python exif-cluster.py ["<photo folder>"] ["<trip regio match>"]
Defaults to the Japan 2025 trip.

Reads (LOCAL, never committed): the photo folder + the BHAG exports in
C:/claude/fvh.com/downloads. Writes a markdown manifest to .../downloads.
"""
import os, re, sys, csv, math, json, datetime
from collections import defaultdict, Counter

DL = "C:/claude/fvh.com/downloads"
PHOTO_DIR = sys.argv[1] if len(sys.argv) > 1 else \
    "C:/claude/fvh.com/scratch/japan-werk/20250920 - Reis naar Japan"
TRIP_MATCH = sys.argv[2] if len(sys.argv) > 2 else "Japan"
OUT = f"{DL}/japan-foto-per-dag.md"

FNAME_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})[ _](\d{2})\.(\d{2})\.(\d{2})")
COORD = re.compile(r"(-?\d{1,3}\.\d+)[^\d,]*,\s*(-?\d{1,3}\.\d+)")

def hav(a, b):
    R = 6371; la1, lo1, la2, lo2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))

# --- EXIF GPS (Pillow) -------------------------------------------------------
try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

def gps_of(path):
    if not HAVE_PIL:
        return None
    try:
        ex = Image.open(path)._getexif()
        if not ex:
            return None
        gps = next((v for k, v in ex.items() if TAGS.get(k) == "GPSInfo"), None)
        if not gps:
            return None
        g = {GPSTAGS.get(k, k): v for k, v in gps.items()}
        if "GPSLatitude" not in g or "GPSLongitude" not in g:
            return None
        def dms(v, ref):
            d, m, s = (float(x) for x in v)
            val = d + m/60 + s/3600
            return -val if ref in ("S", "W") else val
        return (dms(g["GPSLatitude"], g.get("GPSLatitudeRef", "N")),
                dms(g["GPSLongitude"], g.get("GPSLongitudeRef", "E")))
    except Exception:
        return None

# --- trip window + reviewed places (for labelling) ---------------------------
trips = list(csv.DictReader(open(f"{DL}/trips-from-timeline.csv", encoding="utf-8")))
trip = next(t for t in trips if TRIP_MATCH.lower() in t["regio"].lower())
d0 = datetime.date.fromisoformat(trip["van"]); d1 = datetime.date.fromisoformat(trip["tot"])

places = []  # (name, lat, lng)
rev_path = next((os.path.join(r, "Reviews.json")
                 for r, _, f in os.walk(f"{DL}/Maps Takeout") if "Reviews.json" in f), None)
if rev_path:
    for ft in json.load(open(rev_path, encoding="utf-8")).get("features", []):
        p = ft.get("properties", {}); loc = p.get("location", {}) or {}
        g = ft.get("geometry", {}).get("coordinates", [None, None]); lng, lat = (g + [None, None])[:2]
        if lat is None or not loc.get("name"):
            continue
        places.append((loc["name"], lat, lng))

def nearest(lat, lng, maxkm=1.5):
    best = None
    for nm, pa, po in places:
        dkm = hav((lat, lng), (pa, po))
        if best is None or dkm < best[0]:
            best = (dkm, nm)
    return best[1] if best and best[0] <= maxkm else None

# --- scan the folder ---------------------------------------------------------
days = defaultdict(lambda: {"times": [], "gps": 0, "nogps": 0, "places": Counter(), "files": []})
total = skipped = 0
for fn in sorted(os.listdir(PHOTO_DIR)):
    if not fn.lower().endswith((".jpg", ".jpeg", ".png", ".heic")):
        continue
    m = FNAME_DATE.search(fn)
    if not m:
        skipped += 1; continue
    y, mo, d, hh, mm, ss = map(int, m.groups())
    try:
        day = datetime.date(y, mo, d)
    except ValueError:
        skipped += 1; continue
    if not (d0 <= day <= d1):
        continue
    total += 1
    rec = days[day]
    rec["times"].append(f"{hh:02d}:{mm:02d}")
    rec["files"].append(fn)
    ll = gps_of(os.path.join(PHOTO_DIR, fn))
    if ll:
        rec["gps"] += 1
        nm = nearest(*ll)
        if nm:
            rec["places"][nm] += 1
    else:
        rec["nogps"] += 1

# --- write manifest ----------------------------------------------------------
NL = {0: "Maandag", 1: "Dinsdag", 2: "Woensdag", 3: "Donderdag",
      4: "Vrijdag", 5: "Zaterdag", 6: "Zondag"}
lines = [f"# Foto's per dag — {trip['regio']}  ({trip['van']} → {trip['tot']})",
         "",
         f"_{total} foto's in venster · GPS gelezen: {sum(d['gps'] for d in days.values())} · "
         f"geen GPS: {sum(d['nogps'] for d in days.values())} · genegeerd: {skipped}_",
         f"_Bron: {PHOTO_DIR}_", ""]
for day in sorted(days):
    r = days[day]
    span = f"{min(r['times'])}–{max(r['times'])}" if r["times"] else "—"
    lines.append(f"## {NL[day.weekday()]} {day:%d %b}  ·  {len(r['files'])} foto's  ·  {span}")
    if r["places"]:
        top = "  ".join(f"{nm} ({n})" for nm, n in r["places"].most_common(8))
        lines.append(f"- **Plaatsen (via GPS):** {top}")
    if r["nogps"]:
        lines.append(f"- _{r['nogps']} foto's zonder GPS (binnen/EXIF gestript)_")
    lines.append("")

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
print(f"\n→ geschreven: {OUT}")

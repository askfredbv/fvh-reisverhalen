#!/usr/bin/env python3
"""Pin the evening MEALS to days/places from the photos themselves.

For each trip day, take the evening photos (>= 17:00 or before 02:00) and cluster
them by GPS to the nearest reviewed place (distance reported, no cap) — so an
*unreviewed* restaurant still surfaces as 'near X, N km'. No-GPS evening photos
(typical indoor meal shots) are counted: at least the DAY is known via filename.
"""
import os, re, sys, csv, math, json, datetime
from collections import defaultdict, Counter

DL = "C:/claude/fvh.com/downloads"
PHOTO_DIR = sys.argv[1] if len(sys.argv) > 1 else \
    "C:/claude/fvh.com/scratch/japan-werk/20250920 - Reis naar Japan"
TRIP_MATCH = sys.argv[2] if len(sys.argv) > 2 else "Japan"

FNAME = re.compile(r"(\d{4})-(\d{2})-(\d{2})[ _](\d{2})\.(\d{2})\.(\d{2})")

def hav(a, b):
    R = 6371; la1, lo1, la2, lo2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
def gps_of(path):
    try:
        ex = Image.open(path)._getexif()
        if not ex: return None
        gps = next((v for k, v in ex.items() if TAGS.get(k) == "GPSInfo"), None)
        if not gps: return None
        g = {GPSTAGS.get(k, k): v for k, v in gps.items()}
        if "GPSLatitude" not in g or "GPSLongitude" not in g: return None
        def dms(v, ref):
            d, m, s = (float(x) for x in v); val = d + m/60 + s/3600
            return -val if ref in ("S", "W") else val
        return (dms(g["GPSLatitude"], g.get("GPSLatitudeRef", "N")),
                dms(g["GPSLongitude"], g.get("GPSLongitudeRef", "E")))
    except Exception:
        return None

trips = list(csv.DictReader(open(f"{DL}/trips-from-timeline.csv", encoding="utf-8")))
trip = next(t for t in trips if TRIP_MATCH.lower() in t["regio"].lower())
d0 = datetime.date.fromisoformat(trip["van"]); d1 = datetime.date.fromisoformat(trip["tot"])

places = []
rev = next((os.path.join(r, "Reviews.json") for r, _, f in os.walk(f"{DL}/Maps Takeout") if "Reviews.json" in f), None)
for ft in json.load(open(rev, encoding="utf-8")).get("features", []):
    p = ft.get("properties", {}); loc = p.get("location", {}) or {}
    g = ft.get("geometry", {}).get("coordinates", [None, None]); lng, lat = (g + [None, None])[:2]
    if lat is not None and loc.get("name"):
        places.append((loc["name"], lat, lng))

def nearest(lat, lng):
    best = None
    for nm, pa, po in places:
        dkm = hav((lat, lng), (pa, po))
        if best is None or dkm < best[0]: best = (dkm, nm)
    return best  # (km, name)

# collect evening photos
ev = defaultdict(list)  # day -> [(time, gps)]
for fn in sorted(os.listdir(PHOTO_DIR)):
    if not fn.lower().endswith((".jpg", ".jpeg", ".png")): continue
    m = FNAME.search(fn)
    if not m: continue
    y, mo, d, hh, mm, ss = map(int, m.groups())
    try: dt = datetime.datetime(y, mo, d, hh, mm, ss)
    except ValueError: continue
    day = dt.date()
    # an evening photo after 01:00 belongs to the previous calendar day's evening
    eday = day if hh >= 2 else day - datetime.timedelta(days=1)
    if not (d0 <= eday <= d1): continue
    if hh >= 17 or hh < 2:
        ev[eday].append((dt, gps_of(os.path.join(PHOTO_DIR, fn))))

NL = {0:"Ma",1:"Di",2:"Wo",3:"Do",4:"Vr",5:"Za",6:"Zo"}
CITY = {21:"Osaka",22:"Osaka",23:"Osaka→Kyoto",24:"Kyoto",25:"Kyoto→Tokyo",26:"Tokyo",27:"Tokyo"}
for day in sorted(ev):
    shots = sorted(ev[day], key=lambda x: x[0])
    gpsd = [(t, g) for t, g in shots if g]
    nog = len(shots) - len(gpsd)
    print(f"## {NL[day.weekday()]} {day:%d %b}  ({CITY.get(day.day,'?')})  ·  {len(shots)} avondfoto's  ·  {shots[0][0]:%H:%M}–{shots[-1][0]:%H:%M}")
    # cluster GPS evening shots by nearest place
    clu = defaultdict(lambda: [0, [], 99])
    for t, g in gpsd:
        km, nm = nearest(*g)
        c = clu[nm]; c[0] += 1; c[1].append(t); c[2] = min(c[2], km)
    for nm, (n, times, km) in sorted(clu.items(), key=lambda x: -x[1][0]):
        tag = "✓ review" if km <= 0.25 else f"~{km:.1f} km van"
        print(f"   - {n:3d}×  {min(times):%H:%M}–{max(times):%H:%M}  {tag} {nm}")
    if nog:
        print(f"   - {nog:3d}×  zonder GPS (binnen — maaltijd-shots; dag staat wel vast)")
    print()

#!/usr/bin/env python3
"""Parse Google Maps on-device Timeline export → detect multi-day trips away from home.
Local only. Outputs a trip list (date range, days, region, max distance). No place names
(the on-device export has none) — region is guessed from lat/lng bounding boxes."""
import json, re, math
from collections import defaultdict, Counter

PATH = "Tijdlijn.json"
HOME = (51.00, 3.73)          # Gent/Wetteren area
AWAY_KM = 300                 # daily-farthest must exceed this to count as "travel"
MIN_DAYS = 2                  # a trip is >= this many away-days
GAP_DAYS = 1                  # merge clusters separated by <= this many home-days

COORD = re.compile(r'(-?\d{1,3}\.\d+)[^\d,]*,\s*(-?\d{1,3}\.\d+)')

def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)

def haversine(a, b):
    R = 6371
    la1, lo1, la2, lo2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))

def region(lat, lng):
    boxes = [
        ("Japan",        30, 46, 129, 146),
        ("VS-oostkust",  24, 49, -82, -66),
        ("VS-overig",    24, 49, -125, -82),
        ("Malta",        35.7, 36.15, 14.1, 14.65),
        ("Griekenland",  34.8, 41.8, 19.3, 29.8),
        ("Portugal",     36.9, 42.2, -9.6, -6.2),
        ("Italie",       36, 47.2, 6.5, 18.6),
        ("Spanje",       36, 44, -9.4, 3.4),
        ("Frankrijk",    42, 51.2, -5, 8.3),
        ("UK/Ierland",   50, 59, -11, 1.9),
        ("Hongarije",    45.5, 48.6, 16, 23),
        ("Finland",      59, 70.2, 19, 31.6),
        ("Duitsland",    47, 55, 6, 15),
        ("Oostenrijk/CH",45.8, 48.6, 6, 17),
        ("Benelux/thuis",49.4, 53.7, 2.5, 7.4),
    ]
    for name, la0, la1, lo0, lo1 in boxes:
        if la0 <= lat <= la1 and lo0 <= lng <= lo1:
            return name
    return f"?({lat:.1f},{lng:.1f})"

d = json.load(open(PATH, encoding="utf-8"))
segs = d.get("semanticSegments", [])

# Per day: the point FARTHEST from home (catches travel even if mostly idle).
day_far = {}   # 'YYYY-MM-DD' -> (dist, lat, lng)
for s in segs:
    t = s.get("startTime", "")[:10]
    if not t:
        continue
    best = None
    for sv in strings(s):
        m = COORD.search(sv)
        if not m:
            continue
        try:
            lat, lng = float(m.group(1)), float(m.group(2))
        except ValueError:
            continue
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        dist = haversine(HOME, (lat, lng))
        if best is None or dist > best[0]:
            best = (dist, lat, lng)
    if best and (t not in day_far or best[0] > day_far[t][0]):
        day_far[t] = best

# Away days, sorted.
import datetime
def pd(s): return datetime.date.fromisoformat(s)
away = sorted([day for day, (dist, *_ ) in day_far.items() if dist > AWAY_KM])

# Cluster consecutive away-days (allow small gaps).
trips = []
cur = []
for day in away:
    if not cur:
        cur = [day]
    elif (pd(day) - pd(cur[-1])).days <= GAP_DAYS + 1:
        cur.append(day)
    else:
        trips.append(cur); cur = [day]
if cur:
    trips.append(cur)

print(f"\nSegmenten: {len(segs)}  |  dagen met locatie: {len(day_far)}  |  reis-dagen (>{AWAY_KM}km): {len(away)}\n")
print(f"{'van':<11} {'tot':<11} {'dgn':>3}  {'max km':>7}  regio('s)")
print("-"*72)
out = []
for c in trips:
    if len(c) < MIN_DAYS:
        continue
    pts = [day_far[day] for day in c]
    maxd = max(p[0] for p in pts)
    regs = Counter(region(p[1], p[2]) for p in pts)
    label = ", ".join(f"{r}" for r, _ in regs.most_common(2))
    ndays = (pd(c[-1]) - pd(c[0])).days + 1
    out.append((c[0], c[-1], ndays, maxd, label))
    print(f"{c[0]:<11} {c[-1]:<11} {ndays:>3}  {maxd:>7.0f}  {label}")
print(f"\n=> {len(out)} reizen (>= {MIN_DAYS} dagen, >{AWAY_KM}km van huis)")

# Save the trip list as a BHAG seed CSV (UTF-8).
with open("trips-from-timeline.csv", "w", encoding="utf-8") as f:
    f.write("van,tot,dagen,max_km,regio\n")
    for v, t, n, mx, lab in out:
        f.write(f"{v},{t},{n},{mx:.0f},\"{lab}\"\n")
print("CSV: trips-from-timeline.csv")

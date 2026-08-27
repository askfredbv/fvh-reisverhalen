#!/usr/bin/env python3
"""Japan-trip skeleton: order the reviewed places day-by-day using the nearest timeline point's date."""
import json, re, math, csv, datetime, os
from collections import defaultdict

DL="C:/claude/fvh.com/downloads"
COORD=re.compile(r'(-?\d{1,3}\.\d+)[^\d,]*,\s*(-?\d{1,3}\.\d+)')
def hav(a,b):
    R=6371; la1,lo1,la2,lo2=map(math.radians,[a[0],a[1],b[0],b[1]])
    h=math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))
def strings(o):
    if isinstance(o,str): yield o
    elif isinstance(o,dict):
        for v in o.values(): yield from strings(v)
    elif isinstance(o,list):
        for v in o: yield from strings(v)

# Japan trip window
trips=list(csv.DictReader(open(DL+"/trips-from-timeline.csv",encoding="utf-8")))
jp=next(t for t in trips if "Japan" in t["regio"])
d0=datetime.date.fromisoformat(jp["van"]); d1=datetime.date.fromisoformat(jp["tot"])
print(f"# Japan {jp['van']} → {jp['tot']}  ({jp['dagen']} dagen)\n")

# timeline grid (only points within the window, to keep it light + relevant)
grid=defaultdict(list)
for s in json.load(open(DL+"/Tijdlijn.json",encoding="utf-8")).get("semanticSegments",[]):
    day=s.get("startTime","")[:10]
    try: dd=datetime.date.fromisoformat(day)
    except ValueError: continue
    for sv in strings(s):
        m=COORD.search(sv)
        if not m: continue
        try: lat,lng=float(m.group(1)),float(m.group(2))
        except ValueError: continue
        grid[(int(math.floor(lat)),int(math.floor(lng)))].append((dd,lat,lng))

def visit_date(lat,lng):
    best=None; c0,c1=int(math.floor(lat)),int(math.floor(lng))
    for dy in(-1,0,1):
        for dx in(-1,0,1):
            for(dd,la,lo) in grid.get((c0+dy,c1+dx),()):
                d=hav((lat,lng),(la,lo))
                if best is None or d<best[0]: best=(d,dd)
    return best[1] if best and best[0]<=40 else None

# reviews in this trip
feats=json.load(open(next(os.path.join(r,"Reviews.json") for r,_,f in os.walk(DL+"/Maps Takeout") if "Reviews.json" in f),encoding="utf-8")).get("features",[])
byday=defaultdict(list)
for f in feats:
    p=f.get("properties",{}); loc=p.get("location",{}) or {}
    if loc.get("country_code") not in ("JP","DK","FI"): continue   # Japan + layover only
    g=f.get("geometry",{}).get("coordinates",[None,None]); lng,lat=(g+[None,None])[:2]
    if lat is None: continue
    vd=visit_date(lat,lng)
    if vd is None or not (d0<=vd<=d1): continue
    byday[vd].append((loc.get("name",""), p.get("five_star_rating_published",""),
                      (p.get("review_text_published") or "").replace("\n"," ").strip(),
                      loc.get("country_code","")))

for day in sorted(byday):
    print(f"## {day:%A %d %b}".replace("Monday","Maandag").replace("Tuesday","Dinsdag").replace("Wednesday","Woensdag").replace("Thursday","Donderdag").replace("Friday","Vrijdag").replace("Saturday","Zaterdag").replace("Sunday","Zondag"))
    for naam,st,txt,cc in byday[day]:
        star="★"*int(st) if str(st).isdigit() else st
        print(f"  - {naam}  {star}" + (f"  [{cc}]" if cc not in("JP","") else ""))
        if txt: print(f"      “{txt[:200]}{'…' if len(txt)>200 else ''}”")
    print()

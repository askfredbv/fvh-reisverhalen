#!/usr/bin/env python3
"""Build the BHAG dataset: match each Google Maps review to the actual TRIP he was on,
by nearest timeline point (location+date), not the unreliable review write-date.
Outputs a flat CSV (master) + a per-trip dossier (markdown). Local only."""
import json, re, math, csv, datetime, os

DL = "C:/claude/fvh.com/downloads"
TL = os.path.join(DL, "Tijdlijn.json")
RV = None
for root,_,files in os.walk(os.path.join(DL, "Maps Takeout")):
    if "Reviews.json" in files:
        RV = os.path.join(root, "Reviews.json"); break

HOME = (51.00, 3.73)
COORD = re.compile(r'(-?\d{1,3}\.\d+)[^\d,]*,\s*(-?\d{1,3}\.\d+)')
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

# --- trips (from the timeline parser output) ---
trips=[]
with open(os.path.join(DL,"trips-from-timeline.csv"),encoding="utf-8") as f:
    for r in csv.DictReader(f):
        trips.append({"van":r["van"],"tot":r["tot"],"regio":r["regio"].strip('"'),
                      "d0":datetime.date.fromisoformat(r["van"]),"d1":datetime.date.fromisoformat(r["tot"])})
def trip_for_date(d):
    for i,t in enumerate(trips):
        if t["d0"]<=d<=t["d1"]: return i
    return None

# --- timeline points → grid index (1 deg cells) ---
print("Timeline laden + indexeren...")
tl=json.load(open(TL,encoding="utf-8"))
grid={}
for s in tl.get("semanticSegments",[]):
    day=s.get("startTime","")[:10]
    if not day: continue
    try: dd=datetime.date.fromisoformat(day)
    except ValueError: continue
    for sv in strings(s):
        m=COORD.search(sv)
        if not m: continue
        try: lat,lng=float(m.group(1)),float(m.group(2))
        except ValueError: continue
        if not(-90<=lat<=90 and -180<=lng<=180): continue
        grid.setdefault((int(math.floor(lat)),int(math.floor(lng))),[]).append((dd,lat,lng))
print(f"  {sum(len(v) for v in grid.values())} timeline-punten in {len(grid)} cellen")

def nearest_trip(lat,lng):
    """Trip-id via dichtstbijzijnde timeline-punt binnen ~40km; anders None (thuis/onbekend)."""
    best=None
    c0,c1=int(math.floor(lat)),int(math.floor(lng))
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            for (dd,la,lo) in grid.get((c0+dy,c1+dx),()):
                dist=hav((lat,lng),(la,lo))
                if best is None or dist<best[0]: best=(dist,dd)
    if best and best[0]<=40:
        return trip_for_date(best[1])
    return None

# --- reviews ---
print("Reviews matchen...")
feats=json.load(open(RV,encoding="utf-8")).get("features",[])
rows=[]
for f in feats:
    p=f.get("properties",{}); loc=p.get("location",{}) or {}
    g=f.get("geometry",{}).get("coordinates",[None,None])
    lng,lat=(g+[None,None])[:2]
    if lat is None: continue
    txt=p.get("review_text_published") or ""
    tid=nearest_trip(lat,lng)
    t=trips[tid] if tid is not None else None
    rows.append({
        "geschreven": (p.get("date","")[:10]),
        "naam": loc.get("name",""),
        "land": loc.get("country_code",""),
        "adres": loc.get("address",""),
        "lat": round(lat,5), "lng": round(lng,5),
        "sterren": p.get("five_star_rating_published",""),
        "reis": "" if t is None else f"{t['van']}..{t['tot']} ({t['regio']})",
        "reis_idx": "" if tid is None else tid,
        "tekst": txt.replace("\n"," ").strip(),
        "maps_url": p.get("google_maps_url",""),
    })

# --- flat CSV (master) ---
out_csv=os.path.join(DL,"bhag-reviews-flat.csv")
cols=["geschreven","reis","naam","land","adres","lat","lng","sterren","tekst","maps_url","reis_idx"]
with open(out_csv,"w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader()
    for r in sorted(rows,key=lambda r:(r["reis_idx"]=="" , r["reis_idx"] if r["reis_idx"]!="" else 0, r["geschreven"])):
        w.writerow(r)

# --- per-trip dossier (markdown) ---
out_md=os.path.join(DL,"bhag-trip-dossier.md")
with open(out_md,"w",encoding="utf-8") as f:
    f.write("# BHAG trip-dossier — reviews per reis (timeline-gematcht)\n\n")
    for i,t in enumerate(trips):
        tr=[r for r in rows if r["reis_idx"]==i]
        if not tr: continue
        withtxt=[r for r in tr if r["tekst"]]
        f.write(f"## {t['van']} → {t['tot']} — {t['regio']}  ({len(tr)} plekken, {len(withtxt)} met tekst)\n\n")
        for r in sorted(tr,key=lambda r:-1 if r["tekst"] else 0):
            star="★"*int(r["sterren"]) if str(r["sterren"]).isdigit() else r["sterren"]
            f.write(f"- **{r['naam']}** ({r['adres'].split(',')[-1].strip()}) {star}\n")
            if r["tekst"]:
                f.write(f"  > {r['tekst']}\n")
        f.write("\n")
    # niet-gematcht / thuis
    home=[r for r in rows if r["reis_idx"]==""]
    f.write(f"## (Thuis / niet aan een reis gekoppeld: {len(home)} plekken)\n")

# stats
matched=sum(1 for r in rows if r["reis_idx"]!="")
print(f"\nReviews: {len(rows)}  |  aan een reis gekoppeld: {matched}  |  thuis/lokaal: {len(rows)-matched}")
print(f"CSV : {out_csv}")
print(f"MD  : {out_md}")
print("\n=== reviews per reis ===")
for i,t in enumerate(trips):
    n=sum(1 for r in rows if r["reis_idx"]==i)
    if n: print(f"  {t['van']}..{t['tot']} {t['regio']:<14} {n:>3} plekken")

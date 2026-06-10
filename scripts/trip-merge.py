#!/usr/bin/env python3
"""trip-merge — bouwsteen 3/4 van de per-reis foto-pipeline.

Joint alles uit bouwsteen 1+2 met de reviews-database tot één manifest per reis:
per foto → dag, plaats (nearest review op GPS), Gemma-tags, near-dup-cluster, pre-rank.

INPUT  : <out>/photos.csv  (bouwsteen 1)
         <out>/vision.csv  (bouwsteen 2)  — optioneel; missing = lege tags
         <reviews-csv>     (bhag-reviews-flat.csv — pas filteren op --trip)
OUTPUT : <out>/manifest.csv  — fact-tabel met JOIN-kolommen voor bouwsteen 4
         <out>/dag-overzicht.md  — leesbaar per-dag-per-plaats voor de mens

DETERMINISTISCH:
- day  = uit exif_date (of mtime-fallback)
- place = nearest review (van DEZE reis) binnen --place-radius km, op GPS van de foto.
         Foto's zonder GPS krijgen plaats via "dezelfde dag, dichtste foto-met-GPS"
         (kettings-buurt). Resterende = '(onbekend)'.
- dup_group = foto's binnen --dup-window-secs op zelfde plaats → groep.
- prerank: per dup_group de eerste qua tijd → 1, rest → 0. Scene-prioriteit (signage,
           food, people, architecture, …) breekt gelijke tijden.

Gemma's eigennamen (signage_text) NIET gebruiken voor plaats — die mag hallucineren.
Plaats is autoritair via timeline/reviews. (§5 verify, §12 Gemma=dommekracht.)

Usage:
  python trip-merge.py --photos <mastermap> --trip <regio> --out <dossier> \\
    [--reviews <pad/naar/bhag-reviews-flat.csv>] [--place-radius 40] [--dup-window-secs 90]
"""
import argparse, csv, json, math, sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime, date

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_REVIEWS = Path("C:/claude/fvh.com/downloads/bhag-reviews-flat.csv")

SCENE_PRIO = {  # lager = belangrijker als hero-kandidaat
    "signage": 1, "food": 2, "people": 3, "architecture": 4, "temple": 4,
    "cityscape": 5, "landscape": 5, "transport": 6, "interior": 7, "other": 9, "": 9,
}


def hav_km(a, b) -> float:
    R = 6371
    la1, lo1, la2, lo2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def parse_dt(s: str):
    if not s:
        return None
    s = s.strip().replace(" ", "T")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photos", required=True, help="(informatief — mastermap)")
    ap.add_argument("--trip", required=True, help="match-substring op de 'reis' kolom in reviews-csv (case-insensitive)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--reviews", default=str(DEFAULT_REVIEWS))
    ap.add_argument("--place-radius", type=float, default=40.0, help="km — max afstand foto↔review om als plaats te tellen")
    ap.add_argument("--dup-window-secs", type=int, default=90, help="binnen N seconden + zelfde plaats = near-duplicate")
    args = ap.parse_args()

    out = Path(args.out)
    photos_csv = out / "photos.csv"
    vision_csv = out / "vision.csv"
    if not photos_csv.exists():
        sys.exit(f"Geen photos.csv — draai eerst bouwsteen 1: {photos_csv}")

    # 1) photos + vision joinen
    with photos_csv.open("r", encoding="utf-8", newline="") as f:
        photos = list(csv.DictReader(f))
    vision = {}
    if vision_csv.exists():
        with vision_csv.open("r", encoding="utf-8", newline="") as f:
            for v in csv.DictReader(f):
                vision[v["sha1"]] = v

    # 2) reviews filteren op trip
    rev_path = Path(args.reviews)
    if not rev_path.exists():
        sys.exit(f"Reviews-csv niet gevonden: {rev_path}")
    needle = args.trip.lower()
    places = []  # (lat, lng, naam, adres, sterren)
    seen_keys = set()
    all_reis = set()  # alle reis-labels (voor een nuttige hint als de needle niets matcht)
    with rev_path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            reis = r.get("reis", "").strip()
            if reis:
                all_reis.add(reis)
            if needle not in r.get("reis", "").lower():
                continue
            lat, lng = to_float(r.get("lat")), to_float(r.get("lng"))
            if lat is None or lng is None:
                continue
            key = (r.get("naam", ""), round(lat, 4), round(lng, 4))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            places.append({
                "naam": r.get("naam", ""), "adres": r.get("adres", ""),
                "land": r.get("land", ""), "lat": lat, "lng": lng,
                "sterren": r.get("sterren", ""),
            })
    print(f"[trip-merge] trip='{args.trip}'  reviews-plaatsen (uniek): {len(places)}")
    if not places:
        # De 'reis'-labels zijn datum-gecodeerd per regio (bv. '... (VS-oostkust)'), NIET de
        # mensennaam van de reis. Een needle die niets matcht = stil alle plaatsen 'onbekend'.
        print(f"  ⚠️  GEEN reviews-plaats gematcht op --trip '{args.trip}' — elke foto wordt '(onbekend)'.")
        print("      --trip is een substring-match op de 'reis'-kolom. Beschikbare labels:")
        for lbl in sorted(all_reis):
            print(f"        · {lbl}")
        print("      Herstart met een needle die in het juiste label zit (bv. een regio-woord of jaar).")

    # 3) plaats-mapping per foto via GPS
    rows = []
    for p in photos:
        sha1 = p["sha1"]
        v = vision.get(sha1, {})
        lat, lng = to_float(p.get("lat")), to_float(p.get("lon"))
        dt = parse_dt(p.get("exif_date")) or parse_dt(p.get("mtime"))
        day = dt.date().isoformat() if dt else ""
        place_naam, place_dist, place_lat, place_lng = "", "", "", ""
        if lat is not None and lng is not None and places:
            best, bestd = None, 1e9
            for pl in places:
                d = hav_km((lat, lng), (pl["lat"], pl["lng"]))
                if d < bestd:
                    best, bestd = pl, d
            if best and bestd <= args.place_radius:
                place_naam = best["naam"]
                place_dist = round(bestd, 2)
                place_lat, place_lng = best["lat"], best["lng"]
        rows.append({
            "sha1": sha1, "path_rel": p["path_rel"], "filename": p["filename"],
            "media_type": p.get("media_type", "photo"),
            "datetime": dt.isoformat() if dt else "",
            "day": day,
            "lat": p.get("lat", ""), "lon": p.get("lon", ""),
            "place_name": place_naam, "place_dist_km": place_dist,
            "place_lat": place_lat, "place_lng": place_lng,
            "caption": v.get("caption", ""),
            "scene": v.get("scene", ""),
            "sign_text": v.get("sign_text", ""),
            "_dt": dt,  # tijdelijk voor sortering
        })

    # 4) fallback voor GPS-loze foto's: dichtste foto-met-GPS-op-dezelfde-dag erft de plaats.
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(r)
    inherited = 0
    for day, dayrows in by_day.items():
        with_gps = [r for r in dayrows if r["place_name"]]
        if not with_gps:
            continue
        for r in dayrows:
            if r["place_name"]:
                continue
            # zelfde-dag dichtste foto-met-plaats, op tijd
            if not r["_dt"]:
                continue
            best = min(with_gps, key=lambda x: abs((x["_dt"] - r["_dt"]).total_seconds()) if x["_dt"] else 1e9)
            r["place_name"] = best["place_name"] + " (≈)"
            r["place_dist_km"] = ""
            inherited += 1

    # 5) near-dup-clustering per (dag, plaats) binnen window
    rows.sort(key=lambda r: (r["day"], r["place_name"], r["_dt"] or datetime.min))
    gid, last = 0, None
    for r in rows:
        same_place = last and r["day"] == last["day"] and r["place_name"] == last["place_name"]
        close_in_time = same_place and r["_dt"] and last["_dt"] and \
                        abs((r["_dt"] - last["_dt"]).total_seconds()) <= args.dup_window_secs
        if not (same_place and close_in_time):
            gid += 1
        r["dup_group"] = gid
        last = r

    # 6) pre-rank: per dup_group één hero op scene-prioriteit, dan tijd
    groups = defaultdict(list)
    for r in rows:
        groups[r["dup_group"]].append(r)
    for g, items in groups.items():
        items.sort(key=lambda r: (SCENE_PRIO.get(r["scene"], 9), r["_dt"] or datetime.max))
        for i, it in enumerate(items):
            it["prerank"] = 1 if i == 0 else 0

    # 7) manifest.csv schrijven
    fields = ["sha1", "path_rel", "filename", "media_type", "datetime", "day",
              "lat", "lon", "place_name", "place_dist_km", "place_lat", "place_lng",
              "caption", "scene", "sign_text", "dup_group", "prerank"]
    out_csv = out / "manifest.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sorted(rows, key=lambda x: (x["day"], x["place_name"], x["_dt"] or datetime.min)):
            w.writerow({k: r.get(k, "") for k in fields})

    # 8) markdown per-dag-overzicht voor de mens
    md = [f"# {args.trip} — per dag/plaats overzicht\n"]
    md.append(f"_(uit manifest.csv — pre-rank=1 betekent: hero-kandidaat in z'n dup-group; "
              f"`(≈)` markeert foto's wiens plaats geërfd is van een buurfoto op dezelfde dag.)_\n")
    for day in sorted(by_day):
        if not day:
            continue
        md.append(f"\n## {day}\n")
        # Dedup ≈-erfgenamen onder dezelfde plaats; we tonen het label apart in de items.
        per_place = defaultdict(list)
        for r in by_day[day]:
            key = (r["place_name"] or "(onbekend)").replace(" (≈)", "")
            per_place[key].append(r)
        for place, items in sorted(per_place.items(), key=lambda kv: -len(kv[1])):
            items.sort(key=lambda x: x["_dt"] or datetime.min)
            n_photo = sum(1 for x in items if x.get("media_type", "photo") == "photo")
            n_video = sum(1 for x in items if x.get("media_type") == "video")
            n_groups = len({x["dup_group"] for x in items})
            heros = [x for x in items if x.get("prerank") == 1]
            md.append(f"\n### {place}  ·  {n_photo} foto's"
                      + (f" + {n_video} video's" if n_video else "")
                      + f"  ·  {n_groups} clusters\n")
            for h in heros[:8]:  # max 8 hero's per plaats in markdown — rest staat wel in csv
                bits = []
                if h["scene"]: bits.append(h["scene"])
                if h["sign_text"]: bits.append(f'"{h["sign_text"][:80]}"')
                if "(≈)" in (h.get("place_name") or ""): bits.append("≈")
                tag = " · ".join(bits)
                t = h["_dt"].strftime("%H:%M") if h["_dt"] else "??:??"
                md.append(f"- **{t}**  `{h['filename']}`  — {h.get('caption','')[:120]}  _({tag})_")
    (out / "dag-overzicht.md").write_text("\n".join(md), encoding="utf-8")

    # Stats
    n = len(rows)
    n_video = sum(1 for r in rows if r.get("media_type") == "video")
    n_place_gps = sum(1 for r in rows if r["place_name"] and "(≈)" not in r["place_name"])
    n_place_inh = inherited
    n_no_place = sum(1 for r in rows if not r["place_name"])
    n_dup = len({r["dup_group"] for r in rows})
    n_hero = sum(1 for r in rows if r.get("prerank") == 1)
    # Reis-window check: dagen ver buiten de zwaartepunt-week → vermelden (niet filteren).
    days_with_data = sorted({r["day"] for r in rows if r["day"]})
    outlier_days = []
    if len(days_with_data) > 1:
        from collections import Counter
        place_day = Counter(r["day"] for r in rows if r["place_name"] and "(≈)" not in r["place_name"])
        if place_day:
            best_day, _ = place_day.most_common(1)[0]
            best = datetime.fromisoformat(best_day).date()
            for d in days_with_data:
                try:
                    if abs((datetime.fromisoformat(d).date() - best).days) > 21:
                        outlier_days.append(d)
                except Exception:
                    pass

    print(f"[trip-merge] manifest klaar: {out_csv}")
    print(f"  media: {n}   foto's: {n-n_video}   video's: {n_video}")
    print(f"  plaats via GPS: {n_place_gps}   geërfd (zelfde dag): {n_place_inh}   onbekend: {n_no_place}")
    print(f"  dup-clusters: {n_dup}   hero-kandidaten (prerank=1): {n_hero}")
    if outlier_days:
        print(f"  ⚠ dagen >21d buiten reis-zwaartepunt (controleer mastermap): {', '.join(outlier_days[:6])}"
              + (f" …+{len(outlier_days)-6}" if len(outlier_days) > 6 else ""))
    print(f"  per-dag overzicht: {out/'dag-overzicht.md'}")


if __name__ == "__main__":
    main()

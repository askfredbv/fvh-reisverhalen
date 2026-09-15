#!/usr/bin/env python3
"""trip-timeline-places — plaats-resolutie per foto op TIJD i.p.v. GPS-nearest-review.

Waarom: de oude merge matcht elke foto aan de dichtstbijzijnde van Frederiks review-pinnen
op de GPS van de foto. Dat faalt op drie manieren (bevestigd op de Italië-set 2026):
  1. review-pinnen van ANDERE reizen lekken in (bv. een Orvieto-pin uit 2023 op 2026-Bolsena);
  2. twee pinnen dicht bij elkaar → de verkeerde wint (Pizza Zizza-foto's pakten Bloom Hotel);
  3. foto's zonder GPS erven een buur.

Deze voorstap gebruikt de Google Maps **Timeline** (Tijdlijn.json): die weet per BEZOEK
waar je echt was, mét start/eind-tijd en een Google `placeId`. We matchen elke foto op haar
absolute tijdstip (photos.csv `dt_utc`) in het juiste bezoek → placeId + exacte coördinaat.
Dat lost toewijzing op voor ÁLLE foto's (ook zonder GPS, ook de Zwitserland-transit).

Naamgeving van dat bezoek (twee bronnen, in volgorde):
  a. Google Places API (New) op de placeId → officiële naam. Vereist env-key
     GOOGLE_MAPS_API_KEY (of GOOGLE_PLACES_API_KEY); gecached in <out>/cache/places.json.
     Zonder key wordt deze stap stil overgeslagen.
  b. Frederiks eigen reviews (naam + sterren), gematcht op coördinaat (tight) binnen het
     REISVENSTER (zo kan een pin uit een ander jaar niet matchen).

OUTPUT: <out>/photo-places.csv  (sha1, place_id, place_name, place_lat, place_lng, sterren, source)
        → trip-merge.py leest dit via --place-map en gebruikt het i.p.v. GPS-nearest-review.

Privacy: Timeline + reviews blijven lokaal. Enkel de Places-veeg stuurt placeIds (jouw eigen
Google-data) naar Google, en enkel als je de env-key zet.

Usage:
  python trip-timeline-places.py --out <dossier> --timeline <Tijdlijn.json> \\
    [--reviews <bhag-reviews-merged.csv>] [--coord-radius-km 0.3] [--near-minutes 45]
"""
import argparse, csv, json, math, os, re, sys, time, bisect, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_REVIEWS = Path("C:/claude/fvh.com/downloads/bhag-reviews-merged.csv")


def U(s):
    """ISO-string (met offset) → aware UTC datetime, of None."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        # soms staat er een fractie + offset die fromisoformat op oudere py's niet lust
        m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?([+-]\d{2}:?\d{2}|Z)?", s.strip())
        if not m:
            return None
        base = m.group(1)
        off = (m.group(2) or "+00:00").replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(base + off).astimezone(timezone.utc)
        except Exception:
            return None


def latlng(s):
    nums = re.findall(r"-?\d+\.\d+", s or "")
    return (float(nums[0]), float(nums[1])) if len(nums) >= 2 else (None, None)


def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def hav_km(a, b):
    R = 6371
    la1, lo1, la2, lo2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def photo_utc(p):
    """Absoluut UTC-moment van een foto: primair dt_utc, anders exif+offset."""
    u = U(p.get("dt_utc"))
    if u:
        return u
    # fallback: exif_date + tz_offset
    ed, off = (p.get("exif_date") or "").strip(), (p.get("tz_offset") or "").strip()
    if ed and re.match(r"[+-]\d{2}:?\d{2}", off):
        return U(ed.replace(" ", "T") + off)
    return None


def places_nearby(lat, lng, key, cache, radius_m):
    """Places API (New) Nearby Search op een coördinaat → populairste plek in de buurt.
    Voor wandelfoto's van monumenten (Trevi, Pantheon, Sint-Pietersplein) die Google niet als
    apart bezoek logde. Gecached per afgeronde coord. Geeft (naam, place_id, lat, lng)."""
    ck = f"nb:{round(lat, 4)},{round(lng, 4)}"
    c = cache.get(ck)
    if c and c.get("name"):
        return c["name"], c.get("place_id", ""), c.get("lat"), c.get("lng")
    if not key:
        return "", "", None, None
    body = json.dumps({
        "maxResultCount": 1,
        "rankPreference": "POPULARITY",
        "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": float(radius_m)}},
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://places.googleapis.com/v1/places:searchNearby", data=body, method="POST",
        headers={"X-Goog-Api-Key": key, "Content-Type": "application/json",
                 "X-Goog-FieldMask": "places.displayName,places.id,places.location"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        places = data.get("places") or []
        if not places:
            return "", "", None, None
        p0 = places[0]
        name = (p0.get("displayName") or {}).get("text", "")
        pid = p0.get("id", "")
        loc = p0.get("location") or {}
        la, lo = loc.get("latitude"), loc.get("longitude")
        if name:
            cache[ck] = {"name": name, "place_id": pid, "lat": la, "lng": lo}
        time.sleep(0.05)
        return name, pid, la, lo
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        m = re.search(r'"message":\s*"([^"]+)"', body)
        reason = (m.group(1)[:90] if m else f"HTTP {e.code}")
        if reason not in _ERR_SEEN:
            _ERR_SEEN.add(reason)
            print(f"  ⚠ Places Nearby {e.code}: {reason}")
        return "", "", None, None
    except Exception as e:
        print(f"  ⚠ Places Nearby fout: {e}")
        return "", "", None, None


_ERR_SEEN = set()  # dedup: print elke onderscheiden foutreden max 1x


def places_lookup(place_id, key, cache):
    """Google Places API (New) → displayName. Enkel GESLAAGDE lookups (naam≠leeg) worden
    gecached, zodat een herdraai na het aanzetten van de API de mislukte plekken opnieuw
    probeert. Geeft (naam, adres) of ('','')."""
    c = cache.get(place_id)
    if c and c.get("name"):
        return c["name"], c.get("address", "")
    if not key:
        return "", ""
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    req = urllib.request.Request(url, headers={
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": "displayName,formattedAddress",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        name = (data.get("displayName") or {}).get("text", "")
        addr = data.get("formattedAddress", "")
        if name:
            cache[place_id] = {"name": name, "address": addr}  # enkel succes cachen
        time.sleep(0.05)
        return name, addr
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        m = re.search(r'"message":\s*"([^"]+)"', body)
        reason = (m.group(1)[:90] if m else f"HTTP {e.code}")
        if reason not in _ERR_SEEN:
            _ERR_SEEN.add(reason)
            print(f"  ⚠ Places API {e.code}: {reason}")
        return "", ""
    except Exception as e:
        print(f"  ⚠ Places API fout voor {place_id}: {e}")
        return "", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="dossier met photos.csv; output photo-places.csv komt hier")
    ap.add_argument("--timeline", required=True, help="pad naar Tijdlijn.json")
    ap.add_argument("--reviews", default=str(DEFAULT_REVIEWS))
    ap.add_argument("--coord-radius-km", type=float, default=0.3, help="max afstand bezoek↔review voor naam/sterren")
    ap.add_argument("--near-minutes", type=int, default=45, help="foto buiten elk bezoek-venster → dichtste bezoek binnen N min")
    ap.add_argument("--gps-gate-km", type=float, default=0.2, help="out-of-window-foto met eigen GPS verder dan dit van "
                    "het dichtste bezoek → herbenoem op eigen GPS via Places Nearby (lost wandelfoto's van monumenten op)")
    ap.add_argument("--nearby-radius-m", type=float, default=100.0, help="straal voor Places Nearby op de foto-GPS")
    ap.add_argument("--window-pre-days", type=int, default=7, help="reisvenster: dagen vóór eerste fotodag")
    ap.add_argument("--window-post-days", type=int, default=75, help="reisvenster: dagen ná laatste fotodag (reviews komen later)")
    args = ap.parse_args()

    out = Path(args.out)
    photos_csv = out / "photos.csv"
    if not photos_csv.exists():
        sys.exit(f"Geen photos.csv: {photos_csv}")
    photos = list(csv.DictReader(photos_csv.open(encoding="utf-8", newline="")))

    # reisvenster uit de fotodagen
    days = sorted({(p.get("exif_date") or p.get("mtime") or "")[:10] for p in photos if (p.get("exif_date") or p.get("mtime"))})
    days = [d for d in days if d]
    if not days:
        sys.exit("Geen bruikbare fotodatums in photos.csv")
    d0 = datetime.fromisoformat(days[0]).date() - timedelta(days=args.window_pre_days)
    d1 = datetime.fromisoformat(days[-1]).date() + timedelta(days=args.window_post_days)
    print(f"[places] reisvenster (voor review-filter): {d0} .. {d1}   fotodagen: {days[0]}..{days[-1]}")

    # 1) timeline-bezoeken laden (enkel rond het reisvenster, voor snelheid)
    tl = json.load(open(args.timeline, encoding="utf-8"))
    visits = []
    for s in tl.get("semanticSegments", []):
        v = s.get("visit")
        if not v:
            continue
        st, en = U(s.get("startTime")), U(s.get("endTime"))
        if not st or not en:
            continue
        if st.date() < d0 - timedelta(days=2) or st.date() > d1 + timedelta(days=2):
            continue
        tc = v.get("topCandidate", {})
        la, lo = latlng((tc.get("placeLocation") or {}).get("latLng", ""))
        if la is None:
            continue
        visits.append((st, en, tc.get("placeId", ""), la, lo))
    visits.sort()
    starts = [v[0] for v in visits]
    print(f"[places] timeline-bezoeken in venster: {len(visits)}")
    if not visits:
        sys.exit("Geen timeline-bezoeken in het reisvenster — klopt --timeline en de datums?")

    def find_visit(tu):
        i = bisect.bisect_right(starts, tu) - 1
        for j in (i, i - 1, i + 1):
            if 0 <= j < len(visits):
                st, en, *_ = visits[j]
                if st <= tu <= en:
                    return visits[j], "timeline-window"
        cand = [visits[j] for j in (i, i + 1) if 0 <= j < len(visits)]
        if not cand:
            return None, ""
        best = min(cand, key=lambda v: min(abs((v[0] - tu).total_seconds()), abs((v[1] - tu).total_seconds())))
        gap = min(abs((best[0] - tu).total_seconds()), abs((best[1] - tu).total_seconds()))
        if gap <= args.near_minutes * 60:
            return best, "timeline-nearest"
        return None, ""

    # 2) reviews laden en filteren op reisvenster (zo lekken pinnen uit andere jaren niet)
    reviews = []
    rev_path = Path(args.reviews)
    if rev_path.exists():
        for r in csv.DictReader(rev_path.open(encoding="utf-8-sig", newline="")):
            g = (r.get("geschreven") or "")[:10]
            la, lo = to_float(r.get("lat")), to_float(r.get("lng"))
            if la is None or lo is None:
                continue
            try:
                gd = datetime.fromisoformat(g).date() if g else None
            except Exception:
                gd = None
            if gd is None or gd < d0 or gd > d1:
                continue
            reviews.append({"naam": r.get("naam", ""), "land": r.get("land", ""),
                            "lat": la, "lng": lo, "sterren": r.get("sterren", ""),
                            "geschreven": g})
        print(f"[places] reviews in venster: {len(reviews)}  (van {sum(1 for _ in csv.DictReader(rev_path.open(encoding='utf-8-sig')))} totaal)")
    else:
        print(f"[places] ⚠ reviews-csv niet gevonden: {rev_path} — enkel Places-API-namen")

    def nearest_review(la, lo):
        best, bestd = None, 1e9
        for rv in reviews:
            d = hav_km((la, lo), (rv["lat"], rv["lng"]))
            if d < bestd:
                best, bestd = rv, d
        if best and bestd <= args.coord_radius_km:
            return best, bestd
        return None, None

    # 3) foto → bezoek (op tijd)
    per_photo = {}          # sha1 → (place_id, place_lat, place_lng, source)
    pid_coords = {}         # place_id → (lat, lng) representatief
    n_win = n_near = n_none = 0
    for p in photos:
        tu = photo_utc(p)
        if not tu:
            per_photo[p["sha1"]] = ("", "", "", "")
            n_none += 1
            continue
        res, how = find_visit(tu)
        if not res:
            per_photo[p["sha1"]] = ("", "", "", "")
            n_none += 1
            continue
        st, en, pid, la, lo = res
        per_photo[p["sha1"]] = (pid, la, lo, how)
        pid_coords.setdefault(pid, (la, lo))
        n_win += how == "timeline-window"
        n_near += how == "timeline-nearest"
    print(f"[places] foto→bezoek: in-window {n_win}   nearest {n_near}   geen {n_none}   unieke plekken: {len(pid_coords)}")

    # 4) naam + sterren per unieke placeId
    key = os.environ.get("GOOGLE_MAPS_API_KEY") or os.environ.get("GOOGLE_PLACES_API_KEY") or ""
    cache_path = out / "cache" / "places.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    print(f"[places] Places API: {'AAN (key gevonden)' if key else 'UIT (geen env-key) — namen enkel uit reviews'}"
          + (f"   cache: {len(cache)} plekken" if cache else ""))

    # 3b) wandelfoto-correctie: out-of-window-foto's met eigen GPS die ver van hun toegewezen bezoek
    #     liggen (Trevi/Pantheon/Sint-Pietersplein e.d., die Google niet als apart bezoek logde), plus
    #     foto's zonder bezoek maar mét GPS → herbenoem op de EIGEN GPS via Places Nearby.
    def pf(p):
        try:
            return float(p["lat"]), float(p["lon"])
        except Exception:
            return None

    targets = []
    for p in photos:
        g = pf(p)
        if g is None:
            continue
        pid, la, lo, how = per_photo[p["sha1"]]
        if how.startswith("timeline-window"):
            continue  # echte stop (in-window): vertrouwen
        far = True
        if la not in ("", None):
            try:
                far = hav_km(g, (float(la), float(lo))) > args.gps_gate_km
            except Exception:
                far = True
        if how == "" or far:
            targets.append((p["sha1"], g))

    pid_name_hint = {}  # place_id → naam uit Nearby (skip de Details-call)
    n_nearby = 0
    if targets and key:
        clusters = []  # greedy ~120 m
        for sha1, (la, lo) in targets:
            for c in clusters:
                if hav_km((la, lo), (c["lat"], c["lng"])) < 0.12:
                    c["members"].append(sha1)
                    break
            else:
                clusters.append({"lat": la, "lng": lo, "members": [sha1]})
        for c in clusters:
            name, pid, la2, lo2 = places_nearby(c["lat"], c["lng"], key, cache, args.nearby_radius_m)
            if not name or not pid:
                continue
            plat = la2 if la2 is not None else c["lat"]
            plng = lo2 if lo2 is not None else c["lng"]
            pid_name_hint[pid] = name
            pid_coords.setdefault(pid, (plat, plng))
            for sha1 in c["members"]:
                per_photo[sha1] = (pid, plat, plng, "gps-nearby")
            n_nearby += 1
        print(f"[places] Nearby-correctie: {len(clusters)} GPS-clusters → {n_nearby} benoemd "
              f"(wandelfoto's van monumenten, buiten een geregistreerd bezoek)")
    elif targets and not key:
        print(f"[places] {len(targets)} out-of-window-foto's met GPS zouden baat hebben bij Places Nearby "
              f"(geen key → overgeslagen)")

    pid_info = {}  # place_id → (name, sterren, source_naam)
    n_api = n_rev = n_blank = n_nb = 0
    for pid, (la, lo) in pid_coords.items():
        name = pid_name_hint.get(pid, "")
        src = "places-nearby" if name else ""
        if not name:
            name, _addr = places_lookup(pid, key, cache) if pid else ("", "")
            if name:
                src = "places-api"
        rv, _ = nearest_review(la, lo)
        sterren = rv["sterren"] if rv else ""
        if src == "places-nearby":
            n_nb += 1
        elif src == "places-api":
            n_api += 1
        elif rv and rv["naam"]:
            name = rv["naam"]
            n_rev += 1
            src = "review-coord"
        else:
            n_blank += 1
            src = "onbekend"
        pid_info[pid] = (name, sterren, src)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"[places] naamgeving: Places-Details {n_api}   Nearby {n_nb}   review-coord {n_rev}   naamloos {n_blank}")

    # 5) schrijven
    fields = ["sha1", "place_id", "place_name", "place_lat", "place_lng", "sterren", "source"]
    outp = out / "photo-places.csv"
    n_named = 0
    with outp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for p in photos:
            pid, la, lo, how = per_photo[p["sha1"]]
            name, sterren, nsrc = pid_info.get(pid, ("", "", ""))
            if name:
                n_named += 1
            w.writerow({"sha1": p["sha1"], "place_id": pid, "place_name": name,
                        "place_lat": la, "place_lng": lo, "sterren": sterren,
                        "source": (how + ("/" + nsrc if how and nsrc else "")) if how else ""})
    print(f"[places] klaar: {outp}   foto's met naam: {n_named}/{len(photos)}")
    if not key:
        print("       ↳ zet GOOGLE_MAPS_API_KEY en herdraai voor de namen van niet-gereviewde plekken.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""trip-photos-index — bouwsteen 1/4 van de per-reis foto-pipeline.

Scant de **mastermap** van één reis (recursief, multi-bron-vriendelijk: jouw +
partner telefoon, GoPro, kaart-uploads…) en bouwt de **fact-tabel** waarop de
volgende bouwstenen incrementeel kolommen aanvullen. Eén regel per foto.

INPUT  : mastermap met JPG/JPEG/PNG/HEIC (recursief)
OUTPUT : <out>/photos.csv  — kolommen: sha1, path_rel, filename, mtime,
                            exif_date, lat, lon
         <out>/photos-index.log  — wat is geskipt / gefaald

Idempotent + incrementeel: bestaande rijen (op sha1) worden NIET herberekend
(EXIF-parsing is duur op HEIC). Nieuwe foto's worden bij-gescand. Veilig voor
herrun na een onderbroken nacht-batch of als je nieuwe foto's toevoegt.

Read-only op de mastermap. Alle output landt in <out>.

Usage:
  python trip-photos-index.py --photos <mastermap> --trip <regio> --out <dossier>

Example:
  python trip-photos-index.py \\
    --photos "C:/claude/fvh.com/scratch/japan-werk/20250920 - Reis naar Japan" \\
    --trip Japan \\
    --out   "C:/claude/fvh.com/exports/trip-japan"
"""
import argparse, csv, hashlib, os, re, sys, datetime
from pathlib import Path

# Windows-console (cp1252) stikt op '→'/emoji; forceer UTF-8 stdout.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
except ImportError:
    sys.exit("pip install pillow")

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v"}
EXTS = PHOTO_EXTS | VIDEO_EXTS
FNAME_DATE = re.compile(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})[ _T-]?(\d{2})[._:]?(\d{2})[._:]?(\d{2})?")


def media_type_of(suffix: str) -> str:
    s = suffix.lower()
    return "video" if s in VIDEO_EXTS else "photo"


def sha1_of(path: Path, buf: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            chunk = f.read(buf)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def to_deg(rat) -> float:
    """EXIF GPS rationals → decimaal."""
    d, m, s = rat
    return float(d) + float(m) / 60.0 + float(s) / 3600.0


def exif_date_and_gps(path: Path):
    """Best-effort EXIF date + (lat, lon). Vangt fouten af; HEIC kan falen
    zonder pillow-heif — dan val we terug op de filename."""
    date, lat, lon = "", "", ""
    try:
        im = Image.open(path)
        ex = im._getexif() if hasattr(im, "_getexif") else None
        if ex:
            tags = {TAGS.get(k, k): v for k, v in ex.items()}
            for k in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
                if tags.get(k):
                    date = str(tags[k]).strip().replace(":", "-", 2).replace(" ", "T")
                    break
            gps = tags.get("GPSInfo")
            if gps:
                g = {GPSTAGS.get(k, k): v for k, v in gps.items()}
                if g.get("GPSLatitude") and g.get("GPSLongitude"):
                    lat = to_deg(g["GPSLatitude"])
                    if g.get("GPSLatitudeRef") == "S":
                        lat = -lat
                    lon = to_deg(g["GPSLongitude"])
                    if g.get("GPSLongitudeRef") == "W":
                        lon = -lon
    except Exception:
        pass
    return date, lat, lon


def fallback_date_from_name(name: str) -> str:
    m = FNAME_DATE.search(name)
    if not m:
        return ""
    y, mo, d, hh, mm, ss = m.groups()
    return f"{y}-{mo}-{d}T{hh}:{mm}:{ss or '00'}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photos", required=True, help="Mastermap (recursief)")
    ap.add_argument("--trip", required=True, help="Reisregio-label (informatief)")
    ap.add_argument("--out", required=True, help="Dossier-dir voor outputs")
    args = ap.parse_args()

    root = Path(args.photos)
    if not root.is_dir():
        sys.exit(f"--photos bestaat niet of is geen dir: {root}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    csv_path = out / "photos.csv"
    log_path = out / "photos-index.log"

    # incrementeel: bestaande sha1's onthouden zodat we ze niet opnieuw EXIF'en
    known = {}
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                known[row["sha1"]] = row

    files = [p for p in root.rglob("*") if p.suffix.lower() in EXTS and p.is_file()]
    files.sort()
    print(f"[trip-photos-index] trip={args.trip}  mastermap={root}")
    print(f"[trip-photos-index] gevonden: {len(files)} bestanden   bekende rijen: {len(known)}")

    rows, added, reused, errors = [], 0, 0, 0
    with log_path.open("w", encoding="utf-8") as logf:
        for i, p in enumerate(files, 1):
            try:
                h = sha1_of(p)
            except Exception as e:
                errors += 1
                logf.write(f"sha1-fail\t{p}\t{e}\n")
                continue
            if h in known:
                row = dict(known[h])
                row.setdefault("media_type", "photo")  # backward compat
                rows.append(row)
                reused += 1
                continue
            mtype = media_type_of(p.suffix)
            if mtype == "video":
                # Video: EXIF-parse is een ander beest; filename-fallback is genoeg voor de pilot.
                date, lat, lon = fallback_date_from_name(p.name), "", ""
            else:
                date, lat, lon = exif_date_and_gps(p)
                if not date:
                    date = fallback_date_from_name(p.name)
            rel = str(p.relative_to(root)).replace("\\", "/")
            mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")
            rows.append({
                "sha1": h, "path_rel": rel, "filename": p.name,
                "media_type": mtype,
                "mtime": mtime, "exif_date": date,
                "lat": lat, "lon": lon,
            })
            added += 1
            if i % 200 == 0:
                print(f"  …{i}/{len(files)}  (nieuw={added} hergebruikt={reused})")

    fields = ["sha1", "path_rel", "filename", "media_type", "mtime", "exif_date", "lat", "lon"]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

    n_photo = sum(1 for r in rows if r.get("media_type", "photo") == "photo")
    n_video = sum(1 for r in rows if r.get("media_type") == "video")
    with_gps = sum(1 for r in rows if r.get("lat") not in ("", None))
    with_date = sum(1 for r in rows if r.get("exif_date"))
    print(f"[trip-photos-index] klaar: {len(rows)} rijen → {csv_path}")
    print(f"  foto's: {n_photo}   video's: {n_video}")
    print(f"  nieuw geïndexeerd: {added}   hergebruikt uit cache: {reused}   errors: {errors}")
    print(f"  met datum: {with_date}/{len(rows)}   met GPS: {with_gps}/{len(rows)}")
    print(f"  log: {log_path}")


if __name__ == "__main__":
    main()

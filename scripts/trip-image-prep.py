#!/usr/bin/env python3
"""
Bouwsteen 5 — trip-image-prep: gekozen foto's web-klaar maken voor een post.

Draait NA de contactsheet (bouwsteen 4), op de `pick.csv` met jouw gekozen helden.
Doet twee dingen, bewust gescheiden:

  • DETERMINISTISCH (Pillow, geen LLM): auto-orient, resize (langste zijde <= --maxpx),
    naar sRGB/RGB, **EXIF + GPS strippen**, comprimeren → web-klare .jpg.
  • NAAM + ALT (hergebruikt Gemma's caption uit pick.csv): stelt een SEO-bestandsnaam
    voor (place + caption → slug) en een concept-alt-tekst.

⚠️ De voorgestelde namen/alt zijn een EERSTE JET (Gemma's caption kan plausibel-fout zijn —
   denk Sumitomo/Shimono). Daarom schrijft dit script ze naar `image-prep-review.csv`:
   **jij keurt namen + alt na vóór je ze in de Media Library zet.** Machine stelt voor, mens bevestigt.

INPUT  : <out>/pick.csv  (bouwsteen 4)   + de originelen onder --photos
OUTPUT : <out>/web/<seo-naam>.jpg        (web-klaar, EXIF/GPS gestript)
         <out>/image-prep-review.csv     (sha1, origineel, nieuwe naam, alt, dag, plaats, afmeting, kb)

Privacy: leest enkel de originelen (raakt ze niet aan), strijkt EXIF/GPS af op de output.
Outputs blijven lokaal onder <out> — nooit committen.

Gebruik:
  python scripts/trip-image-prep.py --photos "<mastermap>" --trip Japan --out "<out>" [--maxpx 1600] [--quality 82] [--force]
"""
import argparse, csv, json, re, sys, unicodedata
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow ontbreekt — pip install -r requirements.txt")
try:
    import pillow_heif  # HEIC/HEIF (iPhone)
    pillow_heif.register_heif_opener()
except ImportError:
    pass  # geen HEIC-ondersteuning; jpg/png/… werken nog

IMG_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
STOP = {
    "een", "de", "het", "en", "of", "met", "in", "op", "van", "aan", "voor", "naar",
    "te", "bij", "om", "dat", "die", "is", "een", "the", "a", "an", "and", "or",
    "with", "of", "on", "at", "to", "for", "in",
}


def slugify(text: str, maxwords: int = 8, maxlen: int = 64) -> str:
    """place + caption → korte, ascii, hyphen-slug zonder stopwoorden."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    words = re.findall(r"[a-z0-9]+", text)
    kept, seen = [], set()
    for w in words:
        if w in STOP or w in seen:
            continue
        kept.append(w)
        seen.add(w)
        if len(kept) >= maxwords:
            break
    slug = "-".join(kept)[:maxlen].strip("-")
    return slug or "foto"


def unique(name: str, used: set) -> str:
    base, n = name, 2
    while name in used:
        name = f"{base}-{n}"
        n += 1
    used.add(name)
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photos", required=True, help="mastermap met de originele foto's")
    ap.add_argument("--trip", required=True)
    ap.add_argument("--out", required=True, help="trip-outputmap (waar pick.csv staat)")
    ap.add_argument("--maxpx", type=int, default=1600, help="langste zijde in px (geen upscale)")
    ap.add_argument("--quality", type=int, default=82)
    ap.add_argument("--force", action="store_true", help="alles opnieuw encoderen")
    args = ap.parse_args()

    photos = Path(args.photos)
    out = Path(args.out)
    pick = out / "pick.csv"
    if not pick.exists():
        sys.exit(f"Geen pick.csv — kies eerst je helden in de contactsheet (bouwsteen 4): {pick}")

    web = out / "web"
    web.mkdir(parents=True, exist_ok=True)
    cache_path = out / ".image-prep-cache.json"
    cache = json.loads(cache_path.read_text("utf-8")) if cache_path.exists() else {}

    with open(pick, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    used = set()
    review, done, skipped = [], 0, 0
    for r in rows:
        sha1 = r.get("sha1", "")
        rel = r.get("path_rel") or r.get("path") or r.get("filename", "")
        place = (r.get("place_name") or "").replace(" (≈)", "").replace("(onbekend)", "").strip()
        caption = (r.get("caption") or "").strip()
        day = r.get("day", "")

        src = (photos / rel) if not Path(rel).is_absolute() else Path(rel)
        if src.suffix.lower() not in IMG_EXTS:
            skipped += 1
            continue
        if not src.exists():
            print(f"  ontbreekt: {src}")
            skipped += 1
            continue

        name = unique(slugify(f"{place} {caption}") + ".jpg", used)

        # idempotent: zelfde sha1 al verwerkt en bestand bestaat → overslaan
        if not args.force and cache.get(sha1) and (web / cache[sha1]).exists():
            name = cache[sha1]
            used.add(name)
        else:
            try:
                im = Image.open(src)
                im = ImageOps.exif_transpose(im)        # auto-orient
                im = im.convert("RGB")                   # flatten alpha / naar sRGB-achtig
                im.thumbnail((args.maxpx, args.maxpx), Image.LANCZOS)  # geen upscale
                im.save(web / name, "JPEG", quality=args.quality, optimize=True, progressive=True)
                # EXIF/GPS: niet meegegeven bij save → gestript.
                cache[sha1] = name
                done += 1
            except Exception as e:
                print(f"  fout bij {src.name}: {e}")
                skipped += 1
                continue

        w, h = Image.open(web / name).size
        kb = (web / name).stat().st_size // 1024
        review.append({
            "sha1": sha1, "origineel": rel, "nieuwe_naam": name,
            "alt_concept": caption, "dag": day, "plaats": place,
            "afmeting": f"{w}x{h}", "kb": kb,
        })

    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0), "utf-8")
    rev = out / "image-prep-review.csv"
    with open(rev, "w", newline="", encoding="utf-8") as f:
        wcsv = csv.DictWriter(f, fieldnames=["sha1", "origineel", "nieuwe_naam", "alt_concept", "dag", "plaats", "afmeting", "kb"])
        wcsv.writeheader()
        wcsv.writerows(review)

    print(f"[{args.trip}] {done} verwerkt, {skipped} overgeslagen → {web}")
    print(f"Review (namen + alt nakijken vóór upload): {rev}")


if __name__ == "__main__":
    main()

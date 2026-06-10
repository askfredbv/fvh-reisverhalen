#!/usr/bin/env python3
"""
Bouwsteen 5 — trip-image-prep: gekozen foto's web-klaar maken voor een post.

Twee invoer-workflows:
  • pick.csv (bouwsteen 4, de contactsheet)         — standaard
  • --picks-dir <map> : een map met de foto's die je zélf koos (door ze te
    kopiëren). Gematcht op filename tegen manifest.csv → naam/alt/plaats erbij.

Twee taken, bewust gescheiden:
  • DETERMINISTISCH (Pillow): auto-orient, resize op de **langste zijde**, naar RGB,
    **EXIF + GPS strippen**, comprimeren met **budget-fit** (zakt quality tot onder het
    KB-budget, floor q70 — textuur-zware beelden zoals bamboe blazen anders het budget op).
  • NAAM + ALT: SEO-bestandsnaam (plaats + Gemma's caption → slug) + concept-alt.

Rol-besef: **--role hero|inline** zet de fvh-conventie en waarschuwt als een HERO
**portret** is (wordt lelijk gecropt in de featured-zone én de OG social-card).
  hero   → 2000px / q88 / ≤500KB
  inline → 1600px / q85 / ≤300KB   (default)

⚠️ Voorgestelde namen/alt = eerste jet (Gemma kan plausibel-fout zijn — denk Sumitomo).
   Alles landt in image-prep-review-<rol>.csv: **mens keurt na vóór upload.**
   Outputs blijven lokaal onder <out> — nooit committen.

Gebruik:
  python scripts/trip-image-prep.py --photos "<mastermap>" --trip Japan --out "<out>" --role inline
  python scripts/trip-image-prep.py --trip Japan --out "<out>" --role hero --picks-dir "<gekozen-map>"
"""
import argparse, csv, json, re, sys, unicodedata
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow ontbreekt — pip install -r requirements.txt")
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

IMG_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
STOP = {
    "een", "de", "het", "en", "of", "met", "in", "op", "van", "aan", "voor", "naar",
    "te", "bij", "om", "dat", "die", "is", "the", "a", "an", "and", "or", "with", "for",
}
ROLE = {
    "hero":   {"maxpx": 2000, "quality": 88, "budget_kb": 500},
    "inline": {"maxpx": 1600, "quality": 85, "budget_kb": 300},
}
Q_FLOOR = 70


def slugify(text: str, maxwords: int = 8, maxlen: int = 64) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    words, kept, seen = re.findall(r"[a-z0-9]+", text), [], set()
    for w in words:
        if w in STOP or w in seen:
            continue
        kept.append(w); seen.add(w)
        if len(kept) >= maxwords:
            break
    return "-".join(kept)[:maxlen].strip("-") or "foto"


def unique(name: str, used: set) -> str:
    base, n = name, 2
    while name in used:
        name = f"{base.rsplit('.',1)[0]}-{n}.{base.rsplit('.',1)[1]}"
        n += 1
    used.add(name)
    return name


def orient(w: int, h: int) -> str:
    return "portret" if h > w else ("landschap" if w > h else "vierkant")


def load_rows(p: Path):
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def meta_from_row(r: dict) -> dict:
    rel = r.get("path_rel") or r.get("path") or r.get("filename", "")
    return {
        "sha1": r.get("sha1", ""),
        "rel": rel,
        "filename": r.get("filename") or Path(rel).name,
        "place": (r.get("place_name") or "").replace(" (≈)", "").replace("(onbekend)", "").strip(),
        "caption": (r.get("caption") or "").strip(),
        "day": r.get("day", ""),
        "privacy": (r.get("privacy_flag") or "").strip(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photos", help="mastermap met de originelen (vereist in pick.csv-modus)")
    ap.add_argument("--trip", required=True)
    ap.add_argument("--out", required=True, help="trip-outputmap (waar pick.csv / manifest.csv staat)")
    ap.add_argument("--role", choices=["hero", "inline"], default="inline")
    ap.add_argument("--maxpx", type=int, help="override rol-default")
    ap.add_argument("--quality", type=int, help="start-quality, override rol-default")
    ap.add_argument("--budget-kb", type=int, dest="budget_kb", help="max KB, override rol-default")
    ap.add_argument("--picks-dir", help="map met zelf gekozen foto's i.p.v. pick.csv")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    spec = dict(ROLE[args.role])
    if args.maxpx:     spec["maxpx"] = args.maxpx
    if args.quality:   spec["quality"] = args.quality
    if args.budget_kb: spec["budget_kb"] = args.budget_kb

    out = Path(args.out)
    web = out / "web" / args.role
    web.mkdir(parents=True, exist_ok=True)

    # bron-rijen (voor naam/alt/plaats): manifest.csv heeft de volledige set, pick.csv is een subset
    rows = []
    for cand in ("manifest.csv", "pick.csv"):
        if (out / cand).exists():
            rows = load_rows(out / cand); break

    # items = lijst van (bron-pad, meta)
    items = []
    if args.picks_dir:
        lookup = {}
        for r in rows:
            m = meta_from_row(r)
            if m["filename"]:
                lookup[m["filename"].lower()] = m
        pdir = Path(args.picks_dir)
        if not pdir.is_dir():
            sys.exit(f"--picks-dir is geen map: {pdir}")
        for f in sorted(pdir.iterdir()):
            if f.suffix.lower() in IMG_EXTS:
                items.append((f, lookup.get(f.name.lower(), {})))
        if not items:
            sys.exit(f"Geen beelden in --picks-dir: {pdir}")
        if not rows:
            print("  let op: geen manifest.csv/pick.csv gevonden → namen uit bestandsnaam, geen alt/plaats.")
    else:
        pick = out / "pick.csv"
        if not pick.exists():
            sys.exit(f"Geen pick.csv — kies eerst je helden in de contactsheet, of gebruik --picks-dir: {pick}")
        if not args.photos:
            sys.exit("--photos is vereist in pick.csv-modus (om de originelen te vinden)")
        photos = Path(args.photos)
        for r in load_rows(pick):
            m = meta_from_row(r)
            src = (photos / m["rel"]) if not Path(m["rel"]).is_absolute() else Path(m["rel"])
            items.append((src, m))

    cache_path = out / f".image-prep-cache-{args.role}.json"
    cache = json.loads(cache_path.read_text("utf-8")) if cache_path.exists() else {}

    used, review = set(), []
    done = skipped = warns = flagged = 0
    for src, m in items:
        if src.suffix.lower() not in IMG_EXTS or not src.exists():
            print(f"  ontbreekt/overslaan: {src}"); skipped += 1; continue

        cid = m.get("sha1") or src.name
        place, caption = m.get("place", ""), m.get("caption", "")
        base = f"{place} {caption}".strip()
        name = unique(slugify(base or src.stem) + ".jpg", used)
        q_used = spec["quality"]

        if not args.force and cache.get(cid) and (web / cache[cid]).exists():
            name = cache[cid]; used.add(name)
            with Image.open(web / name) as im:
                w, h = im.size
            kb = (web / name).stat().st_size // 1024
        else:
            try:
                im = Image.open(src)
                im = ImageOps.exif_transpose(im)
                im = im.convert("RGB")
                im.thumbnail((spec["maxpx"], spec["maxpx"]), Image.LANCZOS)  # langste zijde, geen upscale
                dst = web / name
                q = spec["quality"]
                while True:  # budget-fit
                    im.save(dst, "JPEG", quality=q, optimize=True, progressive=True)
                    if dst.stat().st_size / 1024 <= spec["budget_kb"] or q <= Q_FLOOR:
                        break
                    q -= 3
                w, h, kb, q_used = im.size[0], im.size[1], dst.stat().st_size // 1024, q
                cache[cid] = name; done += 1
            except Exception as e:
                print(f"  fout bij {src.name}: {e}"); skipped += 1; continue

        ori = orient(w, h)
        warn = ""
        if args.role == "hero" and ori == "portret":
            warn = "HERO is portret — wordt gecropt in featured + OG-card; kies liever landschap"
            print(f"  ⚠️  {name}: {warn}"); warns += 1
        pf = m.get("privacy", "")
        if pf:
            print(f"  🔒 {name}: mogelijk ID/document ({pf}) — NIET publiceren zonder check"); flagged += 1
        review.append({
            "sha1": m.get("sha1", ""), "origineel": src.name, "nieuwe_naam": name,
            "rol": args.role, "orientatie": ori, "alt_concept": caption,
            "dag": m.get("day", ""), "plaats": place, "afmeting": f"{w}x{h}",
            "kb": kb, "quality": q_used, "privacy_flag": pf, "waarschuwing": warn,
        })

    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0), "utf-8")
    rev = out / f"image-prep-review-{args.role}.csv"
    cols = ["sha1", "origineel", "nieuwe_naam", "rol", "orientatie", "alt_concept",
            "dag", "plaats", "afmeting", "kb", "quality", "privacy_flag", "waarschuwing"]
    with open(rev, "w", newline="", encoding="utf-8") as f:
        wc = csv.DictWriter(f, fieldnames=cols); wc.writeheader(); wc.writerows(review)

    print(f"[{args.trip}] rol={args.role}: {done} verwerkt, {skipped} overgeslagen, {warns} waarschuwing(en)"
          + (f", 🔒 {flagged} privacy-flag(s)" if flagged else "") + f" → {web}")
    print(f"Review (naam + alt + oriëntatie nakijken vóór upload): {rev}")


if __name__ == "__main__":
    main()

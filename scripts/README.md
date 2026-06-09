# BHAG data-pipeline — timeline + reviews → trip-master

Turns Frederik's **Google Maps timeline** + **Maps reviews** into a structured trip dataset
(the BHAG seed): a per-trip list, a flat reviews master, and an Excel workbook. **No LLM** — pure
deterministic Python. 100% local.

## Inputs (export these first — both are personal, keep LOCAL)
Export at [takeout.google.com](https://takeout.google.com) and select the **Maps** data:
- **Timeline** → `Tijdlijn.json` — Google **Takeout** → **"Maps (your places)"** gives the
  location-history JSON. (EU exports sometimes hand you CSV instead of JSON.)
- **Reviews** → `Reviews.json` — Google **Takeout** → **"Maps"** gives your reviews (and photos).

(Google's product labels shift over time; selecting both Maps items yields the Timeline JSON +
reviews. Confirmed working via Takeout 2026-06 — an earlier note here wrongly said Takeout no
longer exports the timeline.)

Put both under `C:\claude\fvh.com\downloads\` (the timeline JSON at the root; the Takeout unzipped under
`Maps Takeout\`). ⚠️ The **outputs contain location history + home address — never commit them**; they
stay under `C:\claude\fvh.com\` (per the global artifact-routing rule). Only these *scripts* are tracked.

## Run order
```bash
pip install openpyxl          # one-time (build-xlsx needs it)
cd C:\claude\fvh.com\downloads

# 1. timeline → 21 trips (clusters >300km from home, >=2 days)
python <repo>\scripts\parse-timeline.py            # -> trips-from-timeline.csv

# 2. match each review to the trip he was physically on (nearest timeline point, not write-date)
python <repo>\scripts\build-bhag-dataset.py        # -> bhag-reviews-flat.csv + bhag-trip-dossier.md

# 3. polished Excel master (2 sheets: Reizen + Plaatsen, snapshot values)
python <repo>\scripts\build-xlsx.py                # -> C:\claude\fvh.com\exports\BHAG-reizen-master.xlsx
```

## Notes / knobs
- `parse-timeline.py`: `HOME` = approx home coords (Gent/Wetteren), `AWAY_KM=300`, `MIN_DAYS=2`. The
  on-device timeline has **no place names** — only lat/lng + dates; region is guessed from bounding boxes.
- `build-bhag-dataset.py`: matches a review to a trip by the **nearest timeline point within 40 km**
  (robust against the unreliable review *write* date). Reviews near home / unmatched → "thuis/lokaal".
- Review *write-date ≠ visit-date*; repeat-country trips (many Italy summers) are split by physical
  presence, so a place revisited across years ties to whichever visit is geographically nearest.
- First run (2026-06): 51.443 timeline segments → **21 trips**; 600 reviews → **232 trip-matched**
  (Japan, New York, Malta, Rhodos, Portugal, Italy summers, …). Re-run anytime after a fresh export.

## Photo layer (per-trip, for the writer)
Two reusable helpers that turn a trip's **photo folder** (EXIF dates + GPS) into per-day notes the writer
scans while drafting — same no-LLM, 100%-local approach. Both default to the Japan 2025 trip and take
`["<photo folder>"] ["<trip regio>"]` as args, so they work for any trip.
- `exif-cluster.py` — buckets photos **per day** (matched to the timeline) and labels each with the
  nearest reviewed place where EXIF GPS survives → `japan-foto-per-dag.md` manifest (~10 hero shots/day).
- `evening-meals.py` — clusters the **evening** photos (≥17:00 / <02:00) by GPS to the nearest place
  (distance reported, no cap), so an *unreviewed* restaurant still surfaces — pins meals to day + place.

⚠️ Photo folders live under `C:\claude\fvh.com\scratch\…` (working copies; NAS originals untouched) and
the outputs under `…\downloads` — **never committed**. Only these scripts are tracked.

## Per-trip dossier pipeline (4 bouwstenen, 2026-06)
**The follow-up to the helpers above.** Built for the bulk reality: 1500-2000 photos per trip × 21 trips.
End-to-end *per trip*: master photo folder → indexed → vision-tagged → merged with reviews/timeline → a
local HTML contactsheet where you tick the heroes and export a `pick.csv`. All four scripts share one
argument contract and are **idempotent** (sha1-keyed caches) — interruption is free, re-run is free.

```bash
TRIP=Japan
PHOTOS="C:/claude/fvh.com/scratch/japan-werk/20250920 - Reis naar Japan"
OUT="C:/claude/fvh.com/exports/trip-japan"

python scripts/trip-photos-index.py  --photos "$PHOTOS" --trip "$TRIP" --out "$OUT"   # 1. fact-tabel
python scripts/trip-vision-tag.py    --photos "$PHOTOS" --trip "$TRIP" --out "$OUT"   # 2. Gemma (nacht)
python scripts/trip-merge.py         --photos "$PHOTOS" --trip "$TRIP" --out "$OUT"   # 3. dossier
python scripts/trip-contactsheet.py  --photos "$PHOTOS" --trip "$TRIP" --out "$OUT"   # 4. HTML+picks
```

Per bouwsteen:
- **1 · `trip-photos-index.py`** — scant de mastermap recursief (JPG/PNG/HEIC + MP4/MOV als video), parse't
  EXIF (datum, GPS), fallback op filename-datum. → `photos.csv` (sha1, path, media_type, datetime, lat, lon).
  Idempotent op sha1; ~25s voor 1900 files cold, ~5s warm.
- **2 · `trip-vision-tag.py`** — stuurt elke **foto** door Ollama Gemma 12B (default) en parse't
  caption/scène/bordtekst. Cache per sha1 → onderbreking gratis, herrun gratis. Ctrl-C-safe.
  Video's worden expliciet overgeslagen. → `vision.csv` + `cache/vision/<sha1>.json`. ~15-30s/foto.
- **3 · `trip-merge.py`** — joint `photos.csv` + `vision.csv` + `bhag-reviews-flat.csv` tot één
  `manifest.csv` per reis: per foto dag + plaats (nearest review op GPS, default 40 km), near-dup-cluster
  (default 90s + zelfde plaats), pre-rank (scène-prioriteit → één hero-kandidaat per cluster). Plaats
  voor GPS-loze foto's wordt geërfd van de dichtste foto-met-GPS op dezelfde dag (gemarkeerd "(≈)").
  Outlier-waarschuwing voor dagen >21d buiten het reis-zwaartepunt. → `manifest.csv` + `dag-overzicht.md`.
- **4 · `trip-contactsheet.py`** — genereert thumbnails (256px, sha1-cached) en een **lokale, offline**
  HTML met checkboxes: filter op alleen-hero / verberg-video, "selecteer alle hero's"-knop, "Download
  pick"-knop → `pick.csv` met (sha1, filename, path, day, place, scene, caption) voor de
  optimaliseren-en-upload-pijp (los hiervan). → `contactsheet.html` + `thumbs/`.

⚠️ Identiek aan de helpers boven: inputs leven onder `scratch/`, outputs onder `exports/<trip>/`, **niets
ervan committen**. Enkel de scripts.

**Bewezen op NY (2026-06-06)**: 1198 media → 285 dup-clusters → 285 hero-kandidaten = 4,2× reductie van
manueel-scrollwerk, vóór Gemma's scène-boost. End-to-end pipeline draait zonder code-aanpassing voor élke
reis — alleen `--photos`, `--trip` en `--out` wisselen. Japan-Gemma-batch loopt op 2026-06-06; NY-batch
volgt als de Japan-pilot z'n waarde bewezen heeft.

## Alles in één: `run-trip.py`
Draait bouwsteen 1→4 na elkaar voor één reis (stopt bij de eerste fout). `--photos/--trip/--out` gaan
naar elke stap; `--model`/`--limit` naar vision-tag, `--reviews` naar merge. Smoke-test met `--limit 10`.

```bash
python scripts/run-trip.py --photos "$PHOTOS" --trip "$TRIP" --out "$OUT"
```

Daarna pick je je helden in de contactsheet en draai je bouwsteen 5 (`trip-image-prep`).

## Bouwsteen 5 — web-klaar maken (`trip-image-prep.py`)
Draait ná de contactsheet. **Twee invoer-workflows:** `pick.csv` (default) of **`--picks-dir <map>`**
(een map met de foto's die je zelf koos door ze te kopiëren; gematcht op filename tegen `manifest.csv`
voor naam/alt/plaats). Twee taken, bewust gescheiden:
- **Deterministisch (Pillow, geen LLM):** auto-orient, resize op de **langste zijde**, naar RGB,
  **EXIF + GPS strippen**, comprimeren met **budget-fit** (zakt quality tot onder het KB-budget, floor
  q70) → `<out>/web/<rol>/<seo-naam>.jpg`. Vervangt de handmatige Squoosh-stap.
- **Naam + alt:** SEO-bestandsnaam (plaats + Gemma's caption → slug) + concept-alt.
- **Rol-besef (`--role hero|inline`):** zet de fvh-conventie en **waarschuwt als een HERO portret is**
  (wordt gecropt in featured + OG-card). `hero` = 2000px/q88/≤500KB · `inline` = 1600px/q85/≤300KB (default).
- **Mens-poort:** alles landt in `<out>/image-prep-review-<rol>.csv` (incl. **orientatie** + waarschuwing)
  — **keur namen + alt na vóór upload** (Gemma's caption is een eerste jet, denk Sumitomo/Shimono).
  Idempotent via `.image-prep-cache-<rol>.json`.

```bash
python scripts/trip-image-prep.py --photos "$PHOTOS" --trip "$TRIP" --out "$OUT" --role inline
python scripts/trip-image-prep.py --trip "$TRIP" --out "$OUT" --role hero --picks-dir "<gekozen-map>"
```

## Why no LLM
The data is structured (coords, dates, country codes) → a data job, where scripts beat an LLM (faster,
exact, free, private). Keep the LLM for **writing the articles** in Frederik's voice — not for the data.

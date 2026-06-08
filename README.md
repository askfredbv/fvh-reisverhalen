# fvh-reisverhalen

Turn a large personal photo archive plus your **Google Maps Timeline** into a per-trip
**contactsheet** of hero-candidate photos — so you can start *writing* travel stories instead of
scrolling through thousands of thumbnails. Everything runs **locally**: no cloud, no API account,
no photos ever leave your machine.

This is the toolkit behind a blog post on
[frederikvanhecke.com](https://frederikvanhecke.com) about building with data. *(article link
follows once published)*

## The idea

Two piles of data that are useless on their own:

- **Photos** — content without structure: thousands of files in the order a phone happened to save them.
- **Google Maps Timeline** — structure without content: it knows where you were and when, but not what mattered.

They share one key: **time** (and place). Join them and you can reconstruct a trip's timeline and
surface the handful of photos that actually carry the story.

## What's in here

Two small pipelines, all plain Python, all local.

**1 · Trips from your Timeline + reviews**
- `parse-timeline.py` — Timeline JSON → a list of trips (clusters far from home, multi-day).
- `build-bhag-dataset.py` — match your Maps reviews to the trip you were physically on (not the write-date).
- `build-xlsx.py` — a polished Excel master (trips + places).

**2 · Per-trip photo pipeline (the four building blocks)**
- `trip-photos-index.py` — scan a photo folder → `photos.csv` (sha1, date, GPS).
- `trip-vision-tag.py` — a local vision model (Ollama + Gemma) → `vision.csv` (caption, scene, sign text).
- `trip-merge.py` — photos + timeline + reviews → `manifest.csv` (day, place, near-duplicates).
- `trip-contactsheet.py` — thumbnails + an offline HTML contactsheet with checkboxes → `pick.csv`.
- `trip-image-prep.py` — *(post-pick)* picked photos → web-ready, SEO-named, EXIF-stripped images + a review sheet.

The four `trip-*` scripts share one argument contract (`--photos / --trip / --out`) and are
**idempotent** (sha1-keyed caches): interrupting and re-running is free.

## Requirements

- Python 3.9+
- `pip install -r requirements.txt` (Pillow, pillow-heif, openpyxl)
- For the vision step: [Ollama](https://ollama.com) running locally with a vision model pulled
  (the scripts default to a **Gemma** vision model — see [`scripts/README.md`](scripts/README.md)
  for the exact tag). A modest laptop-class GPU is plenty; it also runs on CPU, slower.

## Get your data (Google Takeout)

Export at [takeout.google.com](https://takeout.google.com) and select the **Maps** data:

- **"Maps (your places)"** → the **Timeline JSON** (your location history).
- **"Maps"** → your **reviews and photos**.

Google's product labels shift over time; selecting both Maps items gives you the Timeline JSON plus
your reviews. (EU exports sometimes hand you CSV instead of JSON.)

## Quickstart (per trip)

```bash
git clone https://github.com/askfredbv/fvh-reisverhalen
cd fvh-reisverhalen
pip install -r requirements.txt

TRIP=Japan
PHOTOS="/path/to/your/trip/photos"
OUT="/path/to/output/trip-japan"

python scripts/trip-photos-index.py --photos "$PHOTOS" --trip "$TRIP" --out "$OUT"
python scripts/trip-vision-tag.py   --photos "$PHOTOS" --trip "$TRIP" --out "$OUT"
python scripts/trip-merge.py        --photos "$PHOTOS" --trip "$TRIP" --out "$OUT"
python scripts/trip-contactsheet.py --photos "$PHOTOS" --trip "$TRIP" --out "$OUT"
```

Open the generated `contactsheet.html`, tick the photos you want, and download `pick.csv`.
Full per-step detail and knobs: [`scripts/README.md`](scripts/README.md).

## Privacy & data

Your exports and outputs contain **location history and your home area**, and can run to **many
gigabytes**. Keep them **local** — they are git-ignored and must never be committed. Only the
scripts are tracked here.

## License

[MIT](LICENSE) — free to use, modify, and share.

# BHAG data-pipeline — timeline + reviews → trip-master

Turns Frederik's **Google Maps timeline** + **Maps reviews** into a structured trip dataset
(the BHAG seed): a per-trip list, a flat reviews master, and an Excel workbook. **No LLM** — pure
deterministic Python. 100% local.

## Inputs (export these first — both are personal, keep LOCAL)
- **Timeline** → `Tijdlijn.json` — export from the **phone** (Google moved Timeline on-device 2024-25;
  Takeout no longer has it): Android → Maps → profile → Timeline → ⋮ → Location & privacy → *Export
  Timeline data*. (EU sometimes gives CSV instead of JSON.)
- **Reviews** → `Reviews.json` — Google **Takeout** → "Maps (your reviews)" → in `Maps (mijn plaatsen)/`.

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

## Why no LLM
The data is structured (coords, dates, country codes) → a data job, where scripts beat an LLM (faster,
exact, free, private). Keep the LLM for **writing the articles** in Frederik's voice — not for the data.

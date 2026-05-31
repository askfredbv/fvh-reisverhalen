# CLAUDE.md — fvh-reisverhalen (the travel-archive BHAG)

> Loads automatically when a session opens here. Separate project from fvh-2027 by design — don't mix.

## The BHAG
Turn Frederik's **1000+ photo-folder archive** (15 years, structure `YYYYMMDD - Event description`) into
a stream of high-quality **travel articles** for frederikvanhecke.com. Travel is the site's proven engine
(GSC) and unique first-hand content strengthens the cross-domain Person entity (see fvh-2027).

## The pipeline (plan)
1. **Triage** — classify folders into **travel vs not**, from the folder *name* + date (no photo
   processing needed), with **confidence tiers** (clearly-travel / clearly-not / ambiguous → Frederik
   confirms). Output = a travel shortlist.
   - ⚠️ **NEVER delete the non-travel folders** (kids, parties, renovations = irreversible family
     memories). Produce a LIST only; Frederik keeps/moves them. Claude does not delete personal data.
2. **Enrich** — Frederik drops the **Google Maps timeline** of each trip into its folder (route/places/dates).
3. **Write** — pilot: **5 articles** from timeline + photos (EXIF dates/GPS, view key images), in
   Frederik's voice (Register B), day-by-day like the Parijs post. Assess quality before scaling.
4. **Publish** — ⚠️ **strip EXIF/GPS** from photos first (privacy + perf); follow the fvh SEO/perf playbook.

## Prioritisation
Pick trips with **a story AND search demand**. GSC already shows demand for: Toscane/Gardameer,
Alentejo/Portugal, Boedapest, Domaine de la Porte/Dolce, Montcabrier. Quality > quantity.

## Cautions
- **Don't delete** non-travel folders — list/move only.
- **Strip EXIF/GPS** on every published photo.
- **Pilot 5 first**, judge quality, then decide on scaling.
- Folder-name triage is cheap; article-writing is the real work.

## Relation to fvh-2027 (reference, don't duplicate)
- **Voice/tone:** fvh-2027 `knowledge/tone-of-voice.md` + read 3–5 live articles before drafting.
- **SEO/perf/publish lessons:** fvh-2027 `knowledge/drupal-schema-perf-lessons.md`, `content-pipeline.md`.
- **The published posts live on fvh.com** (code: `C:\Github\fvh.com-mirror`). This project = the
  content-generation pipeline only.
- **Artifacts:** `C:\claude\fvh.com\` (drafts/scratch), per the global routing rule.

## Status
**Parked / not started (2026-05-31).** Next step: Frederik points to the archive path → run the triage.

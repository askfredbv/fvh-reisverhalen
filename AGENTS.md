# AGENTS.md — fvh-reisverhalen (the travel-archive BHAG)

> Loads automatically when a session opens here. Separate project from fvh-2027 by design — don't mix.

## Scope: what belongs in this project, and what does not (set 2026-11-26)
- **Here:** travel posts for frederikvanhecke.com, and only those: photo pipeline, kapstok, draft,
  image prep, publishing and the live check of the post itself. Sessions for this work sit in the
  sidebar section **"content - fvh"** and start in this folder.
- **Other content** (AI/data, DIY, tech notes, recipes) needs none of the photo pipeline and leans on
  site knowledge: it is written in `C:\Github\fvh-2027`, per `knowledge/content-pipeline.md`, in
  section "website - fvh" (Frederik, 2026-11-26).
- **Not here:** the site itself. Drupal, theme and layout, security, performance, hosting, deploy,
  SEO technique. That is `C:\Github\fvh-2027` (section "website - fvh"), and its open items live in
  that project's ledger, not in this one. If a content session runs into a site defect: note it
  there in one line, do not fix it here.
- **The SOP and the startprompt** are in fvh-2027 `knowledge/reispost-runbook.md`. Read it at the
  start of every post. It is not copied here.

## The BHAG
Turn Frederik's **1000+ photo-folder archive** (15 years, structure `YYYYMMDD - Event description`) into
a stream of high-quality **travel articles** for frederikvanhecke.com. Travel is the site's proven engine
(GSC) and unique first-hand content strengthens the cross-domain Person entity (see fvh-2027).

## The pipeline (plan)
1. **Triage** — classify folders into **travel vs not**, from the folder *name* + date (no photo
   processing needed), with **confidence tiers** (clearly-travel / clearly-not / ambiguous → Frederik
   confirms). Output = a travel shortlist.
   - ⚠️ **NEVER delete the non-travel folders** (kids, parties, renovations = irreversible family
     memories). Produce a LIST only; Frederik keeps/moves them. Codex does not delete personal data.
2. **Enrich** — Frederik drops the **Google Maps timeline** of each trip into its folder (route/places/dates).
3. **Write** — pilot: **5 articles** from timeline + photos (EXIF dates/GPS, view key images), in
   Frederik's voice (Register B), day-by-day like the Parijs post. Assess quality before scaling.
4. **Publish** — ⚠️ **strip EXIF/GPS** from photos first (privacy + perf); follow the fvh SEO/perf playbook.

## Seed sources (besides the photo folders)
- 🌟 **Google Maps reviews (Takeout → "Maps (your reviews)")** — Frederik is a Local Guide L8; his
  reviews are a **ready-made, geo-tagged master list of where he's been**: place, address, **coords**,
  date, star rating, **his own impression**, recommended dishes, and **photos**. This may be the fastest
  way to **list all the trips at once** (cross-check / augment the folder-name triage) AND pre-seed each
  article (the per-place take is already written, in his words). Trips already surfaced from a partial
  glance: **Japan/Kyoto, Italy (Urbino/Perugia/Toscane), Paris, New York (family), Belgian local**.
  - ⚠️ **Voice caveat:** weight the **terse** reviews ("Best in town, simply put.") — the longer,
    adjective-heavy ones read as generic/possibly-AI and are NOT his authentic voice. See fvh-2027
    `knowledge/tone-of-voice.md`.
  - ✅ **Done (2026-06):** exports parsed → **21 trips** (timeline) × **600 reviews** (232 trip-matched).
    The pipeline is built — see **`scripts/`** (`README.md` + parse-timeline / build-bhag-dataset /
    build-xlsx). Outputs (LOCAL, never commit — contain location history + home address):
    `<pad naar jouw exports>\BHAG-reizen-master.xlsx` (master, 2 sheets) +
    `<pad naar jouw downloads>\bhag-trip-dossier.md` (writing-ready per-trip view).
    Re-run the scripts after any fresh export.
- **Timeline (location history)** — per-trip routes + dates. ⚠️ Google moved Timeline **on-device**
  (2024-25): **Takeout no longer exports it** (gives nothing useful). Export from the **phone's Maps app**
  instead: Android → profile → Timeline → ⋮ → Location & privacy settings → **Export Timeline data**;
  iOS → Maps → Settings → Location & Privacy → Export Timeline data. File = **`location-history.json`**
  (JSON; some EU users get **CSV**). Contains semantic trips/places+dates, not just raw GPS. (Pipeline step 2.)

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
- **Image pipeline & cleanup (read before bulk!):** fvh-2027 `knowledge/media-and-cleanup.md` — the
  plain-vanilla beeld-standaard (Media Library, descriptive filenames, alt/caption, Squoosh strips EXIF),
  the reusable `scripts/orphan-cleanup.php`, and the gotchas (revisions pin old files; title edit → slug
  change → regenerate sitemap + GSC). Proven on the Boedapest pilot — this is the workflow you scale here.
- **The published posts live on fvh.com** (code: `<pad naar jouw site-code>`). This project = the
  content-generation pipeline only.
- **Artifacts:** `<pad naar jouw artifacts>` (drafts/scratch), per the global routing rule.

## ⛔ Prerequisite (gate) — foundation first
**Don't start the bulk run until the fvh publish pipeline is proven rock-solid.** Frederik's rule
(2026-05-31): the base infrastructure must "staan als een huis" before scaling — a bug in the pipeline
multiplies across every article. That's *why* fvh is being perfected first. The "go" for this BHAG =
when write → optimise → schema → publish → perf → social is confirmed flawless on the existing posts.

## Status
**Not kept here, because it went stale here.** This section said "next step: the NY article" until
November, while NY had been live since 2026-06-20. Current state lives in the memory ledger
(`open-work-ledger.md`, read first). Publication state never comes from memory either: one curl on
`https://frederikvanhecke.com/sitemap.xml` is the check.

The pipeline (bouwsteen 1 to 5) was proven on the NY pilot in June 2026, see `scripts/README.md`.
⚠️ The bulk-run gate above stays **Frederik's call**: a go for one post is not a go for the bulk.

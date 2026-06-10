#!/usr/bin/env python3
"""trip-contactsheet — bouwsteen 4/4 van de per-reis foto-pipeline.

Genereert per reis een **lokale HTML-contactsheet** voor jouw picks: thumbnails
gegroepeerd per dag → plaats → moment (dup_group). Vink aan wat je wil →
'Download pick' geeft een CSV met de gekozen foto's voor de volgende stap
(optimaliseren + upload-klaar, los hiervan in de Squoosh-pipeline).

INPUT  : <out>/manifest.csv  (bouwsteen 3)
OUTPUT : <out>/contactsheet.html  — open lokaal in browser; werkt offline
         <out>/thumbs/<sha1>.jpg  — 256px thumbs, sha1-cache (incrementeel)

Video's verschijnen als placeholder met VIDEO-badge + filename + datetime —
géén automatische frame-extractie in de pilot (ffmpeg toevoegen kan later).

Usage:
  python trip-contactsheet.py --photos <mastermap> --trip <regio> --out <dossier>
"""
import argparse, csv, html, sys
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("pip install pillow")


def gen_thumb(src: Path, dst: Path, maxdim: int = 256) -> bool:
    if dst.exists():
        return True
    try:
        im = Image.open(src)
        im = ImageOps.exif_transpose(im)  # respecteer EXIF-rotatie (anders liggen portretten op hun kant)
        im = im.convert("RGB")
        im.thumbnail((maxdim, maxdim))
        im.save(dst, "JPEG", quality=80)
        return True
    except Exception as e:
        print(f"  thumb-fout {src.name}: {e}")
        return False


CSS = """
:root{--bg:#0e1014;--card:#181c22;--ink:#e6e7e9;--muted:#9aa0a6;--accent:#3ddc84;--hero:#ffd166;--flag:#ff5d5d}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.4 system-ui,sans-serif}
header{position:sticky;top:0;background:#0e1014ee;backdrop-filter:blur(6px);padding:12px 20px;border-bottom:1px solid #222;z-index:10;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header h1{margin:0;font-size:18px;font-weight:600}
header .stats{color:var(--muted);font-size:13px}
header .spacer{flex:1}
button{background:var(--accent);color:#000;border:0;padding:8px 14px;font-weight:600;border-radius:6px;cursor:pointer}
button.secondary{background:#2b3038;color:var(--ink)}
button:hover{filter:brightness(1.1)}
label.toggle{display:flex;gap:6px;align-items:center;color:var(--muted);cursor:pointer;user-select:none}
main{padding:16px 20px 80px}
.day{margin:24px 0 16px}
.day>summary{font-size:16px;font-weight:600;color:var(--ink);cursor:pointer;padding:8px 0;border-bottom:1px solid #2a2f37;list-style:none}
.day>summary::-webkit-details-marker{display:none}
.day>summary::before{content:'▸ ';color:var(--muted)}
.day[open]>summary::before{content:'▾ '}
.place{margin:12px 0 18px;padding:10px 12px;background:var(--card);border-radius:8px}
.place h3{margin:0 0 8px;font-size:14px;font-weight:600;color:#cfd2d6}
.place h3 .count{color:var(--muted);font-weight:400;margin-left:8px;font-size:12px}
.cluster{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0;padding:6px;border-radius:6px}
.cluster.alt{background:#1f242c}
.tile{position:relative;width:140px;display:flex;flex-direction:column;gap:2px}
.tile input{position:absolute;top:6px;left:6px;width:18px;height:18px;cursor:pointer;z-index:2}
.tile img,.tile .videoph{width:140px;height:140px;object-fit:cover;border-radius:4px;background:#22262d;display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:11px;text-align:center;padding:8px}
.tile.hero img,.tile.hero .videoph{outline:2px solid var(--hero);outline-offset:-2px}
.tile.hero::after{content:'★';position:absolute;top:4px;right:6px;color:var(--hero);font-size:14px}
.tile.video::after{content:'▶ VIDEO';position:absolute;top:4px;right:6px;background:#000a;color:#fff;font-size:10px;padding:2px 5px;border-radius:3px}
.tile .meta{font-size:11px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tile .meta b{color:#cfd2d6}
.tile .scene{display:inline-block;font-size:10px;padding:1px 4px;background:#2b3038;border-radius:3px;color:#cfd2d6;margin-right:3px}
.tile .text{font-size:10px;color:#9fb8c5;font-style:italic;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tile input:checked ~ img,.tile input:checked ~ .videoph{outline:3px solid var(--accent);outline-offset:-3px}
body.hero-only .tile:not(.hero){display:none}
body.hide-video .tile.video{display:none}
body.hide-flagged .tile.flagged{display:none}
.tile.flagged img,.tile.flagged .videoph{outline:2px solid var(--flag);outline-offset:-2px}
.tile .lock{position:absolute;top:5px;left:30px;font-size:14px;z-index:2;filter:drop-shadow(0 0 2px #000)}
"""

JS = """
function recount(){
  const n = document.querySelectorAll('.tile input:checked').length;
  document.getElementById('count').textContent = n;
  document.getElementById('export').disabled = n === 0;
}
document.addEventListener('change', e => { if (e.target.matches('.tile input')) recount(); });

document.getElementById('hero-only').addEventListener('change', e => {
  document.body.classList.toggle('hero-only', e.target.checked);
});
document.getElementById('hide-video').addEventListener('change', e => {
  document.body.classList.toggle('hide-video', e.target.checked);
});
document.getElementById('hide-flagged').addEventListener('change', e => {
  document.body.classList.toggle('hide-flagged', e.target.checked);
});
document.getElementById('select-heroes').addEventListener('click', () => {
  document.querySelectorAll('.tile.hero input').forEach(i => { i.checked = true; });
  recount();
});
document.getElementById('clear').addEventListener('click', () => {
  document.querySelectorAll('.tile input').forEach(i => { i.checked = false; });
  recount();
});
document.getElementById('toggle-all').addEventListener('click', () => {
  document.querySelectorAll('.day').forEach(d => { d.open = !d.open; });
});

document.getElementById('export').addEventListener('click', () => {
  const rows = [['sha1','filename','path_rel','day','place_name','scene','caption','privacy_flag']];
  document.querySelectorAll('.tile input:checked').forEach(i => {
    const t = i.closest('.tile');
    rows.push([t.dataset.sha1, t.dataset.filename, t.dataset.path, t.dataset.day, t.dataset.place, t.dataset.scene, t.dataset.caption, t.dataset.privacy]);
  });
  const csv = rows.map(r => r.map(c => '"' + (c||'').replaceAll('"','""') + '"').join(',')).join('\\n');
  const blob = new Blob([csv], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'pick.csv';
  a.click();
});
recount();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photos", required=True)
    ap.add_argument("--trip", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = Path(args.photos)
    out = Path(args.out)
    mf = out / "manifest.csv"
    if not mf.exists():
        sys.exit(f"Geen manifest.csv — draai eerst bouwsteen 3: {mf}")
    thumb_dir = out / "thumbs"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    with mf.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    # Thumbs genereren (incrementeel)
    photos = [r for r in rows if r.get("media_type", "photo") != "video"]
    print(f"[trip-contactsheet] trip={args.trip}  media={len(rows)}   foto's met thumb-target: {len(photos)}")
    done, skipped_missing = 0, 0
    for i, r in enumerate(photos, 1):
        src = root / r["path_rel"]
        if not src.exists():
            skipped_missing += 1
            continue
        dst = thumb_dir / f"{r['sha1']}.jpg"
        if dst.exists():
            done += 1
            continue
        if gen_thumb(src, dst):
            done += 1
        if i % 200 == 0:
            print(f"  thumbs: {i}/{len(photos)}")
    print(f"  thumbs klaar: {done}   missend: {skipped_missing}")

    # Groeperen day → place → dup_group
    by_day = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        d = r.get("day") or "(geen datum)"
        # ≈-erfgenamen samenvoegen met echte plaats
        p = (r.get("place_name") or "(onbekend)").replace(" (≈)", "")
        by_day[d][p][r.get("dup_group", "0")].append(r)

    # HTML genereren
    n_total = len(rows)
    n_photo = sum(1 for r in rows if r.get("media_type", "photo") != "video")
    n_video = n_total - n_photo
    n_hero = sum(1 for r in rows if r.get("prerank") == "1")

    parts = [f"""<!doctype html><html lang="nl"><head>
<meta charset="utf-8"><title>{html.escape(args.trip)} — contactsheet</title>
<style>{CSS}</style></head><body><header>
<h1>{html.escape(args.trip)}</h1>
<span class="stats">{n_photo} foto's · {n_video} video's · {n_hero} hero-kandidaten · <span id="count">0</span> geselecteerd</span>
<span class="spacer"></span>
<label class="toggle"><input type="checkbox" id="hero-only"> alleen hero ★</label>
<label class="toggle"><input type="checkbox" id="hide-video"> verberg video</label>
<label class="toggle"><input type="checkbox" id="hide-flagged"> verberg 🔒</label>
<button class="secondary" id="toggle-all">expand/collapse</button>
<button class="secondary" id="select-heroes">selecteer alle hero's</button>
<button class="secondary" id="clear">wis selectie</button>
<button id="export" disabled>Download pick</button>
</header><main>"""]

    for day in sorted(by_day):
        if not day:
            continue
        n_day = sum(len(v) for places in by_day[day].values() for v in places.values())
        parts.append(f'<details class="day" open><summary>{html.escape(day)}  <span style="color:var(--muted);font-size:13px;font-weight:400">· {n_day} items</span></summary>')
        # Sorteer plaatsen chronologisch (vroegste foto eerst) — zodat de dag van vroeg naar laat leest
        def _place_min_dt(groups):
            return min((it.get("datetime", "") or "9999") for items in groups.values() for it in items)
        places_sorted = sorted(by_day[day].items(), key=lambda kv: _place_min_dt(kv[1]))
        for place, groups in places_sorted:
            n_pl = sum(len(v) for v in groups.values())
            parts.append(f'<div class="place"><h3>{html.escape(place)}<span class="count">{n_pl} items · {len(groups)} clusters</span></h3>')
            # Sorteer clusters op tijd (eerste item)
            groups_sorted = sorted(groups.items(), key=lambda kv: kv[1][0].get("datetime", ""))
            for gi, (gid, items) in enumerate(groups_sorted):
                items.sort(key=lambda x: x.get("datetime", ""))
                parts.append(f'<div class="cluster{" alt" if gi % 2 else ""}">')
                for it in items:
                    sha1 = it["sha1"]
                    fname = it["filename"]
                    path = it["path_rel"]
                    dt = it.get("datetime", "")
                    t_short = dt[11:16] if len(dt) >= 16 else ""
                    scene = it.get("scene", "")
                    caption = it.get("caption", "")
                    text = it.get("sign_text", "")
                    is_video = it.get("media_type") == "video"
                    is_hero = it.get("prerank") == "1"
                    privacy = it.get("privacy_flag", "")
                    cls = "tile"
                    if is_hero: cls += " hero"
                    if is_video: cls += " video"
                    if privacy: cls += " flagged"
                    data = (
                        f'data-sha1="{html.escape(sha1)}" '
                        f'data-filename="{html.escape(fname)}" '
                        f'data-path="{html.escape(path)}" '
                        f'data-day="{html.escape(day)}" '
                        f'data-place="{html.escape(place)}" '
                        f'data-scene="{html.escape(scene)}" '
                        f'data-caption="{html.escape(caption)}" '
                        f'data-privacy="{html.escape(privacy)}"'
                    )
                    lock = f'<span class="lock" title="mogelijk ID/document: {html.escape(privacy)}">🔒</span>' if privacy else ""
                    if is_video:
                        media = f'<div class="videoph">{html.escape(fname)}</div>'
                    else:
                        media = f'<img loading="lazy" src="thumbs/{sha1}.jpg" alt="">'
                    tooltip_bits = [caption]
                    if text: tooltip_bits.append(f'TEXT: {text}')
                    tooltip = html.escape(" — ".join(b for b in tooltip_bits if b))
                    scene_html = f'<span class="scene">{html.escape(scene)}</span>' if scene else ""
                    text_html = f'<div class="text">"{html.escape(text[:50])}"</div>' if text else ""
                    parts.append(
                        f'<div class="{cls}" {data} title="{tooltip}">'
                        f'<input type="checkbox">'
                        f'{lock}'
                        f'{media}'
                        f'<div class="meta"><b>{t_short}</b> {scene_html}{html.escape(fname[:18])}</div>'
                        f'{text_html}'
                        f'</div>'
                    )
                parts.append('</div>')  # cluster
            parts.append('</div>')  # place
        parts.append('</details>')

    parts.append(f'</main><script>{JS}</script></body></html>')

    html_path = out / "contactsheet.html"
    html_path.write_text("".join(parts), encoding="utf-8")
    print(f"\n[trip-contactsheet] contactsheet: {html_path}")
    print(f"  open in browser:  file:///{str(html_path).replace(chr(92),'/')}")
    print(f"  thumb-folder: {thumb_dir}  ({done} files)")


if __name__ == "__main__":
    main()

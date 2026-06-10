#!/usr/bin/env python3
"""trip-vision-tag — bouwsteen 2/4 van de per-reis foto-pipeline.

Stuurt elke foto uit <out>/photos.csv door een **lokaal vision-model** (Ollama,
default gemma4:12b) en schrijft per foto: caption, scene, sign_text.

NACHT-BATCH-VRIENDELIJK:
- Cache per sha1 in <out>/cache/vision/<sha1>.json — onderbreking en herrun gratis.
- Sliding ETA + Ctrl-C-safe flush van vision.csv.
- --limit voor smoke-tests, --model om te experimenteren.

INPUT  : <out>/photos.csv  (bouwsteen 1 — fact-tabel)
OUTPUT : <out>/cache/vision/<sha1>.json  — per foto, atomisch geschreven
         <out>/vision.csv  — geaggregeerd: sha1, caption, scene, sign_text, vision_secs

Gemma is *dommekracht* (§12 working-with-frederik): caption en bordtekst zijn nuttig,
**eigennamen niet**. Bouwsteen 3 (merge) levert plaats via timeline+GPS — autoritair.

Usage:
  python trip-vision-tag.py --photos <mastermap> --trip <regio> --out <dossier> [--limit N] [--model gemma4:12b]
"""
import argparse, base64, csv, io, json, os, signal, socket, sys, time
from pathlib import Path
from urllib import request as _req, error as _err

try:
    # line_buffering=True: voortgang verschijnt live in een log/redirect (background/
    # scheduled runs bufferden anders stdout -> lege log tijdens de hele batch).
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

try:
    from PIL import Image
except ImportError:
    sys.exit("pip install pillow")

# Optionele HEIC-support — als ontbreekt, skip HEIC met nette log i.p.v. crash.
try:
    import pillow_heif  # noqa: F401
    pillow_heif.register_heif_opener()
    HEIC_OK = True
except Exception:
    HEIC_OK = False

API = "http://localhost:11434/api/generate"

PROMPT = (
    "You are tagging a personal travel photo for a blog. Be concise and literal — "
    "describe only what you actually see, do not invent. Answer EXACTLY in this form:\n"
    "CAPTION: <one short factual sentence>\n"
    "SCENE: <one of: food, landscape, cityscape, people, architecture, temple, signage, transport, interior, other>\n"
    "TEXT: <any clearly readable signage text, else 'none'>"
)


def parse_response(raw: str) -> dict:
    """Trek CAPTION/SCENE/TEXT uit Gemma's vrije tekst; vergeef wat case/format-rommel."""
    out = {"caption": "", "scene": "", "sign_text": ""}
    for line in raw.splitlines():
        s = line.strip()
        u = s.upper()
        if u.startswith("CAPTION:"):
            out["caption"] = s.split(":", 1)[1].strip()
        elif u.startswith("SCENE:"):
            out["scene"] = s.split(":", 1)[1].strip().lower()
        elif u.startswith("TEXT:"):
            t = s.split(":", 1)[1].strip()
            out["sign_text"] = "" if t.lower() in ("none", "n/a", "-") else t
    return out


def small_b64(path: Path, maxdim: int = 1024) -> str:
    im = Image.open(path).convert("RGB")
    im.thumbnail((maxdim, maxdim))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def call_vision(b64: str, model: str) -> tuple[str, float]:
    payload = json.dumps({
        "model": model,
        "prompt": PROMPT,
        "images": [b64],
        "stream": False,
        "think": False,
        # num_predict capt tokens — voorkomt hallucinatie-loops waar Gemma blijft
        # doorgenereren (gezien 2026-06-06: één foto = 7,8KB output, ~50 min hang).
        # 400 tokens is ruim voor CAPTION+SCENE+TEXT.
        "options": {"temperature": 0.1, "num_predict": 400},
    }).encode()
    t0 = time.time()
    req = _req.Request(API, data=payload, headers={"Content-Type": "application/json"})
    # 120s timeout per foto — bij hang doorgaan i.p.v. eindeloos blokkeren.
    with _req.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    return resp.get("response", "").strip(), time.time() - t0


def atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def load_cached(cache_dir: Path) -> dict[str, dict]:
    cached = {}
    for f in cache_dir.glob("*.json"):
        try:
            cached[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return cached


def write_vision_csv(csv_path: Path, cached: dict[str, dict]) -> None:
    fields = ["sha1", "caption", "scene", "sign_text", "vision_secs", "model"]
    tmp = csv_path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for sha1, v in sorted(cached.items()):
            w.writerow({
                "sha1": sha1,
                "caption": v.get("caption", ""),
                "scene": v.get("scene", ""),
                "sign_text": v.get("sign_text", ""),
                "vision_secs": round(v.get("vision_secs", 0), 1),
                "model": v.get("model", ""),
            })
    os.replace(tmp, csv_path)


def fmt_eta(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"


def keep_system_awake():
    """Houd Windows wakker zolang de batch loopt — voorkomt Modern Standby (S0), die een
    nachtelijke run suspendeert ook al staat 'sleep after' op nooit (gezien 2026-06-09:
    batch viel stil ~30 min na idle). Geeft een release-callable terug (no-op buiten Windows)."""
    if sys.platform != "win32":
        return lambda: None
    try:
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        return lambda: ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        return lambda: None


def gpu_sanity_warn(model: str) -> None:
    """Waarschuw één keer als Ollama het model 100% op CPU draait (geen GPU-offload) — dat is
    ~2-3× trager. Veelvoorkomende oorzaak: Ollama koos Vulkan i.p.v. CUDA (start met OLLAMA_VULKAN=0)."""
    try:
        with _req.urlopen("http://localhost:11434/api/ps", timeout=10) as r:
            data = json.loads(r.read())
    except Exception:
        return
    for m in data.get("models", []):
        if model in (m.get("name", ""), m.get("model", "")) or m.get("name", "").startswith(model):
            if m.get("size", 0) and m.get("size_vram", 0) == 0:
                print("  ⚠️  model draait 100% op CPU (geen GPU-offload) — ~2-3× trager dan op GPU.")
                print("      Check `ollama ps`; veelal fix: herstart Ollama met OLLAMA_VULKAN=0 (forceert CUDA).")
            return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photos", required=True)
    ap.add_argument("--trip", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="gemma4:12b")
    ap.add_argument("--limit", type=int, default=0, help="0 = alles; >0 voor smoke-test")
    args = ap.parse_args()

    root = Path(args.photos)
    out = Path(args.out)
    photos_csv = out / "photos.csv"
    vision_csv = out / "vision.csv"
    cache_dir = out / "cache" / "vision"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not photos_csv.exists():
        sys.exit(f"Geen photos.csv — draai eerst bouwsteen 1 (trip-photos-index): {photos_csv}")

    with photos_csv.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    cached = load_cached(cache_dir)
    # Video's hier overslaan — vision-batch is foto-only (per-frame video-analyse is een andere pijp).
    todo = [r for r in rows if r["sha1"] not in cached and r.get("media_type", "photo") != "video"]
    n_video_skip = sum(1 for r in rows if r.get("media_type") == "video")
    if args.limit > 0:
        todo = todo[: args.limit]

    print(f"[trip-vision-tag] trip={args.trip}  model={args.model}  HEIC-support={HEIC_OK}")
    print(f"[trip-vision-tag] media: {len(rows)}  (video's overgeslagen: {n_video_skip})   in cache: {len(cached)}   te doen: {len(todo)}")
    if not todo:
        write_vision_csv(vision_csv, cached)
        print(f"[trip-vision-tag] niets te doen — vision.csv ververst ({len(cached)} rijen)")
        return

    # Ctrl-C-safe: bij interrupt nog vision.csv flushen met wat we hebben.
    interrupted = {"flag": False}
    def _on_sigint(_sig, _frm):
        interrupted["flag"] = True
        print("\n[trip-vision-tag] interrupt opgevangen — flush vision.csv en stop netjes…")
    signal.signal(signal.SIGINT, _on_sigint)

    release_awake = keep_system_awake()  # Windows: voorkom Modern Standby tijdens de batch
    t_start = time.time()
    times: list[float] = []  # sliding window voor ETA
    SKIP_HEIC = not HEIC_OK
    done = 0
    skipped_heic = 0
    errors = 0
    gpu_checked = False

    for i, r in enumerate(todo, 1):
        if interrupted["flag"]:
            break
        sha1 = r["sha1"]
        rel = r["path_rel"]
        path = root / rel
        if not path.exists():
            errors += 1
            print(f"  [{i}/{len(todo)}] BESTAND MIST: {rel}")
            continue
        if SKIP_HEIC and path.suffix.lower() in (".heic", ".heif"):
            skipped_heic += 1
            continue
        try:
            b64 = small_b64(path)
            raw, dt = call_vision(b64, args.model)
            parsed = parse_response(raw)
            parsed.update({"vision_secs": dt, "model": args.model, "raw": raw})
            atomic_write_json(cache_dir / f"{sha1}.json", parsed)
            cached[sha1] = parsed
            done += 1
            if not gpu_checked:  # eenmalig: waarschuw als het model op CPU draait
                gpu_sanity_warn(args.model)
                gpu_checked = True
            times.append(dt)
            if len(times) > 30:
                times.pop(0)
            avg = sum(times) / len(times)
            remaining = len(todo) - i
            eta = remaining * avg
            if i % 5 == 0 or i == len(todo):
                print(f"  [{i}/{len(todo)}]  {dt:4.1f}s  gem {avg:4.1f}s  ETA {fmt_eta(eta)}   {path.name}")
        except _err.URLError as e:
            # time-out = hangende foto → overslaan; échte connectiefout (Ollama down) → stoppen
            if isinstance(getattr(e, "reason", None), (socket.timeout, TimeoutError)):
                errors += 1
                print(f"  [{i}/{len(todo)}] TIME-OUT op {path.name}, overgeslagen")
                continue
            errors += 1
            print(f"  [{i}/{len(todo)}] OLLAMA-FOUT (draait hij?): {e}")
            break
        except (socket.timeout, TimeoutError):
            errors += 1
            print(f"  [{i}/{len(todo)}] TIME-OUT op {path.name}, overgeslagen")
            continue
        except Exception as e:
            errors += 1
            print(f"  [{i}/{len(todo)}] FOUT op {path.name}: {e}")
            continue

    release_awake()  # keep-awake assertie loslaten
    write_vision_csv(vision_csv, cached)
    print(f"\n[trip-vision-tag] klaar in {fmt_eta(time.time() - t_start)}")
    print(f"  verwerkt deze run: {done}   skipped (HEIC, geen pillow-heif): {skipped_heic}   errors: {errors}")
    print(f"  totaal in cache: {len(cached)} / {len(rows)}")
    print(f"  vision.csv: {vision_csv}")
    if interrupted["flag"]:
        print("  (onderbroken — herstart hetzelfde commando om verder te gaan)")


if __name__ == "__main__":
    main()

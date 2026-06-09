#!/usr/bin/env python3
"""
run-trip — dunne runner die bouwsteen 1→4 na elkaar draait voor één reis:

    index → vision-tag → merge → contactsheet

Daarna pick jij je helden in de contactsheet (pick.csv); `trip-image-prep` (bouwsteen 5)
draait apart op die picks. Deze runner stopt bij de eerste fout.

`--photos/--trip/--out` gaan naar elke stap; `--model` en `--limit` naar vision-tag,
`--reviews` naar merge. (Niet meegegeven = de defaults van elke stap.)

Gebruik:
  python scripts/run-trip.py --photos "<mastermap>" --trip Japan --out "<out>"
  python scripts/run-trip.py --photos "<mastermap>" --trip NY --out "<out>" --limit 10   # smoke-test
"""
import argparse, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent

# (script, welke extra-args eraan doorgeven)
STEPS = [
    ("trip-photos-index.py", []),
    ("trip-vision-tag.py",   ["model", "limit"]),
    ("trip-merge.py",        ["reviews"]),
    ("trip-contactsheet.py", []),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photos", required=True)
    ap.add_argument("--trip", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", help="vision-model voor trip-vision-tag")
    ap.add_argument("--limit", type=int, help="vision-tag: beperk aantal foto's (smoke-test)")
    ap.add_argument("--reviews", help="pad naar reviews-csv voor trip-merge")
    args = ap.parse_args()

    extra = {"model": args.model, "limit": args.limit, "reviews": args.reviews}
    base = ["--photos", args.photos, "--trip", args.trip, "--out", args.out]

    print(f"== run-trip: {args.trip} ==  ({len(STEPS)} stappen)\n")
    for i, (script, opts) in enumerate(STEPS, 1):
        cmd = [sys.executable, str(HERE / script)] + base
        for o in opts:
            v = extra.get(o)
            if v is not None:
                cmd += [f"--{o}", str(v)]
        print(f"--- [{i}/{len(STEPS)}] {script} ---")
        t0 = time.time()
        if subprocess.run(cmd).returncode != 0:
            print(f"\n[X] Gestopt: {script} faalde. Draai die stap los om te zien waarom.")
            sys.exit(1)
        print(f"  ok ({time.time() - t0:.0f}s)\n")

    print("Klaar (1->4). Open de contactsheet, pick je helden, en draai dan bouwsteen 5:")
    print(f'  python scripts/trip-image-prep.py --photos "{args.photos}" --trip "{args.trip}" --out "{args.out}" --role inline')


if __name__ == "__main__":
    main()

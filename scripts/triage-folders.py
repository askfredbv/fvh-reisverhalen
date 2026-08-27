#!/usr/bin/env python3
"""Triage van de NAS-mapnamen (read-only tekstlijst) -> reis-vs-niet, in zekerheidstiers.
Raakt NIETS aan: leest enkel het lokale nas-folders.txt en schrijft een lokale markdown-lijst.
De NAS wordt nooit benaderd."""
import re, collections
from pathlib import Path

SRC = Path(r"C:/claude/fvh.com/downloads/nas-folders.txt")
OUT = Path(r"C:/claude/fvh.com/downloads/reizen-triage.md")
PREFIX = r"\\asknas\Media\Pictures"

KNOWN21 = {
    "20150801","20151230","20160710","20160729","20161230","20170813","20180408",
    "20180803","20190727","20200731","20210724","20220729","20230730","20240704",
    "20240921","20241026","20250517","20250721","20250908","20250920","20251230",
}

TRAVEL = [
    "reis","reisje","citytrip","city trip","vakantie","weekend","roadtrip","rondreis","trip",
    "italie","italië","italiereis","toscane","toscana","garda","gardameer","venetie","venetië",
    "venezia","rome","firenze","florence","nerano","amalf","sicili","portugal","alentejo",
    "lissabon","porto","algarve","spanje","barcelona","madrid","andalusi","frankrijk","parijs","paris",
    "sarlat","milandes","montcabrier","manciet","dordogne","provence","nice","domaine","gite",
    "duitsland","berlijn","berlin","munchen","münchen","keulen","koln","köln","hongarije","boedapest",
    "budapest","japan","finland","tokio","kyoto","osaka","malta","griekenland","kreta","rhodos",
    "athene","santorini","engeland","londen","london","schotland","ierland","dublin","amsterdam",
    "oostenrijk","wenen","zwitserland","kroati","amerika","new york","verenigde staten","oostkust",
    "noorwegen","zweden","denemarken","praag","marokko","turkije","egypte","dubai","disney",
]
HOME = [
    "thuis","verbouwing","keuken","keukenblad","tuin","verjaardag","feest","communie","lentefeest",
    "doop","geboorte","zwanger","school","klas","rapport","scouts","chiro","bbq","barbecue","drink",
    "launch","kantoor","askfred","backup","oma","opa","mama ","papa","ten ede","sinterklaas",
    "zwemmen","optreden","ziekenhuis","dokter","tandarts","fotos thuis","foto's thuis",
]

def has(text, kws): return [k for k in kws if k in text]

lines = SRC.read_text(encoding="utf-8-sig").splitlines()
tops = []
for ln in lines:
    ln = ln.strip().lstrip("﻿")
    if not ln.startswith(PREFIX + "\\"):
        continue
    rest = ln[len(PREFIX) + 1:]
    if "\\" in rest:        # subfolder -> overslaan
        continue
    tops.append(rest)
tops = sorted(set(tops))

rows = []
for name in tops:
    m = re.match(r"^(\d{8}|0000)\s*-\s*(.*)$", name)
    date, desc = (m.group(1), m.group(2)) if m else ("", name)
    low = name.lower()
    t, h = has(low, TRAVEL), has(low, HOME)
    tier = "reis" if (t and not h) else ("niet" if (h and not t) else "twijfel")
    rows.append((date, desc, name, tier, date in KNOWN21, t, h))

c = collections.Counter(r[3] for r in rows)
reis = [r for r in rows if r[3] == "reis"]
twijfel = [r for r in rows if r[3] == "twijfel"]
nieuw = [r for r in reis if not r[4]]
in21_reis = [r for r in reis if r[4]]

md = ["# Reizen-triage uit de NAS-mapnamen\n",
      f"> Read-only triage van {len(tops)} top-level mappen. Alleen een lijst; niets aangeraakt, NAS niet benaderd.\n",
      f"\n**Tiers:** reis={c['reis']} · twijfel={c['twijfel']} · niet={c['niet']}  (totaal {len(rows)})\n",
      f"\n**Reis al in je 21 timeline-trips:** {len(in21_reis)}  ·  **reis maar NIET in de 21 (kandidaat-weekends/extra):** {len(nieuw)}\n",
      "\n## Reis — NIET in de 21 (de ontbrekende, incl. weekends)\n"]
for d, desc, name, _, _, t, _ in sorted(nieuw):
    md.append(f"- `{d or '????????'}` {desc}   _(match: {', '.join(t[:3])})_")
md.append("\n## Reis — al in de 21 timeline-trips\n")
for d, desc, name, _, _, _, _ in sorted(in21_reis):
    md.append(f"- `{d}` {desc}")
md.append("\n## Twijfel — jij bevestigt (reis of niet?)\n")
for d, desc, name, _, _, t, h in sorted(twijfel):
    hint = []
    if t: hint.append("reis?: " + ", ".join(t[:2]))
    if h: hint.append("niet?: " + ", ".join(h[:2]))
    md.append(f"- `{d or '????????'}` {desc}" + (f"   _({'; '.join(hint)})_" if hint else ""))

OUT.write_text("\n".join(md), encoding="utf-8")
print(f"top-level mappen: {len(tops)}")
print(f"  reis: {c['reis']}   twijfel: {c['twijfel']}   niet: {c['niet']}")
print(f"  reis al in de 21: {len(in21_reis)}   reis NIEUW (niet in 21): {len(nieuw)}")
print(f"  twijfel-gevallen: {len(twijfel)}")
print(f"output: {OUT}")
print("\n--- REIS, NIEUW (niet in de 21) ---")
for d, desc, name, _, _, t, _ in sorted(nieuw):
    print(f"  {d or '????????'}  {desc[:55]}")

#!/usr/bin/env python3
"""Cureer de reis-triage tot een shortlist: familie-reizen vs uitgesloten (solo/werk/scouts/
restaurant/lokaal-themaweekend), ontdubbel meerdaagse reeksen tot 1 reis, en kruis tegen de
gepubliceerde artikels. Leest enkel lokale bestanden; raakt de NAS niet aan."""
import re, collections
from pathlib import Path
from datetime import date

SRC = Path(r"C:/claude/fvh.com/downloads/nas-folders.txt")
OUT = Path(r"C:/claude/fvh.com/downloads/reizen-shortlist.md")
PREFIX = r"\\asknas\Media\Pictures"

TRAVEL = ["reis","reisje","citytrip","city trip","vakantie","weekend","roadtrip","rondreis","trip",
    "italie","italië","toscane","toscana","garda","venetie","venetië","rome","firenze","florence",
    "nerano","amalf","sicili","portugal","alentejo","lissabon","porto","algarve","spanje","barcelona",
    "madrid","andalusi","frankrijk","parijs","paris","sarlat","milandes","montcabrier","manciet",
    "dordogne","domme","castelnaud","bonaguil","larressingle","toirac","aquitaine","provence","domaine",
    "duitsland","berlijn","berlin","keulen","koln","köln","hongarije","boedapest","japan","finland",
    "malta","griekenland","kreta","rhodos","santorini","engeland","londen","london","ierland","dublin",
    "amsterdam","oostenrijk","wenen","zwitserland","kroati","amerika","new york","oostkust","noorwegen",
    "praag","marokko","turkije","yalikavak","side","mallorca","normandie","disneyland","innerkrems",
    "domburg","burgh-haamstede","barvaux","waimes","houffalize","ardennen","erperheide","aquadelta",
    "skireis","skiweekend","skien","walibi","noto","istrie","rodos","monsaraz","pe no monte","winterberg"]

# Uitsluit-redenen (op de mapnaam). Volgorde = prioriteit van de reden.
EXCLUDE = [
    ("werk",       ["hackathon","bics"," oc weekend","launch","kantoor","askfred"]),
    ("scouts/jeugd",["kapoen","kabouter","welp","jonggids","jongverkenner","scout","chiro","bezinning",
                     "kennismaking","smurf","regenboog","james bond weekend","aladdin weekend",
                     "scoutsweekend","leiding","spelewei"]),
    ("restaurant/eten",["eten ","eten bij","diner "]),
    ("solo/deel",  ["nathalie mallorca","reis nathalie","saar en ruben","saar in ","saar naar","saar op ",
                    "saar weekend","saar terug","saar vertrek","saar skien","italiereis saar","italiereis maarten",
                    "maarten en bigo","maarten welp","maarten kapoen","maarten terug","maarten vertrek",
                    "maarten op ","maarten aan tank","zuidafrikaans weekend","wijn op","vrouwen in malaga",
                    "strip maarten","dromen nieuwe auto","skiweekend frederik"]),
    ("familiebezoek (oma/opa)", ["oma en opa","bij oma","bij opa","oma mj","omi ","omi duitsland"]),
    ("school/jeugd", ["schoolreis","school","ideekids","spelewei","leiding","spaghetti","scoutsweekend"]),
    ("thuis/lokaal", ["thuis","zwemmen","rozenbroeken"]),
]
# Gepubliceerde artikels (trefwoord in reis-tekst -> artikel). DONE = al af op de site.
PUBLISHED = [
    (["boedapest","hongarije"], "Citytrip Boedapest"),
    (["berlijn","berlin"], "Proeven van Berlijn"),
    (["alentejo"], "Portugal Alentejo"),
    (["gardameer","garda"], "Gardameer en Toscane"),
    (["nerano","amalf"], "Nerano/Amalfi/Rome/Toscane"),
    (["montalbino"], "Toscane agriturismo Montalbino"),
    (["manciet","lauroux"], "Manciet Domaine Lauroux"),
    (["montcabrier","dolce"], "Montcabrier Domaine de la Dolce"),
    (["huwelijksreis"], "Elkaar ja gezegd... Italie"),
    (["japan","finland"], "Japan met Voka (DONE)"),
    (["new york","oostkust"], "New York (DONE)"),
]
def first_match(text, table):
    for kws, label in table:
        if any(k in text for k in kws):
            return label
    return None

def excl_reason(text):
    for reason, kws in EXCLUDE:
        if any(k in text for k in kws):
            return reason
    return None

# 1) top-level mappen + datums
lines = SRC.read_text(encoding="utf-8-sig").splitlines()
tops = []
for ln in lines:
    ln = ln.strip().lstrip("﻿")
    if not ln.startswith(PREFIX + "\\"): continue
    rest = ln[len(PREFIX)+1:]
    if "\\" in rest: continue
    tops.append(rest)
tops = sorted(set(tops))

# 2) enkel reis-kandidaten (heeft travel-trefwoord), met datum
cand = []
for name in tops:
    low = name.lower()
    if not any(k in low for k in TRAVEL): continue
    m = re.match(r"^(\d{8})\s*-\s*(.*)$", name)
    if not m: continue
    d = m.group(1)
    try: dt = date(int(d[:4]), int(d[4:6]), int(d[6:8]))
    except ValueError: continue
    cand.append((dt, m.group(2), name, low))
cand.sort()

# 3) ontdubbel: opeenvolgende datums (gat <= 3 dagen) = 1 reis
trips, cur = [], []
for c in cand:
    if cur and (c[0] - cur[-1][0]).days <= 1:
        cur.append(c)
    else:
        if cur: trips.append(cur)
        cur = [c]
if cur: trips.append(cur)

# 4) per reis: uitsluit-reden (meerderheid van de dagen) of familie-reis + publicatie-match
HARD = {"werk", "scouts/jeugd"}   # één map met dit kenmerk sluit de hele reeks uit
NEARBY = ["waimes","ardennen","barvaux","ploegsteert","malvoisin","lontzen","forest","trooz",
          "houffalize","erperheide","lampernisse","spa ","francorchamps","massemen","mechelen",
          "domburg","burgh-haamstede","aquadelta","bruinisse"]
qualifies, excluded, twijfel = [], [], []
for run in trips:
    text = " | ".join(r[3] for r in run)
    reasons = [excl_reason(r[3]) for r in run]
    hard = [w for w in reasons if w in HARD]
    nonexcl = [r for r, why in zip(run, reasons) if not why]
    start, end = run[0][0], run[-1][0]
    span = f"{start.isoformat()}" + (f" .. {end.isoformat()}" if end != start else "")
    descs = "; ".join(dict.fromkeys(r[1] for r in run))  # uniek, volgorde
    if hard:
        excluded.append((span, descs, hard[0], len(run)))
    elif not nonexcl:
        why = collections.Counter(r for r in reasons if r).most_common(1)[0][0]
        excluded.append((span, descs, why, len(run)))
    elif any(nb in text for nb in NEARBY):
        twijfel.append((span, descs, len(run)))
    else:
        pub = first_match(text, PUBLISHED)
        qualifies.append((span, descs, pub, len(run)))

# 5) markdown
md = ["# Reizen-shortlist (voorstel — jij bevestigt)\n",
      f"> Uit {len(cand)} reis-kandidaat-mappen, ontdubbeld tot **{len(trips)} reizen**. "
      f"Familie-reis: {len(qualifies)} · uitgesloten: {len(excluded)}. NAS niet benaderd.\n",
      "\n> **Markeren:** vul achter `::` in — `JA` (op de blog) · `NEE` (eruit) · "
      "`AL <artikelnaam>` (al gepubliceerd). Niets invullen = akkoord met de sectie. "
      "Focus op **twijfel** + de paar **te schrijven** die eigenlijk al af zijn.\n"]
pubd = [q for q in qualifies if q[2]]
todo = [q for q in qualifies if not q[2]]
md.append(f"\n## Komt in aanmerking — AL GEPUBLICEERD ({len(pubd)})\n")
for span, descs, pub, n in pubd:
    md.append(f"- `{span}` **{pub}** — {descs}" + (f"  _({n} mappen)_" if n>1 else "") + "   :: ")
md.append(f"\n## Komt in aanmerking — NOG TE SCHRIJVEN ({len(todo)})\n")
for span, descs, _, n in todo:
    md.append(f"- `{span}` {descs}" + (f"  _({n} mappen)_" if n>1 else "") + "   :: ")
md.append(f"\n## Twijfel — nabij/Belgisch weekend: scouts of gezin? ({len(twijfel)}) — jij beslist\n")
for span, descs, n in sorted(twijfel):
    md.append(f"- `{span}` {descs}" + (f"  _({n} mappen)_" if n>1 else "") + "   :: ")
md.append(f"\n## Uitgesloten ({len(excluded)}) — reden erbij, jij kan overrulen\n")
for span, descs, why, n in sorted(excluded):
    md.append(f"- `{span}` {descs}  → _{why}_   :: ")
OUT.write_text("\n".join(md), encoding="utf-8")

print(f"reis-kandidaat-mappen: {len(cand)}  ->  {len(trips)} reizen na ontdubbelen")
print(f"  komt in aanmerking: {len(qualifies)}  (gepubliceerd {len(pubd)} · te schrijven {len(todo)})")
print(f"  twijfel (nabij weekend): {len(twijfel)}")
print(f"  uitgesloten: {len(excluded)}")
print(f"output: {OUT}\n")
print("--- NOG TE SCHRIJVEN (familie-reis, geen artikel gevonden) ---")
for span, descs, _, n in todo:
    print(f"  {span:24} {descs[:50]}")

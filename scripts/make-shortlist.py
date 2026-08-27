#!/usr/bin/env python3
"""Leest de getagde reizen-shortlist.md en bouwt de definitieve shortlist:
alles behalve `:: NEE` en de uitgesloten-sectie (tenzij `:: JA`). Herbruikbaar:
voeg later JA/AL toe en herdraai."""
import re
from pathlib import Path

SRC = Path(r"C:/claude/fvh.com/downloads/reizen-shortlist.md")
OUT = Path(r"C:/claude/fvh.com/downloads/reizen-shortlist-DEF.md")

section = None
pub, todo = [], []
for ln in SRC.read_text(encoding="utf-8").splitlines():
    if ln.startswith("## "):
        s = ln.lower()
        section = ("pub" if "gepubliceerd" in s else "todo" if "te schrijven" in s
                   else "twijfel" if "twijfel" in s else "excl" if "uitgesloten" in s else None)
        continue
    if not ln.strip().startswith("- ") or section is None:
        continue
    body, _, tagraw = ln.partition("::")
    tag = tagraw.strip().upper()
    body = body.strip().rstrip()
    if body.startswith("- "): body = body[2:].strip()
    m = re.search(r"`([0-9]{4}-[0-9]{2}-[0-9]{2})", body)
    date = m.group(1) if m else "0000-00-00"
    if tag.startswith("NEE"):
        continue
    if section == "pub":
        pub.append((date, body, tag))
    elif section == "todo":
        (pub if tag.startswith("AL") else todo).append((date, body, tag))
    elif section in ("twijfel", "excl"):
        if tag.startswith("JA"):
            todo.append((date, body, tag))

pub.sort(); todo.sort()
md = ["# Reizen-shortlist — DEFINITIEF (werkdocument)\n",
      f"> Na jouw markeringen. Komt in aanmerking voor de reisblog: **{len(pub)+len(todo)}** reizen "
      f"({len(pub)} gepubliceerd · {len(todo)} te schrijven). NEE/uitgesloten weggelaten.\n",
      f"\n## Al gepubliceerd ({len(pub)}) — voor completeness-check\n"]
for d, body, tag in pub:
    md.append(f"- {body}" + (f"   _[{tag}]_" if tag and not tag.startswith("AL") else ""))
md.append(f"\n## Nog te schrijven ({len(todo)}) — de backlog\n")
for d, body, tag in todo:
    md.append(f"- {body}" + (f"   _[{tag}]_" if tag else ""))
OUT.write_text("\n".join(md), encoding="utf-8")

print(f"SHORTLIST: {len(pub)+len(todo)} reizen  ({len(pub)} gepubliceerd · {len(todo)} te schrijven)")
print(f"output: {OUT}\n")
print("--- NOG TE SCHRIJVEN ---")
for d, body, tag in todo:
    txt = re.sub(r"_\(\d+ mappen\)_", "", body)
    print("  " + re.sub(r"\s+", " ", txt)[:78])

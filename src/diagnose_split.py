"""
Kaam: un judgments ko dekhna jinme humara "JUDGMENT" marker nahi mila, aur
pata lagana ki headnote khatam hokar judgment kahan se shuru hota hai.
Ye sirf padhta hai. Koi file badalta nahi.

Chalao (project ke root folder se):
    python src/diagnose_split.py
"""
import glob
import json
import random
import re
import statistics
from collections import Counter

FILES = sorted(glob.glob("data/processed/civil_*.jsonl"))

# Wahi marker jo chunk_corpus.py me tha
MARKER = re.compile(
    r"^(?:J\s*U\s*D\s*G\s*M\s*E\s*N\s*T|O\s*R\s*D\s*E\s*R)\s*:?\s*$", re.I
)
FIRST_PARA = re.compile(r"^1\.\s")

random.seed(7)

# ---------- Step 1: docs ko do groups me baanto ----------
with_marker, without_marker = [], []
marker_variants = Counter()

for fp in FILES:
    for line in open(fp, encoding="utf-8"):
        r = json.loads(line)
        found = None
        for ln in r["text"].split("\n"):
            if MARKER.match(ln.strip()):
                found = ln.strip()
                break
        if found:
            with_marker.append(r)
            marker_variants[found] += 1
        else:
            without_marker.append(r)

print(f"Marker MILA: {len(with_marker)} | Marker NAHI mila: {len(without_marker)}")
print("Marker ke variants:", dict(marker_variants.most_common(6)))

# ---------- Step 2: marker-less docs ki shuruaat ki CAPS lines ----------
# Idea: headnote aur judgment ke beech aksar koi CAPS wali chhoti line hoti hai
# (jaise "CIVIL APPELLATE JURISDICTION"). Dekhte hain kaunsi lines baar baar aati hain.
caps_lines = Counter()
for r in without_marker:
    seen = set()
    for ln in r["text"][:20000].split("\n"):
        s = ln.strip()
        if 2 <= len(s) <= 60 and s not in seen:
            letters = [c for c in s if c.isalpha()]
            if letters and sum(c.isupper() for c in letters) / len(letters) > 0.8:
                seen.add(s)
                caps_lines[s] += 1

print("\n=== Marker-less docs me sabse common CAPS lines (kitne docs me aayi) ===")
for s, n in caps_lines.most_common(30):
    print(f"  {n:4d}  {s}")

# ---------- Step 3: pehla numbered paragraph "1." kahan aata hai ----------
offsets, before_first, no_first = [], Counter(), 0
for r in without_marker:
    lines = r["text"].split("\n")
    pos = 0
    hit = None
    for i, ln in enumerate(lines):
        if FIRST_PARA.match(ln.strip()):
            hit = i
            break
        pos += len(ln) + 1
    if hit is None:
        no_first += 1
        continue
    offsets.append(pos)
    if hit > 0:
        before_first[lines[hit - 1].strip()[:60]] += 1

print(f"\n=== Pehla numbered paragraph '1.' ===")
print(f"Docs jisme '1.' mila hi nahi: {no_first} of {len(without_marker)}")
if offsets:
    print("Judgment text me '1.' kis character position pe aata hai:")
    print(f"  min={min(offsets)} median={int(statistics.median(offsets))} max={max(offsets)}")
print("'1.' se theek pehle wali line (sabse common):")
for s, n in before_first.most_common(12):
    print(f"  {n:4d}  {s!r}")

# ---------- Step 4: 3 random docs ko aankhon se dekho ----------
print("\n=== 3 random docs: '1.' se pehle ki 8 lines ===")
for r in random.sample(without_marker, min(3, len(without_marker))):
    lines = r["text"].split("\n")
    idx = next((i for i, ln in enumerate(lines) if FIRST_PARA.match(ln.strip())), None)
    print(f"\n--- {(r['title'] or '')[:70]} ---")
    if idx is None:
        print("  ('1.' nahi mila. Pehli 8 lines dikha raha hu)")
        for ln in lines[:8]:
            print("  |", ln[:110])
    else:
        for ln in lines[max(0, idx - 8): idx + 1]:
            print("  |", ln[:110])
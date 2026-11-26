"""
patch_golden_helper.py

Kaam: src/golden_helper.py (purani file) me 2 sudhaar lagana:
  1. "k" ke keyword results ab judte hain (replace nahi hote)
  2. --redo option (jaise: --redo Q01,Q07,Q09)

Safe hai: pehle check karta hai ki saari jagah mil rahi hain, tabhi likhta hai.
Agar file pehle se patched hai, to kuch nahi karta.

Chalao (project ke root folder se):
    python src/patch_golden_helper.py
"""
import sys

PATH = "src/golden_helper.py"
s = open(PATH, encoding="utf-8").read()

if "kw_all" in s:
    print("Ye file pehle se patched hai. Kuch karne ki zaroorat nahi.")
    sys.exit(0)

EDITS = [
    # 1) shutil import
    (
        '''import os
import re
from collections import OrderedDict, defaultdict''',
        '''import os
import re
import shutil
from collections import OrderedDict, defaultdict''',
    ),
    # 2) keyword candidates ka accumulator
    (
        '''    cands = list(vec)
    while True:
        print()
        show(cands)''',
        '''    kw_all = []          # keyword candidates, har "k" round ke baad badhte jaate hain (replace nahi hote)
    cands = list(vec)
    while True:
        print()
        show(cands)''',
    ),
    # 3) naye keyword results purane ke baad jodo
    (
        '''            kw = keyword_candidates(chunks, kws, {c["file"] for c in vec}, N_KEYWORD)
            if not kw:
                print("  Koi match nahi mila.")
            cands = list(vec) + kw
            continue''',
        '''            already = {c["file"] for c in vec} | {c["file"] for c in kw_all}
            new = keyword_candidates(chunks, kws, already, N_KEYWORD)
            if not new:
                print("  Koi naya match nahi mila.")
            kw_all = kw_all + new            # purane numbers wahi rahenge, naye neeche jud jaayenge
            cands = list(vec) + kw_all
            continue''',
    ),
    # 4) drop_ids function
    (
        '''def case_view(c, snippet, via):''',
        '''def drop_ids(path, ids):
    """golden file se ye ids hata do (purani file .bak me bachi rehti hai). Kitne hataye wo return karta hai."""
    if not os.path.exists(path):
        return 0
    lines = [l for l in open(path, encoding="utf-8") if l.strip()]
    keep = [l for l in lines if json.loads(l)["id"] not in ids]
    removed = len(lines) - len(keep)
    if removed:
        shutil.copyfile(path, path + ".bak")
        with open(path, "w", encoding="utf-8") as f:
            for l in keep:
                f.write(l if l.endswith("\\n") else l + "\\n")
    return removed


def case_view(c, snippet, via):''',
    ),
    # 5) --redo argument
    (
        '''    ap.add_argument("--golden", default="eval/golden_set.jsonl")
    args = ap.parse_args()''',
        '''    ap.add_argument("--golden", default="eval/golden_set.jsonl")
    ap.add_argument("--redo", default="", help="in sawaalon ko dobara karo, jaise: --redo Q01,Q07")
    args = ap.parse_args()''',
    ),
    # 6) --redo lagao
    (
        '''    questions = load_questions(args.questions)
    finished = done_ids(args.golden)''',
        '''    if args.redo:
        ids = {x.strip().upper() for x in args.redo.split(",") if x.strip()}
        n = drop_ids(args.golden, ids)
        print(f"Redo: {n} purani entry hata di (backup: {args.golden}.bak)")
    questions = load_questions(args.questions)
    finished = done_ids(args.golden)''',
    ),
]

# pehle sab check karo, tabhi likho (all or nothing)
for i, (old, _) in enumerate(EDITS, 1):
    n = s.count(old)
    if n != 1:
        print(f"Badlav {i}: jagah nahi mili (matches = {n}). Kuch nahi likha. Mujhe ye message bhejo.")
        sys.exit(1)

for old, new in EDITS:
    s = s.replace(old, new)

open(PATH, "w", encoding="utf-8").write(s)
print("Patched OK: 6 badlav lag gaye.")
"""

src/chunk_corpus.py me 5 chhote badlav karna (chunk ID ko PDF filename se banana
      aur duplicate PDFs ka report). Ye tab kaam aata hai jab nayi chunk_corpus.py
      download na ho paye.

 agar koi badlav ki jagah nahi mili ya file pehle se patched hai,
to ye kuch bhi likhe bina rukh jata hai.

"""
import sys

PATH = "src/chunk_corpus.py"
s = open(PATH, encoding="utf-8").read()

if "seen_files" in s:
    print("Ye file pehle se patched hai. Kuch karne ki zaroorat nahi.")
    sys.exit(0)

EDITS = [
    # 1) defaultdict import
    (
        "from collections import Counter\n",
        "from collections import Counter, defaultdict\n",
    ),
    # 2) tracking variables
    (
        "n_docs = n_chunks = n_dropped = plaintiffno = 0\nmethods = Counter()",
        "n_docs = n_chunks = n_dropped = plaintiffno = 0\n"
        "seen_files = set()              # ek hi PDF do baar aaye to skip karo\n"
        "dup_docs = []                   # skip hue duplicate docs (report ke liye)\n"
        "case_files = defaultdict(list)  # case_id -> kaunsi PDF files isse judi hain\n"
        "methods = Counter()",
    ),
    # 3) duplicate PDFs skip karo
    (
        '            r = json.loads(line)\n            n_docs += 1\n',
        '            r = json.loads(line)\n'
        '            if r["file"] in seen_files:\n'
        '                dup_docs.append((r["file"], r["title"]))\n'
        '                continue\n'
        '            seen_files.add(r["file"])\n'
        '            case_files[r["case_id"]].append(r["file"])\n'
        '            n_docs += 1\n',
    ),
    # 4) chunk_id ab PDF filename se
    (
        '                        "chunk_id": f"{r[\'case_id\'] or r[\'file\']}::{k:04d}",',
        '                        # FIX: PDF ka filename unique hota hai, case_id nahi (do judgments ka case_id same ho sakta hai)\n'
        '                        "chunk_id": f"{os.path.splitext(r[\'file\'])[0]}::{k:04d}",',
    ),
    # 5) report
    (
        'print("saved:", OUT, round(os.path.getsize(OUT) / 1e6, 1), "MB")\n',
        'print("saved:", OUT, round(os.path.getsize(OUT) / 1e6, 1), "MB")\n'
        '\n'
        '# ---- duplicate check (citation verifier ke liye zaroori) ----\n'
        'print("\\nduplicate PDF files skipped:", len(dup_docs), dup_docs[:3])\n'
        'shared = {cid: fs for cid, fs in case_files.items() if len(fs) > 1}\n'
        'print("case_id jo ek se zyada PDF me hai:", len(shared))\n'
        'for cid, fs in list(shared.items())[:5]:\n'
        '    print("  ", cid, "->", fs)\n',
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
print("Patched OK: 5 badlav lag gaye.")
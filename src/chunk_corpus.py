"""


Kaam: data/processed/civil_*.jsonl ke judgments ko chhote chunks me todna
      aur data/processed/chunks.jsonl me save karna.

v1 se kya badla:
  1. Headnote/judgment split ab 3 rule se hota hai (marker -> judge line -> none)
  2. Ligature repair ka bug fix (plaintiff no -> plaintiffno nahi banega)
  3. 40 characters se chhote kachra chunks hata diye

Chalao (project ke root folder se):
    python src/chunk_corpus.py
"""
import glob
import json
import os
import random
import re
from collections import Counter, defaultdict

FILES = sorted(glob.glob("data/processed/civil_*.jsonl"))
OUT = "data/processed/chunks.jsonl"

MAX_CHARS = 1500   # ek chunk ki lambai (~350 tokens)
MIN_CHARS = 300    # isse chhota aakhri chunk pichhle me merge hoga
DROP_BELOW = 40    # isse chhota chunk hata do

random.seed(5)

# ======================================================================
# STEP 1: vocabulary banao (ligature repair ke liye)
# Corpus me har word kitni baar aaya, ye ginte hain. Jod ke bana word
# agar corpus me kam se kam 5 baar mil chuka hai, tabhi jodenge.
# ======================================================================
word_re = re.compile(r"[A-Za-z]+")
vocab = Counter()
for fp in FILES:
    for line in open(fp, encoding="utf-8"):
        vocab.update(w.lower() for w in word_re.findall(json.loads(line)["text"]))
print("vocab size:", len(vocab))

# PDF se "specific" kabhi "specifi c" ban jata hai (ligature "fi" ke baad extra space)
LIG = re.compile(r"\b([A-Za-z]*(?:fi|ff|ffi|fl|ffl))[ \t]+([a-z]+)\b")
SUFFIXES = {"s", "es", "ed", "ing"}   # "Plaintiff s" -> "Plaintiffs" sahi hai
repaired = Counter()


def repair(text):
    def f(m):
        g1, g2 = m.group(1), m.group(2)
        joined = (g1 + g2).lower()
        # joda hua word corpus me kam se kam 5 baar nahi mila to mat jodo
        if vocab.get(joined, 0) < 5:
            return m.group(0)
        # FIX: agar pehla hissa khud poora word hai (jaise "plaintiff"),
        # to sirf suffix (s, es, ed, ing) hi jodo, "no", "and" jaise words nahi
        g1_is_real_word = len(g1) >= 4 and vocab.get(g1.lower(), 0) >= 300
        if g1_is_real_word and g2.lower() not in SUFFIXES:
            return m.group(0)
        repaired[joined] += 1
        return g1 + g2

    return LIG.sub(f, text)


# ======================================================================
# STEP 2: headnote aur judgment alag karo (3 rule)
#   rule 1: "Judgment" / "Order" / "O R D E R" wali alag line
#   rule 2: judge ke naam wali bina-bracket line, jaise "M. R. SHAH, J."
#           (bench wali line bracket me hoti hai: "[M. R. SHAH, J.]", isliye alag pehchan hoti hai)
#   rule 3: dono nahi mile -> split nahi karenge, "unsplit" label
# ======================================================================
MARKER = re.compile(
    r"^(?:J\s*U\s*D\s*G\s*M\s*E\s*N\s*T|O\s*R\s*D\s*E\s*R)\s*:?\s*$", re.I
)
JUDGE_LINE = re.compile(r"^[A-Z][A-Z.'\-\s]{3,60},\s*JJ?\.?\s*:?$")


def split_sections(text):
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if MARKER.match(ln.strip()):
            return lines[:i], lines[i + 1:], "marker"
    pos = 0
    for i, ln in enumerate(lines):
        # pos > 200: bilkul shuru ki header lines ko chhod do
        if pos > 200 and JUDGE_LINE.match(ln.strip()):
            return lines[:i], lines[i:], "judge_line"
        pos += len(ln) + 1
    return [], lines, "none"


# ======================================================================
# STEP 3: paragraphs banao, phir ~1500 character ke chunks
# Numbered paragraph ("12. The ...") ki boundary pe todte hain.
# ======================================================================
PARA_START = re.compile(r"^\d{1,3}\.\s+[A-Z\"\u201c\u2018(]")
END_PUNCT = re.compile(r"[.?!:;\"\u201d\u2019)]$")
NUM = re.compile(r"^(\d{1,3})\.\s")


def paragraphs(lines):
    paras, cur = [], []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if cur and PARA_START.match(s) and END_PUNCT.search(cur[-1]):
            paras.append(" ".join(cur))
            cur = [s]
        else:
            cur.append(s)
    if cur:
        paras.append(" ".join(cur))
    return [re.sub(r"\s+", " ", p).strip() for p in paras if p.strip()]


def split_long(p):
    """Bahut lamba paragraph ho to sentence boundary pe todo."""
    parts = re.split(r"(?<=[.;:])\s+(?=[A-Z(\"\u201c])", p)
    out, cur = [], ""
    for s in parts:
        if cur and len(cur) + len(s) + 1 > MAX_CHARS:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    final = []
    for o in out:
        while len(o) > int(MAX_CHARS * 1.5):
            final.append(o[:MAX_CHARS])
            o = o[MAX_CHARS:]
        final.append(o)
    return final


def make_chunks(paras):
    pieces = []
    for p in paras:
        m = NUM.match(p)
        num = int(m.group(1)) if m else None
        sub = [p] if len(p) <= MAX_CHARS else split_long(p)
        for j, s in enumerate(sub):
            pieces.append((s, num if j == 0 else None))

    chunks, cur, nums = [], "", []

    def flush():
        nonlocal cur, nums
        if cur:
            chunks.append({
                "text": cur,
                "para_from": nums[0] if nums else None,
                "para_to": nums[-1] if nums else None,
            })
        cur, nums = "", []

    for s, num in pieces:
        if cur and len(cur) + len(s) + 1 > MAX_CHARS:
            flush()
        cur = (cur + " " + s).strip()
        if num is not None:
            nums.append(num)
    flush()

    # aakhri chunk bahut chhota ho to pichhle me jod do
    if len(chunks) >= 2 and len(chunks[-1]["text"]) < MIN_CHARS:
        last = chunks.pop()
        chunks[-1]["text"] += " " + last["text"]
        if last["para_to"] is not None:
            chunks[-1]["para_to"] = last["para_to"]
            if chunks[-1]["para_from"] is None:
                chunks[-1]["para_from"] = last["para_from"]
    return chunks


# ======================================================================
# STEP 4: main loop: har judgment -> repair -> split -> chunks -> file
# ======================================================================
n_docs = n_chunks = n_dropped = plaintiffno = 0
seen_files = set()              # ek hi PDF do baar aaye to skip karo
dup_docs = []                   # skip hue duplicate docs (report ke liye)
case_files = defaultdict(list)  # case_id -> kaunsi PDF files isse judi hain
methods = Counter()
sec_counts = Counter()
lens = []
judge_examples, unsplit_examples = [], []

with open(OUT, "w", encoding="utf-8") as fout:
    for fp in FILES:
        for line in open(fp, encoding="utf-8"):
            r = json.loads(line)
            if r["file"] in seen_files:
                dup_docs.append((r["file"], r["title"]))
                continue
            seen_files.add(r["file"])
            case_files[r["case_id"]].append(r["file"])
            n_docs += 1
            text = repair(r["text"])
            head, body, method = split_sections(text)
            methods[method] += 1

            if method == "judge_line" and len(judge_examples) < 60:
                judge_examples.append((r["title"], head[-3:], body[:3]))
            if method == "none" and len(unsplit_examples) < 60:
                unsplit_examples.append((r["title"], text[:300]))

            sections = [("headnote", head), ("judgment" if method != "none" else "unsplit", body)]
            k = 0
            for section, lines in sections:
                if not lines:
                    continue
                for c in make_chunks(paragraphs(lines)):
                    if len(c["text"]) < DROP_BELOW:
                        n_dropped += 1
                        continue
                    k += 1
                    rec = {
                        # FIX: PDF ka filename unique hota hai, case_id nahi (do judgments ka case_id same ho sakta hai)
                        "chunk_id": f"{os.path.splitext(r['file'])[0]}::{k:04d}",
                        "case_id": r["case_id"], "file": r["file"], "year": r["year"],
                        "title": r["title"], "citation": r["citation"],
                        "decision_date": r["decision_date"],
                        "section": section, "split_method": method,
                        "para_from": c["para_from"], "para_to": c["para_to"],
                        "text": c["text"],
                    }
                    fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n_chunks += 1
                    lens.append(len(c["text"]))
                    sec_counts[section] += 1
                    plaintiffno += c["text"].lower().count("plaintiffno")

# ======================================================================
# STEP 5: report
# ======================================================================
lens.sort()
print("\n===== STATS =====")
print("docs:", n_docs, "| chunks:", n_chunks, "| avg chunks/doc:", round(n_chunks / n_docs, 1))
print("split method:", dict(methods))
print("sections:", dict(sec_counts))
print("dropped tiny chunks (<%d chars):" % DROP_BELOW, n_dropped)
print("chunk chars min/median/p95/max:", lens[0], lens[len(lens) // 2],
      lens[int(len(lens) * 0.95)], lens[-1])
print("ligature repairs:", sum(repaired.values()), "| top:", repaired.most_common(10))
print("'plaintiffno' abhi bhi kitni baar:", plaintiffno)
print("saved:", OUT, round(os.path.getsize(OUT) / 1e6, 1), "MB")

# ---- duplicate check (citation verifier ke liye zaroori) ----
print("\nduplicate PDF files skipped:", len(dup_docs), dup_docs[:3])
shared = {cid: fs for cid, fs in case_files.items() if len(fs) > 1}
print("case_id jo ek se zyada PDF me hai:", len(shared))
for cid, fs in list(shared.items())[:5]:
    print("  ", cid, "->", fs)

print("\n===== judge_line split: 3 examples (headnote ka end | judgment ka start) =====")
for title, h, b in random.sample(judge_examples, min(3, len(judge_examples))):
    print(f"\n--- {(title or '')[:70]} ---")
    for ln in h:
        print("  HEAD |", ln[:100])
    print("  ------- split here -------")
    for ln in b:
        print("  BODY |", ln[:100])

print("\n===== UNSPLIT: 4 examples (pehle 300 characters) =====")
for title, snippet in random.sample(unsplit_examples, min(4, len(unsplit_examples))):
    print(f"\n--- {(title or '')[:70]} ---")
    print("  ", re.sub(r"\s+", " ", snippet))
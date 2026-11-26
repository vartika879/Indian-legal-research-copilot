
import argparse
import datetime
import json
import os
import re
import shutil
from collections import OrderedDict, defaultdict

DB_DIR = "data/chroma"
COLLECTION = "civil_chunks_bge_small"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
CHUNKS = "data/processed/chunks.jsonl"
N_VECTOR = 8     # vector se kitne alag cases dikhane hain
N_KEYWORD = 6    # keyword se kitne alag cases dikhane hain


def snip(text, n=260):
    return re.sub(r"\s+", " ", text)[:n]


def load_questions(path):
    qs = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|", 3)]
        if len(parts) != 4:
            print("  (kharab line skip ki):", line[:60])
            continue
        qs.append(dict(zip(("id", "type", "sub_area", "question"), parts)))
    return qs


def done_ids(path):
    if not os.path.exists(path):
        return set()
    return {json.loads(l)["id"] for l in open(path, encoding="utf-8") if l.strip()}


def drop_ids(path, ids):
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
                f.write(l if l.endswith("\n") else l + "\n")
    return removed


def case_view(c, snippet, via):
    return {
        "file": c["file"], "case_id": c.get("case_id") or "", "citation": c.get("citation") or "",
        "title": c.get("title") or "", "year": c.get("year"), "snippet": snip(snippet), "via": via,
    }


def vector_candidates(model, col, question, n):
    """Top chunks lo, phir ek case ka sirf sabse achha chunk rakho."""
    qvec = model.encode([QUERY_PREFIX + question], normalize_embeddings=True).tolist()
    res = col.query(query_embeddings=qvec, n_results=60)
    seen = OrderedDict()
    for i in range(len(res["ids"][0])):
        m = res["metadatas"][0][i]
        if m["file"] in seen:
            continue
        seen[m["file"]] = case_view(m, res["documents"][0][i], "V")
        if len(seen) >= n:
            break
    return list(seen.values())


def keyword_candidates(chunks, keywords, exclude_files, n):
    """Wo cases jinke chunks me SAARE keywords hain. Jisme zyada chunks match hon wo upar."""
    kws = [k.strip().lower() for k in keywords if k.strip()]
    if not kws:
        return []
    hits = defaultdict(lambda: {"count": 0, "chunk": None})
    for c in chunks:
        t = c["text"].lower()
        if all(k in t for k in kws):
            h = hits[c["file"]]
            h["count"] += 1
            if h["chunk"] is None:
                h["chunk"] = c
    ranked = sorted(hits.values(), key=lambda h: -h["count"])
    out = []
    for h in ranked:
        c = h["chunk"]
        if c["file"] in exclude_files:
            continue
        out.append(case_view(c, c["text"], f"K:{h['count']} chunks"))
        if len(out) >= n:
            break
    return out


def show(cands):
    for i, c in enumerate(cands, 1):
        print(f"[{i}] ({c['via']}) {c['title'][:75]} | {c['case_id'] or 'no-case-id'} | {c['year']}")
        print("      " + c["snippet"] + " ...")


def ask_relevant(vec, chunks, question):
    """Return (relevant_list, answerable). None return = skip question."""
    kw_all = []          # keyword candidates, har "k" round ke baad badhte jaate hain (replace nahi hote)
    cands = list(vec)
    while True:
        print()
        show(cands)
        ans = input("\nRelevant numbers (jaise: 1 3 4) | k = keyword candidates | none = corpus me jawab nahi | s = skip | q = quit : ").strip().lower()
        if ans == "q":
            raise SystemExit("Band kar raha hu. Jo ho chuka wo save hai.")
        if ans == "s":
            return None
        if ans == "none":
            return [], False
        if ans == "k":
            kws = input("Keywords (comma se alag, SAARE chunk me hone chahiye): ").split(",")
            already = {c["file"] for c in vec} | {c["file"] for c in kw_all}
            new = keyword_candidates(chunks, kws, already, N_KEYWORD)
            if not new:
                print("  Koi naya match nahi mila.")
            kw_all = kw_all + new            # purane numbers wahi rahenge, naye neeche jud jaayenge
            cands = list(vec) + kw_all
            continue
        nums = [int(x) for x in re.findall(r"\d+", ans)]
        if nums and all(1 <= x <= len(cands) for x in nums):
            chosen = OrderedDict()
            for x in nums:
                chosen[cands[x - 1]["file"]] = cands[x - 1]
            return list(chosen.values()), True
        print("  Samajh nahi aaya, dobara likho.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="eval/questions_draft.txt")
    ap.add_argument("--golden", default="eval/golden_set.jsonl")
    ap.add_argument("--redo", default="", help="in sawaalon ko dobara karo, jaise: --redo Q01,Q07")
    args = ap.parse_args()

    # heavy imports yahan, taaki upar ke functions bina inke bhi test ho sakein
    import chromadb
    from sentence_transformers import SentenceTransformer

    os.makedirs(os.path.dirname(args.golden), exist_ok=True)
    if args.redo:
        ids = {x.strip().upper() for x in args.redo.split(",") if x.strip()}
        n = drop_ids(args.golden, ids)
        print(f"Redo: {n} purani entry hata di (backup: {args.golden}.bak)")
    questions = load_questions(args.questions)
    finished = done_ids(args.golden)
    todo = [q for q in questions if q["id"] not in finished]
    print(f"Total sawaal: {len(questions)} | ho chuke: {len(finished)} | baaki: {len(todo)}")
    if not todo:
        print("Sab ho chuka.")
        return

    print("Loading model aur chunks ...")
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    col = chromadb.PersistentClient(path=DB_DIR).get_collection(COLLECTION)
    chunks = [json.loads(l) for l in open(CHUNKS, encoding="utf-8")]

    for n, q in enumerate(todo, 1):
        print("\n" + "=" * 100)
        print(f"[{n}/{len(todo)}] {q['id']} | {q['type']} | {q['sub_area']}")
        print("Q:", q["question"])

        if q["type"] == "out_of_scope":
            print("Ye out_of_scope sawaal hai: tool ko iska jawab nahi dena chahiye. Auto-save kar raha hu.")
            relevant, answerable = [], False
        else:
            res = ask_relevant(vector_candidates(model, col, q["question"], N_VECTOR), chunks, q["question"])
            if res is None:
                print("Skip kiya.")
                continue
            relevant, answerable = res

        statutes = "" if not answerable else input("Expected Act/section (optional, jaise 'Limitation Act 1963, Art. 54'): ").strip()
        notes = input("Notes (optional): ").strip()

        rec = {
            "id": q["id"], "question": q["question"], "type": q["type"], "sub_area": q["sub_area"],
            "answerable": answerable,
            "relevant_cases": [
                {k: c[k] for k in ("file", "case_id", "citation", "title", "year")} for c in relevant
            ],
            "expected_statutes": statutes,
            "notes": notes,
            "status": "unvalidated",
            "labeled_by": "self",
            "labeled_on": datetime.date.today().isoformat(),
        }
        with open(args.golden, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"Saved {q['id']} ({len(relevant)} relevant case).")

    print("\nSab sawaal ho gaye. File:", args.golden)


if __name__ == "__main__":
    main()
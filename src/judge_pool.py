
import argparse
import datetime
import json
import os
import re
import shutil
from collections import OrderedDict

GOLDEN = "eval/golden_set.jsonl"
CHUNKS = "data/processed/chunks.jsonl"


def case_ranking(hits):
    """Chunk hits -> alag cases (har case ka pehla/sabse achha chunk)."""
    seen = OrderedDict()
    for h in hits:
        seen.setdefault(h["file"], h)
    return list(seen.values())


def pool_candidates(results_by_system, relevant_files, top_n):
    """
    results_by_system: {system_name: chunk hits}. Har system ke top_n cases lo, jo abhi labeled nahi hain.
    Return: candidates ki list. Har ek: file, title, case_id, chunk_ids (snippet ke liye, max 2),
    found_by {system: rank}. Jo cases zyada systems ne diye aur jo upar the, wo pehle.
    """
    pool = OrderedDict()
    for system, hits in results_by_system.items():
        for rank, h in enumerate(case_ranking(hits)[:top_n], 1):
            if not h["file"] or h["file"] in relevant_files:
                continue
            c = pool.setdefault(h["file"], {"file": h["file"], "title": h["title"], "case_id": h["case_id"],
                                            "chunk_ids": [], "found_by": {}})
            c["found_by"][system] = rank
            if h.get("chunk_id") and h["chunk_id"] not in c["chunk_ids"] and len(c["chunk_ids"]) < 2:
                c["chunk_ids"].append(h["chunk_id"])
    out = list(pool.values())
    out.sort(key=lambda c: (min(c["found_by"].values()), -len(c["found_by"])))
    return out


def snip(text, n=300):
    return re.sub(r"\s+", " ", text)[:n]


def save_rows(path, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def run_session(rows, systems, chunk_info, top_n, golden_path):
    """
    rows: golden records. systems: {name: object with .retrieve(question)}.
    chunk_info: {chunk_id: {"text","citation","year"}}.
    """
    todo = [r for r in rows if r.get("answerable") and r.get("relevant_cases") and not r.get("pool_judged")]
    print(f"Sawaal baaki: {len(todo)} (total answerable: {sum(1 for r in rows if r.get('answerable'))})")
    for n, r in enumerate(todo, 1):
        rel = {c["file"] for c in r["relevant_cases"]}
        results = {name: s.retrieve(r["question"]) for name, s in systems.items()}
        cands = pool_candidates(results, rel, top_n)

        print("\n" + "=" * 100)
        print(f"[{n}/{len(todo)}] {r['id']} | {r['sub_area']}")
        print("Q:", r["question"])
        print(f"(abhi labeled: {len(rel)} cases)")

        if not cands:
            print("Is sawaal me koi unlabeled case top me nahi aaya. Aage badho.")
            r["pool_judged"] = True
            save_rows(golden_path, rows)
            continue

        for i, c in enumerate(cands, 1):
            found = ", ".join(f"{s}#{rk}" for s, rk in c["found_by"].items())
            print(f"\n[{i}] {c['title'][:80]} | {c['case_id'] or 'no-case-id'}")
            print(f"     mila: {found}")
            for cid in c["chunk_ids"]:
                info = chunk_info.get(cid)
                if info:
                    print("     > " + snip(info["text"]) + " ...")

        while True:
            ans = input("\nRelevant numbers (jaise: 1 3) | Enter = koi nahi | s = skip | q = quit : ").strip().lower()
            if ans == "q":
                raise SystemExit("Band kar raha hu. Jo ho chuka wo save hai.")
            if ans == "s":
                chosen = None
                break
            nums = [int(x) for x in re.findall(r"\d+", ans)]
            if ans == "" or (nums and all(1 <= x <= len(cands) for x in nums)):
                chosen = [cands[x - 1] for x in OrderedDict.fromkeys(nums)]
                break
            print("  Samajh nahi aaya, dobara likho.")

        if chosen is None:
            print("Skip kiya (ye sawaal baad me dobara aayega).")
            continue

        for c in chosen:
            info = chunk_info.get(c["chunk_ids"][0], {}) if c["chunk_ids"] else {}
            r["relevant_cases"].append({"file": c["file"], "case_id": c["case_id"],
                                        "citation": info.get("citation", ""), "title": c["title"],
                                        "year": info.get("year"), "added_by": "pooled_judging"})
        r["pool_judged"] = True
        r["pooled_from"] = sorted(systems)
        r["pooled_top_n"] = top_n
        r["pooled_added"] = len(chosen)
        r["pooled_on"] = datetime.date.today().isoformat()
        save_rows(golden_path, rows)
        print(f"Saved {r['id']}: {len(chosen)} naye relevant case jude.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", default=GOLDEN)
    ap.add_argument("--top-n", type=int, default=5)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.golden, encoding="utf-8") if l.strip()]
    bak = args.golden + ".pool.bak"
    if not os.path.exists(bak):
        shutil.copyfile(args.golden, bak)

    print("Loading chunks aur systems (1 se 2 minute) ...")
    chunk_info = {}
    for line in open(CHUNKS, encoding="utf-8"):
        c = json.loads(line)
        chunk_info[c["chunk_id"]] = {"text": c["text"], "citation": c.get("citation") or "", "year": c.get("year")}

    import run_eval as re_
    dense = re_.DenseWithIds()
    sparse = re_.BM25System()
    systems = {"naive": dense, "bm25": sparse, "hybrid": re_.Hybrid(dense=dense, sparse=sparse)}
    run_session(rows, systems, chunk_info, args.top_n, args.golden)
    print("\nSab sawaal ho gaye. Ab teeno systems dobara naapo (run_eval.py).")


if __name__ == "__main__":
    main()

import argparse
import csv
import datetime
import json
import os
import random
import statistics
from collections import Counter, OrderedDict

GOLDEN = "eval/golden_set.jsonl"
OUT_DIR = "eval/results"
KS = (1, 3, 5, 10)
N_CHUNKS = 60            # kitne top chunks lekar unse cases banate hain

DB_DIR = "data/chroma"
COLLECTION = "civil_chunks_bge_small"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


# ======================================================================
# Retrieval systems. Har system ka ek hi kaam: retrieve(question) -> chunk hits
# (best pehle). Har hit: {"file", "title", "case_id", "score"}
# ======================================================================
class NaiveVector:
    """Baseline: sirf embedding search (bge-small + Chroma), koi keyword, koi reranker nahi."""
    name = "naive_vector_bge_small"

    def __init__(self):
        import chromadb
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(MODEL_NAME, device="cpu")
        self.col = chromadb.PersistentClient(path=DB_DIR).get_collection(COLLECTION)

    def retrieve(self, question):
        qvec = self.model.encode([QUERY_PREFIX + question], normalize_embeddings=True).tolist()
        res = self.col.query(query_embeddings=qvec, n_results=N_CHUNKS)
        hits = []
        for i in range(len(res["ids"][0])):
            m = res["metadatas"][0][i]
            hits.append({"file": m["file"], "title": m["title"], "case_id": m["case_id"],
                         "score": 1 - res["distances"][0][i]})
        return hits


SYSTEMS = {"naive": NaiveVector}


# ======================================================================
# Metrics
# ======================================================================
def rank_cases(hits):
    """Chunk hits -> alag alag cases ki list (har case ka pehla/sabse achha chunk rakhte hain)."""
    seen = OrderedDict()
    for h in hits:
        seen.setdefault(h["file"], h)
    return list(seen.values())


def evaluate(rel_files, hits):
    files = [c["file"] for c in rank_cases(hits)]
    first = next((i + 1 for i, f in enumerate(files) if f in rel_files), None)
    out = {f"hit@{k}": int(any(f in rel_files for f in files[:k])) for k in KS}
    out["recall@10"] = len(rel_files & set(files[:10])) / len(rel_files)
    out["rr"] = 1 / first if first else 0.0
    out["first_rank"] = first
    out["distinct@5"] = len({h["file"] for h in hits[:5]})
    out["missed@10"] = sorted(rel_files - set(files[:10]))
    return out


def bootstrap_ci(values, n=2000, seed=0):
    """Chhote sample ka bharosa: sawaalon ko baar baar resample karke 95% range."""
    rng = random.Random(seed)
    means = sorted(
        sum(values[rng.randrange(len(values))] for _ in values) / len(values) for _ in range(n)
    )
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


# ======================================================================
# Main
# ======================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", default="naive", choices=sorted(SYSTEMS))
    ap.add_argument("--golden", default=GOLDEN)
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.golden, encoding="utf-8") if l.strip()]
    scored = [r for r in rows if r.get("answerable") and r.get("relevant_cases")]
    abstain = [r for r in rows if not r.get("answerable")]
    if not scored:
        raise SystemExit("Golden set me koi answerable sawaal nahi mila.")
    status = Counter(r.get("status", "?") for r in rows)

    print("Loading system ...")
    system = SYSTEMS[args.system]()

    # ---------- har sawaal ----------
    per_q = []
    print(f"\n{'ID':<5} {'1st rank':>8} {'hit@5':>6} {'recall@10':>10} {'distinct@5':>11}")
    for r in scored:
        rel = {c["file"] for c in r["relevant_cases"]}
        titles = {c["file"]: c["title"] for c in r["relevant_cases"]}
        hits = system.retrieve(r["question"])
        m = evaluate(rel, hits)
        m.update({"id": r["id"], "n_relevant": len(rel), "top1_sim": hits[0]["score"],
                  "missed_titles": [titles[f] for f in m["missed@10"]]})
        per_q.append(m)
        fr = m["first_rank"] if m["first_rank"] else "-"
        print(f"{r['id']:<5} {fr!s:>8} {m['hit@5']:>6} {m['recall@10']:>10.2f} {m['distinct@5']:>11}")
        for t in m["missed_titles"]:
            print(f"        miss@10: {t[:80]}")

    # ---------- summary ----------
    def mean(key):
        return statistics.mean(q[key] for q in per_q)

    summary = {f"hit@{k}": mean(f"hit@{k}") for k in KS}
    summary["recall@10"] = mean("recall@10")
    summary["mrr"] = mean("rr")
    summary["distinct@5"] = mean("distinct@5")
    ci = {
        "hit@5": bootstrap_ci([q["hit@5"] for q in per_q]),
        "recall@10": bootstrap_ci([q["recall@10"] for q in per_q]),
        "mrr": bootstrap_ci([q["rr"] for q in per_q]),
    }

    print(f"\n===== {system.name} | {len(per_q)} sawaal =====")
    for k in KS:
        extra = f"   95% range [{ci['hit@5'][0]:.2f}, {ci['hit@5'][1]:.2f}]" if k == 5 else ""
        print(f"Hit@{k:<2}      {summary[f'hit@{k}']:.2f}{extra}")
    print(f"MRR         {summary['mrr']:.2f}   95% range [{ci['mrr'][0]:.2f}, {ci['mrr'][1]:.2f}]")
    print(f"Recall@10   {summary['recall@10']:.2f}   95% range [{ci['recall@10'][0]:.2f}, {ci['recall@10'][1]:.2f}]")
    print(f"distinct@5  {summary['distinct@5']:.2f}  (top 5 chunks me alag cases; 5.0 = sab alag)")

    # ---------- out-of-scope sawaal (abstain) ----------
    abstain_sims = []
    if abstain:
        print("\nOut-of-scope / jawab-nahi wale sawaal (retrieval kuch na kuch laata hi hai; dekho similarity kitni):")
        for r in abstain:
            s = system.retrieve(r["question"])[0]["score"]
            abstain_sims.append(s)
            print(f"  {r['id']}: top1 sim = {s:.3f} | {r['question'][:70]}")
        print(f"  in-scope sawaalon ka mean top1 sim = {mean('top1_sim'):.3f} (compare karo)")

    # ---------- save ----------
    os.makedirs(args.out_dir, exist_ok=True)
    today = datetime.date.today().isoformat()
    result = {
        "system": system.name, "date": today, "n_scored": len(per_q), "n_abstain": len(abstain),
        "golden_status": dict(status), "summary": summary,
        "ci95": {k: list(v) for k, v in ci.items()},
        "abstain_top1_sims": abstain_sims, "per_question": per_q,
    }
    json_path = os.path.join(args.out_dir, f"{system.name}.json")
    json.dump(result, open(json_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    csv_path = os.path.join(args.out_dir, "summary.csv")
    new = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "system", "n_scored", "n_abstain", "hit@1", "hit@3", "hit@5",
                        "hit@10", "recall@10", "mrr", "distinct@5", "unvalidated_labels"])
        w.writerow([today, system.name, len(per_q), len(abstain)] +
                   [round(summary[k], 3) for k in ("hit@1", "hit@3", "hit@5", "hit@10", "recall@10", "mrr", "distinct@5")] +
                   [status.get("unvalidated", 0)])

    print(f"\nSaved: {json_path}\n       {csv_path}")
    print("\nREADME ke liye table row:")
    print("| System | Sawaal | Hit@5 | MRR | Recall@10 | distinct@5 |")
    print("|---|---|---|---|---|---|")
    print(f"| {system.name} | {len(per_q)} | {summary['hit@5']:.2f} | {summary['mrr']:.2f} | "
          f"{summary['recall@10']:.2f} | {summary['distinct@5']:.1f} |")
    print(f"\nNOTE: golden set ke {status.get('unvalidated', 0)} entries unvalidated hain (lawyer ne check nahi kiye).")
    print("NOTE: labels isi retriever ke top-8 aur keyword hits se chune gaye the, to ye baseline thoda OPTIMISTIC hai.")


if __name__ == "__main__":
    main()
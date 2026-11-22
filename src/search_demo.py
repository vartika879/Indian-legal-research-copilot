"""

Kaam: ek sawaal (query) pucho, aur Chroma DB se sabse relevant chunks dekho.
Ye humara pehla "naive retrieval" hai (sirf embedding search, koi reranker nahi).

Chalao (project ke root folder se):
    python src/search_demo.py "limitation period for suit for specific performance"
    python src/search_demo.py "adverse possession against government land" -k 8
    python src/search_demo.py "tenant eviction bona fide need" --section judgment
"""
import argparse
import re

import chromadb
from sentence_transformers import SentenceTransformer

DB_DIR = "data/chroma"
COLLECTION = "civil_chunks_bge_small"
MODEL_NAME = "BAAI/bge-small-en-v1.5"

# BGE model ko sawaal ke aage ye instruction lagana padta hai (chunks ke aage nahi)
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5, help="kitne results chahiye")
    ap.add_argument("--section", choices=["headnote", "judgment", "unsplit"], default=None)
    args = ap.parse_args()

    model = SentenceTransformer(MODEL_NAME, device="cpu")
    col = chromadb.PersistentClient(path=DB_DIR).get_collection(COLLECTION)

    # sawaal ko bhi vector banao, phir DB se sabse paas wale chunks nikalo
    qvec = model.encode([QUERY_PREFIX + args.query], normalize_embeddings=True).tolist()
    where = {"section": args.section} if args.section else None
    res = col.query(query_embeddings=qvec, n_results=args.k, where=where)

    print(f"\nQuery: {args.query}\n")
    for i in range(len(res["ids"][0])):
        m = res["metadatas"][0][i]
        sim = 1 - res["distances"][0][i]   # cosine distance -> similarity
        paras = f"paras {m['para_from']}-{m['para_to']}" if m["para_from"] != -1 else "paras n/a"
        print(f"[{i + 1}] sim={sim:.3f} | {m['title'][:70]}")
        print(f"    {m['case_id']} | {m['citation']} | {m['year']} | {m['section']} | {paras}")
        print("    " + re.sub(r"\s+", " ", res["documents"][0][i])[:320] + " ...\n")


if __name__ == "__main__":
    main()
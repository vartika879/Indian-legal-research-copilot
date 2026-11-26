
import argparse
import json
import os
import pickle
import time
from collections import OrderedDict

import numpy as np
from sklearn.feature_extraction.text import CountVectorizer

CHUNKS = "data/processed/chunks.jsonl"
INDEX_PATH = "data/bm25_index.pkl"
K1, B = 1.5, 0.75   # BM25 ke standard parameters

# Chhoti stopword list. sklearn ki standard list me "part" jaise shabd hain jo legal sawaalon
# me zaroori hain ("plaint in part"), isliye apni list.
STOP = [
    "the", "a", "an", "of", "to", "in", "on", "and", "or", "is", "are", "was", "were", "be", "by",
    "for", "with", "as", "at", "that", "this", "it", "its", "from", "under", "what", "when", "which",
    "who", "how", "can", "does", "do", "did", "if", "any", "there", "their", "his", "her", "has", "have",
]


class BM25Index:
    def __init__(self, vec, weights, meta):
        self.vec = vec          # CountVectorizer (shabd -> column)
        self.W = weights        # sparse matrix: har chunk x shabd ka BM25 weight (pehle se nikala hua)
        self.meta = meta        # har chunk ka {chunk_id, file, title, case_id}

    # ---------------- build ----------------
    @classmethod
    def build(cls, chunks_path=CHUNKS, k1=K1, b=B):
        texts, meta = [], []
        for line in open(chunks_path, encoding="utf-8"):
            c = json.loads(line)
            texts.append(c["text"])
            meta.append({"chunk_id": c["chunk_id"], "file": c["file"],
                         "title": c.get("title") or "", "case_id": c.get("case_id") or ""})

        vec = CountVectorizer(lowercase=True, token_pattern=r"(?u)\b[a-z0-9]{2,}\b",
                              stop_words=STOP, dtype=np.float32)
        X = vec.fit_transform(texts).tocsr()          # chunks x shabd, tf (kitni baar aaya)
        n_docs, n_terms = X.shape

        dl = np.asarray(X.sum(axis=1)).ravel()        # har chunk me kitne shabd
        avgdl = dl.mean()
        df = np.bincount(X.indices, minlength=n_terms)  # har shabd kitne chunks me hai
        idf = np.log(1 + (n_docs - df + 0.5) / (df + 0.5)).astype(np.float32)

        rows = np.repeat(np.arange(n_docs), np.diff(X.indptr))   # har non-zero entry ka chunk number
        tf = X.data
        denom = tf + k1 * (1 - b + b * dl[rows] / avgdl)
        W = X.copy()
        W.data = (idf[X.indices] * tf * (k1 + 1) / denom).astype(np.float32)
        return cls(vec, W, meta)

    # ---------------- save / load ----------------
    def save(self, path=INDEX_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"vec": self.vec, "W": self.W, "meta": self.meta}, f, protocol=4)

    @classmethod
    def load(cls, path=INDEX_PATH):
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"BM25 index nahi mila ({path}). Pehle ye chalao:  python src/bm25_index.py")
        d = pickle.load(open(path, "rb"))
        return cls(d["vec"], d["W"], d["meta"])

    # ---------------- search ----------------
    def search(self, query, k=60):
        """Top k chunks (row number, score), best pehle. Score 0 wale chunks nahi aate."""
        q = self.vec.transform([query])
        if q.nnz == 0:
            return []
        q.data[:] = 1.0                                   # query ke har shabd ko ek baar ginte hain
        scores = (self.W @ q.T).toarray().ravel()
        k = min(k, len(scores))
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [(int(i), float(scores[i])) for i in top if scores[i] > 0]

    def hits(self, query, k=60):
        """search() ka result, har hit ke saath chunk_id, file, title, case_id."""
        out = []
        for i, s in self.search(query, k):
            m = self.meta[i]
            out.append({"chunk_id": m["chunk_id"], "file": m["file"], "title": m["title"],
                        "case_id": m["case_id"], "score": s})
        return out


def show_top_cases(index, query, n=5):
    print(f"\nQuery: {query}")
    seen = OrderedDict()
    for h in index.hits(query, k=60):
        seen.setdefault(h["file"], h)
    for rank, h in enumerate(list(seen.values())[:n], 1):
        print(f"  [{rank}] score={h['score']:.1f} | {h['title'][:75]} | {h['case_id'] or 'no-case-id'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--query", default=None)
    args = ap.parse_args()

    if args.rebuild or not os.path.exists(INDEX_PATH):
        t0 = time.time()
        print("Index bana raha hu (pehli baar ~1 minute) ...")
        idx = BM25Index.build()
        idx.save()
        print(f"Done: {idx.W.shape[0]} chunks, {idx.W.shape[1]} alag shabd, "
              f"{round(os.path.getsize(INDEX_PATH) / 1e6)} MB, {time.time() - t0:.0f} sec")
    idx = BM25Index.load()

    queries = [args.query] if args.query else [
        "plaint in part",
        "limitation period for suit for specific performance",
        "madhav prasad",
    ]
    for q in queries:
        show_top_cases(idx, q)


if __name__ == "__main__":
    main()
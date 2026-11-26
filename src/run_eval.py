
from collections import defaultdict

import eval_retrieval as e

RRF_K = 60   # RRF ka standard constant

# BM25 ko kuch na mile to eval ke liye placeholder (file "" kisi relevant case se match nahi hota)
NO_HIT = {"chunk_id": "", "file": "", "title": "(koi keyword match nahi)", "case_id": "", "score": 0.0}


def rrf_fuse(rankings, k=RRF_K):
    """
    rankings: list of lists. Har list ek search ke chunk_ids hai (best pehle).
    Har chunk ko har list se 1/(k + rank) milta hai, aur sab jod diye jaate hain.
    Jo chunk dono lists me upar ho, uska score sabse zyada. Return: [(chunk_id, score)], best pehle.
    """
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, 1):
            scores[chunk_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: -kv[1])


class DenseWithIds(e.NaiveVector):
    """Wahi naive vector search, bas har hit ke saath chunk_id bhi deta hai (fusion ke liye zaroori)."""
    name = "dense_bge_small"

    def retrieve(self, question):
        qvec = self.model.encode([e.QUERY_PREFIX + question], normalize_embeddings=True).tolist()
        res = self.col.query(query_embeddings=qvec, n_results=e.N_CHUNKS)
        hits = []
        for i in range(len(res["ids"][0])):
            m = res["metadatas"][0][i]
            hits.append({"chunk_id": res["ids"][0][i], "file": m["file"], "title": m["title"],
                         "case_id": m["case_id"], "score": 1 - res["distances"][0][i]})
        return hits


class BM25System:
    """Sirf keyword search (BM25)."""
    name = "bm25_only"

    def __init__(self):
        from bm25_index import BM25Index
        self.index = BM25Index.load()

    def search_hits(self, question):
        """Asli hits. Sawaal ka koi shabd corpus me na ho to khali list."""
        return self.index.hits(question, k=e.N_CHUNKS)

    def retrieve(self, question):
        # eval_retrieval.py khali list pe toot jaati hai (hits[0] leti hai), isliye ek khali hit
        # dete hain. Iska file "" hai, to ye kisi sahi case se match nahi hota (miss gina jayega).
        return self.search_hits(question) or [NO_HIT]


class Hybrid:
    """Vector + BM25, RRF se mile hue."""
    name = "hybrid_rrf_dense_bm25"

    def __init__(self, dense=None, sparse=None):
        self.dense = dense or DenseWithIds()
        self.sparse = sparse or BM25System()

    def retrieve(self, question):
        d = self.dense.retrieve(question)
        b = self.sparse.search_hits(question)   # asli hits (placeholder nahi)
        info = {h["chunk_id"]: h for h in d + b}
        fused = rrf_fuse([[h["chunk_id"] for h in d], [h["chunk_id"] for h in b]])
        # score = RRF score (similarity nahi hai, isliye "top1 sim" wali line hybrid/bm25 ke liye mat padhna)
        return [dict(info[cid], score=s) for cid, s in fused[: e.N_CHUNKS]]


def main():
    e.SYSTEMS.update({"bm25": BM25System, "hybrid": Hybrid})
    e.main()


if __name__ == "__main__":
    main()
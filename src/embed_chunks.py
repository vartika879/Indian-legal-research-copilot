"""
 data/processed/chunks.jsonl ke har chunk ko embedding (vector) me badalna
      aur local Chroma database (data/chroma) me save karna.

Resumable hai: beech me ruk jaye to dobara chalao, jo chunks ho chuke wo skip honge.

Chalao (project ke root folder se):
    python src/embed_chunks.py --limit 300     # pehle speed test (sirf 300 chunks)
    python src/embed_chunks.py                 # phir poora
"""
import argparse
import json
import time

import chromadb
from sentence_transformers import SentenceTransformer

CHUNKS = "data/processed/chunks.jsonl"
DB_DIR = "data/chroma"
COLLECTION = "civil_chunks_bge_small"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
ENCODE_BATCH = 32   # model ko ek baar me kitne chunks do (8 GB RAM ke liye chhota rakha)
UPSERT_BATCH = 256  # DB me ek baar me kitne likhne hain


def build_metadata(c):
    """Chroma me None allowed nahi hai, isliye khali values ko -1 ya '' bana dete hain."""
    return {
        "case_id": c["case_id"] or "",
        "file": c["file"],
        "title": (c["title"] or "")[:200],
        "citation": c["citation"] or "",
        "year": int(c["year"]),
        "decision_date": c["decision_date"] or "",
        "section": c["section"],
        "para_from": -1 if c["para_from"] is None else c["para_from"],
        "para_to": -1 if c["para_to"] is None else c["para_to"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="sirf pehle N chunks (speed test ke liye)")
    args = ap.parse_args()

    # ---------- Step 1: chunks padho, duplicate ids hatao ----------
    chunks, seen, dupes = [], set(), 0
    for line in open(CHUNKS, encoding="utf-8"):
        c = json.loads(line)
        if c["chunk_id"] in seen:
            dupes += 1
            continue
        seen.add(c["chunk_id"])
        chunks.append(c)
    if args.limit:
        chunks = chunks[: args.limit]
    print(f"chunks loaded: {len(chunks)} (duplicate ids skipped: {dupes})")

    # ---------- Step 2: DB kholo, dekho kya pehle se ho chuka hai ----------
    client = chromadb.PersistentClient(path=DB_DIR)
    col = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    done = set(col.get(include=[])["ids"])
    pending = [c for c in chunks if c["chunk_id"] not in done]
    print(f"already in DB: {len(done)} | to embed now: {len(pending)}")
    if not pending:
        print("Kuch karne ko nahi bacha.")
        return

    # ---------- Step 3: model load (pehli baar ~130 MB download hoga) ----------
    print("loading model:", MODEL_NAME)
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    model.max_seq_length = 512

    # ---------- Step 4: batch me embed karo aur DB me daalo ----------
    t0 = time.time()
    for start in range(0, len(pending), UPSERT_BATCH):
        batch = pending[start: start + UPSERT_BATCH]
        texts = [c["text"] for c in batch]
        # normalize_embeddings=True: cosine similarity ke liye vectors ki lambai 1 kar dete hain
        vecs = model.encode(texts, batch_size=ENCODE_BATCH, normalize_embeddings=True,
                            show_progress_bar=False)
        col.upsert(
            ids=[c["chunk_id"] for c in batch],
            embeddings=vecs.tolist(),
            documents=texts,
            metadatas=[build_metadata(c) for c in batch],
        )
        n_done = start + len(batch)
        elapsed = time.time() - t0
        rate = n_done / elapsed
        eta_min = (len(pending) - n_done) / rate / 60
        print(f"  {n_done}/{len(pending)} chunks | {rate:.1f} chunks/sec | ETA ~{eta_min:.0f} min")

    print(f"\nDone. DB me total chunks: {col.count()} | time: {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
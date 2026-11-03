import boto3, os, json, tarfile
from botocore import UNSIGNED
from botocore.config import Config
import fitz  # pymupdf

s3 = boto3.client("s3", region_name="ap-south-1",
                  config=Config(signature_version=UNSIGNED))
BUCKET = "indian-supreme-court-judgments"
YEAR = 2023
os.makedirs("data/raw", exist_ok=True)

# 1) index.json
idx_key = f"data/tar/year={YEAR}/english/english.index.json"
idx_local = f"data/raw/{YEAR}_english.index.json"
s3.download_file(BUCKET, idx_key, idx_local)
idx = json.load(open(idx_local, encoding="utf-8"))
print("index type:", type(idx).__name__)
if isinstance(idx, dict):
    print("index keys (first 10):", list(idx.keys())[:10])
    for k in list(idx.keys())[:2]:
        print(" ", k, "->", str(idx[k])[:300])
else:
    print("entries:", len(idx))
    print("first entry:", str(idx[0])[:300])

# 2) tar download (progress ke saath)
tar_key = f"data/tar/year={YEAR}/english/english.tar"
tar_local = f"data/raw/{YEAR}_english.tar"
if not os.path.exists(tar_local):
    total = s3.head_object(Bucket=BUCKET, Key=tar_key)["ContentLength"]
    done = {"n": 0, "last": -1}
    def cb(n):
        done["n"] += n
        pct = int(done["n"] * 100 / total)
        if pct != done["last"] and pct % 10 == 0:
            done["last"] = pct
            print(f"  download {pct}%")
    print("\nDownloading tar ...")
    s3.download_file(BUCKET, tar_key, tar_local, Callback=cb)
print("tar size MB:", round(os.path.getsize(tar_local) / 1e6, 1))

# 3) tar ke andar kya hai
members = []
with tarfile.open(tar_local) as tf:
    for m in tf:
        if m.isfile():
            members.append(m.name)
print("files in tar:", len(members))
print("first 5:", members[:5])

# 4) 3 PDFs nikalo aur text padho
os.makedirs("data/raw/sample_pdfs", exist_ok=True)
picked = [n for n in members if n.lower().endswith(".pdf")][:3]
with tarfile.open(tar_local) as tf:
    for name in picked:
        tf.extract(name, "data/raw/sample_pdfs")
        p = os.path.join("data/raw/sample_pdfs", name)
        doc = fitz.open(p)
        text = "\n".join(page.get_text() for page in doc)
        print("\n" + "=" * 60)
        print(name, "| pages:", len(doc), "| chars:", len(text))
        print(text[:700])

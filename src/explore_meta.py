import boto3, os
import pandas as pd
from botocore import UNSIGNED
from botocore.config import Config

s3 = boto3.client("s3", region_name="ap-south-1",
                  config=Config(signature_version=UNSIGNED))
BUCKET = "indian-supreme-court-judgments"


def list_keys(prefix, limit=20):
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, MaxKeys=limit)
    return [(o["Key"], round(o["Size"] / 1e6, 2)) for o in resp.get("Contents", [])]


def list_prefixes(prefix):
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, Delimiter="/")
    return [p["Prefix"] for p in resp.get("CommonPrefixes", [])]


print("== metadata/parquet/ ==")
for p in list_prefixes("metadata/parquet/")[:5]:
    print(" ", p)
pq_keys = list_keys("metadata/parquet/year=2023/")
if not pq_keys:
    pq_keys = list_keys("metadata/parquet/")
for k, mb in pq_keys:
    print(f"  {k}  ({mb} MB)")

print("\n== data/pdf/ ==")
for p in list_prefixes("data/pdf/")[:5]:
    print(" ", p)

# pehli parquet file download karo (chhoti hogi)
target = next((k for k, mb in pq_keys if k.endswith(".parquet") and mb < 50), None)
if target is None:
    print("\nKoi chhoti parquet file nahi mili, upar ka output bhej do.")
else:
    os.makedirs("data/raw", exist_ok=True)
    local = "data/raw/sample_meta.parquet"
    s3.download_file(BUCKET, target, local)
    df = pd.read_parquet(local)
    print(f"\nDownloaded: {target}")
    print("Rows:", len(df))
    print("\nColumns:")
    for c in df.columns:
        print(" ", c, "|", df[c].dtype)
    print("\nPehli 2 rows:")
    with pd.option_context("display.max_colwidth", 80, "display.width", 200):
        print(df.head(2).T)

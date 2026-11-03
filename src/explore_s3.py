import boto3
from botocore import UNSIGNED
from botocore.config import Config

s3 = boto3.client("s3", region_name="ap-south-1",
                  config=Config(signature_version=UNSIGNED))
BUCKET = "indian-supreme-court-judgments"


def list_prefixes(prefix):
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, Delimiter="/")
    return [p["Prefix"] for p in resp.get("CommonPrefixes", [])]


def list_files(prefix, limit=15):
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, MaxKeys=limit)
    return [(o["Key"], round(o["Size"] / 1e6, 2)) for o in resp.get("Contents", [])]


print("== data/ ==")
for p in list_prefixes("data/"):
    print(" ", p)

print("\n== data/tar/ (pehle 5 aur aakhri 5) ==")
years = list_prefixes("data/tar/")
for p in years[:5] + years[-5:]:
    print(" ", p)

print("\n== data/tar/year=2023/ ==")
for p in list_prefixes("data/tar/year=2023/"):
    print(" ", p)
for key, mb in list_files("data/tar/year=2023/"):
    print(f"  {key}  ({mb} MB)")

print("\n== metadata/ ==")
for p in list_prefixes("metadata/"):
    print(" ", p)

print("\n== metadata/ files (sample) ==")
for key, mb in list_files("metadata/", limit=15):
    print(f"  {key}  ({mb} MB)")
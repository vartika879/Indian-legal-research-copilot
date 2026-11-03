import sys, os, re, json, csv, tarfile, unicodedata
import boto3, pandas as pd, pymupdf
from botocore import UNSIGNED
from botocore.config import Config
from civil_filter import classify

BUCKET = "indian-supreme-court-judgments"
s3 = boto3.client("s3", region_name="ap-south-1",
                  config=Config(signature_version=UNSIGNED))
os.makedirs("data/raw", exist_ok=True)
os.makedirs("data/processed", exist_ok=True)

NOISE = [
    re.compile(r"^[A-H]$"),
    re.compile(r"^\d{1,4}$"),
    re.compile(r"^SUPREME COURT REPORTS$"),
    re.compile(r"^\[\d{4}\]\s*\d+\s*S\.C\.R\.(\s*\d+)?(\s*:\s*\d{4}\s*INSC\s*\d+)?$"),
]


def clean(text):
    text = unicodedata.normalize("NFKC", text)
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if any(p.match(s) for p in NOISE):
            continue
        out.append(s)
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def forum_of(head):
    m = re.search(r"\(([^()]{0,80}?(?:Appeal|Petition|Case|Application|Reference)[^()]{0,80})\)", head)
    case_no = m.group(1).strip() if m else None
    low = (case_no or head[:1500]).lower()
    if "criminal" in low:
        forum = "criminal"
    elif "civil" in low:
        forum = "civil_side"
    else:
        forum = "other"
    return case_no, forum


def download(key, local):
    total = s3.head_object(Bucket=BUCKET, Key=key)["ContentLength"]
    st = {"n": 0, "last": -1}

    def cb(n):
        st["n"] += n
        pct = int(st["n"] * 100 / total)
        if pct != st["last"] and pct % 20 == 0:
            st["last"] = pct
            print(f"    download {pct}% of {round(total/1e6)} MB")

    s3.download_file(BUCKET, key, local, Callback=cb)


def process_year(year):
    out = f"data/processed/civil_{year}.jsonl"
    if os.path.exists(out):
        print(f"[{year}] already done, skipping")
        return
    meta_local = f"data/raw/meta_{year}.parquet"
    if not os.path.exists(meta_local):
        s3.download_file(BUCKET, f"metadata/parquet/year={year}/metadata.parquet", meta_local)
    meta = pd.read_parquet(meta_local)
    meta_by_file = {f"{r['path']}_EN.pdf": r for _, r in meta.iterrows()}

    tar_local = f"data/raw/{year}_english.tar"
    if not os.path.exists(tar_local):
        print(f"[{year}] downloading tar ...")
        download(f"data/tar/year={year}/english/english.tar", tar_local)

    total = flagged = errors = no_meta = 0
    tmp = out + ".tmp"
    with tarfile.open(tar_local) as tf, open(tmp, "w", encoding="utf-8") as fout:
        members = [m for m in tf if m.isfile() and m.name.lower().endswith(".pdf")]
        for i, m in enumerate(members, 1):
            total += 1
            try:
                data = tf.extractfile(m).read()
                doc = pymupdf.open(stream=data, filetype="pdf")
                raw = "\n".join(p.get_text() for p in doc)
                doc.close()
            except Exception as e:
                errors += 1
                continue
            text = clean(raw)
            case_no, forum = forum_of(text[:3000])
            c = classify(text, forum)
            if not c["civil_flag"]:
                continue
            row = meta_by_file.get(m.name)
            if row is None:
                no_meta += 1
            flagged += 1
            rec = {
                "file": m.name, "year": year,
                "case_id": None if row is None else row["case_id"],
                "title": None if row is None else row["title"],
                "citation": None if row is None else row["citation"],
                "decision_date": None if row is None else row["decision_date"],
                "disposal_nature": None if row is None else row["disposal_nature"],
                "judge": None if row is None else row["judge"],
                "case_number": case_no, "forum": forum,
                "civil_score": c["score"],
                "civil_terms": c["core"] + c["soft"] + c["weak"],
                "n_chars": len(text), "text": text,
            }
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if i % 200 == 0:
                print(f"    {i}/{len(members)} done, flagged so far: {flagged}")
    os.replace(tmp, out)
    os.remove(tar_local)

    stats_file = "data/processed/year_stats.csv"
    new = not os.path.exists(stats_file)
    with open(stats_file, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["year", "pdfs", "flagged", "rate", "errors", "no_meta"])
        w.writerow([year, total, flagged, round(flagged / max(total, 1), 3), errors, no_meta])
    print(f"[{year}] pdfs={total} flagged={flagged} errors={errors} no_meta={no_meta}")


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:]]
    years = [args[0]] if len(args) == 1 else list(range(args[0], args[1] + 1))
    for y in years:
        try:
            process_year(y)
        except Exception as e:
            print(f"[{y}] FAILED: {e}")

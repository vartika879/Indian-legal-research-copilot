import tarfile, json, re, unicodedata, os
from collections import Counter
import pandas as pd
import pymupdf

YEAR = 2023
TAR = f"data/raw/{YEAR}_english.tar"
META = "data/raw/sample_meta.parquet"
OUT = f"data/processed/{YEAR}.jsonl"
os.makedirs("data/processed", exist_ok=True)

meta = pd.read_parquet(META)
meta_by_file = {f"{r['path']}_EN.pdf": r for _, r in meta.iterrows()}

NOISE = [
    re.compile(r"^[A-H]$"),
    re.compile(r"^\d{1,4}$"),
    re.compile(r"^SUPREME COURT REPORTS$"),
    re.compile(r"^\[\d{4}\]\s*\d+\s*S\.C\.R\.(\s*\d+)?(\s*:\s*\d{4}\s*INSC\s*\d+)?$"),
]

TERMS = {
    "cpc": r"code of civil procedure|c\.p\.c",
    "transfer_of_property": r"transfer of property act",
    "specific_relief": r"specific relief act|specific performance",
    "limitation": r"limitation act|barred by limitation",
    "contract": r"contract act|sale of goods act",
    "easements": r"easement",
    "registration": r"registration act",
    "rent_tenancy": r"rent control|tenant|landlord|eviction|lease",
    "partition_title": r"partition|declaration of title|suit for possession|adverse possession",
    "succession": r"succession act|probate|testamentary",
    "mortgage": r"mortgage|redemption",
}
TERMS_RE = {k: re.compile(v) for k, v in TERMS.items()}


def clean(text):
    text = unicodedata.normalize("NFKC", text)
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if any(p.match(s) for p in NOISE):
            continue
        out.append(s)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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


stats = Counter()
term_counts = Counter()
lengths = []
sample_shown = False

with tarfile.open(TAR) as tf, open(OUT, "w", encoding="utf-8") as fout:
    members = [m for m in tf if m.isfile() and m.name.lower().endswith(".pdf")]
    for i, m in enumerate(members, 1):
        try:
            data = tf.extractfile(m).read()
            doc = pymupdf.open(stream=data, filetype="pdf")
            raw = "\n".join(p.get_text() for p in doc)
            doc.close()
        except Exception as e:
            stats["pdf_error"] += 1
            print("ERROR", m.name, e)
            continue

        text = clean(raw)
        row = meta_by_file.get(m.name)
        stats["matched_meta" if row is not None else "no_meta"] += 1

        head = text[:8000].lower()
        found = [k for k, rx in TERMS_RE.items() if rx.search(head)]
        for k in found:
            term_counts[k] += 1
        case_no, forum = forum_of(text[:3000])
        stats["forum_" + forum] += 1
        if found:
            stats["civil_subject_flag"] += 1
        lengths.append(len(text))

        rec = {
            "file": m.name,
            "case_id": None if row is None else row["case_id"],
            "title": None if row is None else row["title"],
            "citation": None if row is None else row["citation"],
            "decision_date": None if row is None else row["decision_date"],
            "disposal_nature": None if row is None else row["disposal_nature"],
            "judge": None if row is None else row["judge"],
            "case_number": case_no,
            "forum": forum,
            "civil_terms": found,
            "n_chars": len(text),
            "text": text,
        }
        fout.write(json.dumps(rec, ensure_ascii=False) + "\n")

        if not sample_shown and len(text) > 5000 and i > 2:
            sample_shown = True
            print("\n--- SAMPLE (cleaned, 900 chars) from", m.name, "---")
            print(text[:900])
            print("--- END SAMPLE ---\n")

        if i % 100 == 0:
            print(f"  processed {i}/{len(members)}")

print("\n===== STATS =====")
print("total pdfs:", len(members))
for k, v in sorted(stats.items()):
    print(f"  {k}: {v}")
if lengths:
    print("avg chars:", int(sum(lengths) / len(lengths)), "| max:", max(lengths))
print("\nCivil subject keyword counts:")
for k, v in term_counts.most_common():
    print(f"  {k}: {v}")
print("\nSaved:", OUT, "| MB:", round(os.path.getsize(OUT) / 1e6, 1))

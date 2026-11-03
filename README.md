(.venv) PS C:\Users\varti\indian-legal-research-copilot> @'
>> import re
>> 
>> HEAD_N = 3500  # title + bench + headnotes
>> 
>> CORE = {
>>     "transfer_of_property": r"transfer of property act",
>>     "specific_relief": r"specific relief act|specific performance",
>>     "contract": r"indian contract act|sale of goods act|breach of contract",
>>     "easements": r"\beasements?\b",
>>     "partition_title": r"\bpartition\b|declaration of title|suit for possession|adverse possession",
>>     "succession": r"succession act|\bprobate\b|testamentary",
>>     "mortgage": r"\bmortgage\b|\bredemption\b",
>>     "civil_procedure": r"res judicata|temporary injunction|permanent injunction|execution of (?:the )?decree|decree[- ]holder",
>>     "tenancy": r"rent control|\btenan(?:t|ts|cy)\b|\blandlords?\b|\beviction\b",
>> }
>> SOFT = {
>>     "cpc": r"code of civil procedure|\bc\.?p\.?c\.?\b",
>>     "civil_suit": r"\bplaintiffs?\b|\bsuit\b|\bsale deed\b|agreement (?:to|for) sell|agreement for sale|title suit",
>> }
>> WEAK = {
>>     "lease": r"\bleases?\b|\bleasehold\b",
>>     "limitation": r"limitation act|barred by limitation|period of limitation",
>>     "registration": r"registration act|unregistered",
>> }
>> NEG = re.compile(
>>     r"land acquisition|acquisition proceedings|income[- ]tax|central excise|service tax"
>>     r"|customs act|employee.?s compensation|eco-sensitive",
>>     re.I,
>> )
>>
>> C_RE = {k: re.compile(v, re.I) for k, v in CORE.items()}
>> S_RE = {k: re.compile(v, re.I) for k, v in SOFT.items()}
>> W_RE = {k: re.compile(v, re.I) for k, v in WEAK.items()}
>>
>>
>> def classify(text, forum):
>>     head = text[:HEAD_N]
>>     core = [k for k, rx in C_RE.items() if rx.search(head)]
>>     soft = [k for k, rx in S_RE.items() if rx.search(head)]
>>     weak = [k for k, rx in W_RE.items() if rx.search(head)]
>>     neg = bool(NEG.search(head))
>>     score = 2 * len(core) + 1 * len(soft) + 0.5 * len(weak)
>>     flag = (forum != "criminal") and score >= 2 and (len(core) >= 1 or not neg)
>>     return {"core": core, "soft": soft, "weak": weak, "neg": neg,        
>>             "score": score, "civil_flag": flag}
>> '@ | Set-Content -Encoding utf8 src\civil_filter.py
(.venv) PS C:\Users\varti\indian-legal-research-copilot> @'
>> import json, random, re, csv
>> from collections import Counter
>> from civil_filter import classify
>>
>> rows = [json.loads(l) for l in open("data/processed/2023.jsonl", encoding="utf-8")]
>> random.seed(3)
>> for r in rows:
>>     r["c"] = classify(r["text"], r["forum"])
>>
>> flag = [r for r in rows if r["c"]["civil_flag"]]
>> border = [r for r in flag if r["c"]["score"] == 2]
>> print("total:", len(rows), "| flagged:", len(flag), "| borderline (score=2):", len(border))
>> print("excluded by NEG (had civil words but land-acq/tax etc):",
>>       sum(1 for r in rows if r["c"]["neg"] and not r["c"]["core"] and r["c"]["score"] >= 2))
>> cnt = Counter(k for r in flag for k in r["c"]["core"] + r["c"]["soft"] + r["c"]["weak"])
>> print("terms:", dict(cnt.most_common()))
>>
>>
>> def snip(r):
>>     return re.sub(r"\s+", " ", r["text"][250:560])
>>
>>
>> def show(title, group, n):
>>     print(f"\n=== {title} ===")
>>     for r in random.sample(group, min(n, len(group))):
>>         print("-", (r["title"] or "")[:80], "| score", r["c"]["score"])  
>>         print("  ", snip(r))
>>
>>
>> show("10 FLAGGED (random)", flag, 10)
>> show("6 BORDERLINE (score=2)", border, 6)
>>
>> with open("data/processed/2023_civil_flagged.csv", "w", newline="", encoding="utf-8") as f:
>>     w = csv.writer(f)
>>     w.writerow(["case_id", "title", "citation", "score", "terms", "lawyer_says_civil(Y/N)"])
>>     for r in flag:
>>         w.writerow([r["case_id"], r["title"], r["citation"], r["c"]["score"],
>>                     ";".join(r["c"]["core"] + r["c"]["soft"] + r["c"]["weak"]), ""])
>> print("\nSaved data/processed/2023_civil_flagged.csv")
>> '@ | Set-Content -Encoding utf8 src\check_filter3.py
(.venv) PS C:\Users\varti\indian-legal-research-copilot> python src/check_filter3.py
total: 854 | flagged: 90 | borderline (score=2): 24
excluded by NEG (had civil words but land-acq/tax etc): 2
terms: {'civil_suit': 63, 'cpc': 34, 'tenancy': 26, 'partition_title': 25, 'civil_procedure': 12, 'transfer_of_property': 11, 'lease': 10, 'succession': 10, 'specific_relief': 8, 'limitation': 7, 'mortgage': 6, 'registration': 5, 'contract': 4}

=== 10 FLAGGED (random) ===
- MOHAMMED ABDUL WAHID versus NILOFER & ANR | score 2.0
   tween a party to a suit and a witness in a suit, does the phrase plaintiff ’s/ defendant’s witness exclude the plaintiff or defendant themselves, when they appear as witnesses in their own cause; and whether Ord. VII r. 14, Ord VIII r. 1-A and Ord. XIII r. 1 CPC, enjoin the party under-taking cross examinati
- SABBIR (DEAD) THROUGH LRS versus ANJUMAN (SINCE DECEASED) THROUGH LRS | score 3.5
   rmance was fi led within the period of limitation; (ii) Whether the respondents were ready and willing to perform their part of the contract. Suit – Specific performance – Limitation – Readiness and willingness to perform contract – Respondents fi led suit for specifi c performance – The suit was decreed – Th
- JHABBAR SINGH (DECEASED) THROUGH LEGAL HEIRS & ORS. versus JAGTAR SINGH S/O DARS | score 4.0
   , 1887 – ss. 118, 121, 123 – Right of pre-emption – Suit for possession of the suit lands by the respondent against the appellants-buyer, on the ground that he as a co-sharer in the joint khewat along with the owner-vendor had a superior right to pre- empt the sales, and that he was not put to any notice of s
- S. NARAHARI AND ORS versus S.R. KUMAR AND ORS. | score 4.0
   me Court to approach the High Court in review, automatically places the said matter in the escalation matrix, and makes the remedy of Special Leave Petition available again – Held: It is necessary for the same to be adjudicated and deliberated upon by a larger bench of the Supreme Court. Referring the matter
- PRAKASH (DEAD) BY LR. versus G. ARADHYA AND ORS. | score 5.0
   r a mortgage. Transfer of Property Act, 1882 – s.58(c) – Two documents executed on same day, Sale Deed and Reconveyance Deed/agreement of buy back deed, transaction if mortgage or absolute sale of the property: Held: Proviso to sub-section (c) of s.58 provides that no transaction shall be deemed to be a mortg
- SMRITI DEBBARMA (DEAD) THROUGH LEGAL REPRESENTATIVE versus PRABHA RANJAN DEBBARM | score 3.0
   creed the suit holding that the plaintiff had right, title and interest in the subject property and was entitled to khas possession of the property after evicting all the defendants – High Court reversed the judgment of trial court holding that plaintiff on basis of evidence and documents placed on record had
- BAINI PRASAD (D) THR. LRS. versus DURGA DEVI | score 3.0
   emolition of the structure put on by the appellant and for permanent prohibitory injunction restraining the appellant from interfering with the said land – Appellant’s case that two years ago he had carried out construction of the verandah in the land as part of his residential house bonfidely believing it to
- MOHINDER SINGH(DEAD) THROUGH LRS AND ANOTHER versus NARAIN SINGH AND OTHERS | score 3.0
    – Delhi Land Reforms Act, 1954 – ss. 3(5), 150 – Delhi Development Act, 1957 – Special provisions as to rural areas – Recorded Bhumidhar sold his land in a village in Delhi to one vide registered sale deed – He again sold some portion of his land to respondents vide sale deed in 1989 and their names were mut
- C. HARIDASAN versus ANAPPATH PARAKKATTU VASUDEVA KURUP & OTHERS | score 3.0
   acts execution of the agreement to sell land between the parties and receipt of consideration by the appellant-buyer – Balance amount to be paid within six months provided the respondent-seller made available the document of title and purchase certificate after measuring the property – Thereafter notice serve
- GURJIT SINGH (D) THROUGH LRS versus UNION TERRITORY, CHANDIGARH & ORS. | score 2.0
   d/or in front of his shop as a matter of right – Held: To do business in the shop and to carry on business on the auction platform, are both different and distinct – Merely because a person is having a licence and doing business in a particular shop, he is not entitled to the auction platform as a matter of r

=== 6 BORDERLINE (score=2) ===
- SHAH NEWAZ KHAN & ORS. versus STATE OF NAGALAND & ORS | score 2.0
   pellant-plaintiff moved an application u/s. 24 of CPC before the Gauhati High Court (Common High Court for the states of Assam, Nagaland and two other states) for an order to transfer of a suit filed by appellant in the court of the District Judge, Dimapur, Nagaland to the court of the District Judge at Gauha
- THE KOUSHIK MUTUALLY AIDED COOPERATIVE HOUSING SOCIETY versus AMEENA BEGUM & ANO | score 2.0
   ondent seeking condonation of delay in fi ling the petition to set aside the ex-parte decree was dismissed by Trial Court. Consequently, the petition fi led under Order IX Rule 13 CPC seeking setting aside of the ex-parte decree was also dismissed. In revision, High Court set aside the order by which the appl
- YADAIAH AND ANR. versus STATE OF TELANGANA AND OTHERS | score 2.0
   ment of non-occupied land in the 1960s to landless scheduled caste/scheduled tribe persons for the purpose of cultivation which was upheld by the Division Bench of the High Court is challenged; as also pertains to the issues of law concerning res judicata, nature of assignment and violation of conditions of a
- Y. P. LELE versus MAHARASHTRA STATE ELECTRICITY DISTRIBUTION COMPANY LTD. & ORS. | score 2.0
   an error in applying the explanation to Or. XVII, r.2 CPC and based upon it held that an application u/Or. IX Rule 13 CPC would not be maintainable as the presence of the defendant would be deemed to be recorded at the time of disposal of the suit. Code of Civil Procedure, 1908 – Explanation to Or. XVII, r.2
- SURESH LATARUJI RAMTEKE versus SAU. SUMANBAI PANDURANG PETKAR & ORS. | score 2.0
   rtunity of hearing to the parties on addressing the framed substantial questions of law, the High Court could have proceeded to decide the same in an appeal u/s.100, CPC particularly, when the fi ndings of fact rendered by two Courts, were sought to be reversed; and further, whether without summoning and per
- COMMITTEE OF MANAGEMENT ANJUMAN INTEZAMIA MASAJID, VARANASI versus RAKHI SINGH A | score 2.0
   OTES Issue under consideration : Order of the High Court dismissing the appeal against an order of the District Judge directing an archeological survey of the area in which the Gyanvapi Mosque is situated. Code of Civil Procedure, 1908 – Application u/s.75(c) and Or.26, r.10A of CPC allowed by the District Ju

Saved data/processed/2023_civil_flagged.csv
(.venv) PS C:\Users\varti\indian-legal-research-copilot> @'
>> import sys, os, re, json, csv, tarfile, unicodedata
>> import boto3, pandas as pd, pymupdf
>> from botocore import UNSIGNED
>> from botocore.config import Config
>> from civil_filter import classify
>>
>> BUCKET = "indian-supreme-court-judgments"
>> s3 = boto3.client("s3", region_name="ap-south-1",
>>                   config=Config(signature_version=UNSIGNED))
>> os.makedirs("data/raw", exist_ok=True)
>> os.makedirs("data/processed", exist_ok=True)
>>
>> NOISE = [
>>     re.compile(r"^[A-H]$"),
>>     re.compile(r"^\d{1,4}$"),
>>     re.compile(r"^SUPREME COURT REPORTS$"),
>>     re.compile(r"^\[\d{4}\]\s*\d+\s*S\.C\.R\.(\s*\d+)?(\s*:\s*\d{4}\s*INSC\s*\d+)?$"),
>> ]
>>
>>
>> def clean(text):
>>     text = unicodedata.normalize("NFKC", text)
>>     out = []
>>     for ln in text.splitlines():
>>         s = ln.strip()
>>         if any(p.match(s) for p in NOISE):
>>             continue
>>         out.append(s)
>>     text = "\n".join(out)
>>     return re.sub(r"\n{3,}", "\n\n", text).strip()
>>
>>
>> def forum_of(head):
>>     m = re.search(r"\(([^()]{0,80}?(?:Appeal|Petition|Case|Application|Reference)[^()]{0,80})\)", head)
>>     case_no = m.group(1).strip() if m else None
>>     low = (case_no or head[:1500]).lower()
>>     if "criminal" in low:
>>         forum = "criminal"
>>     elif "civil" in low:
>>         forum = "civil_side"
>>     else:
>>         forum = "other"
>>     return case_no, forum
>>
>>
>> def download(key, local):
>>     total = s3.head_object(Bucket=BUCKET, Key=key)["ContentLength"]      
>>     st = {"n": 0, "last": -1}
>>
>>     def cb(n):
>>         st["n"] += n
>>         pct = int(st["n"] * 100 / total)
>>         if pct != st["last"] and pct % 20 == 0:
>>             st["last"] = pct
>>             print(f"    download {pct}% of {round(total/1e6)} MB")       
>>
>>     s3.download_file(BUCKET, key, local, Callback=cb)
>>
>>
>> def process_year(year):
>>     out = f"data/processed/civil_{year}.jsonl"
>>     if os.path.exists(out):
>>         print(f"[{year}] already done, skipping")
>>         return
>>     meta_local = f"data/raw/meta_{year}.parquet"
>>     if not os.path.exists(meta_local):
>>         s3.download_file(BUCKET, f"metadata/parquet/year={year}/metadata.parquet", meta_local)
>>     meta = pd.read_parquet(meta_local)
>>     meta_by_file = {f"{r['path']}_EN.pdf": r for _, r in meta.iterrows()}
>>
>>     tar_local = f"data/raw/{year}_english.tar"
>>     if not os.path.exists(tar_local):
>>         print(f"[{year}] downloading tar ...")
>>         download(f"data/tar/year={year}/english/english.tar", tar_local) 
>>
>>     total = flagged = errors = no_meta = 0
>>     tmp = out + ".tmp"
>>     with tarfile.open(tar_local) as tf, open(tmp, "w", encoding="utf-8") as fout:
>>         members = [m for m in tf if m.isfile() and m.name.lower().endswith(".pdf")]
>>         for i, m in enumerate(members, 1):
>>             total += 1
>>             try:
>>                 data = tf.extractfile(m).read()
>>                 doc = pymupdf.open(stream=data, filetype="pdf")
>>                 raw = "\n".join(p.get_text() for p in doc)
>>                 doc.close()
>>             except Exception as e:
>>                 errors += 1
>>                 continue
>>             text = clean(raw)
>>             case_no, forum = forum_of(text[:3000])
>>             c = classify(text, forum)
>>             if not c["civil_flag"]:
>>                 continue
>>             row = meta_by_file.get(m.name)
>>             if row is None:
>>                 no_meta += 1
>>             flagged += 1
>>             rec = {
>>                 "file": m.name, "year": year,
>>                 "case_id": None if row is None else row["case_id"],      
>>                 "title": None if row is None else row["title"],
>>                 "citation": None if row is None else row["citation"],    
>>                 "decision_date": None if row is None else row["decision_date"],
>>                 "disposal_nature": None if row is None else row["disposal_nature"],
>>                 "judge": None if row is None else row["judge"],
>>                 "case_number": case_no, "forum": forum,
>>                 "civil_score": c["score"],
>>                 "civil_terms": c["core"] + c["soft"] + c["weak"],        
>>                 "n_chars": len(text), "text": text,
>>             }
>>             fout.write(json.dumps(rec, ensure_ascii=False) + "\n")       
>>             if i % 200 == 0:
>>                 print(f"    {i}/{len(members)} done, flagged so far: {flagged}")
>>     os.replace(tmp, out)
>>     os.remove(tar_local)
>>
>>     stats_file = "data/processed/year_stats.csv"
>>     new = not os.path.exists(stats_file)
>>     with open(stats_file, "a", newline="") as f:
>>         w = csv.writer(f)
>>         if new:
>>             w.writerow(["year", "pdfs", "flagged", "rate", "errors", "no_meta"])
>>         w.writerow([year, total, flagged, round(flagged / max(total, 1), 3), errors, no_meta])
>>     print(f"[{year}] pdfs={total} flagged={flagged} errors={errors} no_meta={no_meta}")
>>
>>
>> if __name__ == "__main__":
>>     args = [int(a) for a in sys.argv[1:]]
>>     years = [args[0]] if len(args) == 1 else list(range(args[0], args[1] + 1))
>>     for y in years:
>>         try:
>>             process_year(y)
>>         except Exception as e:
>>             print(f"[{y}] FAILED: {e}")
>> '@ | Set-Content -Encoding utf8 src\build_corpus.py
(.venv) PS C:\Users\varti\indian-legal-research-copilot> python src/build_corpus.py 2022
[2022] downloading tar ...
    download 0% of 451 MB
    download 20% of 451 MB
    download 40% of 451 MB
    download 60% of 451 MB
    download 80% of 451 MB
    download 100% of 451 MB
[2022] pdfs=1017 flagged=132 errors=0 no_meta=0
(.venv) PS C:\Users\varti\indian-legal-research-copilot> python src/build_corpus.py 2015 2026
[2015] downloading tar ...
    download 0% of 508 MB
    download 20% of 508 MB
    download 40% of 508 MB
    download 60% of 508 MB
    download 80% of 508 MB
    download 100% of 508 MB
[2015] pdfs=761 flagged=106 errors=0 no_meta=0
[2016] downloading tar ...
    download 0% of 387 MB
    download 20% of 387 MB
    download 40% of 387 MB
    download 60% of 387 MB
    download 80% of 387 MB
    download 100% of 387 MB
[2016] pdfs=589 flagged=72 errors=0 no_meta=0
[2017] downloading tar ...
    download 0% of 502 MB
    download 20% of 502 MB
    download 40% of 502 MB
    download 60% of 502 MB
    download 80% of 502 MB
    download 100% of 502 MB
    600/732 done, flagged so far: 112
[2017] pdfs=732 flagged=135 errors=0 no_meta=0
[2018] downloading tar ...
    download 0% of 323 MB
    download 20% of 323 MB
    download 40% of 323 MB
    download 60% of 323 MB
    download 80% of 323 MB
    download 100% of 323 MB
    200/795 done, flagged so far: 24
[2018] pdfs=795 flagged=91 errors=0 no_meta=0
[2019] downloading tar ...
    download 0% of 392 MB
    download 20% of 392 MB
    download 40% of 392 MB
    download 60% of 392 MB
    download 80% of 392 MB
    download 100% of 392 MB
[2019] pdfs=1050 flagged=176 errors=0 no_meta=0
[2020] downloading tar ...
    download 0% of 253 MB
    download 20% of 253 MB
    download 40% of 253 MB
    download 60% of 253 MB
    download 80% of 253 MB
    download 100% of 253 MB
    200/571 done, flagged so far: 37
[2020] pdfs=571 flagged=90 errors=0 no_meta=0
[2021] downloading tar ...
    download 0% of 373 MB
    download 20% of 373 MB
    download 40% of 373 MB
    download 60% of 373 MB
    download 80% of 373 MB
    download 100% of 373 MB
[2021] pdfs=708 flagged=91 errors=0 no_meta=0
[2022] already done, skipping
    800/854 done, flagged so far: 85
[2023] pdfs=854 flagged=90 errors=0 no_meta=0
[2024] downloading tar ...
    download 0% of 203 MB
    download 20% of 203 MB
    download 40% of 203 MB
    download 60% of 203 MB
    download 80% of 203 MB
    download 100% of 203 MB
[2024] pdfs=782 flagged=118 errors=0 no_meta=0
[2025] downloading tar ...
    download 0% of 177 MB
    download 20% of 177 MB
    download 40% of 177 MB
    download 60% of 177 MB
    download 80% of 177 MB
    download 100% of 177 MB
    200/897 done, flagged so far: 27
    400/897 done, flagged so far: 51
    600/897 done, flagged so far: 82
[2025] pdfs=897 flagged=121 errors=0 no_meta=0
[2026] downloading tar ...
    download 0% of 49 MB
    download 20% of 49 MB
    download 40% of 49 MB
    download 60% of 49 MB
    download 80% of 49 MB
    download 100% of 49 MB
    200/245 done, flagged so far: 25
[2026] pdfs=245 flagged=30 errors=0 no_meta=0
(.venv) PS C:\Users\varti\indian-legal-research-copilot> 
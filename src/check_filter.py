import json, random
from collections import Counter
from civil_filter import find_terms

rows = [json.loads(l) for l in open("data/processed/2023.jsonl", encoding="utf-8")]
random.seed(1)

flagged, not_flagged = [], []
cnt = Counter()
for r in rows:
    t = find_terms(r["text"])
    r["new_terms"] = t
    (flagged if t else not_flagged).append(r)
    for k in t:
        cnt[k] += 1

print("total:", len(rows))
print("flagged:", len(flagged), "| not flagged:", len(not_flagged))
print("flagged with 2+ terms:", sum(1 for r in flagged if len(r["new_terms"]) >= 2))
print("\nterm counts:")
for k, v in cnt.most_common():
    print(" ", k, v)

print("\n=== 15 random FLAGGED ===")
for r in random.sample(flagged, 15):
    print("-", (r["title"] or "")[:90], "|", r["new_terms"])

print("\n=== 12 random NOT flagged ===")
for r in random.sample(not_flagged, 12):
    print("-", (r["title"] or "")[:90])

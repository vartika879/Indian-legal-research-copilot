import json, random, re, csv
from collections import Counter
from civil_filter import classify

rows = [json.loads(l) for l in open("data/processed/2023.jsonl", encoding="utf-8")]
random.seed(3)
for r in rows:
    r["c"] = classify(r["text"], r["forum"])

flag = [r for r in rows if r["c"]["civil_flag"]]
border = [r for r in flag if r["c"]["score"] == 2]
print("total:", len(rows), "| flagged:", len(flag), "| borderline (score=2):", len(border))
print("excluded by NEG (had civil words but land-acq/tax etc):",
      sum(1 for r in rows if r["c"]["neg"] and not r["c"]["core"] and r["c"]["score"] >= 2))
cnt = Counter(k for r in flag for k in r["c"]["core"] + r["c"]["soft"] + r["c"]["weak"])
print("terms:", dict(cnt.most_common()))


def snip(r):
    return re.sub(r"\s+", " ", r["text"][250:560])


def show(title, group, n):
    print(f"\n=== {title} ===")
    for r in random.sample(group, min(n, len(group))):
        print("-", (r["title"] or "")[:80], "| score", r["c"]["score"])
        print("  ", snip(r))


show("10 FLAGGED (random)", flag, 10)
show("6 BORDERLINE (score=2)", border, 6)

with open("data/processed/2023_civil_flagged.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["case_id", "title", "citation", "score", "terms", "lawyer_says_civil(Y/N)"])
    for r in flag:
        w.writerow([r["case_id"], r["title"], r["citation"], r["c"]["score"],
                    ";".join(r["c"]["core"] + r["c"]["soft"] + r["c"]["weak"]), ""])
print("\nSaved data/processed/2023_civil_flagged.csv")

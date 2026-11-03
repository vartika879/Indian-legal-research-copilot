import json, random, re
from collections import Counter
from civil_filter import classify

rows = [json.loads(l) for l in open("data/processed/2023.jsonl", encoding="utf-8")]
random.seed(2)
for r in rows:
    r["c"] = classify(r["text"])

flag = [r for r in rows if r["c"]["civil_flag"]]
weak_only = [r for r in flag if not r["c"]["strong"]]
strong = [r for r in flag if r["c"]["strong"]]
missed = [r for r in rows if not r["c"]["civil_flag"] and r["forum"] == "civil_side"]

print("total:", len(rows), "| flagged:", len(flag),
      "| strong:", len(strong), "| weak-only:", len(weak_only))
print("civil_side but NOT flagged:", len(missed))
cnt = Counter(k for r in flag for k in r["c"]["strong"] + r["c"]["weak"])
print("terms:", dict(cnt.most_common()))


def snip(r):
    s = re.sub(r"\s+", " ", r["text"][250:650])
    return s


def show(title, group, n):
    print(f"\n=== {title} ===")
    for r in random.sample(group, min(n, len(group))):
        print("-", (r["title"] or "")[:80])
        print("  terms:", r["c"]["strong"] + r["c"]["weak"])
        print("  ", snip(r))


show("8 FLAGGED (strong)", strong, 8)
show("6 FLAGGED (weak-only)", weak_only, 6)
show("8 civil_side but NOT flagged", missed, 8)

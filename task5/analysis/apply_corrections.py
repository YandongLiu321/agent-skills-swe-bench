"""Apply the confirmed evaluation-environment corrections to the summary tables.

Confirmed artifacts (same patch passed elsewhere; local re-runs all passed):
  m1: (django, test-driven-development)              recheck 3/3 resolved
  m1: (requests, test-driven-development)             recheck 5/5 resolved
  m1: (requests, verification-before-completion)      recheck 5/5 resolved
Infrastructure failures in m2 (InternalServerError + empty patch):
  (sphinx, sphinx-docs) x2, (sphinx, sphinx-build) x1

Reads summary_accuracy.csv, subtracts these from the broken counts, writes
summary_accuracy_corrected.csv and summary_pooled_skill_corrected.csv.
"""

import csv
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

CORRECTIONS = {
    ("django", "test-driven-development"): 1,
    ("requests", "test-driven-development"): 1,
    ("requests", "verification-before-completion"): 1,
    ("sphinx", "sphinx-docs"): 2,
    ("sphinx", "sphinx-build"): 1,
}

rows = list(csv.DictReader(open(os.path.join(HERE, "summary_accuracy.csv"), encoding="utf-8-sig")))
out = []
for r in rows:
    key = (r["case"], r["skill"])
    adj = CORRECTIONS.get(key, 0)
    n = int(r["n"])
    b = max(0, int(r["broken"]) - adj)
    out.append(dict(case=r["case"], skill=r["skill"], n=n, broken=b,
                    kept=f"{n-b}/{n}", accuracy=round((n - b) / n, 4),
                    correction=adj, source=r["source"]))

with open(os.path.join(HERE, "summary_accuracy_corrected.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)

# pooled
pool = defaultdict(lambda: dict(n=0, broken=0, cases=set()))
for r in out:
    p = pool[r["skill"]]
    p["n"] += r["n"]
    p["broken"] += r["broken"]
    p["cases"].add(r["case"])
pooled = []
for s, p in sorted(pool.items(), key=lambda kv: -kv[1]["n"]):
    n, b = p["n"], p["broken"]
    pooled.append(dict(skill=s, cases_covered=len(p["cases"]), n=n, broken=b,
                       kept=f"{n-b}/{n}", accuracy=round((n - b) / n, 4)))
with open(os.path.join(HERE, "summary_pooled_skill_corrected.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(pooled[0].keys()))
    w.writeheader()
    w.writerows(pooled)

total_n = sum(r["n"] for r in out)
total_b = sum(r["broken"] for r in out)
print(f"corrected: {total_b} broken / {total_n} = {total_b/total_n*100:.2f}%")
print(f"before:    {sum(int(r['broken']) for r in rows)} / {sum(int(r['n']) for r in rows)}")
print("\nper-skill corrected (top/bottom):")
for p in pooled[:6] + pooled[-6:]:
    print(f"  {p['skill']:32s} {p['broken']:2d}/{p['n']:3d} = {p['accuracy']*100:5.1f}%")
print("\nwrote summary_accuracy_corrected.csv, summary_pooled_skill_corrected.csv")

"""Breakdown of the merge plan: what can be evaluated now vs what is still missing."""

import csv
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DATA = os.path.join(HERE, "data")

verdicts = json.load(open(os.path.join(REPO, "task5", "split", "baseline_verdicts.json"), encoding="utf-8"))
passed = {c: set(v["resolved"]) for c, v in verdicts.items()}
share = {m: json.load(open(os.path.join(REPO, "task5", "split", f"machine{m}.json"), encoding="utf-8"))
         for m in (1, 2, 3)}

rows = list(csv.DictReader(open(os.path.join(DATA, "merge_plan.csv"), encoding="utf-8-sig")))
# merge_plan has one row per run record (duplicates included)
seen = defaultdict(set)  # machine -> (case, arm, instance)
for r in rows:
    seen[r["machine"]].add((r["case"], r["arm"], r["instance"]))

for m in ("m1", "m2", "m3", "phase1"):
    keys = seen[m]
    non_base = [k for k in keys if k[1] != "baseline" and not k[1].startswith("baseline")]
    on_passed = [k for k in non_base if k[2] in passed.get(k[0], set())]
    print(f"{m:7s}: unique keys={len(keys):5d}  non-baseline={len(non_base):5d}  "
          f"on baseline-passed instances={len(on_passed):5d}")

# union of non-baseline keys on passed instances, by case
union = defaultdict(set)
for m in ("m1", "m2", "m3", "phase1"):
    for (c, a, i) in seen[m]:
        if a == "baseline" or a.startswith("baseline"):
            continue
        if i in passed.get(c, set()):
            union[(c, a)].add(i)
print(f"\nunion (case, arm) pairs: {len(union)}")
print(f"union (case, arm, instance) keys: {sum(len(v) for v in union.values())}")
print("\nper case: covered passed instances (union over arms) / expected 10 skills")
for c in sorted(passed):
    arms = {a: v for (cc, a), v in union.items() if cc == c}
    insts = set().union(*arms.values()) if arms else set()
    print(f"  {c:14s} inst={len(insts):3d}/{len(passed[c]):3d}  arms={len(arms):2d}  "
          f"expected arm-runs={len(passed[c]) * 10:4d}  have={sum(len(v) for v in arms.values()):4d}")

print("\nmissing arm-runs per case (expected 10 per instance):")
total_missing = 0
for c in sorted(passed):
    have = sum(len(v) for (cc, a), v in union.items() if cc == c)
    exp = len(passed[c]) * 10
    miss = exp - have
    total_missing += max(miss, 0)
    print(f"  {c:14s} {have:4d}/{exp:4d}  missing {max(miss, 0):4d}")
print(f"TOTAL missing arm-runs vs 4050: {total_missing}")

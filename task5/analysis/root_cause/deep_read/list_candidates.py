"""List all 101 crossover instances with n_resolved, success/failure arms, and failure labels.

Used to pick a stratified deep-read sample (1-3 / 4-6 / 7-9 resolved skills).
"""
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CROSS = ROOT / "task5" / "analysis" / "crossover"
LABELS = ROOT / "others_finding" / "_extracted" / "B2_20261023" / "任务B材料" / "phase2_final_20261023" / "output" / "final_failure_labels_437.csv"

slots = defaultdict(dict)
for r in csv.DictReader(open(CROSS / "arm_slot_map.csv", encoding="utf-8-sig")):
    slots[r["case"]][int(r["arm_slot"])] = r["skill"]

labels = defaultdict(list)
for r in csv.DictReader(open(LABELS, encoding="utf-8-sig")):
    labels[(r["case"], r["instance"], r["skill"])].append(r["final_label"])

rows = []
for r in csv.DictReader(open(CROSS / "instances.csv", encoding="utf-8-sig")):
    n = int(r["n_resolved"])
    if not (1 <= n <= 9):
        continue
    case, inst = r["case"], r["instance"]
    ok, bad = [], []
    for i in range(1, 11):
        skill = slots[case][i]
        (ok if r[f"arm_{i}"] == "1" else bad).append(skill)
    lab = []
    for s in bad:
        lab.extend(labels.get((case, inst, s), ["<no-label>"]))
    rows.append((case, inst, r["phase"], n, ok, bad, sorted(set(lab))))

rows.sort(key=lambda x: (x[3], x[0], x[1]))

print(f"total crossover: {len(rows)}")
for case, inst, phase, n, ok, bad, lab in rows:
    print(f"{n}\t{case:14s}\t{inst:40s}\t{phase}\tOK={','.join(ok)}\tFAIL={','.join(bad)}\tLABELS={','.join(lab)}")

"""Do 10 skills on the same instance converge on the same patch, or scatter?

For each machine1 instance: Jaccard similarity of changed-line sets between every pair
of arms, split into broken-broken / kept-kept / mixed pairs (where kept arms exist).
Also: how many arms submit a non-empty patch, and whether the single kept arm is an
outlier in patch content (a hint that the task has multiple plausible wrong answers).
"""

import csv
import json
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
M1 = os.path.join(REPO, "other_machine", "machine1", "machine1_全部轨迹")
DATA = os.path.join(HERE, "data")

outcome = {}
for r in csv.DictReader(open(os.path.join(DATA, "runs.csv"), encoding="utf-8-sig")):
    if r["machine"] == "machine1":
        outcome[(r["instance"], r["skill"])] = r["outcome"]

by_inst = defaultdict(list)
for dp, _, fs in os.walk(os.path.join(M1, "skills")):
    for f in fs:
        if not f.endswith(".traj.json"):
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, os.path.join(M1, "skills")).split(os.sep)
        inst, skill = rel[0], rel[1]
        d = json.load(open(p, encoding="utf-8"))
        by_inst[inst].append(dict(skill=skill, outcome=outcome.get((inst, skill)),
                                  sub=d.get("info", {}).get("submission") or "",
                                  steps=(d.get("info", {}).get("model_stats") or {}).get("api_calls")))


def lineset(s):
    return {l.strip() for l in s.splitlines()
            if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))}


print(f"{'instance':42s} {'n':>2s} {'empty':>5s} {'BB':>6s} {'BK':>6s} {'KK':>6s}")
summary = []
for inst, arms in sorted(by_inst.items()):
    sets = [(a["skill"], a["outcome"], lineset(a["sub"])) for a in arms]
    empty = sum(1 for _, _, s in sets if not s)
    bb, bk, kk = [], [], []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            si, oi = sets[i][2], sets[i][1]
            sj, oj = sets[j][2], sets[j][1]
            if not si or not sj:
                continue
            v = len(si & sj) / len(si | sj)
            pair = "".join(sorted([oi[0] if oi else "?", oj[0] if oj else "?"]))
            if oi == "broken" and oj == "broken":
                bb.append(v)
            elif oi == "kept" and oj == "kept":
                kk.append(v)
            elif oi != oj:
                bk.append(v)
    row = dict(instance=inst, n=len(sets), empty=empty,
               BB=float(np.mean(bb)) if bb else None,
               BK=float(np.mean(bk)) if bk else None,
               KK=float(np.mean(kk)) if kk else None)
    summary.append(row)
    print(f"{inst:42s} {row['n']:2d} {empty:5d} "
          f"{('%.2f' % row['BB']) if row['BB'] is not None else '   - ':>6s} "
          f"{('%.2f' % row['BK']) if row['BK'] is not None else '   - ':>6s} "
          f"{('%.2f' % row['KK']) if row['KK'] is not None else '   - ':>6s}")

bb = [r["BB"] for r in summary if r["BB"] is not None]
bk = [r["BK"] for r in summary if r["BK"] is not None]
print(f"\ninstances with >=2 broken arms: {len(bb)}")
print(f"mean within-broken Jaccard: {np.mean(bb):.2f}")
print(f"mean broken-vs-kept Jaccard: {np.mean(bk):.2f} (over {len(bk)} instances with both)")

with open(os.path.join(DATA, "patch_similarity.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
    w.writeheader()
    w.writerows(summary)
print("wrote data/patch_similarity.csv")

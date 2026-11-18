"""Classify every broken arm by its patch relation to the kept arms on the same instance.

Categories
  identical   : the broken patch is byte-identical to some kept arm's patch
                -> the break cannot be caused by the skill text
  near_miss   : Jaccard >= 0.75 to the best kept patch (a small mistake on the right fix)
  different   : Jaccard < 0.75 (a different approach)
  no_kept     : instance has no kept arm to compare with (cannot classify)

Also: for machine2, compare failed patches against machine1's kept patches on the same
instance (instances that appear in both splits).
"""

import csv
import hashlib
import json
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
M1 = os.path.join(REPO, "other_machine", "machine1", "machine1_全部轨迹")
M2 = os.path.join(REPO, "other_machine", "machine2", "machine2_63_failed_trajectories_2026-10-17")
DATA = os.path.join(HERE, "data")


def lineset(s):
    return {l.strip() for l in s.splitlines()
            if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))}


def norm_patch(s):
    return "\n".join(l.rstrip() for l in (s or "").replace("\r\n", "\n").splitlines()).strip()


def jac(a, b):
    if not a or not b:
        return float("nan")
    return len(a & b) / len(a | b)


# ---- machine1 ----
outcome = {}
for r in csv.DictReader(open(os.path.join(DATA, "runs.csv"), encoding="utf-8-sig")):
    if r["machine"] == "machine1":
        outcome[(r["instance"], r["skill"])] = r["outcome"]

by_inst = defaultdict(lambda: {"broken": [], "kept": []})
for dp, _, fs in os.walk(os.path.join(M1, "skills")):
    for f in fs:
        if not f.endswith(".traj.json"):
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, os.path.join(M1, "skills")).split(os.sep)
        inst, skill = rel[0], rel[1]
        d = json.load(open(p, encoding="utf-8"))
        sub = norm_patch(d.get("info", {}).get("submission") or "")
        o = outcome.get((inst, skill))
        if o in ("kept", "broken"):
            by_inst[inst][o].append(dict(skill=skill, sub=sub,
                                         sha=hashlib.sha256(sub.encode()).hexdigest(),
                                         lines=lineset(sub)))

cats = defaultdict(list)
rows = []
for inst, d in sorted(by_inst.items()):
    kept = d["kept"]
    for b in d["broken"]:
        if not kept:
            cat = "no_kept"
        elif any(b["sha"] == k["sha"] for k in kept):
            cat = "identical"
        else:
            js = [jac(b["lines"], k["lines"]) for k in kept]
            js = [v for v in js if not np.isnan(v)]
            best = max(js) if js else float("nan")
            cat = "near_miss" if (js and best >= 0.75) else "different"
        cats[cat].append((inst, b["skill"]))
        rows.append(dict(instance=inst, skill=b["skill"], category=cat,
                         best_jaccard="" if cat == "identical" or cat == "no_kept" else round(best, 3)))

print("### machine1 broken arms by patch relation to kept arms")
for c in ("identical", "near_miss", "different", "no_kept"):
    print(f"  {c:10s}: {len(cats[c]):2d} / 53")
    for inst, s in cats[c]:
        print(f"      {inst:42s} {s}")

with open(os.path.join(DATA, "failure_taxonomy.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

# ---- machine2 failed patch vs machine1 kept patch on same instance ----
print("\n### machine2 failed patches vs machine1 kept patches (shared instances)")
m1_kept_by_inst = defaultdict(list)
for inst, d in by_inst.items():
    for k in d["kept"]:
        m1_kept_by_inst[inst].append(k)
m2rows = list(csv.DictReader(open(os.path.join(M2, "失败运行清单_63条.csv"), encoding="utf-8-sig")))
shared = 0
ident = 0
for r in m2rows:
    inst = r["instance_id"]
    if inst not in m1_kept_by_inst:
        continue
    shared += 1
    p = os.path.join(M2, r["package_relative_path"])
    if not os.path.isfile(p):
        continue
    d = json.load(open(p, encoding="utf-8"))
    sub = norm_patch(d.get("info", {}).get("submission") or "")
    s = hashlib.sha256(sub.encode()).hexdigest()
    ls = lineset(sub)
    if any(s == k["sha"] for k in m1_kept_by_inst[inst]):
        ident += 1
        print(f"  IDENTICAL to machine1 kept patch: {inst} / {r['skill']}")
    else:
        js = [jac(ls, k["lines"]) for k in m1_kept_by_inst[inst]]
        js = [v for v in js if not np.isnan(v)]
        if js and max(js) >= 0.75:
            print(f"  near-miss ({max(js):.2f}): {inst} / {r['skill']}")
print(f"\nmachine2 failed runs on instances also present in machine1: {shared}")
print(f"  of which patch identical to a machine1 kept patch: {ident}")

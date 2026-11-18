"""Dry run for merging the three machines' runs into task5/runs.

Does NOT copy anything. Produces:
  - per (machine, case, arm) run counts
  - conflicts: same (case, arm, instance) with a different patch in another source
  - a merge plan: unique instances per (case, arm) after union
  - the evaluation workload for the final table
Writes data/merge_plan.csv and prints a summary.
"""

import csv
import glob
import hashlib
import json
import os
import tarfile
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DATA = os.path.join(HERE, "data")
RUNS = os.path.join(REPO, "task5", "runs")
M1 = os.path.join(REPO, "other_machine", "machine1", "machine1_全部轨迹")
M2 = os.path.join(REPO, "other_machine", "machine2", "machine2_63_failed_trajectories_2026-10-17")
M3_TAR = os.path.join(REPO, "other_machine", "machine3", "machine3_runs_回传.tar.gz")

SRC = {"pydata": "xarray", "mwaskom": "seaborn", "psf": "requests",
       "pylint-dev": "pylint", "pytest-dev": "pytest", "sphinx-doc": "sphinx", "pallets": "flask"}
norm = lambda c: SRC.get(c, c)


def sha(s):
    return hashlib.sha256((s or "").strip().encode()).hexdigest()


def traj_patch(path):
    d = json.load(open(path, encoding="utf-8"))
    return d.get("info", {}).get("submission") or ""


runs = []  # dict(machine, case, arm, instance, sha)

# machine1
for dp, _, fs in os.walk(os.path.join(M1, "skills")):
    for f in fs:
        if not f.endswith(".traj.json"):
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, os.path.join(M1, "skills")).split(os.sep)
        inst, arm = rel[0], rel[1]
        runs.append(dict(machine="m1", case=norm(inst.split("__")[0]), arm=arm,
                         instance=inst, sha=sha(traj_patch(p))))
for dp, _, fs in os.walk(os.path.join(M1, "baseline")):
    for f in fs:
        if f.endswith(".traj.json"):
            inst = f.replace(".traj.json", "")
            runs.append(dict(machine="m1", case=norm(inst.split("__")[0]), arm="baseline",
                             instance=inst, sha=sha(traj_patch(os.path.join(dp, f)))))

# machine2 (failures only)
for r in csv.DictReader(open(os.path.join(M2, "失败运行清单_63条.csv"), encoding="utf-8-sig")):
    p = os.path.join(M2, r["package_relative_path"])
    runs.append(dict(machine="m2", case=norm(r["case"].split("__")[0]), arm=r["skill"],
                     instance=r["instance_id"], sha=sha(traj_patch(p)) if os.path.isfile(p) else ""))

# machine3 (from tar preds)
with tarfile.open(M3_TAR) as tf:
    for name in tf.getnames():
        if not name.endswith("/preds.json"):
            continue
        parts = name.split("/")
        case, arm = norm(parts[0]), parts[1]
        try:
            d = json.loads(tf.extractfile(name).read().decode("utf-8"))
        except Exception:
            continue
        for inst, v in d.items():
            runs.append(dict(machine="m3", case=case, arm=arm, instance=inst,
                             sha=sha(v.get("model_patch") or "")))

# existing phase-1 runs
for case_dir in sorted(glob.glob(os.path.join(RUNS, "*"))):
    if not os.path.isdir(case_dir):
        continue
    case = os.path.basename(case_dir)
    for arm_dir in sorted(glob.glob(os.path.join(case_dir, "*"))):
        if not os.path.isdir(arm_dir):
            continue
        arm = os.path.basename(arm_dir)
        preds = os.path.join(arm_dir, "preds.json")
        if not os.path.isfile(preds):
            continue
        try:
            d = json.load(open(preds, encoding="utf-8"))
        except Exception:
            continue
        for inst, v in d.items():
            runs.append(dict(machine="phase1", case=case, arm=arm, instance=inst,
                             sha=sha(v.get("model_patch") or "")))

print(f"total run records (all sources): {len(runs)}")
by_machine = defaultdict(int)
for r in runs:
    by_machine[r["machine"]] += 1
print("by machine:", dict(by_machine))

# duplicates across sources
by_key = defaultdict(list)
for r in runs:
    by_key[(r["case"], r["arm"], r["instance"])].append(r)
conflicts, dup_ok = [], []
for k, rs in by_key.items():
    shas = {r["sha"] for r in rs if r["sha"]}
    if len(rs) > 1:
        (conflicts if len(shas) > 1 else dup_ok).append((k, rs))
print(f"duplicate (case,arm,instance) keys: {len(dup_ok) + len(conflicts)}")
print(f"  identical patch duplicates: {len(dup_ok)}")
print(f"  conflicting patches: {len(conflicts)}")
for k, rs in conflicts[:10]:
    print("   CONFLICT", k, [(r["machine"], r["sha"][:8]) for r in rs])

# merge plan: unique keys per (case, arm), excluding m3 invalid? we do not know validity here
plan = defaultdict(set)
for r in runs:
    plan[(r["case"], r["arm"])].add(r["instance"])
print(f"\nunique (case, arm) pairs after union: {len(plan)}")
print(f"unique (case, arm, instance) records after union: {sum(len(v) for v in plan.values())}")

# workload for the final eval: only phase-2 arms (non-baseline) and instances in the 405 passed set
verdicts = json.load(open(os.path.join(REPO, "task5", "split", "baseline_verdicts.json"), encoding="utf-8"))
passed = {c: set(v["resolved"]) for c, v in verdicts.items()}
eval_n = 0
for (case, arm), insts in plan.items():
    if arm in ("baseline",) or arm.startswith("baseline"):
        continue
    eval_n += len(insts & passed.get(case, set()))
print(f"final-eval workload (non-baseline, passed instances): {eval_n}")

with open(os.path.join(DATA, "merge_plan.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["machine", "case", "arm", "instance", "patch_sha"])
    for r in runs:
        w.writerow([r["machine"], r["case"], r["arm"], r["instance"], r["sha"][:16]])
print("wrote data/merge_plan.csv")

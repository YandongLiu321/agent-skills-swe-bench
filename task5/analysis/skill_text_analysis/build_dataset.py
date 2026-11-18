"""Build the unified run-level dataset used by all downstream analyses.

Inputs
  task5/runs/*/baseline/*/*.traj.json                 official baseline verdicts (phase 1)
  task5/split/baseline_verdicts.json                  official pass/fail
  other_machine/machine1/machine1_全部轨迹/            all 1350 skill trajs + 135 baseline + eval JSONs
  other_machine/machine2/machine2_63_failed_trajectories_2026-10-17/
  other_machine/machine1/all_experiment_runs(2).csv    m1 self-reported resolved (cross-check)

Output
  data/runs.csv     one row per (machine, case, instance, skill)
  data/skills.csv   one row per skill with text features (written by extract_features.py)

Columns in runs.csv:
  machine, case, instance, skill, skill_type, resolved, outcome,
  steps, prompt_tokens, completion_tokens, cached_tokens, cost_usd, exit_status,
  empty_patch, infra_failure, source
"""

import csv
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

SRC_MAP = {"pydata": "xarray", "mwaskom": "seaborn", "psf": "requests",
           "pylint-dev": "pylint", "pytest-dev": "pytest", "sphinx-doc": "sphinx"}
case_of = lambda inst: SRC_MAP.get(inst.split("__")[0], inst.split("__")[0])

# Which skills are "dedicated" to a case vs universal. From task5/skills/cases/* or OVERVIEW.
OVERVIEW = os.path.join(REPO, "task5", "skills", "OVERVIEW.md")
dedicated = defaultdict(set)
for line in open(OVERVIEW, encoding="utf-8"):
    m = re.match(r"\|\s*`([^`]+)`\s*\|\s*([^|]+)\|", line)
    if m:
        skill, cases = m.group(1).strip(), m.group(2).strip()
        if "全部" in cases or "个 case" in cases:
            continue
        for c in re.findall(r"[a-z\-]+", cases.lower()):
            dedicated[skill].add(c)


def skill_type(skill, case):
    return "dedicated" if case in dedicated.get(skill, set()) else "generic"


def msg_tokens(m):
    return sum(len(v) if isinstance(v, str) else len(json.dumps(v, ensure_ascii=False))
               for k, v in m.items() if k != "role" and v is not None) / 4.0


def traj_stats(path):
    d = json.load(open(path, encoding="utf-8"))
    info = d.get("info", {})
    st = info.get("model_stats") or {}
    return dict(
        instance=d.get("instance_id"),
        exit_status=info.get("exit_status"),
        steps=st.get("api_calls"),
        cost=st.get("instance_cost"),
        model=((info.get("config") or {}).get("model") or {}).get("model_name"),
        messages=d.get("messages", []),
    )


rows = []

# ---------------------------------------------------------------- machine1
M1 = os.path.join(REPO, "other_machine", "machine1", "machine1_全部轨迹")

# official verdicts
verdict = {}
ev_dir = os.path.join(M1, "官方评测汇总")
for fn in os.listdir(ev_dir):
    if not fn.endswith(".json"):
        continue
    d = json.load(open(os.path.join(ev_dir, fn), encoding="utf-8"))
    m = re.match(r"deepseek__deepseek-v4-flash\.(.+?)__(baseline|[^.]+)\.json$", fn)
    if not m:
        continue
    case, arm = m.group(1), m.group(2)
    for i in d.get("resolved_ids", []):
        verdict[(case, arm, i)] = 1
    for i in d.get("unresolved_ids", []):
        verdict[(case, arm, i)] = 0

base_calls, base_cost = {}, {}
for dp, _, fs in os.walk(os.path.join(M1, "baseline")):
    for f in fs:
        if f.endswith(".traj.json"):
            s = traj_stats(os.path.join(dp, f))
            base_calls[s["instance"]] = s["steps"]
            base_cost[s["instance"]] = s["cost"]

for dp, _, fs in os.walk(os.path.join(M1, "skills")):
    for f in fs:
        if not f.endswith(".traj.json"):
            continue
        p = os.path.join(dp, f)
        s = traj_stats(p)
        inst = s["instance"] or f.replace(".traj.json", "")
        case = case_of(inst)
        # skills/<instance>/<skill>/<file>
        rel = os.path.relpath(p, os.path.join(M1, "skills")).split(os.sep)
        skill = rel[1]
        res = verdict.get((case, skill, inst))
        rows.append(dict(
            machine="machine1", case=case, instance=inst, skill=skill,
            skill_type=skill_type(skill, case),
            resolved="" if res is None else res,
            outcome="" if res is None else ("kept" if res else "broken"),
            steps=s["steps"],
            prompt_tokens=round(sum(msg_tokens(m) for m in s["messages"])),
            completion_tokens="",
            cached_tokens="",
            cost_usd=s["cost"],
            exit_status=s["exit_status"],
            empty_patch=0, infra_failure=0,
            source=os.path.relpath(p, REPO),
        ))

# ---------------------------------------------------------------- machine2
M2 = os.path.join(REPO, "other_machine", "machine2", "machine2_63_failed_trajectories_2026-10-17")
for r in csv.DictReader(open(os.path.join(M2, "失败运行清单_63条.csv"), encoding="utf-8-sig")):
    inst = r["instance_id"]
    case = case_of(inst)
    infra = int(r["infra_failure"]) or int(r["evaluation_error"]) or (
        1 if r["exit_status"] != "Submitted" and int(r["empty_patch"]) else 0)
    rows.append(dict(
        machine="machine2", case=case, instance=inst, skill=r["skill"],
        skill_type=r["skill_type"],
        resolved=0, outcome="infra" if infra else "broken",
        steps=int(r["steps"]), prompt_tokens=int(r["prompt_tokens"]),
        completion_tokens=int(r["completion_tokens"]), cached_tokens=int(r["cached_tokens"]),
        cost_usd=float(r["cost_usd"]), exit_status=r["exit_status"],
        empty_patch=int(r["empty_patch"]), infra_failure=infra,
        source=os.path.join("other_machine/machine2/...", r["package_relative_path"]),
    ))

cols = ["machine", "case", "instance", "skill", "skill_type", "resolved", "outcome",
        "steps", "prompt_tokens", "completion_tokens", "cached_tokens", "cost_usd",
        "exit_status", "empty_patch", "infra_failure", "source"]
with open(os.path.join(DATA, "runs.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)

print(f"runs.csv: {len(rows)} rows")
from collections import Counter
print("  by machine/outcome:", Counter((r["machine"], r["outcome"]) for r in rows))
print("  skills:", len({r["skill"] for r in rows}), "| cases:", len({r["case"] for r in rows}))
print("  dedicated/generic:", Counter(r["skill_type"] for r in rows))
print("  m1 baseline steps available for", len(base_calls), "instances")
json.dump(dict(base_calls=base_calls, base_cost=base_cost),
          open(os.path.join(DATA, "baseline_stats.json"), "w", encoding="utf-8"), indent=0)

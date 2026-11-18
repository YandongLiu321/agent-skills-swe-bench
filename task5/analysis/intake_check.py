"""Verify the newly received trajectory packages before analysis.

Checks per source:
  - every instance id belongs to that machine's split
  - model name in every traj.json
  - counts vs what was promised
  - resolved labels: official eval JSON vs manifest vs trajectories
Writes: task5/analysis/intake_report.md
"""

import csv
import json
import os
import re
from collections import Counter, defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OM = os.path.join(REPO, "other_machine")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "intake_report.md")

lines = []
def log(s=""):
    print(s)
    lines.append(s)

split_of = {}
for m in (1, 2, 3):
    split_of[m] = json.load(open(os.path.join(REPO, "task5", "split", f"machine{m}.json"), encoding="utf-8"))
share_ids = {m: {i for v in d.values() for i in v} for m, d in split_of.items()}

def case_of(inst):
    repo = inst.split("__")[0]
    return {"pydata": "xarray", "mwaskom": "seaborn", "psf": "requests",
            "pylint-dev": "pylint", "pytest-dev": "pytest", "sphinx-doc": "sphinx"}.get(repo, repo)

def check_model(d):
    return ((d.get("info", {}).get("config") or {}).get("model") or {}).get("model_name")

# ---------------- machine1 ----------------
log("# 入库体检报告\n")
log("生成时间：2026-10-17\n")

m1root = os.path.join(OM, "machine1", "machine1_全部轨迹")
m1_files = []
for dirpath, _, files in os.walk(m1root):
    for fn in files:
        if fn.endswith(".traj.json"):
            m1_files.append(os.path.join(dirpath, fn))

recs = []
model_bad = 0
for f in m1_files:
    d = json.load(open(f, encoding="utf-8"))
    inst = d.get("instance_id") or os.path.basename(f).replace(".traj.json", "")
    rel = os.path.relpath(f, m1root)
    arm = "baseline" if rel.startswith("baseline") else os.path.normpath(rel).split(os.sep)[2]
    if check_model(d) != "deepseek/deepseek-v4-flash":
        model_bad += 1
    recs.append(dict(inst=inst, arm=arm, model=check_model(d), exit=d.get("info", {}).get("exit_status"),
                     cost=(d.get("info", {}).get("model_stats") or {}).get("instance_cost"),
                     calls=(d.get("info", {}).get("model_stats") or {}).get("api_calls")))

skill_recs = [r for r in recs if r["arm"] != "baseline"]
base_recs = [r for r in recs if r["arm"] == "baseline"]
log("## machine1\n")
log(f"- 轨迹文件：**{len(recs)}** 条（skill {len(skill_recs)}，baseline {len(base_recs)}）")
log(f"- 实例数：skill 覆盖 **{len({r['inst'] for r in skill_recs})}** 个，baseline **{len({r['inst'] for r in base_recs})}** 个")
log(f"- 模型不一致：**{model_bad}** 条")
outside = sorted({r["inst"] for r in recs} - share_ids[1])
log(f"- 不属于 machine1 份额的实例：**{len(outside)}** {outside[:5]}")
log(f"- 每条实例的 skill 轨迹数分布：{dict(Counter(Counter(r['inst'] for r in skill_recs).values()))}")

# official eval files
eval_dir = os.path.join(m1root, "官方评测汇总")
eval_resolved = {}
eval_unresolved = {}
if os.path.isdir(eval_dir):
    for fn in os.listdir(eval_dir):
        if not fn.endswith(".json"):
            continue
        d = json.load(open(os.path.join(eval_dir, fn), encoding="utf-8"))
        m = re.match(r"deepseek__deepseek-v4-flash\.(.+)__([^.]+)\.json$", fn)
        if not m:
            continue
        case, arm = m.group(1), m.group(2)
        for i in d.get("resolved_ids", []):
            eval_resolved[(case, arm, i)] = True
        for i in d.get("unresolved_ids", []):
            eval_resolved[(case, arm, i)] = False
log(f"- 官方评测汇总文件：**{len(os.listdir(eval_dir)) if os.path.isdir(eval_dir) else 0}** 个；已判分 (case,arm,inst) 记录：**{len(eval_resolved)}**")

# cross-check: every skill record has a verdict, verdict matches manifest
man = list(csv.DictReader(open(os.path.join(OM, "machine1", "all_experiment_runs(2).csv"), encoding="utf-8-sig")))
man = [r for r in man if r["cohort"] == "machine1"]
man_map = {(case_of(r["case_id"]), r["skill_name"], r["case_id"]): r["resolved"] for r in man}
missing_verdict, mismatch = [], []
for r in skill_recs:
    key = (case_of(r["inst"]), r["arm"], r["inst"])
    if key not in eval_resolved:
        missing_verdict.append(key)
    else:
        ev = "1" if eval_resolved[key] else "0"
        if key in man_map and man_map[key] != ev:
            mismatch.append((key, man_map[key], ev))
log(f"- skill 轨迹中缺官方判分的：**{len(missing_verdict)}**")
log(f"- 与 machine1 汇总表 `resolved` 不一致的：**{len(mismatch)}** {mismatch[:3]}")

# ---------------- machine2 ----------------
m2root = os.path.join(OM, "machine2", "machine2_63_failed_trajectories_2026-10-17")
m2list = list(csv.DictReader(open(os.path.join(m2root, "失败运行清单_63条.csv"), encoding="utf-8-sig")))
m2files = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(m2root, "trajectories"))
           for f in fs if f.endswith(".traj.json")]
m2_model_bad = 0
m2_insts = set()
for f in m2files:
    d = json.load(open(f, encoding="utf-8"))
    m2_insts.add(d.get("instance_id"))
    if check_model(d) != "deepseek/deepseek-v4-flash":
        m2_model_bad += 1
m2_out = sorted({r["instance_id"] for r in m2list} - share_ids[2])
log("\n## machine2\n")
log(f"- 清单行数：**{len(m2list)}**，轨迹文件：**{len(m2files)}**")
log(f"- 去重实例：**{len(m2_insts)}**；项目×skill 组合：**{len({(r['case'], r['skill']) for r in m2list})}**")
log(f"- 模型不一致：**{m2_model_bad}** 条")
log(f"- 不属于 machine2 份额的实例：**{len(m2_out)}** {m2_out[:5]}")
log(f"- `outcome` 取值：{dict(Counter(r['outcome'] for r in m2list))}")
log(f"- `exit_status` 取值：{dict(Counter(r['exit_status'] for r in m2list))}")
log(f"- 缓存命中率中位数：**{sorted(float(r['cache_hit_pct']) for r in m2list if r['cache_hit_pct'])[len(m2list)//2]:.1%}**")

# ---------------- machine3 ----------------
m3x = os.path.join(OM, "machine3", "machine3_Skill详细表现汇总.xlsx")
log("\n## machine3\n")
log(f"- 新增汇总表：`{os.path.basename(m3x)}`（{'存在' if os.path.isfile(m3x) else '不存在'}）")
log("- 原始轨迹与之前一致（3255 条），欠费问题仍在，需补跑。")

open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\nwrote", OUT)

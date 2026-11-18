"""Deep dive on the strongest within-instance signal: testing behaviour.

For the 17 machine1 instances with both broken and kept runs, show per-instance
test-command counts and the actual test commands. Then check whether the machine2
failure set shows the same process signature (no kept arm available, so compare
against machine1 kept baselines only as reference).
"""

import csv
import os
import re
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

rows = list(csv.DictReader(open(os.path.join(DATA, "traj_metrics.csv"), encoding="utf-8-sig")))
m1 = [r for r in rows if r["machine"] == "machine1"]
by = defaultdict(lambda: {"broken": [], "kept": []})
for r in m1:
    by[(r["case"], r["instance"])][r["outcome"]].append(r)

print("### per-instance: test commands and steps")
print("| instance | broken arms | test_cmds B/K | steps B/K |")
print("|---|---:|---|---|")
for (case, inst), d in sorted(by.items()):
    if not d["broken"] or not d["kept"]:
        continue
    b = [float(r["test_cmds"]) for r in d["broken"]]
    k = [float(r["test_cmds"]) for r in d["kept"]]
    sb = [float(r["steps"]) for r in d["broken"]]
    sk = [float(r["steps"]) for r in d["kept"]]
    print(f"| {inst} | {len(b)} | {np.mean(b):.1f} / {np.mean(k):.1f} | "
          f"{np.mean(sb):.0f} / {np.mean(sk):.0f} |")

# machine2: failures only
m2 = [r for r in rows if r["machine"] == "machine2" and r["outcome"] == "broken"]
print(f"\n### machine2 failures: n={len(m2)}, test_cmds mean={np.mean([float(r['test_cmds']) for r in m2]):.1f}, "
      f"steps mean={np.mean([float(r['steps']) for r in m2]):.1f}")

# which skills' broken runs ran the fewest tests
print("\n### broken runs by skill (machine1): mean test commands")
bs = defaultdict(list)
for r in m1:
    if r["outcome"] == "broken":
        bs[r["skill"]].append(float(r["test_cmds"]))
for s, v in sorted(bs.items(), key=lambda kv: np.mean(kv[1])):
    print(f"  {s:32s} n={len(v):2d} mean_test_cmds={np.mean(v):5.1f}")

# spot: what did the single kept arm of matplotlib-23299 do vs the 9 broken?
print("\n### matplotlib-23299: kept vs broken process")
d = by[("matplotlib", "matplotlib__matplotlib-23299")]
for grp, rs in d.items():
    print(f"  {grp}: n={len(rs)}")
    for r in rs:
        print(f"    {r['skill']:32s} steps={r['steps']:>3s} test={r['test_cmds']:>2s} "
              f"search={r['search_cmds']:>2s} patch+={r['patch_lines_added']:>3s} "
              f"tracebacks={r['tracebacks']:>2s} exit={r['exit_status']}")

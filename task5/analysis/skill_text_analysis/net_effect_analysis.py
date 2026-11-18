"""Does skill text predict the NET effect (rescue on failed + break on passed)?

Phase 1 (group cohort) gives rescue counts on baseline-failed instances.
Phase 2 (machine1) gives break counts on baseline-passed instances.
For each skill x case:
  rescue_rate = rescued / failed_instances_run
  break_rate  = broken  / passed_instances_run   (network artifacts removed)
  net_delta   = rescue_rate * (N_failed/N) - break_rate * (N_passed/N)
Then: v2 features -> net_delta, within-case rank + permutation + BH-FDR.

This is the outcome the research actually cares about: good skill = net positive.
"""

import csv
import json
import os
from collections import defaultdict

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DATA = os.path.join(HERE, "data")
SRC = {"pydata": "xarray", "mwaskom": "seaborn", "psf": "requests",
       "pylint-dev": "pylint", "pytest-dev": "pytest", "sphinx-doc": "sphinx",
       "pallets": "flask"}
norm = lambda c: SRC.get(c, c)

feat_rows = list(csv.DictReader(open(os.path.join(DATA, "skills_v2.csv"), encoding="utf-8-sig")))
feat_names = [k for k in feat_rows[0] if k not in ("skill", "skill_type", "cases", "n_cases")]
F = {r["skill"]: {k: float(r[k]) for k in feat_names} for r in feat_rows}

verdicts = json.load(open(os.path.join(REPO, "task5", "split", "baseline_verdicts.json"), encoding="utf-8"))
N_total = {c: v["submitted"] for c, v in verdicts.items()}
N_pass = {c: len(v["resolved"]) for c, v in verdicts.items()}
N_fail = {c: N_total[c] - N_pass[c] for c in N_total}

# phase 1 rescue
rescue = defaultdict(lambda: [0, 0])
with open(os.path.join(REPO, "other_machine", "machine1", "all_experiment_runs(2).csv"), encoding="utf-8-sig") as fh:
    for row in csv.DictReader(fh):
        if row["cohort"] != "group":
            continue
        c = norm(row["case_id"].split("__")[0])
        s = row["skill_name"]
        rescue[(s, c)][1] += 1
        rescue[(s, c)][0] += 1 if row["resolved"] == "1" else 0

# phase 2 breaks (corrected)
NET = {("psf__requests-1921", "test-driven-development"),
       ("psf__requests-1921", "verification-before-completion")}
broken = defaultdict(lambda: [0, 0])
for r in csv.DictReader(open(os.path.join(DATA, "runs.csv"), encoding="utf-8-sig")):
    if r["machine"] != "machine1" or r["outcome"] not in ("kept", "broken"):
        continue
    o = "kept" if (r["instance"], r["skill"]) in NET else r["outcome"]
    broken[(r["skill"], r["case"])][1] += 1
    broken[(r["skill"], r["case"])][0] += 1 if o == "broken" else 0

# net effect per skill x case
net = {}
for (s, c), (b, n) in broken.items():
    if (s, c) not in rescue:
        continue
    rr, rn = rescue[(s, c)]
    wf = N_fail[c] / N_total[c]
    wp = N_pass[c] / N_total[c]
    net[(s, c)] = (rr / rn) * wf - (b / n) * wp

print(f"skill x case net-effect cells: {len(net)}")
print(f"positive net: {sum(1 for v in net.values() if v > 0)}  "
      f"negative: {sum(1 for v in net.values() if v < 0)}")

# aggregate per skill (equal weight per case)
by_skill = defaultdict(list)
for (s, c), v in net.items():
    by_skill[s].append(v)
print("\n### net effect per skill (mean over its cases; + = net positive)")
for s, v in sorted(by_skill.items(), key=lambda kv: -np.mean(kv[1])):
    print(f"  {s:32s} {np.mean(v)*100:+.2f}pp over {len(v)} cases")

# within-case ranks of net effect
ranks = {}
for c in sorted({k[1] for k in net}):
    ss = [s for (s, cc) in net if cc == c]
    vals = [net[(s, c)] for s in ss]
    rr = stats.rankdata([-v for v in vals], method="average")
    for s, rv in zip(ss, rr):
        ranks.setdefault(s, []).append(rv)

by_case_skills = defaultdict(list)
for (s, c) in net:
    by_case_skills[c].append(s)

def contrast(fvals):
    diffs = []
    for c, ss in by_case_skills.items():
        if len(ss) < 4:
            continue
        v = np.array([fvals[s] for s in ss])
        if np.std(v) == 0:
            continue
        med = np.median(v)
        hi = [s for s, x in zip(ss, v) if x > med]
        lo = [s for s, x in zip(ss, v) if x < med]
        if not hi or not lo:
            continue
        diffs.append(np.mean([np.mean(ranks[s]) for s in hi]) - np.mean([np.mean(ranks[s]) for s in lo]))
    return float(np.mean(diffs)) if diffs else 0.0

rng = np.random.default_rng(0)
results = []
for f in feat_names:
    fvals = {s: F[s][f] for s in F}
    obs = contrast(fvals)
    null = []
    for _ in range(5000):
        perm = {}
        for c, ss in by_case_skills.items():
            vals = [fvals[s] for s in ss]
            rng.shuffle(vals)
            for s, v in zip(ss, vals):
                perm[s] = v
        null.append(contrast(perm))
    p = (1 + np.sum(np.abs(null) >= abs(obs))) / (1 + len(null))
    xs = np.array([fvals[s] for s in sorted(by_skill)])
    ys = np.array([np.mean(by_skill[s]) for s in sorted(by_skill)])
    ok = ~np.isnan(xs) & ~np.isnan(ys)
    rho = stats.spearmanr(xs[ok], ys[ok]).statistic if ok.sum() > 5 else float("nan")
    results.append(dict(feature=f, rank_contrast=obs, rho=rho, p=p))

results.sort(key=lambda r: r["p"])
m = len(results)
prev = 1.0
for i in range(m - 1, -1, -1):
    q = min(prev, results[i]["p"] * m / (i + 1))
    results[i]["q"] = q
    prev = q
results.sort(key=lambda r: r["q"])
print("\n### features vs net effect")
print(f"{'feature':22s} {'rank':>7s} {'rho':>7s} {'p':>7s} {'q':>7s}")
for r in results[:15]:
    print(f"{r['feature']:22s} {r['rank_contrast']:7.2f} {r['rho']:7.3f} {r['p']:7.3f} {r['q']:7.3f}")
print(f"min q = {min(r['q'] for r in results):.3f}")

with open(os.path.join(DATA, "net_effect.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["skill", "case", "net_delta", "rescue_rate", "break_rate"])
    for (s, c), v in sorted(net.items()):
        rr, rn = rescue[(s, c)]
        b, n = broken[(s, c)]
        w.writerow([s, c, round(v, 5), round(rr / rn, 4), round(b / n, 4)])
print("wrote data/net_effect.csv")

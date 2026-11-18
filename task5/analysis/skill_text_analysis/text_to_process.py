"""Does skill text shape the agent's process, even when it does not change outcomes?

Outcome per skill (machine1): mean steps, test commands, test density, patch size,
search commands, cost. Standardised within case (case dummies remove case difficulty).
Features: v2 (36). Test: within-case rank contrast + permutation + BH-FDR over all
feature x outcome pairs.

This is the most sensitive test available: process variables are continuous and have
much more variance than the binary resolved outcome.
"""

import csv
import os
from collections import defaultdict

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

feat_rows = list(csv.DictReader(open(os.path.join(DATA, "skills_v2.csv"), encoding="utf-8-sig")))
feat_names = [k for k in feat_rows[0] if k not in ("skill", "skill_type", "cases", "n_cases")]
F = {r["skill"]: {k: float(r[k]) for k in feat_names} for r in feat_rows}

metrics = list(csv.DictReader(open(os.path.join(DATA, "traj_metrics.csv"), encoding="utf-8-sig")))
m1 = [r for r in metrics if r["machine"] == "machine1"]

OUTCOMES = {
    "steps": lambda r: float(r["steps"]),
    "test_cmds": lambda r: float(r["test_cmds"]),
    "test_per_step": lambda r: float(r["test_cmds"]) / max(float(r["steps"]), 1),
    "search_cmds": lambda r: float(r["search_cmds"]),
    "patch_lines": lambda r: float(r["patch_lines_added"]),
    "cost": lambda r: float(r["cost"] or 0),
    "edit_cmds": lambda r: float(r["edit_cmds"]),
}

# skill x case mean outcome
cell = defaultdict(lambda: defaultdict(list))
for r in m1:
    for name, f in OUTCOMES.items():
        cell[(r["skill"], r["case"])][name].append(f(r))

def skill_means(name):
    means, cases = {}, defaultdict(list)
    for (s, c), d in cell.items():
        if s not in F or not d[name]:
            continue
        means.setdefault(s, []).append(np.mean(d[name]))
        cases[s].append(c)
    return {s: np.mean(v) for s, v in means.items()}

# within-case rank transform for each outcome
def within_case_rank(name):
    ranks = {}
    for c in sorted({k[1] for k in cell}):
        ss = [s for (s, cc) in cell if cc == c and s in F]
        vals = [np.mean(cell[(s, c)][name]) for s in ss]
        rr = stats.rankdata(vals, method="average")
        for s, v in zip(ss, rr):
            ranks.setdefault(s, []).append(v)
    return {s: np.mean(v) for s, v in ranks.items()}

rng = np.random.default_rng(0)
by_case_skills = defaultdict(list)
for (s, c) in cell:
    if s in F:
        by_case_skills[c].append(s)

def contrast(fvals, ranks):
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
        diffs.append(np.mean([ranks[s] for s in hi]) - np.mean([ranks[s] for s in lo]))
    return float(np.mean(diffs)) if diffs else 0.0

results = []
for name in OUTCOMES:
    ranks = within_case_rank(name)
    for f in feat_names:
        fvals = {s: F[s][f] for s in F}
        obs = contrast(fvals, ranks)
        null = []
        for _ in range(3000):
            perm = {}
            for c, ss in by_case_skills.items():
                vals = [fvals[s] for s in ss]
                rng.shuffle(vals)
                for s, v in zip(ss, vals):
                    perm[s] = v
            null.append(contrast(perm, ranks))
        p = (1 + np.sum(np.abs(null) >= abs(obs))) / (1 + len(null))
        # effect direction: correlation in the original (unranked) skill means
        m = skill_means(name)
        xs = np.array([fvals[s] for s in sorted(m)])
        ys = np.array([m[s] for s in sorted(m)])
        rho = stats.spearmanr(xs, ys).statistic
        results.append(dict(outcome=name, feature=f, rank_contrast=obs,
                            rho=rho, p=p))

results.sort(key=lambda r: r["p"])
m = len(results)
prev = 1.0
for i in range(m - 1, -1, -1):
    q = min(prev, results[i]["p"] * m / (i + 1))
    results[i]["q"] = q
    prev = q
results.sort(key=lambda r: r["q"])

print(f"tests: {m} (7 outcomes x 36 features)")
print(f"{'outcome':14s} {'feature':22s} {'rank':>7s} {'rho':>7s} {'p':>7s} {'q':>7s}")
for r in results[:20]:
    print(f"{r['outcome']:14s} {r['feature']:22s} {r['rank_contrast']:7.2f} "
          f"{r['rho']:7.3f} {r['p']:7.3f} {r['q']:7.3f}")
print(f"\nsignificant at q<0.1: {sum(1 for r in results if r['q'] < 0.1)}")
print(f"significant at q<0.05: {sum(1 for r in results if r['q'] < 0.05)}")

with open(os.path.join(DATA, "text_to_process.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)
print("wrote data/text_to_process.csv")

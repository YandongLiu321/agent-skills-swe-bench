"""Step 2b: do skill text features predict within-case performance?

Outcome: per-skill keep rate on machine1 (same instances inside each case, so case
difficulty cancels). Because within-case between-skill variance is ~0 (see
variance_decomp), this is expected to find little. We report every test honestly:

  - pooled Spearman (feature vs keep rate)                 [confounded by case]
  - within-case rank average: for each case, rank the 10 skills by keep rate and
    average the rank of skills above/below each feature's median        [case-controlled]
  - permutation p by shuffling feature values within case (2000x)
  - Benjamini-Hochberg FDR across features

Writes data/feature_tests.csv and prints a compact report.
"""

import csv
import os
from collections import defaultdict

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

runs = [r for r in csv.DictReader(open(os.path.join(DATA, "runs.csv"), encoding="utf-8-sig"))
        if r["machine"] == "machine1" and r["outcome"] in ("kept", "broken")]
skills = list(csv.DictReader(open(os.path.join(DATA, "skills.csv"), encoding="utf-8-sig")))
feat_names = [k for k in skills[0] if k not in ("skill", "skill_type", "cases", "n_cases")]
feature = {r["skill"]: {k: float(r[k]) for k in feat_names} for r in skills}
stype = {r["skill"]: r["skill_type"] for r in skills}

# per skill x case keep rate
cell = defaultdict(lambda: [0, 0])  # [broken, n]
for r in runs:
    cell[(r["skill"], r["case"])][1] += 1
    if r["outcome"] == "broken":
        cell[(r["skill"], r["case"])][0] += 1

# per skill overall keep rate
skill_rate = {}
for s in feature:
    y = n = 0
    for (ss, c), (b, nn) in cell.items():
        if ss == s:
            y += b; n += nn
    skill_rate[s] = 1 - y / n if n else float("nan")

# per-case ranks (1 = best keep rate; ties averaged)
ranks = {}
for c in {k[1] for k in cell}:
    ss = [s for (s, cc) in cell if cc == c]
    rates = [1 - cell[(s, c)][0] / cell[(s, c)][1] for s in ss]
    r = stats.rankdata([-x for x in rates], method="average")
    for s, rv in zip(ss, r):
        ranks.setdefault(s, []).append(rv)

rng = np.random.default_rng(0)


def within_case_contrast(fvals):
    """Mean within-case rank of skills above vs below the case's feature median."""
    diffs = []
    for c in sorted({k[1] for k in cell}):
        ss = [s for (s, cc) in cell if cc == c]
        if len(ss) < 4:
            continue
        v = np.array([fvals[s] for s in ss])
        if np.nanstd(v) == 0:
            continue
        med = np.nanmedian(v)
        hi = [s for s, x in zip(ss, v) if x > med]
        lo = [s for s, x in zip(ss, v) if x < med]
        if not hi or not lo:
            continue
        # average rank (lower rank = better) of high-feature skills minus low-feature
        diffs.append(np.mean([np.mean(ranks[s]) for s in hi]) - np.mean([np.mean(ranks[s]) for s in lo]))
    return float(np.mean(diffs)) if diffs else 0.0


results = []
for f in feat_names:
    fvals = {s: feature[s][f] for s in feature}
    xs = np.array([fvals[s] for s in sorted(feature)])
    ys = np.array([skill_rate[s] for s in sorted(feature)])
    ok = ~np.isnan(xs) & ~np.isnan(ys)
    if ok.sum() < 8 or np.nanstd(xs[ok]) == 0:
        continue
    rho, p_pool = stats.spearmanr(xs[ok], ys[ok])
    obs = within_case_contrast(fvals)
    # permutation: shuffle feature values within each case
    null = []
    by_case = defaultdict(list)
    for (s, c) in cell:
        by_case[c].append(s)
    for _ in range(2000):
        perm = {}
        for c, ss in by_case.items():
            vals = [fvals[s] for s in ss]
            rng.shuffle(vals)
            for s, v in zip(ss, vals):
                perm[s] = v
        null.append(within_case_contrast(perm))
    null = np.array(null)
    p_perm = (1 + np.sum(np.abs(null) >= abs(obs))) / (1 + len(null))
    results.append(dict(feature=f, spearman_pooled=rho, p_pooled=p_pool,
                        rank_contrast=obs, p_perm=p_perm,
                        n_skills=int(ok.sum()),
                        sd_feature=float(np.nanstd(xs[ok]))))

# BH-FDR
results.sort(key=lambda r: r["p_perm"])
m = len(results)
prev = 1.0
for i in range(m - 1, -1, -1):
    q = min(prev, results[i]["p_perm"] * m / (i + 1))
    results[i]["q_perm"] = q
    prev = q
results.sort(key=lambda r: r["rank_contrast"])

out = os.path.join(DATA, "feature_tests.csv")
with open(out, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)

print(f"features tested: {m}  (33 skills, 11 cases)")
print(f"within-case skill variance: tau2=0 by construction check; see variance_decomp.json")
print(f"{'feature':26s} {'rho_pool':>9s} {'rank_diff':>10s} {'p_perm':>9s} {'q':>8s}")
for r in results[:15]:
    print(f"{r['feature']:26s} {r['spearman_pooled']:9.3f} {r['rank_contrast']:10.3f} "
          f"{r['p_perm']:9.3f} {r['q_perm']:8.3f}")
print("\nmin q:", min(r["q_perm"] for r in results))
print("wrote", out)

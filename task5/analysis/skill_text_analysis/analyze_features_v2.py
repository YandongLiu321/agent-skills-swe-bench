"""v2 feature analysis on corrected outcomes.

Outcome: per-skill keep rate on machine1, computed twice:
  raw      : all 53 broken
  corrected: exclude the 2 requests-1921 arms proven to be a network artifact
             (identical patch passed 8/10 times; failures show 44x httpbin 502)

Tests for each feature:
  - pooled Spearman (for reference only; confounded by case)
  - within-case: for each case rank the 10 skills by keep rate; contrast mean rank of
    skills above vs below the case medians of the feature
  - permutation p (shuffle feature within case, 5000x), BH-FDR
  - top-3 vs bottom-3 per case: difference in feature values, case-clustered bootstrap CI
Writes data/feature_tests_v2.csv and prints the summary.
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
skills = list(csv.DictReader(open(os.path.join(DATA, "skills_v2.csv"), encoding="utf-8-sig")))
feat_names = [k for k in skills[0] if k not in ("skill", "skill_type", "cases", "n_cases")]
F = {r["skill"]: {k: float(r[k]) for k in feat_names} for r in skills}

NETWORK_ARTIFACTS = {("psf__requests-1921", "test-driven-development"),
                     ("psf__requests-1921", "verification-before-completion")}


def keep_rates(corrected):
    cell = defaultdict(lambda: [0, 0])  # [broken, n]
    for r in runs:
        if corrected and (r["instance"], r["skill"]) in NETWORK_ARTIFACTS:
            r = dict(r, outcome="kept")
        cell[(r["skill"], r["case"])][1] += 1
        if r["outcome"] == "broken":
            cell[(r["skill"], r["case"])][0] += 1
    overall = {}
    for s in F:
        y = n = 0
        for (ss, c), (b, nn) in cell.items():
            if ss == s:
                y += b; n += nn
        overall[s] = 1 - y / n if n else float("nan")
    return cell, overall


def ranks_by_case(cell):
    ranks = {}
    for c in sorted({k[1] for k in cell}):
        ss = [s for (s, cc) in cell if cc == c]
        rates = [1 - cell[(s, c)][0] / cell[(s, c)][1] for s in ss]
        r = stats.rankdata([-x for x in rates], method="average")
        for s, rv in zip(ss, r):
            ranks.setdefault(s, []).append(rv)
    return ranks


def within_case_contrast(fvals, cell, ranks):
    diffs = []
    for c in sorted({k[1] for k in cell}):
        ss = [s for (s, cc) in cell if cc == c]
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


def top_bottom_delta(fvals, cell, k=3):
    """Within each case: mean feature of top-k skills minus bottom-k (keep-rate)."""
    deltas = []
    for c in sorted({k2[1] for k2 in cell}):
        ss = [s for (s, cc) in cell if cc == c]
        if len(ss) < 2 * k:
            continue
        rates = {s: 1 - cell[(s, c)][0] / cell[(s, c)][1] for s in ss}
        order = sorted(ss, key=lambda s: -rates[s])
        top, bot = order[:k], order[-k:]
        deltas.append(np.mean([fvals[s] for s in top]) - np.mean([fvals[s] for s in bot]))
    return deltas


def analyze(corrected, label):
    cell, overall = keep_rates(corrected)
    ranks = ranks_by_case(cell)
    rng = np.random.default_rng(0)
    by_case = defaultdict(list)
    for r in runs:
        by_case[r["case"]].append(r)

    out = []
    for f in feat_names:
        fvals = {s: F[s][f] for s in F}
        xs = np.array([fvals[s] for s in sorted(F)])
        ys = np.array([overall[s] for s in sorted(F)])
        ok = ~np.isnan(xs) & ~np.isnan(ys)
        if ok.sum() < 8 or np.std(xs[ok]) == 0:
            continue
        rho, _ = stats.spearmanr(xs[ok], ys[ok])
        obs = within_case_contrast(fvals, cell, ranks)
        null = []
        for _ in range(5000):
            perm = {}
            for c, rs in by_case.items():
                ss = list({x["skill"] for x in rs})
                vals = [fvals[s] for s in ss]
                rng.shuffle(vals)
                for s, v in zip(ss, vals):
                    perm[s] = v
            null.append(within_case_contrast(perm, cell, ranks))
        p_perm = (1 + np.sum(np.abs(null) >= abs(obs))) / (1 + len(null))

        deltas = np.array(top_bottom_delta(fvals, cell))
        # bootstrap over cases
        boot = [np.mean(rng.choice(deltas, size=len(deltas), replace=True)) for _ in range(2000)]
        lo, hi = np.quantile(boot, [0.025, 0.975])
        out.append(dict(cohort=label, feature=f, spearman_pooled=rho,
                        rank_contrast=obs, p_perm=p_perm,
                        top_bottom_delta=float(np.mean(deltas)),
                        ci_low=float(lo), ci_high=float(hi),
                        n_cases=len(deltas)))

    out.sort(key=lambda r: r["p_perm"])
    m = len(out)
    prev = 1.0
    for i in range(m - 1, -1, -1):
        q = min(prev, out[i]["p_perm"] * m / (i + 1))
        out[i]["q_perm"] = q
        prev = q
    out.sort(key=lambda r: -abs(r["top_bottom_delta"]))
    return out


def show(res, label):
    print(f"\n=== {label} ===")
    print(f"{'feature':22s} {'rho':>7s} {'rank':>7s} {'p':>7s} {'q':>7s} "
          f"{'top-bot':>8s} {'95% CI':>18s}")
    for r in res[:18]:
        print(f"{r['feature']:22s} {r['spearman_pooled']:7.3f} {r['rank_contrast']:7.2f} "
              f"{r['p_perm']:7.3f} {r['q_perm']:7.3f} {r['top_bottom_delta']:8.2f} "
              f"[{r['ci_low']:7.2f}, {r['ci_high']:7.2f}]")
    print(f"  min q = {min(r['q_perm'] for r in res):.3f}; "
          f"features with CI excluding 0: "
          f"{sum(1 for r in res if r['ci_low'] * r['ci_high'] > 0)} / {len(res)}")


raw = analyze(False, "raw")
cor = analyze(True, "corrected")
show(raw, "raw (53 broken)")
show(cor, "corrected (51 broken; requests artifacts removed)")

with open(os.path.join(DATA, "feature_tests_v2.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(cor[0].keys()))
    w.writeheader()
    w.writerows(raw + cor)
print("\nwrote data/feature_tests_v2.csv")

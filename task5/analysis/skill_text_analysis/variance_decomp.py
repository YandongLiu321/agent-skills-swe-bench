"""Step 1: how much of the breakage variance is instance vs skill vs case?

Primary dataset: machine1 (complete design: 135 instances x 10 skills = 1350 trials,
official verdicts). machine2 sent only its 60 valid failures, so its kept runs have no
instance ids; machine2 is used only for an arm-level cross-check.

Estimator (within a parent stratum):
  observed variance of group rates around the parent mean,
  minus the binomial sampling variance E[p(1-p)/n],
  = between-group variance component (method of moments, unequal-n weighted).
LR tests compare a constant rate within each parent vs a separate rate per group.

Writes: data/variance_decomp.json
"""

import csv
import json
import os
from collections import defaultdict

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

rows = list(csv.DictReader(open(os.path.join(DATA, "runs.csv"), encoding="utf-8-sig")))
m1 = [r for r in rows if r["machine"] == "machine1" and r["outcome"] in ("broken", "kept")]
for r in m1:
    r["y"] = 1 if r["outcome"] == "broken" else 0
m2 = [r for r in rows if r["machine"] == "machine2" and r["outcome"] == "broken"]
m2_denom = {"astropy": 7, "django": 66, "matplotlib": 9, "pylint": 2, "pytest": 5,
            "scikit-learn": 12, "sphinx": 10, "sympy": 18, "xarray": 6}

print(f"machine1 trials: {len(m1)}, broken: {sum(r['y'] for r in m1)}")
print(f"machine2 failed arms: {len(m2)} over {len({(r['case'], r['skill']) for r in m2})} arms")


def tau2_between(rows, key, parent=None):
    """Between-group variance of rates (residual to explicit binomial noise)."""
    strata = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        p = r[parent] if parent else "all"
        strata[p][r[key]][0] += r["y"]
        strata[p][r[key]][1] += 1
    obs_dev, exp_dev, weights = [], [], []
    for p, groups in strata.items():
        Y = sum(y for y, _ in groups.values())
        N = sum(n for _, n in groups.values())
        pbar = Y / N if N else 0
        for y, n in groups.values():
            if n == 0:
                continue
            obs_dev.append(n * (y / n - pbar) ** 2)
            exp_dev.append(pbar * (1 - pbar))
            weights.append(n)
    if not obs_dev:
        return 0.0, 0.0, 0.0, 0
    obs, exp, w = np.array(obs_dev), np.array(exp_dev), np.array(weights)
    # unbiased-ish: observed squared deviation minus expected binomial contribution
    tau2 = max(0.0, float(np.sum(obs - exp) / np.sum(w)))
    return tau2, float(np.average(obs / w, weights=w)), float(np.average(exp / w, weights=w)), len(obs_dev)


def lr_test(rows, key, parent=None):
    strata = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        p = r[parent] if parent else "all"
        strata[p][r[key]][0] += r["y"]
        strata[p][r[key]][1] += 1
    ll0 = ll1 = 0.0
    n_groups = n_censored = 0
    for p, groups in strata.items():
        Y = sum(y for y, _ in groups.values())
        N = sum(n for _, n in groups.values())
        if Y == 0 or Y == N:
            n_censored += len(groups)
            continue
        pbar = Y / N
        ll0 += Y * np.log(pbar) + (N - Y) * np.log(1 - pbar)
        for y, n in groups.values():
            n_groups += 1
            if 0 < y < n:
                ph = y / n
                ll1 += y * np.log(ph) + (n - y) * np.log(1 - ph)
            elif y == 0 or y == n:
                # saturated model fits 0 or 1 exactly -> ll 0 for that group
                pass
    df = n_groups - len(strata) + n_censored
    df = max(df, 1)
    chi2 = 2 * (ll1 - ll0)
    return chi2, df, stats.chi2.sf(chi2, df), n_censored


report = {"n_trials": len(m1), "n_broken": int(sum(r["y"] for r in m1))}
print("\n=== variance components: machine1 (1350 trials) ===")
for key, parent in (("case", None), ("skill", None), ("instance", None),
                    ("skill", "case"), ("instance", "case")):
    tau2, obs, exp, g = tau2_between(m1, key, parent)
    label = f"{key}" + (f" within {parent}" if parent else "")
    print(f"{label:22s}: groups={g:4d}  var_obs={obs:.3e}  var_binom={exp:.3e}  "
          f"tau2={tau2:.3e}  sd={tau2 ** 0.5:.3f}")
    report[f"tau2_{label.replace(' ', '_')}"] = dict(tau2=tau2, observed=obs, binomial=exp,
                                                    groups=g, sd=tau2 ** 0.5)

print("\n=== LR tests (machine1) ===")
for key, parent in (("case", None), ("skill", "case"), ("instance", "case")):
    chi2, df, p, cens = lr_test(m1, key, parent)
    label = f"{key}" + (f" within {parent}" if parent else "")
    print(f"{label:22s}: chi2={chi2:8.2f}  df={df:4d}  p={p:.3g}  (all-0/all-1 groups: {cens})")
    report[f"lr_{label.replace(' ', '_')}"] = dict(chi2=chi2, df=df, p=p, censored=cens)

# permutation: shuffle skill labels within case
rng = np.random.default_rng(0)
by_case = defaultdict(list)
for r in m1:
    by_case[r["case"]].append(r)
obs_tau = report["tau2_skill_within_case"]["tau2"]
null = []
for _ in range(2000):
    sh = []
    for c, rs in by_case.items():
        labels = [r["skill"] for r in rs]
        rng.shuffle(labels)
        sh.extend(dict(r, skill=l) for r, l in zip(rs, labels))
    null.append(tau2_between(sh, "skill", "case")[0])
null = np.array(null)
p_perm = (1 + np.sum(null >= obs_tau)) / (1 + len(null))
print(f"\npermutation skill-within-case: observed tau2={obs_tau:.3e}  "
      f"null median={np.median(null):.3e}  q95={np.quantile(null, 0.95):.3e}  p={p_perm:.3f}")
report["perm_skill_within_case"] = dict(observed=obs_tau, null_median=float(np.median(null)),
                                        null_q95=float(np.quantile(null, 0.95)), p=float(p_perm))

obs_tau_i = report["tau2_instance_within_case"]["tau2"]
null_i = []
for _ in range(500):
    sh = []
    for c, rs in by_case.items():
        labels = [r["instance"] for r in rs]
        rng.shuffle(labels)
        sh.extend(dict(r, instance=l) for r, l in zip(rs, labels))
    null_i.append(tau2_between(sh, "instance", "case")[0])
null_i = np.array(null_i)
p_perm_i = (1 + np.sum(null_i >= obs_tau_i)) / (1 + len(null_i))
print(f"permutation instance-within-case: observed tau2={obs_tau_i:.3e}  "
      f"null median={np.median(null_i):.3e}  p={p_perm_i:.3f}")
report["perm_instance_within_case"] = dict(observed=obs_tau_i, null_median=float(np.median(null_i)),
                                           p=float(p_perm_i))

# ---- machine2 arm-level cross-check ----
print("\n=== machine2 arm-level rates (21 instances) ===")
arm = defaultdict(lambda: [0, 0])
for r in m2:
    arm[(r["case"], r["skill"])][0] += 1
    arm[(r["case"], r["skill"])][1] = m2_denom[r["case"]]
m2_rows = []
for (c, s), (y, n) in sorted(arm.items()):
    m2_rows.append(dict(case=c, skill=s, y=y, n=n, y_=y, n_=n))
tau2, obs, exp, g = tau2_between(m2_rows, "skill", "case")
print(f"skill within case: groups={g}  var_obs={obs:.3e}  binom={exp:.3e}  tau2={tau2:.3e}")
report["m2_armlevel_skill_within_case"] = dict(tau2=tau2, observed=obs, binomial=exp, groups=g)
chi2, df, p, cens = lr_test(m2_rows, "skill", "case")
print(f"LR skill within case: chi2={chi2:.2f} df={df} p={p:.3g}")
report["m2_lr_skill_within_case"] = dict(chi2=chi2, df=df, p=p)

json.dump(report, open(os.path.join(DATA, "variance_decomp.json"), "w"), indent=2)
print("\nwrote data/variance_decomp.json")

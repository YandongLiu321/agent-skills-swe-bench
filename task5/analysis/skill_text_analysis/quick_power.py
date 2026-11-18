"""Quick test 3: power of the current design and of the proposed 2x2x2 experiment."""

import json
import os
from collections import defaultdict

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

# actual design: instances per case in machine1, 10 skills each
share = json.load(open(os.path.join(REPO, "task5", "split", "machine1.json"), encoding="utf-8"))
n_inst = {c: len(v) for c, v in share.items()}
base = 0.042  # observed break rate

print("### current design: power of the within-case top-3 vs bottom-3 sign test")
print("(assumes an ideal feature that perfectly ranks the true skill effect)")
rng = np.random.default_rng(0)
for tau in (0.005, 0.01, 0.02, 0.03, 0.05):
    hits = 0
    trials = 400
    for _ in range(trials):
        signs = []
        for c, n in n_inst.items():
            # 10 skills with true effects; observed break rates from binomial draws
            eff = rng.normal(0, tau, 10)
            p = np.clip(base + eff, 0, 1)
            obs = rng.binomial(n, p) / n
            order = np.argsort(-obs)  # best (lowest break) first
            top, bot = order[:3], order[-3:]
            # ideal feature ranks true effect; lower feature = better skill
            feat = -eff
            signs.append(np.mean(feat[top]) < np.mean(feat[bot]))
        # two-sided sign test over 11 cases; p<0.05 needs >=9/11 (two-sided ~0.065) -> use >=10
        k = sum(signs)
        p_sign = stats.binomtest(k, len(signs), 0.5).pvalue
        hits += p_sign < 0.05
    print(f"  skill sd = {tau*100:.1f}pp -> power ~ {hits/trials*100:.0f}%")

print("\n### proposed 2x2x2 experiment: two-proportion power, n=1215 runs per variant")
for p2 in (0.05, 0.06, 0.07, 0.08, 0.10):
    p1 = 0.042
    n = 1215
    se = np.sqrt(p1 * (1 - p1) / n + p2 * (1 - p2) / n)
    z = abs(p2 - p1) / se
    power = 1 - stats.norm.cdf(1.96 - z) + stats.norm.cdf(-1.96 - z)
    print(f"  baseline {p1*100:.1f}% -> {p2*100:.1f}% (delta {(p2-p1)*100:.1f}pp): power ~ {power*100:.0f}%")
# minimum detectable difference at 80% power
from scipy.optimize import brentq
def power_for(delta):
    p1, n = 0.042, 1215
    p2 = p1 + delta
    se = np.sqrt(p1 * (1 - p1) / n + p2 * (1 - p2) / n)
    z = delta / se
    return 1 - stats.norm.cdf(1.96 - z) + stats.norm.cdf(-1.96 - z) - 0.8
mdd = brentq(power_for, 0.001, 0.1)
print(f"  minimum detectable difference at 80% power: {mdd*100:.2f}pp")

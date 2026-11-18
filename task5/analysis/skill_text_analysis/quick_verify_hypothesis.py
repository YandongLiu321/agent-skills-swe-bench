"""Test the verification-density hypothesis on the net effect, and control for
length / imperative density / skill type.
"""

import csv
import json
import os
import re
from collections import defaultdict

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DATA = os.path.join(HERE, "data")
SKILLS = os.path.join(REPO, "task5", "skills")
SRC = {"pydata": "xarray", "mwaskom": "seaborn", "psf": "requests",
       "pylint-dev": "pylint", "pytest-dev": "pytest", "sphinx-doc": "sphinx", "pallets": "flask"}
norm = lambda c: SRC.get(c, c)

verdicts = json.load(open(os.path.join(REPO, "task5", "split", "baseline_verdicts.json"), encoding="utf-8"))
N = {c: v["submitted"] for c, v in verdicts.items()}
P = {c: len(v["resolved"]) for c, v in verdicts.items()}
F = {c: N[c] - P[c] for c in N}

rescue = defaultdict(lambda: [0, 0])
with open(os.path.join(REPO, "other_machine", "machine1", "all_experiment_runs(2).csv"), encoding="utf-8-sig") as fh:
    for row in csv.DictReader(fh):
        if row["cohort"] != "group":
            continue
        c = norm(row["case_id"].split("__")[0])
        rescue[(row["skill_name"], c)][1] += 1
        rescue[(row["skill_name"], c)][0] += 1 if row["resolved"] == "1" else 0

NET = {("psf__requests-1921", "test-driven-development"),
       ("psf__requests-1921", "verification-before-completion")}
broken = defaultdict(lambda: [0, 0])
for r in csv.DictReader(open(os.path.join(DATA, "runs.csv"), encoding="utf-8-sig")):
    if r["machine"] != "machine1" or r["outcome"] not in ("kept", "broken"):
        continue
    o = "kept" if (r["instance"], r["skill"]) in NET else r["outcome"]
    broken[(r["skill"], r["case"])][1] += 1
    broken[(r["skill"], r["case"])][0] += 1 if o == "broken" else 0

net = {}
for (s, c), (b, n) in broken.items():
    if (s, c) not in rescue:
        continue
    rr, rn = rescue[(s, c)]
    net[(s, c)] = (rr / rn) * (F[c] / N[c]) - (b / n) * (P[c] / N[c])


def measure(s):
    text = open(os.path.join(SKILLS, s, "SKILL.md"), encoding="utf-8").read()
    body = re.split(r"^---\n.*?\n---\n", text, maxsplit=1, flags=re.S)[-1] if text.startswith("---") else text
    words = re.findall(r"[A-Za-z][A-Za-z0-9_'-]*", body)
    nw = max(len(words), 1)
    v1 = len(re.findall(r"\b(run|execute|check|verify|test|validate|confirm)\b[^.]*\b(test|suite|command|output|result)s?\b", body, re.I)) / nw * 1000
    imp = len(re.findall(r"\b(read|inspect|run|execute|check|verify|test|fix|update|change|add|remove|write|create|edit|modify|analyze|identify|report|document|install|build|lint|format|commit|diff)\b", body, re.I)) / nw * 1000
    return dict(v1=v1, words=len(words), imp=imp, sentences=len(re.findall(r"(?<=[.!?])\s+", body)))


M = {s: measure(s) for s in {k[0] for k in net}}
stype = {}
for r in csv.DictReader(open(os.path.join(DATA, "runs.csv"), encoding="utf-8-sig")):
    stype[r["skill"]] = r["skill_type"]

print("### net effect vs v1 (verification density)")
deltas = []
for c in sorted({k[1] for k in net}):
    ss = [s for (s, cc) in net if cc == c and s in M]
    if len(ss) < 6:
        continue
    order = sorted(ss, key=lambda s: -net[(s, c)])
    top, bot = order[:3], order[-3:]
    deltas.append(np.mean([M[s]["v1"] for s in top]) - np.mean([M[s]["v1"] for s in bot]))
d = np.array(deltas)
pos = int((d < 0).sum())
print(f"  top-3 (best net) lower v1 in {pos}/{len(d)} cases, mean={d.mean():+.2f}, "
      f"sign p={stats.binomtest(pos, len(d), 0.5).pvalue:.3f}")

# aggregate per skill
by = defaultdict(list)
for (s, c), v in net.items():
    by[s].append(v)
print("\n### control checks")
xs = np.array([M[s]["v1"] for s in sorted(by)])
ys = np.array([np.mean(by[s]) for s in sorted(by)])
print("  v1 vs mean net: rho=%.3f p=%.3f" % stats.spearmanr(xs, ys))
for ctrl in ("words", "imp", "sentences"):
    zs = np.array([M[s][ctrl] for s in sorted(by)])
    print(f"  v1 vs {ctrl}: rho=%.3f p=%.3f" % stats.spearmanr(xs, zs))
# partial spearman of v1 vs net controlling for words
def partial(x, y, z):
    rxy = stats.spearmanr(x, y).statistic
    rxz = stats.spearmanr(x, z).statistic
    ryz = stats.spearmanr(y, z).statistic
    return (rxy - rxz * ryz) / np.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
for ctrl in ("words", "imp"):
    zs = np.array([M[s][ctrl] for s in sorted(by)])
    print(f"  partial rho(v1, net | {ctrl}) = {partial(xs, ys, zs):.3f}")
# dedicated vs generic
for t in ("dedicated", "generic"):
    ss = [s for s in by if stype.get(s) == t]
    print(f"  {t:9s}: n={len(ss):2d} mean v1={np.mean([M[s]['v1'] for s in ss]):6.2f} "
          f"mean net={np.mean([np.mean(by[s]) for s in ss])*100:+.2f}pp")

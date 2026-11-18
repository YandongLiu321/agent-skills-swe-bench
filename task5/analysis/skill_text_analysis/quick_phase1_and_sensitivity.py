"""Quick tests 2 and 4:
  2) does "verification density" predict phase-1 rescue as well? (two-sided consistency)
  4) does the direction survive alternative operationalisations of verification density?
"""

import csv
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

# phase-1 rescue per case x skill
rescue = defaultdict(lambda: [0, 0])
with open(os.path.join(REPO, "other_machine", "machine1", "all_experiment_runs(2).csv"), encoding="utf-8-sig") as fh:
    for row in csv.DictReader(fh):
        if row["cohort"] != "group":
            continue
        c = norm(row["case_id"].split("__")[0])
        rescue[(row["skill_name"], c)][1] += 1
        rescue[(row["skill_name"], c)][0] += 1 if row["resolved"] == "1" else 0

rate = {k: y / n for k, (y, n) in rescue.items()}
skills = sorted({s for s, _ in rate})

# alternative verification measures
def measures(text):
    body = re.split(r"^---\n.*?\n---\n", text, maxsplit=1, flags=re.S)[-1] if text.startswith("---") else text
    words = re.findall(r"[A-Za-z][A-Za-z0-9_'-]*", body)
    nw = max(len(words), 1)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", body) if len(s.strip()) > 15]
    return {
        "v1_sentences": len(re.findall(r"\b(run|execute|check|verify|test|validate|confirm)\b[^.]*\b(test|suite|command|output|result)s?\b", body, re.I)) / nw * 1000,
        "v2_testwords": len(re.findall(r"\b(test|tests|pytest|unittest|suite)\b", body, re.I)) / nw * 1000,
        "v3_testcommands": len(re.findall(r"\b(pytest|unittest|python -m pytest|tox|nosetests)\b", body, re.I)) / nw * 1000,
        "v4_verify_per_sentence": len(re.findall(r"\b(verify|check|validate|confirm)\b", body, re.I)) / max(len(sentences), 1),
        "v5_assertwords": len(re.findall(r"\b(assert|expect|should (be|pass|fail)|must (pass|fail))\b", body, re.I)) / nw * 1000,
    }

m = {}
for s in skills:
    p = os.path.join(SKILLS, s, "SKILL.md")
    if not os.path.isfile(p):
        continue
    m[s] = measures(open(p, encoding="utf-8").read())

print("### Test 2: verification density vs phase-1 rescue (within case)")
for feat in ("v1_sentences", "v2_testwords", "v3_testcommands", "v4_verify_per_sentence", "v5_assertwords"):
    deltas = []
    detail = []
    for c in sorted({k[1] for k in rate}):
        ss = [s for (s, cc) in rate if cc == c and s in m]
        if len(ss) < 6:
            continue
        vals = {s: m[s][feat] for s in ss}
        r = {s: rate[(s, c)] for s in ss}
        order = sorted(ss, key=lambda s: -r[s])
        top, bot = order[:3], order[-3:]
        d = np.mean([vals[s] for s in top]) - np.mean([vals[s] for s in bot])
        deltas.append(d)
        detail.append((c, d))
    if not deltas:
        continue
    d = np.array(deltas)
    pos = int((d < 0).sum())
    p = stats.binomtest(pos, len(d), 0.5).pvalue
    print(f"  {feat:24s} top<bottom in {pos}/{len(d)} cases  mean={d.mean():+.2f}  sign p={p:.3f}")

print("\n### Test 4: same direction under alternative measures (phase-2 keep rate)")
# phase-2 keep rate per skill x case
cell = defaultdict(lambda: [0, 0])
NET = {("psf__requests-1921", "test-driven-development"),
       ("psf__requests-1921", "verification-before-completion")}
for r in csv.DictReader(open(os.path.join(DATA, "runs.csv"), encoding="utf-8-sig")):
    if r["machine"] != "machine1" or r["outcome"] not in ("kept", "broken"):
        continue
    o = "kept" if (r["instance"], r["skill"]) in NET else r["outcome"]
    cell[(r["skill"], r["case"])][1] += 1
    cell[(r["skill"], r["case"])][0] += 1 if o == "broken" else 0
keep = {(s, c): 1 - b / n for (s, c), (b, n) in cell.items()}

for feat in ("v1_sentences", "v2_testwords", "v3_testcommands", "v4_verify_per_sentence", "v5_assertwords"):
    deltas = []
    for c in sorted({k[1] for k in keep}):
        ss = [s for (s, cc) in keep if cc == c and s in m]
        if len(ss) < 6:
            continue
        vals = {s: m[s][feat] for s in ss}
        r = {s: keep[(s, c)] for s in ss}
        order = sorted(ss, key=lambda s: -r[s])
        top, bot = order[:3], order[-3:]
        deltas.append(np.mean([vals[s] for s in top]) - np.mean([vals[s] for s in bot]))
    d = np.array(deltas)
    pos = int((d < 0).sum())
    p = stats.binomtest(pos, len(d), 0.5).pvalue
    print(f"  {feat:24s} top<bottom in {pos}/{len(d)} cases  mean={d.mean():+.2f}  sign p={p:.3f}")

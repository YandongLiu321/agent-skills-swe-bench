"""Per-case best/worst skills and their text profiles (for close reading)."""

import csv
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

runs = [r for r in csv.DictReader(open(os.path.join(DATA, "runs.csv"), encoding="utf-8-sig"))
        if r["machine"] == "machine1" and r["outcome"] in ("kept", "broken")]
skills = {r["skill"]: r for r in csv.DictReader(open(os.path.join(DATA, "skills_v2.csv"), encoding="utf-8-sig"))}
NETWORK = {("psf__requests-1921", "test-driven-development"),
           ("psf__requests-1921", "verification-before-completion")}

cell = defaultdict(lambda: [0, 0])
for r in runs:
    outcome = "kept" if (r["instance"], r["skill"]) in NETWORK else r["outcome"]
    cell[(r["skill"], r["case"])][1] += 1
    if outcome == "broken":
        cell[(r["skill"], r["case"])][0] += 1

print("### per case: best and worst skills")
print("| case | n | best (kept) | worst (kept) |")
print("|---|---:|---|---|")
for c in sorted({k[1] for k in cell}, key=lambda x: -cell[(next(s for (s, cc) in cell if cc == x), x)][1]):
    ss = [s for (s, cc) in cell if cc == c]
    n = cell[(ss[0], c)][1]
    rates = {s: 1 - cell[(s, c)][0] / cell[(s, c)][1] for s in ss}
    order = sorted(ss, key=lambda s: (-rates[s], s))
    best, worst = order[0], order[-1]
    print(f"| {c} | {n} | `{best}` {rates[best]*100:.1f}% | `{worst}` {rates[worst]*100:.1f}% |")

print("\n### text profile of django's best/worst (n=59, most power)")
for s in ("debugging-and-error-recovery", "test-driven-development", "django-security"):
    x = skills[s]
    print(f"\n--- {s}  (kept {1-cell[(s,'django')][0]/cell[(s,'django')][1]*100:.1f}%)")
    for k in ("body_words", "est_tokens", "heading_count", "sec_workflow", "sec_examples",
              "sec_verification", "sec_antipattern", "sec_scope", "sec_output",
              "paths", "commands", "verify_sentences", "hard", "soft", "conditionals",
              "imperatives", "patch_words", "hard_per1k", "verify_per1k"):
        print(f"  {k:20s} {x[k]}")

print("\n### headings of the three")
import re
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for s in ("debugging-and-error-recovery", "test-driven-development", "django-security"):
    body = open(os.path.join(REPO, "task5", "skills", s, "SKILL.md"), encoding="utf-8").read()
    heads = re.findall(r"^(#{1,6})\s+(.*)$", body, re.M)
    print(f"\n--- {s} ({len(heads)} headings)")
    print("  " + " | ".join(h[1][:40] for h in heads[:18]))

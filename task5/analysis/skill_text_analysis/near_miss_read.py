"""For each near-miss broken run, show exactly which changed lines differ from the
best kept patch, and print the skill's guidance that is closest to that decision.
"""

import csv
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
M1 = os.path.join(REPO, "other_machine", "machine1", "machine1_全部轨迹")
DATA = os.path.join(HERE, "data")

NEAR = [
    ("django__django-10973", "django-patterns"),
    ("django__django-10973", "django-verification"),
    ("django__django-13837", "django-perf-review"),
    ("django__django-13837", "test-driven-development"),
    ("django__django-16560", "django-security"),
]

outcome = {}
for r in csv.DictReader(open(os.path.join(DATA, "runs.csv"), encoding="utf-8-sig")):
    if r["machine"] == "machine1":
        outcome[(r["instance"], r["skill"])] = r["outcome"]


def load(inst, skill):
    p = os.path.join(M1, "skills", inst, skill, inst + ".traj.json")
    d = json.load(open(p, encoding="utf-8"))
    return d.get("info", {}).get("submission") or ""


def lineset(s):
    return {l.strip() for l in s.splitlines()
            if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))}


def best_kept(inst):
    best = None
    for (i, s), o in outcome.items():
        if i != inst or o != "kept":
            continue
        sub = load(i, s)
        # pick the kept patch with the most lines (most complete)
        n = len(lineset(sub))
        if best is None or n > best[0]:
            best = (n, s, sub)
    return best


for inst, skill in NEAR:
    sub = load(inst, skill)
    kept = best_kept(inst)
    if not kept:
        continue
    b, k = lineset(sub), lineset(kept[2])
    only_b = sorted(b - k)[:8]
    only_k = sorted(k - b)[:8]
    print("=" * 100)
    print(f"{inst}  broken arm = {skill}   kept reference = {kept[1]}")
    print(f"  broken patch: {len(sub)} chars, {len(b)} changed lines")
    print(f"  kept patch  : {len(kept[2])} chars, {len(k)} changed lines")
    print("  lines only in the BROKEN patch:")
    for l in only_b:
        print("    ", l[:160])
    print("  lines only in the KEPT patch:")
    for l in only_k:
        print("    ", l[:160])

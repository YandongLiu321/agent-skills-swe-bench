"""Look for identical submitted patches with different verdicts (flaky-eval smoking gun),
and characterise the discrimination power of patch similarity.

If two arms submit the exact same patch and one is resolved while the other is not,
the skill cannot be the cause of that break.
"""

import csv
import hashlib
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
M1 = os.path.join(REPO, "other_machine", "machine1", "machine1_全部轨迹")
DATA = os.path.join(HERE, "data")

outcome = {}
for r in csv.DictReader(open(os.path.join(DATA, "runs.csv"), encoding="utf-8-sig")):
    if r["machine"] == "machine1":
        outcome[(r["instance"], r["skill"])] = r["outcome"]

by_inst = defaultdict(list)
for dp, _, fs in os.walk(os.path.join(M1, "skills")):
    for f in fs:
        if not f.endswith(".traj.json"):
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, os.path.join(M1, "skills")).split(os.sep)
        inst, skill = rel[0], rel[1]
        d = json.load(open(p, encoding="utf-8"))
        sub = d.get("info", {}).get("submission") or ""
        # normalize: strip trailing whitespace, sort? keep order but normalize CRLF
        norm = "\n".join(l.rstrip() for l in sub.replace("\r\n", "\n").splitlines()).strip()
        by_inst[inst].append(dict(skill=skill, outcome=outcome.get((inst, skill)),
                                  sha=hashlib.sha256(norm.encode()).hexdigest()[:16],
                                  sub=norm,
                                  steps=(d.get("info", {}).get("model_stats") or {}).get("api_calls")))

print("### instances where identical patch text got both verdicts")
found = 0
for inst, arms in sorted(by_inst.items()):
    groups = defaultdict(list)
    for a in arms:
        groups[a["sha"]].append(a)
    for sha, g in groups.items():
        outs = {x["outcome"] for x in g}
        if len(g) > 1 and len(outs) > 1:
            found += 1
            print(f"  {inst}: {len(g)} arms share identical patch, verdicts={sorted(outs)}")
            for x in g:
                print(f"      {x['skill']:32s} {x['outcome']:7s} steps={x['steps']}")
print(f"\ninstances with identical-patch-different-verdict: {found}")

print("\n### exact-identical patches within the same verdict (sanity)")
same = 0
for inst, arms in sorted(by_inst.items()):
    groups = defaultdict(list)
    for a in arms:
        groups[a["sha"]].append(a)
    for sha, g in groups.items():
        if len(g) > 1:
            same += 1
print(f"groups of >=2 identical patches (any verdict): {same}")

# do broken patches differ from each other more than kept patches do?
print("\n### spread of patch content")
for inst, arms in sorted(by_inst.items()):
    for o in ("broken", "kept"):
        vals = [a for a in arms if a["outcome"] == o]
        if len(vals) < 2:
            continue
    # summary printed elsewhere (patch_similarity.csv)

"""Summarise the recheck eval reports for the two identical-patch experiments."""

import glob
import json
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
REPORTS = os.path.join(REPO, "task5", "eval_reports")

for case, arm_prefix, inst in (
    ("django", "recheck-13089", "django__django-13089"),
    ("requests", "recheck-1921", "psf__requests-1921"),
):
    print(f"### {inst}")
    files = sorted(glob.glob(os.path.join(REPORTS, f"*{case}__{arm_prefix}__r*.json")))
    if not files:
        print("  (no reports yet)")
        continue
    verdicts = []
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        if "resolved_ids" in d:
            res = inst in (d.get("resolved_ids") or [])
            unres = inst in (d.get("unresolved_ids") or [])
            empty = inst in (d.get("empty_patch_ids") or [])
            verdicts.append(res)
            print(f"  {os.path.basename(f)}: resolved={res} unresolved={unres} "
                  f"empty={empty} submitted={d.get('submitted_instances')} "
                  f"failure_reasons={d.get('failure_reasons')}")
        else:
            v = d.get(inst) or {}
            ts = v.get("tests_status") or {}
            verdicts.append(bool(v.get("resolved")))
            print(f"  {os.path.basename(f)}: resolved={v.get('resolved')} "
                  f"F2P fail={len(ts.get('FAIL_TO_PASS', {}).get('failure', []))} "
                  f"P2P fail={len(ts.get('PASS_TO_PASS', {}).get('failure', []))}")
    print(f"  -> {sum(verdicts)}/{len(verdicts)} resolved")

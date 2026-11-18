"""Prepare the two quick re-evaluation experiments.

  django__django-13089 / test-driven-development   x3 repeats
  psf__requests-1921  / test-driven-development   x5 repeats

Each repeat becomes its own arm dir under task5/runs/<case>/recheck-...@rN/ with a
preds.json holding the exact patch from machine1. run_eval.py then scores them;
the arm names deliberately avoid colliding with existing arms.
"""

import json
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
M1 = os.path.join(REPO, "other_machine", "machine1", "machine1_全部轨迹", "skills")
RUNS = os.path.join(REPO, "task5", "runs")


def patch(inst, skill):
    p = os.path.join(M1, inst, skill, inst + ".traj.json")
    d = json.load(open(p, encoding="utf-8"))
    return d["info"]["submission"]


def write_arm(case, arm, inst, sub):
    d = os.path.join(RUNS, case, arm)
    os.makedirs(d, exist_ok=True)
    preds = {inst: {"model_name_or_path": "deepseek/deepseek-v4-flash",
                    "instance_id": inst, "model_patch": sub}}
    with open(os.path.join(d, "preds.json"), "w", encoding="utf-8") as f:
        json.dump(preds, f, ensure_ascii=False)
    print("wrote", d)


sub = patch("django__django-13089", "test-driven-development")
for i in (1, 2, 3):
    write_arm("django", f"recheck-13089@r{i}", "django__django-13089", sub)

sub2 = patch("psf__requests-1921", "test-driven-development")
for i in (1, 2, 3, 4, 5):
    write_arm("requests", f"recheck-1921@r{i}", "psf__requests-1921", sub2)

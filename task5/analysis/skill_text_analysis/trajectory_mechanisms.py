"""Step 3: what differs between a kept and a broken run on the SAME instance?

Dataset: machine1 (complete; 10 skills per instance) + machine2's 63 failures.
For every run we classify each bash command and compute process-level metrics.
Then within each instance we contrast broken runs vs kept runs (paired by instance).

Writes data/traj_metrics.csv (one row per run) and data/mechanism_summary.json.
"""

import csv
import json
import os
import re
from collections import Counter, defaultdict

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DATA = os.path.join(HERE, "data")
M1 = os.path.join(REPO, "other_machine", "machine1", "machine1_全部轨迹")

runs_meta = list(csv.DictReader(open(os.path.join(DATA, "runs.csv"), encoding="utf-8-sig")))
verdict = {(r["machine"], r["instance"], r["skill"]): r["outcome"] for r in runs_meta}

# ------------------------------------------------------------------ command classes
EDIT_RE = re.compile(
    r"(git apply|patch -p|apply_patch|>>\s*\S+\.py|sed -i|python - <<|cat >|tee |"
    r"perl -0pi|\bpython\b[^\n]*\bwrite|\bopen\(|\.write\(|edit_file|str_replace)")
TEST_RE = re.compile(r"(\bpytest\b|\bunittest\b|python -m (pytest|unittest)|tox\b|"
                     r"python [^\n]*test[^\n]*\.py|nosetests|\bpython -c[^\n]*assert)")
READ_RE = re.compile(r"^\s*(cat |sed -n|head |tail |less |more |nl )|python -c[^\n]*(read|open)")
SEARCH_RE = re.compile(r"\b(grep|rg |ag |find |fd |git grep|ack )")
GIT_STATE_RE = re.compile(r"git (status|log|diff|show|blame|rev-parse)")
INSTALL_RE = re.compile(r"\b(pip install|apt-get|conda install|uv pip)")
VERIFY_RE = re.compile(r"(git diff|git status|pytest|unittest|\.py\b)")
TESTPATH_RE = re.compile(r"(test[s]?/[\w./-]+\.py|[\w/]+/test_[\w./-]+\.py|[\w/]+_test\.py)")
DIFF_RE = re.compile(r"^diff --git", re.M)


def classify(cmd):
    tags = set()
    if EDIT_RE.search(cmd):
        tags.add("edit")
    if TEST_RE.search(cmd):
        tags.add("test")
    if READ_RE.search(cmd):
        tags.add("read")
    if SEARCH_RE.search(cmd):
        tags.add("search")
    if GIT_STATE_RE.search(cmd):
        tags.add("git")
    if INSTALL_RE.search(cmd):
        tags.add("install")
    if not tags:
        tags.add("other")
    return tags


def run_metrics(path, skill):
    d = json.load(open(path, encoding="utf-8"))
    info = d.get("info", {})
    msgs = d.get("messages", [])
    submission = info.get("submission") or ""
    # commands and outputs
    cmds, outs = [], []
    for m in msgs:
        if m.get("role") == "assistant":
            for tc in (m.get("tool_calls") or []):
                fn = (tc or {}).get("function") or {}
                if fn.get("name") == "bash":
                    try:
                        a = json.loads(fn.get("arguments") or "{}")
                        cmds.append(a.get("command", ""))
                    except Exception:
                        cmds.append("")
                elif fn.get("name") == "load_skill_asset":
                    cmds.append("__load_skill_asset__")
        elif m.get("role") == "tool":
            extra = m.get("extra") or {}
            outs.append(extra.get("raw_output") or m.get("content") or "")
    tags = Counter()
    per_cmd_tags = []
    for c in cmds:
        t = classify(c)
        per_cmd_tags.append(t)
        for x in t:
            tags[x] += 1
    n = max(len(cmds), 1)

    # first edit position
    first_edit = next((i for i, t in enumerate(per_cmd_tags) if "edit" in t), None)
    # does the agent run the actual tests at least once?
    test_cmds = [c for c, t in zip(cmds, per_cmd_tags) if "test" in t]
    # number of distinct test paths touched by commands
    test_paths = {p for c in cmds for p in TESTPATH_RE.findall(c)}
    # did the agent ever read a test file?
    touched_tests = bool(test_paths)
    # patch properties
    added = sum(1 for l in submission.splitlines() if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in submission.splitlines() if l.startswith("-") and not l.startswith("---"))
    files = len(DIFF_RE.findall(submission))
    # failure signals in outputs: traceback / assert / error
    trace = sum(1 for o in outs if "Traceback (most recent call last)" in o)
    errors = sum(1 for o in outs if re.search(r"\b(Error|FAILED|AssertionError)\b", o))
    return dict(
        steps=len(cmds),
        edit_cmds=tags["edit"], test_cmds=tags["test"], read_cmds=tags["read"],
        search_cmds=tags["search"], git_cmds=tags["git"], install_cmds=tags["install"],
        other_cmds=tags["other"],
        edit_ratio=tags["edit"] / n, test_ratio=tags["test"] / n,
        read_ratio=tags["read"] / n, search_ratio=tags["search"] / n,
        first_edit_step=-1 if first_edit is None else first_edit,
        post_edit_steps=0 if first_edit is None else len(cmds) - first_edit,
        n_test_paths=len(test_paths), touched_tests=int(touched_tests),
        tracebacks=trace, error_outputs=errors,
        patch_lines_added=added, patch_lines_removed=removed, patch_files=files,
        patch_len=len(submission),
        used_asset=int("__load_skill_asset__" in cmds),
        exit_status=info.get("exit_status"),
        cost=(info.get("model_stats") or {}).get("instance_cost"),
        api_calls=(info.get("model_stats") or {}).get("api_calls"),
    )


rows = []
# machine1
for dp, _, fs in os.walk(os.path.join(M1, "skills")):
    for f in fs:
        if not f.endswith(".traj.json"):
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, os.path.join(M1, "skills")).split(os.sep)
        inst, skill = rel[0], rel[1]
        case = inst.split("__")[0]
        case = {"pydata": "xarray", "mwaskom": "seaborn", "psf": "requests",
                "pylint-dev": "pylint", "pytest-dev": "pytest", "sphinx-doc": "sphinx"}.get(case, case)
        outcome = verdict.get(("machine1", inst, skill))
        if outcome not in ("kept", "broken"):
            continue
        m = run_metrics(p, skill)
        m.update(machine="machine1", case=case, instance=inst, skill=skill, outcome=outcome)
        rows.append(m)

# machine2 failures
M2 = os.path.join(REPO, "other_machine", "machine2", "machine2_63_failed_trajectories_2026-10-17")
for r in csv.DictReader(open(os.path.join(M2, "失败运行清单_63条.csv"), encoding="utf-8-sig")):
    if r["package_relative_path"].endswith(".traj.json"):
        p = os.path.join(M2, r["package_relative_path"])
    else:
        p = os.path.join(M2, r["package_relative_path"])
    if not os.path.isfile(p):
        continue
    infra = int(r["infra_failure"]) or int(r["evaluation_error"]) or (
        1 if r["exit_status"] != "Submitted" and int(r["empty_patch"]) else 0)
    m = run_metrics(p, r["skill"])
    m.update(machine="machine2", case=r["case"], instance=r["instance_id"], skill=r["skill"],
             outcome="infra" if infra else "broken")
    rows.append(m)

cols = ["machine", "case", "instance", "skill", "outcome"] + [
    k for k in rows[0] if k not in ("machine", "case", "instance", "skill", "outcome")]
with open(os.path.join(DATA, "traj_metrics.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
print(f"traj_metrics.csv: {len(rows)} runs")
print("outcomes:", Counter((r['machine'], r['outcome']) for r in rows))

# ------------------------------------------------------------------ paired analysis
print("\n=== within-instance contrast: broken vs kept (machine1) ===")
m1 = [r for r in rows if r["machine"] == "machine1"]
by_inst = defaultdict(lambda: {"broken": [], "kept": []})
for r in m1:
    by_inst[r["instance"]][r["outcome"]].append(r)

metrics = ["steps", "edit_cmds", "test_cmds", "read_cmds", "search_cmds", "git_cmds",
           "edit_ratio", "test_ratio", "first_edit_step", "post_edit_steps",
           "tracebacks", "error_outputs", "patch_lines_added", "patch_files",
           "n_test_paths", "touched_tests", "used_asset", "cost"]
summary = {}
for m in metrics:
    diffs, bvals, kvals = [], [], []
    for inst, d in by_inst.items():
        if not d["broken"] or not d["kept"]:
            continue
        b = np.mean([float(r[m]) for r in d["broken"]])
        k = np.mean([float(r[m]) for r in d["kept"]])
        diffs.append(b - k); bvals.append(b); kvals.append(k)
    if len(diffs) < 4:
        continue
    diffs = np.array(diffs)
    # sign test: how often broken > kept
    pos = int(np.sum(diffs > 0)); neg = int(np.sum(diffs < 0))
    p_sign = stats.binomtest(pos, pos + neg, 0.5).pvalue if pos + neg else 1.0
    t, p_t = stats.ttest_rel(bvals, kvals)
    summary[m] = dict(n_inst=len(diffs), broken_mean=float(np.mean(bvals)),
                      kept_mean=float(np.mean(kvals)), diff=float(np.mean(diffs)),
                      sign_pos=pos, sign_neg=neg, p_sign=float(p_sign),
                      t=float(t), p_ttest=float(p_t))
print(f"{'metric':20s} {'broken':>9s} {'kept':>9s} {'diff':>9s} {'sign+/-':>10s} {'p_sign':>8s}")
for m, s in sorted(summary.items(), key=lambda kv: kv[1]["p_sign"]):
    print(f"{m:20s} {s['broken_mean']:9.3f} {s['kept_mean']:9.3f} {s['diff']:9.3f} "
          f"{s['sign_pos']:4d}/{s['sign_neg']:<4d} {s['p_sign']:8.3f}")

json.dump(summary, open(os.path.join(DATA, "mechanism_summary.json"), "w"), indent=2)
print("\nwrote data/mechanism_summary.json")

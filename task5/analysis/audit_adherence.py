"""Audit observable skill adherence in the final 4050 runs.

No model calls.  For each final (machine, case, skill, instance) run we parse the
trajectory and record process behaviours that the skill texts ask for:

  has_test                 any test-runner command
  test_after_last_edit     a test-runner command after the last file edit
  reproduce_before_edit    a test-runner command before the first edit
  test_file_edit           the submitted patch / commands touch tests/
  specific_test            at least one test command targets a test/file/nodeid
  full_suite_test          at least one test command does not target a specific test

The final run index comes from task5/split/machine{1,2,3}.json plus the 10 skill
arms per case in task5/analysis/final/final_accuracy_by_case_skill.csv.
Trajectories are selected from the three machines; for m3 the original valid
run is preferred and the rerun packages fill the 282 original failures.
"""
import csv
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T5 = ROOT / "task5"
ANA = T5 / "analysis"
FINAL = ANA / "final"
OUT = ANA / "adherence_audit"
M1 = ROOT / "other_machine" / "machine1"
M2 = ROOT / "other_machine" / "machine2" / "machine2_全部1350运行原始数据_三条重跑修正版_2026-10-18"
M3 = ROOT / "other_machine" / "machine3"

TEST_RE = re.compile(
    r"\b(?:pytest|py\.test|unittest|tox)\b|(?:tests/)?runtests\.py|\bmanage\.py\s+test\b|\bctest\b",
    re.I,
)
SPECIFIC_RE = re.compile(r"::|\s-k\s|test_[A-Za-z0-9_]+\.py")
EDIT_RE = re.compile(r"\b(?:sed\s+-i|perl\s+-[a-z]*i|apply_patch)\b", re.I)
WRITE_RE = re.compile(
    r"(?:cat\s*>>?|tee\s+(?:-a\s+)?|echo\s+[^|;&\n]*>>?|printf\s+[^|;&\n]*>>?)\s*([^\s;&|]+)",
    re.I,
)
TEST_PATH_RE = re.compile(r"(?:^|/)tests?/|(?:^|/)test_[A-Za-z0-9_]+\.py$", re.I)
PATCH_PATH_RE = re.compile(r"(?:^|/)(?:patch\.txt|[^/]+\.(?:diff|patch))$", re.I)
TMP_RE = re.compile(r"(?:/tmp\b|/var/tmp\b|\$TMPDIR|\\Temp\\|/Temp/)", re.I)
TEST_PATCH_RE = re.compile(
    r"diff --git a/(?:tests?/|.*/tests?/)|^\+\+\+ b/(?:tests?/|.*/tests?/)|"
    r"diff --git a/.*test_[^/]*\.py|^\+\+\+ b/.*test_[^/]*\.py",
    re.M,
)
CASE_OF_PREFIX = {
    "astropy": "astropy", "django": "django", "matplotlib": "matplotlib",
    "mwaskom": "seaborn", "pallets": "flask", "psf": "requests",
    "pydata": "xarray", "pylint-dev": "pylint", "pytest-dev": "pytest",
    "scikit-learn": "scikit-learn", "sphinx-doc": "sphinx", "sympy": "sympy",
}


def case_of(instance_id: str) -> str:
    return CASE_OF_PREFIX.get(instance_id.split("__", 1)[0], instance_id.split("__", 1)[0])


def read_json(p):
    return json.load(open(p, encoding="utf-8"))


def rel_path(p):
    """Store repository-relative paths only; the uploaded audit must not
    contain the user's absolute Windows home directory."""
    try:
        return Path(p).resolve().relative_to(ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return Path(p).name


def commands_of(d):
    cmds = []
    for m in d.get("messages", []):
        for tc in (m.get("tool_calls") or []):
            a = (tc.get("function") or {}).get("arguments", "")
            if isinstance(a, str):
                try:
                    a = json.loads(a)
                except (ValueError, TypeError):
                    a = {"command": a}
            if isinstance(a, dict) and isinstance(a.get("command"), str):
                cmds.append(a["command"])
    return cmds


def skill_blocks(d):
    names = []
    for m in d.get("messages", []):
        if m.get("role") not in ("system", "user"):
            continue
        s = m.get("content", "")
        if not isinstance(s, str):
            continue
        names += re.findall(r"<skill\b[^>]*\bname=[\"\']([^\"\']+)[\"\']", s)
    return names


def is_test(c):
    return bool(TEST_RE.search(c))


def is_specific_test(c):
    if SPECIFIC_RE.search(c):
        return True
    m = re.search(r"runtests\.py\s+([^\s|;&]+)", c)
    if m and "." in m.group(1) and not m.group(1).startswith("-"):
        return True
    return False


def _write_targets(c):
    ts = [m.group(1) for m in WRITE_RE.finditer(c)]
    ts += [m.group(1) for m in re.finditer(r"sed\s+-i\S*\s+([^\s;&|]+)", c, re.I)]
    return ts


def is_edit(c):
    # Scratch files under /tmp are not repository edits.  A command that
    # mentions /tmp anywhere is conservatively treated as non-repo work.
    if TMP_RE.search(c):
        return False
    # git apply/patch can be a dry run; only actual application counts.
    if re.search(r"\bgit\s+apply\b", c, re.I):
        if re.search(r"\bgit\s+apply\b[^\n;&|]*--(?:check|stat|numstat|summary)\b", c, re.I):
            return False
        return True
    if re.search(r"\bpatch\s+-p", c, re.I):
        return not bool(re.search(r"--dry-run", c, re.I))
    targets = _write_targets(c)
    if targets:
        # A command that only writes tests/ or patch artifacts is not a source edit.
        return any(not (TEST_PATH_RE.search(p) or PATCH_PATH_RE.search(p)) for p in targets)
    if EDIT_RE.search(c):
        return True
    # Python heredoc / -c: only if it actually opens for writing.
    if re.search(r"python[^\n]*<<", c, re.I) or re.search(r"python\s+-c\b", c, re.I):
        if re.search(
            r"""(?:open\([^)\n]*["']w|\.write\(|\.write_text\(|write_text\(|\.write_bytes\()""",
            c, re.I,
        ):
            py_targets = re.findall(r"""["']([^"']+\.py)["']""", c)
            if py_targets:
                return any(not (TEST_PATH_RE.search(p) or PATCH_PATH_RE.search(p)) for p in py_targets)
            return True
    return False


def behaviour(d):
    cmds = commands_of(d)
    test_idx = [i for i, c in enumerate(cmds) if is_test(c)]
    edit_idx = [i for i, c in enumerate(cmds) if is_edit(c)]
    test_cmds = [cmds[i] for i in test_idx]
    specific = [c for c in test_cmds if is_specific_test(c)]
    full = [c for c in test_cmds if not is_specific_test(c)]
    submission = (d.get("info", {}).get("submission") or "")
    # Only the submitted patch is reliable here.  A command-level fallback
    # false-positives on commands that edit source and mention a test path
    # in the same shell line (e.g. a heredoc edit followed by pytest).
    test_file_edit = bool(TEST_PATCH_RE.search(submission))
    has_test = bool(test_idx)
    edited = bool(edit_idx)
    test_after_last_edit = has_test and (not edited or max(test_idx) > max(edit_idx))
    reproduce_before_edit = has_test and (not edited or min(test_idx) < min(edit_idx))
    return {
        "steps": (d.get("info", {}).get("model_stats") or {}).get("api_calls") or 0,
        "command_calls": len(cmds),
        "test_calls": len(test_cmds),
        "specific_test_calls": len(specific),
        "full_test_calls": len(full),
        "has_test": int(has_test),
        "test_after_last_edit": int(test_after_last_edit),
        "reproduce_before_edit": int(reproduce_before_edit),
        "test_file_edit": int(test_file_edit),
        "edited": int(edited),
        "final_cmd_test": int(bool(cmds) and is_test(cmds[-1])),
        "specific_test": int(bool(specific)),
        "full_suite_test": int(bool(full)),
    }


def add_candidate(store, key, cand):
    store[key].append(cand)


def candidate_from_file(machine, path, skill_from_path=None):
    try:
        d = read_json(path)
    except Exception:
        return None
    if (d.get("info", {}).get("exit_status") != "Submitted"):
        return None
    iid = d.get("instance_id") or Path(path).stem.replace(".traj", "")
    names = skill_blocks(d)
    skill = skill_from_path or (names[0] if len(names) == 1 else None)
    if not skill:
        return None
    skill = skill.split("@", 1)[0]
    if skill in ("baseline",):
        return None
    b = behaviour(d)
    return {"machine": machine, "case": case_of(iid), "skill": skill, "instance": iid,
            "path": rel_path(path), "skill_source": "path" if skill_from_path else "prompt", **b}


def candidate_from_zip(zf, name):
    try:
        d = json.loads(zf.read(name).decode("utf-8"))
    except Exception:
        return None
    if (d.get("info", {}).get("exit_status") != "Submitted"):
        return None
    iid = d.get("instance_id")
    parts = name.split("/")
    # trajectories/<case>/<skill>/<hash>/<instance>.traj.json
    skill = parts[2] if len(parts) > 3 and parts[0] == "trajectories" else None
    if not skill:
        names = skill_blocks(d)
        skill = names[0] if len(names) == 1 else None
    if not iid or not skill:
        return None
    skill = skill.split("@", 1)[0]
    return {"machine": "m3", "case": case_of(iid), "skill": skill, "instance": iid,
            "path": f"{name} (zip)", "skill_source": "path" if len(parts) > 3 else "prompt",
            **behaviour(d)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    final_rows = list(csv.DictReader(open(FINAL / "final_accuracy_by_case_skill.csv", encoding="utf-8-sig")))
    skills_by_case = defaultdict(list)
    for r in final_rows:
        skills_by_case[r["case"]].append(r["skill"])
    expected = {}
    for machine in ("m1", "m2", "m3"):
        share = read_json(T5 / "split" / f"machine{machine[-1]}.json")
        for case, instances in share.items():
            for inst in instances:
                for skill in skills_by_case[case]:
                    expected[(machine, case, skill, inst)] = 1
    print("expected runs", len(expected), flush=True)

    store = defaultdict(list)
    # m1
    for p in (M1 / "machine1_全部轨迹" / "skills").glob("*/*/*.traj.json"):
        skill = p.parent.name
        c = candidate_from_file("m1", p, skill)
        if c: add_candidate(store, (c["machine"], c["case"], c["skill"], c["instance"]), c)
    # m2
    for p in (M2 / "trajectories").glob("*/*/*/*.traj.json"):
        skill = p.parent.parent.name
        c = candidate_from_file("m2", p, skill)
        if c: add_candidate(store, (c["machine"], c["case"], c["skill"], c["instance"]), c)
    # m3 original
    for p in (M3 / "machine3_轨迹" / "mini-swe-agent-skill-group" / "task5" / "runs").glob("*/*/*/*.traj.json"):
        skill = p.parent.parent.name
        c = candidate_from_file("m3", p, skill)
        if c: add_candidate(store, (c["machine"], c["case"], c["skill"], c["instance"]), c)
    # p1
    for p in (M3 / "machine3_第1份_80条轨迹与评测报告").glob("*/*/*/trajectory.json"):
        skill = p.parent.parent.name
        c = candidate_from_file("m3", p, skill)
        if c: add_candidate(store, (c["machine"], c["case"], c["skill"], c["instance"]), c)
    # p2/p3 (skill only in the rendered prompt)
    for base in [M3 / "machine3_补跑轨迹(1)"]:
        for p in base.rglob("*.traj.json"):
            c = candidate_from_file("m3", p, None)
            if c: add_candidate(store, (c["machine"], c["case"], c["skill"], c["instance"]), c)
    # p4 zip
    zp = M3 / "machine3_补跑第4份_全部79条轨迹及评测_2026-10-18.zip"
    if zp.exists():
        with zipfile.ZipFile(zp) as zf:
            for n in zf.namelist():
                if n.endswith(".traj.json"):
                    c = candidate_from_zip(zf, n)
                    if c: add_candidate(store, (c["machine"], c["case"], c["skill"], c["instance"]), c)
    print("candidate keys", len(store), "candidate files", sum(len(v) for v in store.values()), flush=True)

    # choose one: original valid first, then a non-empty submission / more commands
    chosen = {}
    for key, cands in store.items():
        cands = sorted(cands, key=lambda c: (
            0 if "machine3_轨迹" in c["path"] else 1,
            0 if c["command_calls"] else 1,
            -c["command_calls"],
        ))
        chosen[key] = cands[0]
    found = set(chosen) & set(expected)
    missing = sorted(set(expected) - set(chosen))
    extra = sorted(set(chosen) - set(expected))
    print("found expected", len(found), "missing", len(missing), "extra", len(extra), flush=True)
    if missing:
        print("missing sample", missing[:20], flush=True)
    if extra:
        print("extra sample", extra[:20], flush=True)

    # outcomes (m1/m2 only; m3 per-run outcomes are not in the final aggregate)
    m1_out = {}
    for r in csv.DictReader(open(M1 / "all_experiment_runs(2).csv", encoding="utf-8-sig")):
        if r.get("cohort") != "machine1":
            continue
        m1_out[(r["case_id"], r["skill_name"])] = int(float(r["resolved"]))
    # two confirmed requests-1921 corrections
    for skill in ("test-driven-development", "verification-before-completion"):
        m1_out[("psf__requests-1921", skill)] = 1
    m2_out = {}
    for r in csv.DictReader(open(M2 / "manifests" / "全部运行清单_1350条.csv", encoding="utf-8-sig")):
        m2_out[(r["instance_id"], r["skill"])] = int(r["official_resolved"])

    rows = []
    for key in sorted(expected):
        c = chosen.get(key)
        if not c:
            continue
        outcome = ""
        if c["machine"] == "m1":
            outcome = m1_out.get((c["instance"], c["skill"]), "")
        elif c["machine"] == "m2":
            outcome = m2_out.get((c["instance"], c["skill"]), "")
        rows.append({**c, "outcome": outcome})
    with open(OUT / "runs.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["machine", "case", "skill", "instance", "outcome",
                                           "steps", "command_calls", "test_calls",
                                           "specific_test_calls", "full_test_calls",
                                           "has_test", "test_after_last_edit",
                                           "reproduce_before_edit", "test_file_edit", "edited",
                                           "final_cmd_test", "specific_test", "full_suite_test",
                                           "skill_source", "path"])
        w.writeheader(); w.writerows(rows)

    # Within-case relative adherence: compare each skill cell with the other
    # nine arms of the same case, then average over the cases the skill covers.
    rel_metrics = ["has_test", "test_after_last_edit", "reproduce_before_edit",
                   "specific_test", "full_suite_test"]
    cells = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for m in rel_metrics:
            cells[(r["case"], r["skill"])][m].append(int(r[m]))
    skills_in_case = defaultdict(list)
    for case, skill in cells:
        skills_in_case[case].append(skill)
    rel = defaultdict(lambda: defaultdict(list))
    for (case, skill), d in cells.items():
        for m in rel_metrics:
            v = sum(d[m]) / len(d[m]) if d[m] else 0.0
            peers = []
            for s in skills_in_case[case]:
                dd = cells[(case, s)][m]
                peers.append(sum(dd) / len(dd) if dd else 0.0)
            rel[skill][m].append(v - sum(peers) / len(peers))
    rel_rows = []
    for skill in sorted(rel):
        row = {"skill": skill, "n_cases": len(rel[skill][rel_metrics[0]])}
        for m in rel_metrics:
            row[f"{m}_pp"] = round(100 * sum(rel[skill][m]) / len(rel[skill][m]), 2)
        rel_rows.append(row)
    with open(OUT / "summary_within_case_relative.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["skill", "n_cases"] + [f"{m}_pp" for m in rel_metrics])
        w.writeheader(); w.writerows(rel_rows)

    def agg(rs):
        n = len(rs)
        def rate(col):
            return round(sum(int(r[col]) for r in rs) / n, 4) if n else ""
        return {
            "n": n,
            "has_test": rate("has_test"),
            "test_after_last_edit": rate("test_after_last_edit"),
            "reproduce_before_edit": rate("reproduce_before_edit"),
            "test_file_edit": rate("test_file_edit"),
            "specific_test": rate("specific_test"),
            "full_suite_test": rate("full_suite_test"),
            "final_cmd_test": rate("final_cmd_test"),
            "mean_steps": round(sum(float(r["steps"]) for r in rs) / n, 2) if n else "",
            "mean_test_calls": round(sum(float(r["test_calls"]) for r in rs) / n, 2) if n else "",
        }
    def write_group(name, groups):
        keys = list(groups)
        with open(OUT / name, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=["group"] + list(agg(groups[keys[0]]).keys()))
            w.writeheader()
            for k in keys:
                w.writerow({"group": k, **agg(groups[k])})

    by_skill = defaultdict(list); by_case = defaultdict(list); by_machine = defaultdict(list)
    by_outcome = defaultdict(list); by_type = defaultdict(list)
    type_of = {(r["case"], r["skill"]): r["type"] for r in []}  # filled below
    # type from pooled table
    pooled = {r["skill"]: r["type"] for r in csv.DictReader(open(FINAL / "final_pooled_skill.csv", encoding="utf-8-sig"))}
    for r in rows:
        by_skill[r["skill"]].append(r); by_case[r["case"]].append(r); by_machine[r["machine"]].append(r)
        by_type[pooled.get(r["skill"], "?")].append(r)
        if r["outcome"] != "":
            by_outcome[str(r["outcome"])].append(r)
    write_group("summary_by_skill.csv", dict(sorted(by_skill.items())))
    write_group("summary_by_case.csv", dict(sorted(by_case.items())))
    write_group("summary_by_machine.csv", dict(sorted(by_machine.items())))
    write_group("summary_by_outcome.csv", dict(sorted(by_outcome.items())))
    write_group("summary_by_type.csv", dict(sorted(by_type.items())))

    def pct(x): return f"{x*100:.1f}%"
    allr = agg(rows)
    lines = [
        "# Skill 依从性审计（2026-10-19）", "",
        f"- 预期 final runs：**{len(expected)}**；实际匹配：**{len(rows)}**；缺失：**{len(missing)}**。",
        f"- 整体：有测试命令 **{pct(allr['has_test'])}**；最后编辑之后有测试 **{pct(allr['test_after_last_edit'])}**；",
        f"  编辑前先复现 **{pct(allr['reproduce_before_edit'])}**；改测试文件 **{pct(allr['test_file_edit'])}**；",
        f"  有具体测试目标 **{pct(allr['specific_test'])}**；跑过全量 suite **{pct(allr['full_suite_test'])}**。",
        "",
        "## 按 skill",
        "",
        "| skill | n | 有测试 | 最后编辑后测试 | 先复现 | 改测试文件 | 具体测试 | 全量 suite |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for skill, rs in sorted(by_skill.items(), key=lambda kv: -len(kv[1])):
        a = agg(rs)
        lines.append(f"| {skill} | {a['n']} | {pct(a['has_test'])} | {pct(a['test_after_last_edit'])} | "
                     f"{pct(a['reproduce_before_edit'])} | {pct(a['test_file_edit'])} | "
                     f"{pct(a['specific_test'])} | {pct(a['full_suite_test'])} |")
    key_skills = {"verification-before-completion", "systematic-debugging",
                  "test-driven-development", "django-verification",
                  "python-error-handling", "pytest-advanced"}
    show_rel = [r for r in rel_rows if r["skill"] in key_skills
                or abs(r["test_after_last_edit_pp"]) > 5
                or abs(r["reproduce_before_edit_pp"]) > 5]
    lines += ["", "## Case 内相对依从性（百分点；控制 case）", "",
              "| skill | 测试后编辑 | 先复现 | 具体测试 | 全量 suite |",
              "|---|---:|---:|---:|---:|"]
    for r in show_rel:
        lines.append(f"| {r['skill']} | {r['test_after_last_edit_pp']:+.1f} | "
                     f"{r['reproduce_before_edit_pp']:+.1f} | {r['specific_test_pp']:+.1f} | "
                     f"{r['full_suite_test_pp']:+.1f} |")
    lines += ["", "完整表见 `summary_within_case_relative.csv`。正值表示该 skill 比同 case 其他臂更常出现该行为。", ""]
    lines += ["## 按 outcome（仅 m1+m2，2700 条有逐条判定）", "",
              "| outcome | n | 有测试 | 最后编辑后测试 | 先复现 | 改测试文件 | 具体测试 | 全量 suite |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for o, rs in sorted(by_outcome.items()):
        a = agg(rs)
        lines.append(f"| {o} | {a['n']} | {pct(a['has_test'])} | {pct(a['test_after_last_edit'])} | "
                     f"{pct(a['reproduce_before_edit'])} | {pct(a['test_file_edit'])} | "
                     f"{pct(a['specific_test'])} | {pct(a['full_suite_test'])} |")
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", OUT / "summary.md", flush=True)
    print("\n".join(lines[:12]), flush=True)


if __name__ == "__main__":
    main()

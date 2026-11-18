"""Build failure_table_437: one row per failed run in the 101-instance crossover set.

Joins three sources:
  1. B's final_failure_labels_437.csv   (label, confidence, evidence, quality flags)
  2. A's A_toolcall_features_v2.csv     (process features; traj_path as cross-check)
  3. experiment_data/00_benchmark_inputs/swe_bench_verified.jsonl
     (gold patch, test_patch, FAIL_TO_PASS / PASS_TO_PASS)

For each row it extracts:
  - the final patch from the trajectory's last `exit` message;
  - file sets of final patch / gold patch / test_patch, with overlap metrics;
  - hunk function contexts of final patch vs gold patch (F2/F3 calibration signal);
  - test_patch assertion shape counts (F1 calibration signal);
  - whether newly added test functions actually appear in FAIL_TO_PASS (F4 signal).

Outputs (all under full_coding/):
  failure_table_437.csv          main table, utf-8-sig
  failure_table_437_summary.json distribution summary

Usage:
  PYTHONIOENCODING=utf-8 python task5/analysis/root_cause/full_coding/build_failure_table.py
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
B_LABELS = (ROOT / "others_finding" / "_extracted" / "B2_20261023" / "任务B材料"
            / "phase2_final_20261023" / "output" / "final_failure_labels_437.csv")
DATASET = ROOT / "experiment_data" / "00_benchmark_inputs" / "swe_bench_verified.jsonl"
OUT_DIR = Path(__file__).resolve().parent
OUT_CSV = OUT_DIR / "failure_table_437.csv"
OUT_SUMMARY = OUT_DIR / "failure_table_437_summary.json"

DIFF_GIT_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")
PLUS_RE = re.compile(r"^\+\+\+ b/(.+)$")
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@ ?(.*)$")
CTX_TOKEN_RE = re.compile(r"^(?:async\s+def|def|class)\s+([A-Za-z_][\w.]*)")
NEW_TEST_RE = re.compile(r"^\+\s*def (test_\w+)")
ASSERT_RE = re.compile(r"^\+\s*assert\b")


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def find_a_features():
    """A's feature CSV sits under a directory whose name is mojibake in some shells."""
    hits = sorted((ROOT / "others_finding").rglob("A_toolcall_features_v2.csv"))
    for p in hits:
        if "A3_20261024" in str(p):
            return p
    if hits:
        return hits[0]
    raise FileNotFoundError("A_toolcall_features_v2.csv not found under others_finding/")


def load_dataset():
    out = {}
    with open(DATASET, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            out[d["instance_id"]] = d
    return out


def as_list(v):
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            x = json.loads(v)
            return x if isinstance(x, list) else [v]
        except Exception:
            return [v]
    return []


def parse_patch(text):
    """Return (files, func_contexts, added, removed, hunks) for a unified diff."""
    files, contexts = [], []
    added = removed = hunks = 0
    for line in (text or "").splitlines():
        m = DIFF_GIT_RE.match(line)
        if m:
            files.append(m.group(2))
            continue
        m = PLUS_RE.match(line)
        if m and not line.startswith("+++ /dev/null"):
            if not files or files[-1] != m.group(1):
                files.append(m.group(1))
            continue
        m = HUNK_RE.match(line)
        if m:
            hunks += 1
            ctx = m.group(1).strip()
            tok = CTX_TOKEN_RE.match(ctx)
            name = tok.group(1) if tok else (ctx.split("(")[0].strip() if ctx else "")
            if name:
                contexts.append(name)
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    # de-dup preserving order
    seen = set()
    uniq = []
    for x in files:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq, contexts, added, removed, hunks


def jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return None
    return len(sa & sb) / len(sa | sb)


def test_patch_signals(test_patch_text, f2p):
    added_assert = eq_string = raises = is_cmp = in_cmp = 0
    new_tests = []
    for line in test_patch_text.splitlines():
        if NEW_TEST_RE.match(line):
            new_tests.append(NEW_TEST_RE.match(line).group(1))
        if not ASSERT_RE.match(line):
            if "pytest.raises" in line:
                raises += 1
            continue
        added_assert += 1
        if "==" in line:
            eq_string += 1
        if " is " in line or " is not " in line:
            is_cmp += 1
        if re.search(r"\bassert\b.*\bin\b", line):
            in_cmp += 1
        if "pytest.raises" in line:
            raises += 1
    f2p_names = set()
    for t in f2p:
        # Formats seen: "path::test_x[param]" and "test_x (module.Class)".
        name = t.split("::")[-1].strip().split()[0].split("[")[0]
        f2p_names.add(name)
    hit = [t for t in new_tests if t in f2p_names]
    return {
        "test_added_asserts": added_assert,
        "test_assert_eq_lines": eq_string,
        "test_assert_is_lines": is_cmp,
        "test_assert_in_lines": in_cmp,
        "test_pytest_raises": raises,
        "test_new_tests": ";".join(new_tests),
        "test_new_tests_in_f2p": ("all" if new_tests and len(hit) == len(new_tests)
                                  else "some" if hit
                                  else "none" if new_tests
                                  else "n/a"),
        "test_new_tests_f2p_hits": len(hit),
    }


def exit_status(content):
    if "diff --git" in content:
        return "patch"
    if content.startswith("LimitsExceeded"):
        return "limits_exceeded"
    if "BadRequestError" in content or "Insufficient Balance" in content:
        return "api_error"
    return "other"


def phase_of(path_str):
    if "02_phase1_rescue_95" in path_str:
        return "phase1"
    if "03_phase2_retention_405" in path_str:
        return "phase2"
    return "unknown"


def main():
    labels = read_csv(B_LABELS)
    a_path = find_a_features()
    a_rows = read_csv(a_path)
    a_by_key = {(r["case"], r["instance"], r["skill"]): r for r in a_rows}
    dataset = load_dataset()

    # n_resolved per instance over all 1010 runs of the crossover set
    resolved_by_instance = defaultdict(int)
    arms_by_instance = defaultdict(int)
    for r in a_rows:
        arms_by_instance[r["instance"]] += 1
        if r["resolved"] == "1":
            resolved_by_instance[r["instance"]] += 1

    out_rows = []
    missing_join = []
    for r in labels:
        key = (r["case"], r["instance"], r["skill"])
        a = a_by_key.get(key)
        if a is None:
            missing_join.append(key)
            a = {}
        ds = dataset[r["instance"]]
        traj_path = ROOT / r["trajectory_source"]
        traj = json.load(open(traj_path, encoding="utf-8"))
        exits = [m for m in traj.get("messages", []) if m.get("role") == "exit"]
        exit_content = (exits[-1].get("content") or "") if exits else ""
        status = exit_status(exit_content)
        final_patch = exit_content if status == "patch" else ""

        p_files, p_ctx, p_add, p_rem, p_hunks = parse_patch(final_patch)
        g_files, g_ctx, g_add, g_rem, g_hunks = parse_patch(ds.get("patch", ""))
        t_files, _, t_add, _, t_hunks = parse_patch(ds.get("test_patch", ""))

        gold_set, patch_set = set(g_files), set(p_files)
        touched_gold = len(patch_set & gold_set)
        touched_tests = len(set(p_files) & set(t_files))
        exact = bool(gold_set) and patch_set == gold_set

        f2p = as_list(ds.get("FAIL_TO_PASS"))
        p2p = as_list(ds.get("PASS_TO_PASS"))
        tsignals = test_patch_signals(ds.get("test_patch", ""), f2p)

        row = {
            "case": r["case"],
            "instance": r["instance"],
            "skill": r["skill"],
            "phase": phase_of(r["trajectory_source"]),
            "final_label": r["final_label"],
            "original_label": r["original_label"],
            "confidence": r["confidence"],
            "label_changed": r["label_changed"],
            "evidence": r["evidence"],
            "quality_flag": r["quality_flag"],
            "evidence_status": r["evidence_status"],
            "patch_outcome_conflict": r["patch_outcome_conflict"],
            "evaluation_identity_basis": r["evaluation_identity_basis"],
            "run_id": r["run_id"],
            "traj_path": r["trajectory_source"],
            "final_patch_status": status,
            "final_patch": final_patch,
            "final_patch_len": len(final_patch),
            "patch_files": ";".join(p_files),
            "patch_n_files": len(p_files),
            "patch_added": p_add,
            "patch_removed": p_rem,
            "patch_hunks": p_hunks,
            "patch_func_contexts": ";".join(p_ctx),
            "gold_files": ";".join(g_files),
            "gold_n_files": len(g_files),
            "gold_added": g_add,
            "gold_removed": g_rem,
            "gold_func_contexts": ";".join(g_ctx),
            "test_files": ";".join(t_files),
            "test_n_files": len(t_files),
            "test_added": t_add,
            "files_exact_match_gold": exact,
            "patch_subset_of_gold": bool(patch_set) and patch_set <= gold_set,
            "gold_subset_of_patch": bool(gold_set) and gold_set <= patch_set,
            "files_disjoint_gold": bool(patch_set) and not (patch_set & gold_set),
            "files_jaccard_gold": jaccard(p_files, g_files),
            "func_jaccard_gold": jaccard(p_ctx, g_ctx),
            "n_gold_files_touched": touched_gold,
            "n_test_files_touched": touched_tests,
            "n_f2p": len(f2p),
            "n_p2p": len(p2p),
            "f2p_tests": " | ".join(f2p),
            "n_resolved_instance": resolved_by_instance.get(r["instance"], 0),
            "n_arms_instance": arms_by_instance.get(r["instance"], 0),
            "a_n_steps": a.get("n_steps", ""),
            "a_n_edits": a.get("n_edits", ""),
            "a_n_tests": a.get("n_tests", ""),
            "a_n_commands": a.get("n_commands", ""),
            "a_info_exit": a.get("info_exit", ""),
            "a_info_calls": a.get("info_calls", ""),
            "a_info_cost": a.get("info_cost", ""),
            "a_traj_path": a.get("traj_path", ""),
        }
        row.update(tsignals)
        out_rows.append(row)

    fieldnames = list(out_rows[0].keys())
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    summary = {
        "rows": len(out_rows),
        "join_missing": missing_join,
        "final_patch_status": dict(Counter(r["final_patch_status"] for r in out_rows)),
        "final_label": dict(Counter(r["final_label"] for r in out_rows)),
        "phase": dict(Counter(r["phase"] for r in out_rows)),
        "files_exact_match_gold": sum(r["files_exact_match_gold"] for r in out_rows),
        "patch_subset_of_gold": sum(r["patch_subset_of_gold"] for r in out_rows),
        "gold_subset_of_patch": sum(r["gold_subset_of_patch"] for r in out_rows),
        "files_disjoint_gold": sum(r["files_disjoint_gold"] for r in out_rows),
        "patch_touches_test_files": sum(1 for r in out_rows if r["n_test_files_touched"]),
        "new_tests_not_in_f2p": sum(1 for r in out_rows if r["test_new_tests_in_f2p"] == "none"),
        "new_tests_in_f2p": dict(Counter(r["test_new_tests_in_f2p"] for r in out_rows)),
        "labels_by_files_exact": {
            lab: dict(Counter(r["files_exact_match_gold"] for r in out_rows
                              if r["final_label"] == lab))
            for lab in sorted({r["final_label"] for r in out_rows})
        },
    }
    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"wrote {OUT_CSV} ({len(out_rows)} rows, {len(fieldnames)} cols)")
    print(f"wrote {OUT_SUMMARY}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if missing_join:
        print(f"WARNING: {len(missing_join)} rows missing A features: {missing_join[:5]}",
              file=sys.stderr)


if __name__ == "__main__":
    main()

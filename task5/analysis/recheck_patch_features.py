"""Recompute the four patch features as success-minus-failure paired differences.

Used by data_audit_20261031.md. Run from repo root:
    python task5/analysis/recheck_patch_features.py

Inputs:
  - B final table: others_finding/_extracted/B2_20261023/任务B材料/
    phase2_final_20261023/output/integrated_1010_with_final_labels.csv
  - B4 contamination table: others_finding/_extracted/B4_20261024/
    incremental_audit_20261024/output/B_label_contamination.csv

Definition: for each instance with both a resolved=1 and resolved=0 run,
compute mean(feature | success) - mean(feature | failure); average the 101
instance-level differences (equal weight). This is the paired difference
reported in C's feature_summary_recomputed.md, not a Skill-vs-baseline
comparison and not the difference of the two overall group means.
"""

import csv
import os
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

B_PATH = os.path.join(
    REPO,
    "others_finding/_extracted/B2_20261023/任务B材料/"
    "phase2_final_20261023/output/integrated_1010_with_final_labels.csv",
)
CONTAM_PATH = os.path.join(
    REPO,
    "others_finding/_extracted/B4_20261024/"
    "incremental_audit_20261024/output/B_label_contamination.csv",
)
FEATURES = ["B_location_jaccard", "B_patch_text_similarity", "B_file_recall", "A_n_tests"]


def as_float(row, key):
    value = row.get(key, "")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def paired_diff(rows, feature):
    by_instance = defaultdict(lambda: {"success": [], "failure": []})
    for row in rows:
        value = as_float(row, feature)
        if value is None:
            continue
        if row["resolved"] == "1":
            by_instance[row["instance"]]["success"].append(value)
        elif row["resolved"] == "0":
            by_instance[row["instance"]]["failure"].append(value)
    diffs = [
        statistics.mean(groups["success"]) - statistics.mean(groups["failure"])
        for groups in by_instance.values()
        if groups["success"] and groups["failure"]
    ]
    return statistics.mean(diffs), len(diffs)


def main():
    rows = list(csv.DictReader(open(B_PATH, encoding="utf-8-sig", errors="replace")))
    contamination = list(
        csv.DictReader(open(CONTAM_PATH, encoding="utf-8-sig", errors="replace"))
    )
    high_proxy = {
        row["run_id"]
        for row in contamination
        if row.get("contamination_tier") == "high_proxy"
    }

    groups = {
        "main": rows,
        "S1_no_uncertain": [r for r in rows if r["final_label"] != "uncertain"],
        "S2_no_same_patch_conflict": [
            r for r in rows if r["B_identical_patch_outcome_conflict"] != "1"
        ],
        "S3_no_C_unreviewed": [
            r
            for r in rows
            if r["label_source"] != "C_source_carried_forward_not_row_audited"
        ],
        "S4a_no_high_proxy": [r for r in rows if r["run_id"] not in high_proxy],
    }
    groups["S4b_all"] = [
        r
        for r in groups["S1_no_uncertain"]
        if r["B_identical_patch_outcome_conflict"] != "1"
        and r["label_source"] != "C_source_carried_forward_not_row_audited"
        and r["run_id"] not in high_proxy
    ]

    print(f"{'group':28s} {'n_inst':>6s} " + " ".join(f"{f:>26s}" for f in FEATURES))
    for name, subset in groups.items():
        cells = []
        for feature in FEATURES:
            mean, n = paired_diff(subset, feature)
            cells.append(f"{mean:+.3f} (n={n})")
        print(f"{name:28s} {len(subset):6d} " + " ".join(f"{c:>26s}" for c in cells))


if __name__ == "__main__":
    main()

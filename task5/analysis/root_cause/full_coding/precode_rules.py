"""First-pass rule coding of the 437 failures + calibration check on the 12 deep reads.

Rules are deliberately conservative: the table's location signals can decide F4 and
most F2/F3 cases, but F1 vs F3 vs F2 inside the same function region needs reading.
Every row gets a code, a confidence, a reason, and `needs_manual` when the rule
cannot separate the candidates.

Usage:
  PYTHONIOENCODING=utf-8 python precode_rules.py            # write pre-code CSV + report
  PYTHONIOENCODING=utf-8 python precode_rules.py --validate # print 12-case agreement
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABLE = HERE / "failure_table_437.csv"
CALIB = HERE / "calibration_12.csv"
OUT = HERE / "precode_437.csv"
REPORT = HERE / "precode_437_summary.json"


def truthy(v):
    return str(v).strip().lower() == "true"


def code_row(r):
    """Return (code, confidence, reason, needs_manual)."""
    if truthy(r["patch_outcome_conflict"]):
        return "F4", "high", "B 记录 patch_outcome_conflict=True（同补丁不同判定）", False
    if r["final_patch_status"] != "patch":
        return "F4", "high", f"未提交有效补丁（{r['final_patch_status']}），属 infra/预算终止", False

    exact = truthy(r["files_exact_match_gold"])
    subset = truthy(r["patch_subset_of_gold"])
    disjoint = truthy(r["files_disjoint_gold"])
    sup = truthy(r["gold_subset_of_patch"])
    touched = int(r["n_gold_files_touched"] or 0)
    gold_n = int(r["gold_n_files"] or 0)
    patch_n = int(r["patch_n_files"] or 0)
    eq = int(r["test_added_asserts"] or 0)
    eq_lines = int(r["test_assert_eq_lines"] or 0)
    f2p_none = r["test_new_tests_in_f2p"] == "none"

    if f2p_none and eq > 0:
        return "F4", "medium", "test_patch 新增测试不在 FAIL_TO_PASS（评测链可疑）", True

    if disjoint:
        return "F2", "high", "补丁与 gold 文件完全不相交（修在别的文件）", False

    if touched == 0:
        return "F2", "high", "补丁未触及任何 gold 文件", False

    if subset and patch_n < gold_n:
        return "F3", "high", f"补丁只覆盖 {patch_n}/{gold_n} 个 gold 文件（漏入口）", False

    if exact or sup:
        if eq_lines > 0:
            return "F1", "low", "文件与 gold 对齐且测试有精确相等断言；同区域内 F1/F3 需读补丁", True
        return "F3", "medium", "文件与 gold 对齐、测试无精确相等断言；倾向漏分支", True

    # overlap with extra files / partial contexts
    if eq_lines > 0:
        return "F2", "low", "补丁动到 gold 文件但另改文件/函数；精确断言提示也可能读错契约", True
    return "F3", "low", "补丁动到 gold 文件但与 gold 函数上下文不一致", True


def load_table():
    with open(TABLE, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def validate(rows):
    with open(CALIB, encoding="utf-8-sig", newline="") as f:
        cal = list(csv.DictReader(f))
    by_key = {(r["instance"], r["skill"]): r for r in rows}
    print(f"{'instance':45s} {'skill':32s} {'true':3s} {'rule':4s} {'conf':6s} agree")
    n_ok = 0
    misses = []
    for c in cal:
        r = by_key[(c["instance"], c["fail_skill"])]
        code, conf, reason, manual = code_row(r)
        ok = code == c["main_cause"]
        n_ok += ok
        print(f"{c['instance']:45s} {c['fail_skill']:32s} {c['main_cause']:3s} "
              f"{code:4s} {conf:6s} {'OK' if ok else 'MISS'}  {reason}")
        if not ok:
            misses.append((c["instance"], c["main_cause"], code, conf, reason))
    print(f"\nagreement: {n_ok}/{len(cal)}")
    if misses:
        print("misses:")
        for m in misses:
            print(" ", m)
    return n_ok, len(cal)


def main():
    rows = load_table()
    out = []
    for r in rows:
        code, conf, reason, manual = code_row(r)
        out.append({
            "case": r["case"], "instance": r["instance"], "skill": r["skill"],
            "phase": r["phase"], "b_label": r["final_label"],
            "n_resolved_instance": r["n_resolved_instance"],
            "rule_code": code, "rule_confidence": conf, "rule_reason": reason,
            "needs_manual": manual,
        })
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)

    summary = {
        "rows": len(out),
        "rule_code": dict(Counter(x["rule_code"] for x in out)),
        "rule_confidence": dict(Counter(x["rule_confidence"] for x in out)),
        "needs_manual": sum(bool(x["needs_manual"]) for x in out),
        "by_b_label_and_rule": {
            lab: dict(Counter(x["rule_code"] for x in out if x["b_label"] == lab))
            for lab in sorted({x["b_label"] for x in out})
        },
    }
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"wrote {OUT}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if "--validate" in sys.argv:
        print("\n=== calibration on 12 deep reads ===")
        validate(rows)


if __name__ == "__main__":
    main()

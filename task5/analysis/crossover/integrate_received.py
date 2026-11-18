"""Join A/B/C deliverables into one 1,010-row table."""
import csv
import openpyxl
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXT = ROOT / "others_finding" / "_extracted"
OUT = ROOT / "task5" / "analysis" / "crossover"


def read_csv(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def read_sheet(p, header_row=4):
    wb = openpyxl.load_workbook(p, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(min_row=header_row, values_only=True))
    h = rows[0]
    return [dict(zip(h, r)) for r in rows[1:] if r and r[0]]


def main():
    base = read_csv(EXT / "B" / "任务B材料" / "inputs" / "mixed_1010_authoritative.csv")
    assignment = read_csv(OUT / "assignment.csv")
    owner_by_inst = {(r["case"], r["instance"]): r["person"] for r in assignment}

    A = read_csv(EXT / "A" / "A任务_交叉实例分析" / "A_run_labels.csv")
    A_tool = read_csv(EXT / "A" / "A任务_交叉实例分析" / "A_toolcall_features.csv")
    B_labels = read_csv(EXT / "B" / "任务B材料" / "results" / "B_153_failure_labels.csv")
    B_patch = read_csv(EXT / "B" / "任务B材料" / "results" / "all_1010_patch_features.csv")
    C_labels = read_sheet(EXT / "C" / "任务C_最终交付包_2026-10-23" / "03_330条run级人工标注" / "任务C_330条总标注表.xlsx")
    C_fit = read_sheet(EXT / "C" / "任务C_最终交付包_2026-10-23" / "05_1010条文本特征" / "人工判断_最终.xlsx")
    C_issue = read_sheet(EXT / "C" / "任务C_最终交付包_2026-10-23" / "05_1010条文本特征" / "问题描述特征.xlsx")
    C_skill = read_sheet(EXT / "C" / "任务C_最终交付包_2026-10-23" / "05_1010条文本特征" / "skill文本特征.xlsx")

    key = lambda r: (r["case"], r["instance"], r["skill"])
    A = {key(r): r for r in A}
    A_tool = {key(r): r for r in A_tool}
    B_labels = {key(r): r for r in B_labels}
    B_patch = {key(r): r for r in B_patch}
    C_labels = {key(r): r for r in C_labels}
    C_fit = {key(r): r for r in C_fit}
    C_issue = {(r["case"], r["instance"]): r for r in C_issue}
    C_skill = {(r["case"], r["skill"]): r for r in C_skill}

    out = []
    for r in base:
        k = key(r)
        o = dict(r)
        o["owner"] = owner_by_inst.get((r["case"], r["instance"]), "")
        src = o["owner"]
        o["label_source"] = src
        o["label_quality"] = "auto_rule" if src == "A" else ("human_research" if src == "B" else "ai_assisted_user_confirmed")
        o["label"] = ""
        o["label_confidence"] = ""
        o["label_evidence"] = ""
        o["label_attribution"] = ""
        if src == "A" and k in A:
            a = A[k]
            o["label"] = a.get("失败标签", "")
            o["label_confidence"] = a.get("置信度", "")
            o["label_evidence"] = a.get("证据", "")
            o["label_attribution"] = a.get("skill还是instance", "")
            o["A_result_text"] = a.get("结果", "")
            o["A_fingerprint_wrong_location"] = a.get("指纹_定位错", "")
            o["A_fingerprint_incomplete_patch"] = a.get("指纹_补丁不完整", "")
            o["A_fingerprint_test_misread"] = a.get("指纹_测试读错", "")
            o["A_fingerprint_tool_loop"] = a.get("指纹_工具循环", "")
            o["A_fingerprint_premature_submit"] = a.get("指纹_过早提交", "")
        if src == "B" and k in B_labels:
            b = B_labels[k]
            o["label"] = b.get("main_label", "")
            o["label_confidence"] = b.get("confidence", "")
            o["label_evidence"] = b.get("finding", "") + " | " + b.get("patch_evidence", "")
            o["label_attribution"] = b.get("attribution", "")
            o["B_label_cn"] = b.get("main_label_cn", "")
            o["B_evidence_file"] = b.get("evidence_file", "")
            o["B_quality_warning"] = b.get("quality_warning", "")
            o["B_subtype"] = b.get("subtype", "")
        if src == "C" and k in C_labels:
            c = C_labels[k]
            o["label"] = c.get("primary_failure_reason") or ""
            o["label_confidence"] = c.get("annotation_status", "")
            o["label_evidence"] = c.get("evidence", "") or ""
            o["label_attribution"] = ""
            o["C_success_behavior"] = c.get("success_behavior", "") or ""
            o["C_timeline"] = c.get("timeline_summary", "") or ""
            o["C_uncertain"] = c.get("uncertain", "")
            o["C_fingerprint_wrong_location"] = c.get("fingerprint_wrong_location", "")
            o["C_fingerprint_incomplete_patch"] = c.get("fingerprint_incomplete_patch", "")
            o["C_fingerprint_test_misread"] = c.get("fingerprint_test_misread", "")
            o["C_fingerprint_tool_loop"] = c.get("fingerprint_tool_loop", "")
            o["C_fingerprint_premature_submit"] = c.get("fingerprint_premature_submit", "")

        if k in A_tool:
            for kk, vv in A_tool[k].items():
                if kk not in ("case", "instance", "skill"):
                    o["A_" + kk] = vv
        if k in B_patch:
            for kk, vv in B_patch[k].items():
                if kk not in ("case", "instance", "skill"):
                    o["B_" + kk] = vv
        if k in C_fit:
            c = C_fit[k]
            o["C_fit_judgment"] = c.get("fit_judgment", "")
            o["C_fit_evidence"] = c.get("evidence", "")
            o["C_fit_notes"] = c.get("notes", "")
            o["C_fit_review_status"] = c.get("review_status", "")
            o["C_issue_features_confirmed"] = c.get("issue_features_confirmed", "")
            o["C_skill_features_confirmed"] = c.get("skill_features_confirmed", "")
        if (r["case"], r["instance"]) in C_issue:
            for kk, vv in C_issue[(r["case"], r["instance"])].items():
                if kk not in ("case", "instance"):
                    o["C_issue_" + kk] = vv
        if (r["case"], r["skill"]) in C_skill:
            for kk, vv in C_skill[(r["case"], r["skill"])].items():
                if kk not in ("case", "skill"):
                    o["C_skill_" + kk] = vv
        out.append(o)

    assert len(out) == 1010
    assert len({key(r) for r in out}) == 1010
    assert sum(int(r["resolved"]) for r in out) == 573
    with open(OUT / "integrated_1010.csv", "w", newline="", encoding="utf-8-sig") as f:
        # union columns in stable order
        cols = []
        seen = set()
        for r in out:
            for c in r:
                if c not in seen:
                    seen.add(c); cols.append(c)
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(out)
    print("wrote integrated_1010.csv", len(out), "rows", len(cols), "cols")
    print("owners", Counter(r["owner"] for r in out))
    print("labels", Counter((r["label_source"], r["label"]) for r in out if r["label"]))
    print("C fit", Counter(r.get("C_fit_judgment", "") for r in out))


if __name__ == "__main__":
    main()

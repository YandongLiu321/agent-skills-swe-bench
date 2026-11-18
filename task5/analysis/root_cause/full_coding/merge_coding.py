"""Merge manual + batch + rule coding into coding_437_v1.csv and report.

Priority: manual_50 > review/codes_batch_*.csv > precode_437 (rule, high confidence).

Outputs:
  coding_437_v1.csv
  coding_437_v1_summary.json
  coding_437_v1_report.md
"""
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABLE = HERE / "failure_table_437.csv"
MANUAL = HERE / "coding_manual_50.csv"
PRECODE = HERE / "precode_437.csv"
OUT = HERE / "coding_437_v1.csv"
SUMMARY = HERE / "coding_437_v1_summary.json"
REPORT = HERE / "coding_437_v1_report.md"
VALID = {"F1", "F2", "F3", "F4", "U"}


def read_csv(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def pct(k, n):
    if n == 0:
        return "0/0"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100*k/n:.1f}% [{100*lo:.1f}, {100*hi:.1f}]"


def main():
    table = read_csv(TABLE)
    for i, r in enumerate(table, 1):
        r["row_id"] = f"{i:04d}"
    by_id = {r["row_id"]: r for r in table}

    codes = {}
    sources = {}
    for p in [MANUAL, HERE / "coding_manual_extra.csv"]:
        if not p.exists():
            continue
        for r in read_csv(p):
            codes[r["row_id"]] = r
            sources[r["row_id"]] = p.stem
    for p in sorted((HERE / "review").glob("codes_batch_*.csv")):
        for r in read_csv(p):
            rid = r.get("row_id", "").strip()
            if not rid:
                continue
            # manual wins
            if rid not in codes:
                codes[rid] = r
                sources[rid] = p.stem
    missing = [rid for rid in by_id if rid not in codes]
    pre_by_key = {(r["instance"], r["skill"]): r for r in read_csv(PRECODE)}
    for rid in missing:
        t = by_id[rid]
        p = pre_by_key.get((t["instance"], t["skill"]))
        if p is None:
            codes[rid] = {"row_id": rid, "instance": t["instance"], "skill": t["skill"],
                          "main_cause": "U", "secondary_cause": "", "confidence": "low",
                          "evidence": "no coding and no rule"}
            sources[rid] = "missing"
        else:
            codes[rid] = {"row_id": rid, "instance": t["instance"], "skill": t["skill"],
                          "main_cause": p["rule_code"], "secondary_cause": "",
                          "confidence": p["rule_confidence"], "evidence": p["rule_reason"]}
            sources[rid] = "rule_precode"

    rows = []
    bad = []
    for t in table:
        rid = t["row_id"]
        c = codes[rid]
        code = (c.get("main_cause") or "").strip()
        conf = (c.get("confidence") or "").strip()
        if code not in VALID:
            bad.append((rid, code))
            code = "U"
        # Rule-only coding of `uncertain` rows: do not assert a cause from weak signals.
        if sources[rid] == "rule_precode" and t["final_label"] == "uncertain":
            if code in {"F1", "F3"} or (code == "F4" and conf == "medium"):
                code = "U"
                conf = "low"
                c["evidence"] = "B=uncertain 且规则仅有弱信号，无法归因"
        rows.append({
            "row_id": rid,
            "case": t["case"],
            "instance": t["instance"],
            "skill": t["skill"],
            "phase": t["phase"],
            "b_label": t["final_label"],
            "n_resolved_instance": t["n_resolved_instance"],
            "main_cause": code,
            "secondary_cause": (c.get("secondary_cause") or "").strip(),
            "confidence": conf,
            "evidence": (c.get("evidence") or "").strip(),
            "source": sources[rid],
        })

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    main = [r for r in rows if r["main_cause"] in {"F1", "F2", "F3"}]
    dist = Counter(r["main_cause"] for r in rows)
    summary = {
        "rows": len(rows),
        "bad_codes": bad,
        "source": dict(Counter(r["source"] for r in rows)),
        "main_cause": dict(dist),
        "main_denominator_F1F2F3": len(main),
        "main_share": {c: pct(sum(1 for r in rows if r["main_cause"] == c), len(main))
                       for c in ["F1", "F2", "F3"]},
        "by_b_label": {
            lab: dict(Counter(r["main_cause"] for r in rows if r["b_label"] == lab))
            for lab in sorted({r["b_label"] for r in rows})
        },
        "by_repo": {
            repo: dict(Counter(r["main_cause"] for r in rows if r["case"] == repo))
            for repo in sorted({r["case"] for r in rows})
        },
        "by_n_resolved": {},
    }
    def layer(n):
        n = int(n)
        return "1-3" if n <= 3 else "4-6" if n <= 6 else "7-9"
    for lay in ["1-3", "4-6", "7-9"]:
        sub = [r for r in rows if layer(r["n_resolved_instance"]) == lay]
        summary["by_n_resolved"][lay] = dict(Counter(r["main_cause"] for r in sub))
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    lines = ["# 437 条失败原因编码 v1（规则首过 + 人工/批次编码合并）", "",
             f"- 总条数：{len(rows)}",
             f"- 来源：{dict(Counter(r['source'] for r in rows))}",
             f"- 主因分布（全部）：{dict(dist)}",
             f"- F1/F2/F3 主分母：{len(main)}；占比见下", "",
             "| 原因 | 主分母占比 | Wilson 95% CI |", "|---|---:|---|"]
    for c in ["F1", "F2", "F3"]:
        k = sum(1 for r in rows if r["main_cause"] == c)
        lo, hi = wilson(k, len(main))
        lines.append(f"| {c} | {k}/{len(main)} = {100*k/len(main):.1f}% | [{100*lo:.1f}, {100*hi:.1f}] |")
    lines += ["", "## 按 B 标签", "", "| B 标签 | F1 | F2 | F3 | F4 | U |", "|---|---:|---:|---:|---:|---:|"]
    for lab in ["wrong_fix", "incomplete_patch", "wrong_location", "uncertain", "other"]:
        c = Counter(r["main_cause"] for r in rows if r["b_label"] == lab)
        lines.append(f"| {lab} | {c['F1']} | {c['F2']} | {c['F3']} | {c['F4']} | {c['U']} |")
    lines += ["", "## 按仓库", "", "| 仓库 | F1 | F2 | F3 | F4 | U |", "|---|---:|---:|---:|---:|---:|"]
    for repo in sorted({r["case"] for r in rows}):
        c = Counter(r["main_cause"] for r in rows if r["case"] == repo)
        lines.append(f"| {repo} | {c['F1']} | {c['F2']} | {c['F3']} | {c['F4']} | {c['U']} |")
    lines += ["", "## 按 n_resolved 层", "", "| 层 | F1 | F2 | F3 | F4 | U |", "|---|---:|---:|---:|---:|---:|"]
    for lay in ["1-3", "4-6", "7-9"]:
        c = Counter(r["main_cause"] for r in rows if layer(r["n_resolved_instance"]) == lay)
        lines.append(f"| {lay} | {c['F1']} | {c['F2']} | {c['F3']} | {c['F4']} | {c['U']} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {OUT} ({len(rows)} rows)")
    print(f"wrote {REPORT}")
    print(json.dumps(summary, ensure_ascii=False, indent=2)[:3000])


if __name__ == "__main__":
    main()

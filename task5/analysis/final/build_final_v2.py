"""Add the phase-1 rescue layer and explicit denominators to every final table.

The existing final tables cover the 4050 phase-2 runs on baseline-passed
instances.  The full 500-instance experiment also has 950 phase-1 runs on
baseline-failed instances (287 rescued).  This script joins the two layers and
writes each table with a `data_basis` column that states exactly what its
numbers are computed from.

Run after build_final.py.
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

REPO = Path(__file__).resolve().parents[3]
FINAL = REPO / "experiment_data" / "05_final_tables"
RESCUE = FINAL / "phase1_rescue_by_case_skill.csv"
BASIS_SKILL = (
    "n_passed=baseline-passed instances for this case x skill; "
    "retained=skill resolved on them; broken=n_passed-retained; "
    "n_failed=baseline-failed instances for this case x skill; "
    "rescued=skill resolved on them; n_all=n_passed+n_failed; "
    "skill_successes=retained+rescued; overall_accuracy=skill_successes/n_all; "
    "retention_accuracy=retained/n_passed"
)
BASIS_BASE = (
    "baseline row (no skill): n_passed=baseline passed; retained=baseline passed; "
    "broken=0; n_failed=baseline failed; rescued=0; n_all=case_total; "
    "skill_successes=baseline passed; overall_accuracy=baseline pass rate; "
    "retention_accuracy=100%"
)
BASIS_CASE = (
    "10 skill arms per instance: n_passed=passed instances x10; "
    "retained=sum of 10 skill retentions; broken=sum of 10 skill regressions; "
    "n_failed=failed instances x10; rescued=sum of 10 skill rescues; "
    "n_all=n_passed+n_failed; skill_successes=retained+rescued; "
    "overall_accuracy=skill_successes/n_all; retention_accuracy=retained/n_passed"
)
BASIS_POOL = (
    "all instances covered by this skill: n_passed=sum of baseline-passed instances; "
    "retained=skill resolved on them; broken=n_passed-retained; "
    "n_failed=sum of baseline-failed instances; rescued=skill resolved on them; "
    "n_all=n_passed+n_failed; skill_successes=retained+rescued; "
    "overall_accuracy=skill_successes/n_all; retention_accuracy=retained/n_passed"
)


def read(name):
    return list(csv.DictReader(open(FINAL / name, encoding="utf-8-sig")))


def write(name, cols, rows):
    with open(FINAL / name, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def pct(x):
    return round(float(x) * 100, 2)


def main():
    metrics = read("final_case_skill_metrics.csv")
    acc_skill = read("final_accuracy_by_case_skill.csv")
    base = {r["case"]: r for r in read("final_baseline.csv")}
    rescue = {(r["case"], r["skill"]): r for r in read("phase1_rescue_by_case_skill.csv")}

    # Ensure every case x skill has a rescue row, including flask (0 failed),
    # and state the basis directly in the rescue table.
    rescue_basis = (
        "phase-1 local first-round runs with baseline_resolved=0: "
        "n_failed=assigned failed runs for this case x skill; "
        "rescued=runs with resolved=1"
    )
    skill_keys = [(r["case"], r["skill"]) for r in acc_skill]
    with open(RESCUE, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh); w.writerow(["case", "skill", "n_failed", "rescued", "data_basis"])
        for c, s in sorted(skill_keys):
            r = rescue.get((c, s), {"n_failed": "0", "rescued": "0"})
            w.writerow([c, s, int(r["n_failed"]), int(r["rescued"]), rescue_basis])
    rescue = {(r["case"], r["skill"]): r for r in read(RESCUE)}

    # 1) case x skill, with both strata
    out_skill = []
    for r in metrics:
        case, arm = r["case"], r["arm"]
        if arm == "baseline":
            case_total = int(r.get("case_total") or r.get("n_all"))
            case_passed = int(r.get("case_passed") or r.get("n_passed"))
            rec = {
                "case": case, "arm": arm, "type": "baseline",
                "n_passed": case_passed, "retained": case_passed, "broken": 0,
                "n_failed": case_total - case_passed, "rescued": 0,
                "n_all": case_total, "skill_successes": case_passed,
                "overall_accuracy": round(case_passed / case_total, 6),
                "overall_accuracy_pct": pct(case_passed / case_total),
                "retention_accuracy": 1.0, "retention_accuracy_pct": 100.0,
                "avg_tokens_m": r["avg_tokens_m"], "avg_steps": r["avg_steps"],
                "metric_n": r["metric_n"], "data_basis": BASIS_BASE,
            }
        else:
            n_passed = int(r.get("n_passed") or r["n"])
            retained = int(r.get("retained") or r["resolved"])
            broken = int(r.get("broken") or (n_passed - retained))
            rr = rescue[(case, arm)]
            n_failed = int(rr["n_failed"]); rescued = int(rr["rescued"])
            n_all = n_passed + n_failed
            succ = retained + rescued
            case_total = int(base[case]["case_total"])
            if n_failed and n_all != case_total:
                raise SystemExit(f"n_all mismatch {case}/{arm}: {n_all} vs {case_total}")
            rec = {
                "case": case, "arm": arm, "type": r["type"],
                "n_passed": n_passed, "retained": retained, "broken": broken,
                "n_failed": n_failed, "rescued": rescued, "n_all": n_all,
                "skill_successes": succ,
                "overall_accuracy": round(succ / n_all, 6) if n_all else "",
                "overall_accuracy_pct": pct(succ / n_all) if n_all else "",
                "retention_accuracy": round(retained / n_passed, 6) if n_passed else "",
                "retention_accuracy_pct": pct(retained / n_passed) if n_passed else "",
                "avg_tokens_m": r["avg_tokens_m"], "avg_steps": r["avg_steps"],
                "metric_n": r["metric_n"], "data_basis": BASIS_SKILL,
            }
        out_skill.append(rec)

    cols_skill = ["case", "arm", "type", "n_passed", "retained", "broken",
                  "n_failed", "rescued", "n_all", "skill_successes",
                  "overall_accuracy", "overall_accuracy_pct",
                  "retention_accuracy", "retention_accuracy_pct",
                  "avg_tokens_m", "avg_steps", "metric_n", "data_basis"]
    write("final_case_skill_metrics.csv", cols_skill, out_skill)

    # 2) case x skill, accuracy-only
    out_acc_skill = [{k: r[k] for k in ["case", "arm", "type", "n_passed", "retained",
                                        "broken", "n_failed", "rescued", "n_all",
                                        "skill_successes", "overall_accuracy",
                                        "overall_accuracy_pct", "retention_accuracy",
                                        "retention_accuracy_pct", "data_basis"]}
                     for r in out_skill if r["arm"] != "baseline"]
    write("final_accuracy_by_case_skill.csv",
          ["case", "skill", "type", "n_passed", "retained", "broken", "n_failed",
           "rescued", "n_all", "skill_successes", "overall_accuracy",
           "overall_accuracy_pct", "retention_accuracy", "retention_accuracy_pct", "data_basis"],
          [{"case": r["case"], "skill": r["arm"], **{k: r[k] for k in r if k not in ("case", "arm")}}
           for r in out_acc_skill])

    # 3) by case
    by_case = defaultdict(Counter)
    for r in out_skill:
        if r["arm"] == "baseline":
            continue
        a = by_case[r["case"]]
        for k in ["n_passed", "retained", "broken", "n_failed", "rescued", "n_all", "skill_successes"]:
            a[k] += int(r[k])
    out_case = []
    for case in sorted(by_case):
        a = by_case[case]
        b = base[case]
        out_case.append({
            "case": case, **{k: a[k] for k in ["n_passed", "retained", "broken", "n_failed",
                                               "rescued", "n_all", "skill_successes"]},
            "overall_accuracy": round(a["skill_successes"] / a["n_all"], 6),
            "overall_accuracy_pct": pct(a["skill_successes"] / a["n_all"]),
            "retention_accuracy": round(a["retained"] / a["n_passed"], 6),
            "retention_accuracy_pct": pct(a["retained"] / a["n_passed"]),
            "baseline_accuracy": b["accuracy"],
            "baseline_accuracy_pct": b["accuracy_pct"],
            "data_basis": BASIS_CASE + "; baseline_accuracy=baseline resolved/case_total",
        })
    write("final_accuracy_by_case.csv",
          ["case", "n_passed", "retained", "broken", "n_failed", "rescued", "n_all",
           "skill_successes", "overall_accuracy", "overall_accuracy_pct",
           "retention_accuracy", "retention_accuracy_pct",
           "baseline_accuracy", "baseline_accuracy_pct", "data_basis"], out_case)

    # 4) pooled by skill
    by_skill = defaultdict(Counter)
    for r in out_skill:
        if r["arm"] == "baseline":
            continue
        a = by_skill[r["arm"]]
        a["cases"] += 1
        for k in ["n_passed", "retained", "broken", "n_failed", "rescued", "n_all", "skill_successes"]:
            a[k] += int(r[k])
    out_pool = []
    for skill in sorted(by_skill):
        a = by_skill[skill]
        out_pool.append({
            "skill": skill, "type": "generic" if skill in {
                "code-review-and-quality", "debugging-and-error-recovery", "python-anti-patterns",
                "python-error-handling", "python-pro", "python-project-structure",
                "systematic-debugging", "test-driven-development", "verification-before-completion"} else "dedicated",
            "cases_covered": a["cases"],
            **{k: a[k] for k in ["n_passed", "retained", "broken", "n_failed",
                                 "rescued", "n_all", "skill_successes"]},
            "overall_accuracy": round(a["skill_successes"] / a["n_all"], 6),
            "overall_accuracy_pct": pct(a["skill_successes"] / a["n_all"]),
            "retention_accuracy": round(a["retained"] / a["n_passed"], 6),
            "retention_accuracy_pct": pct(a["retained"] / a["n_passed"]),
            "data_basis": BASIS_POOL,
        })
    write("final_pooled_skill.csv",
          ["skill", "type", "cases_covered", "n_passed", "retained", "broken", "n_failed",
           "rescued", "n_all", "skill_successes", "overall_accuracy", "overall_accuracy_pct",
           "retention_accuracy", "retention_accuracy_pct", "data_basis"], out_pool)

    # 5) overall: two explicit scopes
    total_pass = sum(int(r["n_passed"]) for r in out_skill if r["arm"] != "baseline")
    total_ret = sum(int(r["retained"]) for r in out_skill if r["arm"] != "baseline")
    total_broken = sum(int(r["broken"]) for r in out_skill if r["arm"] != "baseline")
    total_failed = sum(int(r["n_failed"]) for r in out_skill if r["arm"] != "baseline")
    total_rescued = sum(int(r["rescued"]) for r in out_skill if r["arm"] != "baseline")
    total_all = total_pass + total_failed
    total_succ = total_ret + total_rescued
    out_overall = [
        {"scope": "phase2_baseline_passed", "n_passed": total_pass, "retained": total_ret,
         "broken": total_broken, "n_failed": 0, "rescued": 0, "n_all": total_pass,
         "skill_successes": total_ret,
         "overall_accuracy": round(total_ret / total_pass, 6),
         "overall_accuracy_pct": pct(total_ret / total_pass),
         "baseline_n": 405, "baseline_successes": 405, "baseline_accuracy": 1.0,
         "baseline_accuracy_pct": 100.0, "net_pp": round((total_ret / total_pass - 1) * 100, 2),
         "data_basis": "phase-2 only; denominator is baseline-passed instances x10; baseline on the same instances is 405/405"},
        {"scope": "all_500_instances", "n_passed": total_pass, "retained": total_ret,
         "broken": total_broken, "n_failed": total_failed, "rescued": total_rescued,
         "n_all": total_all, "skill_successes": total_succ,
         "overall_accuracy": round(total_succ / total_all, 6),
         "overall_accuracy_pct": pct(total_succ / total_all),
         "baseline_n": 500, "baseline_successes": 405, "baseline_accuracy": 0.81,
         "baseline_accuracy_pct": 81.0,
         "net_pp": round((total_succ / total_all - 0.81) * 100, 2),
         "data_basis": "phase-1 failed instances x10 + phase-2 passed instances x10 = 5000; skill_successes=retained+rescued; baseline=405/500"},
    ]
    write("final_overall.csv",
          ["scope", "n_passed", "retained", "broken", "n_failed", "rescued", "n_all",
           "skill_successes", "overall_accuracy", "overall_accuracy_pct",
           "baseline_n", "baseline_successes", "baseline_accuracy", "baseline_accuracy_pct",
           "net_pp", "data_basis"], out_overall)

    # 6) baseline table with explicit basis
    out_base = []
    for case, b in base.items():
        total = int(b["case_total"]); passed = int(b["case_passed"])
        out_base.append({**b, "n_failed": total - passed, "n_all": total,
                         "data_basis": BASIS_BASE})
    write("final_baseline.csv",
          ["case", "case_total", "case_passed", "n_failed", "n_all", "accuracy",
           "accuracy_pct", "total_tokens", "total_tokens_m", "avg_tokens",
           "avg_tokens_m", "avg_steps", "metric_n", "data_basis"], out_base)

    print("skill totals", total_pass, total_ret, total_broken, total_failed, total_rescued, total_all, total_succ)
    print("overall", out_overall)

    # 7) Excel workbook with a first 口径说明 sheet and every table's data_basis.
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("口径说明")
    for row in [
        ("表", "数据口径"),
        ("全部实验", "500 个 baseline 实例 × 10 个 skill = 5000 次；其中 405 个通过题 ×10=4050（二期），95 个失败题 ×10=950（一期）。"),
        ("baseline", "500 个实例的一次无 skill 运行；405 通过（81.0%），95 失败。"),
        ("final_overall.csv", "两行：phase2_baseline_passed（4050 次保持率 95.21%）和 all_500_instances（5000 次总成功率 82.86%）。主口径看 all_500_instances。"),
        ("final_case_skill_metrics.csv", "132 行 = 12 行 baseline 参考 + 120 行 case×skill；baseline 行 n_all=case_total，skill 行 n_passed=baseline 通过数、n_failed=baseline 失败数；每行都有 data_basis。"),
        ("final_accuracy_by_case_skill.csv", "120 行 = 12 case ×10 skill；n_passed/retained/broken 是二期通过题；n_failed/rescued 是一期失败题；n_all=n_passed+n_failed。"),
        ("final_accuracy_by_case.csv", "12 行；每个 case 的 10 个 skill 合并：n_passed=通过题×10，n_failed=失败题×10。"),
        ("final_pooled_skill.csv", "34 行；每个 skill 覆盖的 case 合并；n_all 是该 skill 实际覆盖的全部实例，不一定是 500。"),
        ("final_baseline.csv", "12 行 baseline；accuracy=passed/total；token/steps 只在 baseline 通过子集上算。"),
        ("phase1_rescue_by_case_skill.csv", "120 行；一期 baseline 失败题的首轮 skill 运行，n_failed/rescued 按 case×skill 汇总。"),
        ("不要混用", "95.21% 是 phase2 保持率，不是总体成功率；总体成功率是 82.86%（4143/5000）。"),
    ]:
        ws.append(row)
    for title, name in [("case_skill_metrics", "final_case_skill_metrics.csv"),
                        ("by_case_skill", "final_accuracy_by_case_skill.csv"),
                        ("by_case", "final_accuracy_by_case.csv"),
                        ("by_skill", "final_pooled_skill.csv"),
                        ("overall", "final_overall.csv"),
                        ("baseline", "final_baseline.csv"),
                        ("phase1_rescue", "phase1_rescue_by_case_skill.csv")]:
        ws = wb.create_sheet(title)
        with open(FINAL / name, encoding="utf-8-sig", newline="") as fh:
            for row in csv.reader(fh):
                ws.append(row)
    wb.save(FINAL / "final_tables.xlsx")

    # 8) summary with the all-5000 headline and per-table denominators.
    lines = [
        "# 最终表（2026-10-18；2026-10-19 补入一期 rescue）", "",
        "## 主口径（全部 500 个实例）", "",
        f"- 全部 skill 运行：**{total_all}**（405 通过题 ×10 + 95 失败题 ×10）。",
        f"- 成功：**{total_succ}**（保持 {total_ret} + 救回 {total_rescued}）。",
        f"- 总体成功率：**{total_succ / total_all:.2%}**（{total_succ}/{total_all}）。",
        "- baseline：**405/500 = 81.00%**；净变化 **+1.86pp**。",
        "- 其中弄坏：**194** 次（4.79% of 4050）；救回：**287** 次。",
        "",
        "## 两个必须分开的口径", "",
        f"- **phase2 保持率**：{total_ret}/{total_pass} = **{total_ret / total_pass:.2%}**；分母是 baseline 已通过题 ×10。",
        "- 同样这 405 题，baseline 是 **405/405 = 100%**；所以 skill 在这层是 **−4.79pp**，不是提升。",
        f"- **all_500_instances**：{total_succ}/{total_all} = **{total_succ / total_all:.2%}**；这是回答“全部 500 题加 skill 后总体怎样”的数字。",
        "",
        "## 表格（每个 CSV 都带 data_basis 列）", "",
        "| 文件 | 行数 | 数据口径 |",
        "|---|---:|---|",
        "| `final_overall.csv` | 2 | 一行 phase2 保持率；一行 all-5000 总成功率 |",
        "| `final_case_skill_metrics.csv` | 132 | 12 baseline 参考 + 120 case×skill；含 n_passed/retained/broken/n_failed/rescued/n_all |",
        "| `final_accuracy_by_case_skill.csv` | 120 | case×skill，含两期合并后的 overall_accuracy |",
        "| `final_accuracy_by_case.csv` | 12 | 每个 case 的 10 skill 合并；n_passed=通过题×10，n_failed=失败题×10 |",
        "| `final_pooled_skill.csv` | 34 | 每个 skill 覆盖的全部实例；n_all 随覆盖范围变化 |",
        "| `final_baseline.csv` | 12 | baseline 500 题；accuracy=passed/total |",
        "| `phase1_rescue_by_case_skill.csv` | 120 | 一期失败题首轮运行；n_failed/rescued |",
        "| `final_tables.xlsx` | 8 sheets | 第一张 `口径说明`，其余为上述表 |",
        "",
        "## 怎么读", "",
        "- `n_passed` = baseline 已通过实例数；`retained` = 加 skill 后仍成功；`broken` = n_passed−retained。",
        "- `n_failed` = baseline 失败实例数；`rescued` = 加 skill 后成功；`n_all=n_passed+n_failed`。",
        "- `skill_successes=retained+rescued`；`overall_accuracy=skill_successes/n_all`。",
        "- `retention_accuracy=retained/n_passed`；它只在“已通过题”这个分层里有效，不能当总体成功率。",
        "- `data_basis` 列逐表写明每个数字的分子/分母来源。",
        "",
        "## 数据质量", "",
        "- 10 条 sphinx-9711 解析器误判、2 条 requests-1921 网络环境误判已修正；",
        "- 3 条空补丁重跑后 resolved；142 条空补丁用 b1/b4 补判；",
        "- 一期 950 次失败题运行来自首轮本地运行（repeat=1）；救回 287 次，53/95 道题至少一个 skill 臂成功。",
        "",
        "## 旧表", "",
        "旧的 `summary_accuracy*.csv` 等基于 m1+m2 的 2700 条 / 4.07%，已移到 `task5/analysis/_deprecated_2026-10-18/`，不要再用。",
    ]
    (FINAL / "final_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

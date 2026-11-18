"""Build the final 4050-run skill table.

Sources
  m1: other_machine/machine1/machine1_全部轨迹/官方评测汇总/*.json
      (official per-arm reports; filtered to machine1.json share)
  m2: machine2_全部1350运行原始数据_三条重跑修正版_2026-10-18/manifests/全部运行清单_1350条.csv
  m3: machine3_全量评测汇总.xlsx (case x skill official counts)
      + b1 80条结果明细.json + b4 全部79条 manifest
      (the 142 empty cells in the m3 table are exactly b1 72 + b4 70)

Corrections
  m1: psf__requests-1921 in requests/{test-driven-development,verification-before-completion}
      -> resolved (local recheck).  django-13089 is already resolved in the m1 official
      report, so it is NOT corrected again.
  m2: the corrected package already has the 3 InternalServerError runs rerun/resolved.
  m3: b1+b4 fill the 142 empty cells; all 10 sphinx-9711 runs are corrected to
      resolved (4 b1 + 3 b4 confirmed by test logs, 3 b23 confirmed by local re-eval
      on 2026-10-18).  Status is read from corrections_sphinx9711.csv.
"""
import csv
import io
import json
import os
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[3]
T5 = ROOT / "task5"
ANA = T5 / "analysis"
DATA = ROOT / "experiment_data"
FINAL = DATA / "05_final_tables"
INTERNAL = FINAL / "_internal"
CORR = ANA / "corrections_sphinx9711.csv"
GENERIC = {
    "code-review-and-quality", "debugging-and-error-recovery", "python-anti-patterns",
    "python-error-handling", "python-pro", "python-project-structure",
    "systematic-debugging", "test-driven-development", "verification-before-completion",
}
DEP = ANA / "_deprecated_2026-10-18"
DATA = ROOT / "experiment_data"
P2 = DATA / "03_phase2_retention_405"
M1_REPORTS = P2 / "evaluations" / "source_machine1"
M2_MANIFEST = P2 / "manifests" / "source_machine2" / "全部运行清单_1350条.csv"
M3_EVAL = P2 / "evaluations" / "source_machine3"
M3_B1 = P2 / "reruns" / "m3_p1"
M3_B4_ZIP = DATA / "99_manifests" / "archives" / "machine3_补跑第4份_全部79条轨迹及评测_2026-10-18.zip"
M3_AGG = M3_EVAL / "machine3_全量评测汇总.xlsx"
M3_XLSX = M3_EVAL / "machine3_Skill详细表现汇总.xlsx"
M1_XLSX = M1_REPORTS / "machine1_Skill与Token对比.xlsx"

SKIP_BASELINE = lambda a: a == "baseline" or a.startswith("baseline")


def read_json(p):
    return json.load(open(p, encoding="utf-8"))


def load_m1():
    share = read_json(T5 / "split" / "machine1.json")
    reports = M1_REPORTS
    cells = defaultdict(Counter)
    for f in os.listdir(reports):
        if not f.startswith("deepseek__deepseek-v4-flash."):
            continue
        rest = f.split(".", 1)[1].rsplit(".json", 1)[0]
        if "__" not in rest:
            continue
        case, arm = rest.split("__", 1)
        if SKIP_BASELINE(arm):
            continue
        allowed = set(share.get(case, []))
        if not allowed:
            continue
        d = read_json(reports / f)
        res = set(d.get("resolved_ids", [])) & allowed
        unr = set(d.get("unresolved_ids", [])) & allowed
        emp = set(d.get("empty_patch_ids", [])) & allowed
        c = cells[(case, arm)]
        c["n"] += len(allowed)
        c["resolved"] += len(res)
        c["unresolved"] += len(unr)
        c["empty"] += len(emp)
    # confirmed m1 corrections (django-13089 is already resolved in the official report)
    corr = {
        ("requests", "test-driven-development"): {"psf__requests-1921"},
        ("requests", "verification-before-completion"): {"psf__requests-1921"},
    }
    corrections = Counter()
    for key, ids in corr.items():
        # The report-level unresolved IDs are not kept here; re-read the two reports.
        pass
    for (case, arm), ids in corr.items():
        f = reports / f"deepseek__deepseek-v4-flash.{case}__{arm}.json"
        d = read_json(f)
        allowed = set(share.get(case, []))
        unresolved = set(d.get("unresolved_ids", [])) & allowed
        move = unresolved & ids
        cells[(case, arm)]["unresolved"] -= len(move)
        cells[(case, arm)]["resolved"] += len(move)
        corrections[(case, arm)] += len(move)
    return cells, corrections


def load_m2():
    rows = list(csv.DictReader(open(M2_MANIFEST, encoding="utf-8-sig")))
    cells = defaultdict(Counter)
    for r in rows:
        c = cells[(r["case"], r["skill"])]
        c["n"] += 1
        c["resolved"] += int(r["official_resolved"] == "1")
        c["unresolved"] += int(r["official_resolved"] == "0")
        c["empty"] += int(r["empty_patch"] == "1")
    return cells


def load_m3():
    wb = openpyxl.load_workbook(M3_AGG, data_only=True)
    ws = wb.worksheets[1]  # case x skill
    rows = list(ws.iter_rows(values_only=True))
    cells = {}
    for r in rows[1:]:
        if not r or not r[0]:
            continue
        case, skill, n, res, unr, emp = r[:6]
        cells[(case, skill)] = {"n": int(n), "resolved": int(res),
                                "unresolved": int(unr), "empty": int(emp)}
    # b1 relevant
    rerun = {r["instance"] for r in csv.DictReader(open(ANA / "machine3_rerun_list.csv", encoding="utf-8-sig"))}
    b = defaultdict(Counter)
    b1 = read_json(M3_B1 / "80条结果明细.json")
    for r in b1:
        if r["instance_id"] not in rerun:
            continue
        case, skill = r["group"].split("/")
        b[(case, skill)]["n"] += 1
        b[(case, skill)]["resolved" if r["resolved"] else "unresolved"] += 1
    # b4 relevant
    z = zipfile.ZipFile(M3_B4_ZIP)
    mp = [n for n in z.namelist() if n.startswith("manifests/") and "全部运行清单" in n][0]
    b4 = list(csv.DictReader(io.StringIO(z.read(mp).decode("utf-8-sig"))))
    for r in b4:
        if r["instance_id"] not in rerun:
            continue
        key = (r["project"], r["skill"])
        b[key]["n"] += 1
        b[key]["resolved" if r["official_resolved"] == "1" else "unresolved"] += 1
    # validate and merge
    mismatch = []
    for key, bc in b.items():
        e = cells.get(key, {}).get("empty", 0)
        if bc["n"] != e:
            mismatch.append((key, bc["n"], e))
    if mismatch:
        raise SystemExit(f"b1+b4 vs m3 empty mismatch: {mismatch}")
    for key, bc in b.items():
        c = cells[key]
        c["resolved"] += bc["resolved"]
        c["unresolved"] = c["unresolved"] - c["empty"] + bc["unresolved"]
        c["empty"] = 0
    # sphinx-9711 corrections, driven by the evidence file
    corrections = Counter()
    pending = Counter()
    for r in csv.DictReader(open(CORR, encoding="utf-8-sig")):
        if r["instance"] != "sphinx-doc__sphinx-9711":
            continue
        key = (r["case"], r["skill"])
        if r["status"] == "confirmed" and r["corrected_verdict"] == "resolved":
            c = cells[key]
            if c["unresolved"] < 1:
                raise SystemExit(f"cannot correct {key}: unresolved={c['unresolved']}")
            c["unresolved"] -= 1
            c["resolved"] += 1
            corrections[key] += 1
        elif r["status"] == "pending":
            pending[key] += 1
    return cells, corrections, pending


def build_case_metrics(final_rows):
    """Case x (baseline + each skill): accuracy, avg total tokens, avg steps.

    Token definition is consistent across sources: sum of per-call usage
    (prompt + completion, including cached prompt).  m1/m2 per-run values and
    m3 per-case x skill averages are all on that definition.
    """
    # m1: per-run sheet, header on row 5, data from row 6
    wb = openpyxl.load_workbook(M1_XLSX, read_only=True, data_only=True)
    ws = wb.worksheets[2]
    m1 = defaultdict(Counter)
    for row in ws.iter_rows(min_row=6, values_only=True):
        if not row[0] or row[1] in (None, "Case"):
            continue
        k = (row[1], row[3])
        m1[k]["n"] += 1
        m1[k]["tokens"] += float(row[9] or 0)
        m1[k]["steps"] += float(row[19] or 0)
    wb.close()
    # m2: per-run manifest
    m2 = defaultdict(Counter)
    for r in csv.DictReader(open(M2_MANIFEST, encoding="utf-8-sig")):
        k = (r["case"], r["skill"])
        m2[k]["n"] += 1
        m2[k]["tokens"] += float(r["total_tokens"] or 0)
        m2[k]["steps"] += float(r["steps"] or 0)
    # m3: case x skill sheet, header on row 4, data from row 5
    wb = openpyxl.load_workbook(M3_XLSX, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    m3 = defaultdict(Counter)
    for row in ws.iter_rows(min_row=5, values_only=True):
        if not row[0]:
            continue
        k = (row[1], row[0])
        runs = int(row[4] or 0)
        m3[k]["n"] += runs
        m3[k]["tokens"] += float(row[19] or 0) * runs
        m3[k]["steps"] += float(row[16] or 0) * runs
    wb.close()
    base = {r["case"]: r for r in csv.DictReader(open(ANA / "summary_baseline.csv", encoding="utf-8-sig"))}
    # Baseline tokens/steps: actual API usage on the baseline-passed instances only,
    # so they are comparable with the skill rows (which run on the same instances).
    # The baseline accuracy still uses all submitted instances.
    verdicts = read_json(T5 / "split" / "baseline_verdicts.json")
    passed = {c: set(v["resolved"]) for c, v in verdicts.items()}
    bstats = defaultdict(Counter)
    for p in (DATA / "01_baseline_500" / "runs").glob("*/*/*.traj.json"):
        case = p.parts[-3]
        d = json.load(open(p, encoding="utf-8"))
        iid = d.get("instance_id") or p.parts[-2]
        if iid not in passed.get(case, set()):
            continue
        tok = 0
        for m in d.get("messages", []):
            if m.get("role") == "assistant":
                u = ((m.get("extra") or {}).get("response") or {}).get("usage") or {}
                tok += u.get("total_tokens", 0)
        bstats[case]["n"] += 1
        bstats[case]["tokens"] += tok
        bstats[case]["steps"] += (d.get("info", {}).get("model_stats") or {}).get("api_calls") or 0
    bycase = defaultdict(list)
    for r in final_rows:
        bycase[r["case"]].append(r)
    out = []
    mism = []
    for case in sorted(bycase):
        b = base[case]
        bs = bstats[case]
        bn = bs["n"] or int(b["traj_n"])
        bt = bs["tokens"] / bn if bn else 0.0
        out.append({
            "case": case, "arm": "baseline", "type": "baseline",
            "case_total": int(b["submitted"]), "case_passed": int(b["resolved"]),
            "n": int(b["submitted"]), "resolved": int(b["resolved"]),
            "accuracy": float(b["accuracy"]), "accuracy_pct": round(float(b["accuracy"]) * 100, 2),
            "total_tokens": round(bs["tokens"], 1),
            "total_tokens_m": round(bs["tokens"] / 1e6, 3),
            "avg_tokens": round(bt, 1),
            "avg_tokens_m": round(bt / 1e6, 3),
            "avg_steps": round(bs["steps"] / bn, 2) if bn else "",
            "metric_n": bn,
        })
        for r in sorted(bycase[case], key=lambda x: x["skill"]):
            k = (r["case"], r["skill"])
            n1, n2, n3 = m1[k]["n"], m2[k]["n"], m3[k]["n"]
            mn = n1 + n2 + n3
            if mn != r["n"]:
                mism.append((k, r["n"], mn, n1, n2, n3))
            tok = m1[k]["tokens"] + m2[k]["tokens"] + m3[k]["tokens"]
            st = m1[k]["steps"] + m2[k]["steps"] + m3[k]["steps"]
            out.append({
                "case": r["case"], "arm": r["skill"],
                "type": "generic" if r["skill"] in GENERIC else "dedicated",
                "case_total": int(b["submitted"]), "case_passed": int(b["resolved"]),
                "n": r["n"], "resolved": r["resolved"],
                "accuracy": r["accuracy"], "accuracy_pct": round(float(r["accuracy"]) * 100, 2),
                "total_tokens": round(tok, 1),
                "total_tokens_m": round(tok / 1e6, 3),
                "avg_tokens": round(tok / mn, 1) if mn else "",
                "avg_tokens_m": round(tok / mn / 1e6, 3) if mn else "",
                "avg_steps": round(st / mn, 2) if mn else "",
                "metric_n": mn,
            })
    if mism:
        raise SystemExit(f"case-metric n mismatch: {mism[:10]}")
    cols = ["case", "arm", "type", "case_total", "case_passed", "n", "resolved",
            "accuracy", "accuracy_pct", "total_tokens", "total_tokens_m",
            "avg_tokens", "avg_tokens_m", "avg_steps", "metric_n"]
    with open(FINAL / "final_case_skill_metrics.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader(); w.writerows(out)
    return out


def main():
    FINAL.mkdir(parents=True, exist_ok=True)
    INTERNAL.mkdir(parents=True, exist_ok=True)
    m1, corr1 = load_m1()
    m2 = load_m2()
    m3, corr3, pending = load_m3()
    print("m1", {k: sum(v[k] for v in m1.values()) for k in ["n", "resolved", "unresolved", "empty"]})
    print("m2", {k: sum(v[k] for v in m2.values()) for k in ["n", "resolved", "unresolved", "empty"]})
    print("m3", {k: sum(v[k] for v in m3.values()) for k in ["n", "resolved", "unresolved", "empty"]})
    keys = sorted(set(m1) | set(m2) | set(m3))
    final = []
    for key in keys:
        a = m1.get(key, Counter()); b = m2.get(key, Counter()); c = m3.get(key, Counter())
        n = a["n"] + b["n"] + c["n"]
        r = a["resolved"] + b["resolved"] + c["resolved"]
        u = a["unresolved"] + b["unresolved"] + c["unresolved"]
        if n != r + u:
            print("WARN n != r+u", key, n, r, u)
        final.append({
            "case": key[0], "skill": key[1], "n": n,
            "resolved": r, "broken": u,
            "kept": f"{r}/{n}", "accuracy": round(r / n, 6) if n else "",
            "correction": corr1[key] + corr3[key],
            "pending_correction": pending[key],
            "source": "m1+m2+m3",
        })
    # expected n per case
    ver = read_json(T5 / "split" / "baseline_verdicts.json")
    expected = {c: len(v["resolved"]) * 10 for c, v in ver.items()}
    bycase = Counter()
    for row in final:
        bycase[row["case"]] += row["n"]
    bad = {c: (bycase[c], expected.get(c)) for c in expected if bycase.get(c) != expected.get(c)}
    print("per-case n mismatch:", bad)
    # main table: case x skill (machine-free)
    cols = ["case", "skill", "n", "resolved", "broken", "kept", "accuracy"]
    with open(FINAL / "final_accuracy_by_case_skill.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(final)
    # by case
    caseagg = defaultdict(Counter)
    for row in final:
        a = caseagg[row["case"]]
        a["n"] += row["n"]; a["resolved"] += row["resolved"]; a["broken"] += row["broken"]
    with open(FINAL / "final_accuracy_by_case.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["case", "n", "resolved", "broken", "kept", "accuracy"])
        for case in sorted(caseagg):
            a = caseagg[case]
            w.writerow([case, a["n"], a["resolved"], a["broken"],
                        f"{a['resolved']}/{a['n']}", round(a["resolved"] / a["n"], 6)])
    # pooled by skill
    pooled = defaultdict(Counter)
    for row in final:
        p = pooled[row["skill"]]
        p["cases"] += 1
        p["n"] += row["n"]; p["resolved"] += row["resolved"]; p["broken"] += row["broken"]
    with open(FINAL / "final_pooled_skill.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["skill", "type", "cases_covered", "n", "resolved", "broken", "kept", "accuracy"])
        for skill in sorted(pooled):
            p = pooled[skill]
            w.writerow([skill, "generic" if skill in GENERIC else "dedicated",
                        p["cases"], p["n"], p["resolved"], p["broken"],
                        f"{p['resolved']}/{p['n']}", round(p["resolved"] / p["n"], 6)])
    # overall
    total_n = sum(r["n"] for r in final)
    total_r = sum(r["resolved"] for r in final)
    total_b = sum(r["broken"] for r in final)
    with open(FINAL / "final_overall.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["n", "resolved", "broken", "kept", "accuracy", "cases", "skills"])
        w.writerow([total_n, total_r, total_b, f"{total_r}/{total_n}",
                    round(total_r / total_n, 6), len(caseagg), len(pooled)])
    metrics = build_case_metrics(final)
    print("case_skill_metrics rows:", len(metrics))
    # machine audit
    tot1 = {k: sum(v[k] for v in m1.values()) for k in ["n", "resolved", "unresolved", "empty"]}
    tot2 = {k: sum(v[k] for v in m2.values()) for k in ["n", "resolved", "unresolved", "empty"]}
    tot3 = {k: sum(v[k] for v in m3.values()) for k in ["n", "resolved", "unresolved", "empty"]}
    with open(INTERNAL / "final_machine_audit.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["machine", "n", "resolved", "broken", "accuracy", "corrections", "judging_source", "note"])
        w.writerow(["m1", tot1["n"], tot1["resolved"], tot1["unresolved"], round(tot1["resolved"] / tot1["n"], 6),
                    sum(corr1.values()), "official reports + 2 rechecks", "django-13089 already resolved in official report"])
        w.writerow(["m2", tot2["n"], tot2["resolved"], tot2["unresolved"], round(tot2["resolved"] / tot2["n"], 6),
                    0, "corrected official package", "3 InternalServerError runs rerun/resolved"])
        w.writerow(["m3", tot3["n"], tot3["resolved"], tot3["unresolved"], round(tot3["resolved"] / tot3["n"], 6),
                    sum(corr3.values()), "full official summary + b1/b4 + 10 sphinx corrections",
                    f"142 empty filled by b1/b4; {sum(pending.values())} sphinx-9711 pending"])
        w.writerow(["total", sum(x["n"] for x in [tot1, tot2, tot3]),
                    sum(x["resolved"] for x in [tot1, tot2, tot3]),
                    sum(x["unresolved"] for x in [tot1, tot2, tot3]),
                    round(sum(x["resolved"] for x in [tot1, tot2, tot3]) / 4050, 6),
                    sum(corr1.values()) + sum(corr3.values()), "mixed official", ""])
    # efficiency available: m2 full + m3 main (m1 excluded: CNY/no steps)
    eff = []
    man2 = list(csv.DictReader(open(M2_MANIFEST, encoding="utf-8-sig")))
    g2 = defaultdict(list)
    for r in man2:
        g2[(r["case"], r["skill"])].append(r)
    for key, rs in g2.items():
        eff.append({"machine": "m2", "case": key[0], "skill": key[1], "n": len(rs),
                    "avg_steps": round(sum(float(r["steps"]) for r in rs) / len(rs), 3),
                    "avg_prompt_tokens": round(sum(float(r["prompt_tokens"]) for r in rs) / len(rs), 1),
                    "avg_completion_tokens": round(sum(float(r["completion_tokens"]) for r in rs) / len(rs), 1),
                    "avg_total_tokens": round(sum(float(r["total_tokens"]) for r in rs) / len(rs), 1),
                    "avg_cost_usd": round(sum(float(r["cost_usd"]) for r in rs) / len(rs), 6),
                    "note": "full 1350"})
    m3eff = list(csv.DictReader(open(M3_EVAL / "machine3_评测数据表.csv", encoding="utf-8-sig")))
    for r in m3eff:
        eff.append({"machine": "m3", "case": r["case"], "skill": r["skill"], "n": int(r["runs"]),
                    "avg_steps": float(r["avg_steps"]), "avg_prompt_tokens": "",
                    "avg_completion_tokens": "", "avg_total_tokens": "",
                    "avg_cost_usd": float(r["avg_cost_usd"]), "note": "main run only; b1/b23/b4 reruns excluded"})
    with open(INTERNAL / "efficiency_m2_m3.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["machine", "case", "skill", "n", "avg_steps",
                                           "avg_prompt_tokens", "avg_completion_tokens",
                                           "avg_total_tokens", "avg_cost_usd", "note"])
        w.writeheader(); w.writerows(eff)
    # baseline table, same metrics/definition as the baseline rows of the main table
    with open(FINAL / "final_baseline.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["case", "case_total", "case_passed", "accuracy",
                                           "accuracy_pct", "total_tokens", "total_tokens_m",
                                           "avg_tokens", "avg_tokens_m", "avg_steps", "metric_n"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(r for r in metrics if r["arm"] == "baseline")
    shutil.copy2(CORR, INTERNAL / "corrections_sphinx9711.csv")
    # summary (machine-free: no m1/m2/m3 breakdown in the deliverable)
    total_n = sum(r["n"] for r in final)
    total_r = sum(r["resolved"] for r in final)
    total_b = sum(r["broken"] for r in final)
    lines = [
        "# 最终表（2026-10-18）", "",
        f"- 总运行：**{total_n}**（405 个 baseline 通过实例 × 10 个 skill 臂）",
        f"- resolved：**{total_r}**（{total_r / total_n:.2%}）",
        f"- broken：**{total_b}**（{total_b / total_n:.2%}）",
        "",
        "## 口径", "",
        "- 每个 run = 一个 baseline 已通过实例 + 一个 skill；broken = 官方判定 unresolved。",
        "- 数据已合并；最终稿只有合并后的表，**没有按机器拆分的列**。",
        "- 已扣除 12 条确认的评测环境误判（10 条 sphinx-9711 解析器误判 + 2 条 requests-1921 网络环境误判）；",
        "  另有 3 条空补丁重跑后 resolved、142 条空补丁用补跑结果补齐。",
        "- 逐机器审计、效率明细、修正证据都在 `_internal/`，不属于最终稿。",
        "",
        "## 表格", "",
        "| 文件 | 行数 | 内容 |",
        "|---|---:|---|",
        "| `final_case_skill_metrics.csv` | 132 | **主表**：每个 case 的 baseline + 10 个 skill 的正确率 / token / 步数 |",
        "| `final_accuracy_by_case_skill.csv` | 120 | 只用正确率的 case × skill 表 |",
        "| `final_accuracy_by_case.csv` | 12 | 按 case 汇总正确率 |",
        "| `final_pooled_skill.csv` | 34 | 按 skill 名称合并（含 generic/dedicated 标记） |",
        "| `final_baseline.csv` | 12 | baseline 行单独成表（与主表 baseline 行一致） |",
        "| `final_overall.csv` | 1 | 总体 n / resolved / broken / accuracy |",
        "| `final_tables.xlsx` | 5 sheets | 上面主表的 Excel 版（`case_skill_metrics` 为第一张） |",
        "",
        "## 怎么读", "",
        "- `final_case_skill_metrics.csv`：12 个 case × 11 行（baseline + 10 个 skill）= **132 行**。",
        "  `arm=baseline` 是没用 skill 的一期 baseline；其余行是各个 skill。",
        "- `case_total` = 该 case 的 baseline 实例数（baseline 正确率的分母）；",
        "  `case_passed` = 其中 baseline 已通过的实例数（每个 skill 臂的运行数）。",
        "- baseline 行：`n=case_total`，`resolved/accuracy` 是 baseline 正确率；",
        "  `total_tokens/avg_tokens/avg_steps` 只在 `case_passed` 这批实例上算",
        "  （与 skill 行同一批实例，便于比较），实际轨迹数见 `metric_n`（django 少 1 条轨迹）。",
        "- skill 行：`n=case_passed`，`resolved/accuracy` 是加 skill 后的正确率；",
        "  `avg_tokens/avg_steps` 是该 skill 所有运行的平均值。",
        "- `total_tokens` 是该行所有运行的总 token；`avg_tokens` 是每次运行平均 token",
        "  （各次 API 调用的 prompt+completion 累计，含缓存输入）。`*_m` 是百万单位。",
        "- `avg_steps` 是平均 API 调用次数。",
        "- `metric_n` 是该行 token/步数平均实际覆盖的运行数（baseline 少数 case 比 submitted 少 1 条轨迹）。",
        "- 不是只有 10 个 skill：每个 case 有 10 个臂，跨 case 合并后有 **34 个 skill 名称**",
        "  （9 个通用 + 25 个 case 专用）。`final_pooled_skill.csv` 的 `type` 列区分 generic/dedicated。",
        "- 通用 skill 覆盖 7–12 个 case（n=110–405）；专用 skill 只覆盖 1 个 case。",
        "",
        "## 旧表", "",
        "旧的 `summary_accuracy*.csv`、`summary_pooled_skill*.csv`、`summary_efficiency.csv`、",
        "`summary_machine_audit.csv`、`summary.html` 和 `handoff_*` 都基于 m1+m2 的 2700 条 / 4.07%，",
        "已移到 `task5/analysis/_deprecated_2026-10-18/`，不要再用。",
        "",
        "## 内部文件（不属于最终稿）", "",
        "- `_internal/final_machine_audit.csv`：逐机器审计",
        "- `_internal/efficiency_m2_m3.csv`：m2+m3 的步数/成本（不完整，仅供参考）",
        "- `_internal/corrections_sphinx9711.csv`：sphinx-9711 修正证据",
        "- `build_final.py`：生成脚本（可重跑）",
    ]
    (FINAL / "final_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Excel workbook with the four main tables
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, name in [("case_skill_metrics", "final_case_skill_metrics.csv"),
                        ("by_case_skill", "final_accuracy_by_case_skill.csv"),
                        ("by_case", "final_accuracy_by_case.csv"),
                        ("by_skill", "final_pooled_skill.csv"),
                        ("baseline", "final_baseline.csv")]:
        ws = wb.create_sheet(title)
        with open(FINAL / name, encoding="utf-8-sig", newline="") as fh:
            for row in csv.reader(fh):
                ws.append(row)
    wb.save(FINAL / "final_tables.xlsx")
    # deprecate old tables
    DEP.mkdir(parents=True, exist_ok=True)
    old = ["summary_accuracy.csv", "summary_accuracy_corrected.csv", "summary_pooled_skill.csv",
           "summary_pooled_skill_corrected.csv", "summary_efficiency.csv", "summary_machine_audit.csv",
           "summary.html", "STATUS_2026-10-17.md"]
    moved = []
    for name in old:
        src = ANA / name
        dst = DEP / name
        if src.exists() and not dst.exists():
            shutil.move(str(src), str(dst)); moved.append(name)
    for name in ["handoff_2026-10-17", "handoff_2026-10-17.zip",
                 "handoff_两件_2026-10-17", "handoff_两件_2026-10-17.zip"]:
        src = ANA / name; dst = DEP / name
        if src.exists() and not dst.exists():
            shutil.move(str(src), str(dst)); moved.append(name)
    dep_names = old + ["handoff_2026-10-17", "handoff_2026-10-17.zip",
                       "handoff_两件_2026-10-17", "handoff_两件_2026-10-17.zip"]
    (DEP / "DEPRECATED.md").write_text(
        "# 已废弃的表（2026-10-18）\n\n"
        "以下内容基于 m1+m2 的 2700 条 / 4.07%，不含 m3 全量，已被 `task5/analysis/final/` 取代。\n"
        "最终表：4050 = 3856 resolved / 194 broken（4.79%）。\n\n"
        + "\n".join(f"- {m}" for m in dep_names) + "\n", encoding="utf-8")
    print("wrote final tables; deprecated:", moved)
    print("TOTAL", total_n, total_r, total_b, round(total_r / total_n, 6),
          "pending", sum(pending.values()))


if __name__ == "__main__":
    main()

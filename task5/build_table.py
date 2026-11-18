#!/usr/bin/env python3
"""Build the result tables: per (case, arm), plus a pooled across-cases view.

Usage:
    python task5/build_table.py

Reads   experiment_data/02_phase1_rescue_95/runs/<case>/<arm>/<instance>/<instance>.traj.json
        task5/eval_reports/*.<case>__<arm>[@<rep>].json
Writes  task5/results.csv    long format, one row per (case, arm)
        task5/results.md     pooled table first, then per-case detail

Why the pooled table is the headline
------------------------------------
A single case is usually too small to detect anything. flask has exactly one
instance in SWE-bench Verified, so its accuracy can only ever be 0% or 100% no
matter how often it is repeated, and seaborn has two. Only django (n=231) has
the power to resolve a ~5pp effect on its own. Pooling all 500 instances is the
only comparison that can answer "does this skill help".

Repeats
-------
Same-instance re-runs of an identical configuration differ by ~40% in step count
(measured; fix.md section 4.4 reports -71%..+61%). Cases smaller than
`--repeat-below` instances are therefore run several times and merged per
instance as a pass *rate*, not a majority vote: an instance that passed 2 of 3
runs counts as 0.67, which keeps ties from needing a special case.

Column notes
------------
steps       `api_calls`, NOT message count: `parallel_tool_calls: true` lets one
            assistant message carry several tool calls (fix.md section 6.1).
tokens      prompt / completion / cache-hit are separate. A skill's cost shows
            up as *input* tokens, and DeepSeek caches them, so a single "total
            tokens" column makes a merely-cached skill look cheaper than it is.
paired_d*   mean over the SAME instances of (skill - baseline). Pairing removes
            per-instance difficulty, which is what makes a small effect visible.
infra       containers that died before the model was called. Excluded from the
            denominator: counting them as wrong answers would make any arm that
            crashed more look worse (fix.md section 5.4).
"""

import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T5 = ROOT / "task5"
DATA_ROOT = ROOT / "experiment_data"
RUNS = DATA_ROOT / "02_phase1_rescue_95" / "runs"
REPORTS = DATA_ROOT / "02_phase1_rescue_95" / "evaluations"

# What each skill is meant to fix, from modeling/analyze_trajectory.py's modes.
SKILL_TARGET = {
    "systematic-debugging": "no-repro / locate-fail",
    "debugging-and-error-recovery": "no-repro",
    "verification-before-completion": "no-verify",
    "test-driven-development": "no-repro / no-verify",
    "python-anti-patterns": "wrong-scope",
    "code-review-and-quality": "wrong-scope",
    "code-simplification": "wrong-scope",
    "python-error-handling": "no-repro",
    "python-project-structure": "locate-fail",
    "python-pro": "no-verify",
}


def run_id_for(case: str, arm_dir: str) -> str:
    """Report id for an arm; keeps `@` out of the harness's container names.

    See run_eval.run_id_for - an `@` in the run id makes the harness build an
    illegal Docker container name, which fails the instance silently.
    """
    return f"{case}__{arm_dir}".replace("@", "__r")


def skill_chars(name: str) -> int:
    p = T5 / "skills" / name / "SKILL.md"
    return p.stat().st_size if p.exists() else 0


def dedicated_skills(case: str) -> list[str]:
    f = T5 / "cases_index.json"
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8")).get(case, {}).get("dedicated") or []


def traj_stats(path: Path) -> dict | None:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    info = d.get("info", {})
    ms = info.get("model_stats", {})
    prompt = completion = cache_hit = 0
    for m in d.get("messages", []):
        u = (m.get("extra") or {}).get("response", {}).get("usage") or {}
        prompt += u.get("prompt_tokens") or 0
        completion += u.get("completion_tokens") or 0
        cache_hit += u.get("prompt_cache_hit_tokens") or 0
    return {
        "instance_id": d.get("instance_id", path.parent.name),
        "api_calls": ms.get("api_calls", 0),
        "cost": ms.get("instance_cost", 0.0),
        "exit_status": info.get("exit_status", ""),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "cache_hit_tokens": cache_hit,
        "model": info.get("config", {}).get("model", {}).get("model_name", ""),
    }


def collect() -> list[dict]:
    rows = []
    if not RUNS.is_dir():
        return rows
    for case_dir in sorted(d for d in RUNS.iterdir() if d.is_dir()):
        case = case_dir.name
        by_arm: dict[str, list[Path]] = defaultdict(list)
        for arm_dir in sorted(d for d in case_dir.iterdir() if d.is_dir()):
            by_arm[arm_dir.name.split("@")[0]].append(arm_dir)

        for arm, dirs in sorted(by_arm.items()):
            # instance_id -> verdict per repeat; instance_id -> stats (first rep)
            verdicts: dict[str, list[bool]] = defaultdict(list)
            # Every repeat's stats, not just the first: the accuracy column
            # merges all repeats, so the cost/step/token columns must too or
            # they describe a different experiment than the one being reported.
            stats: dict[str, list[dict]] = defaultdict(list)
            infra: set[str] = set()
            empty: set[str] = set()
            partial: list[str] = []
            for arm_dir in dirs:
                rep = next(iter(REPORTS.glob(f"*.{run_id_for(case, arm_dir.name)}.json")), None)
                if rep:
                    d = json.loads(rep.read_text(encoding="utf-8"))
                    # An interrupted evaluation leaves a report covering only
                    # the instances it got to. Its verdicts would still average
                    # into a plausible-looking accuracy over a smaller n - and a
                    # smaller n is not a signal here, because arms run with
                    # --only-failures legitimately cover fewer instances. Flag
                    # the row instead of quietly reporting a subset as the score.
                    sc = (d.get("resolved_instances") or 0) + (d.get("unresolved_instances") or 0)
                    sub = d.get("submitted_instances") or 0
                    n_empty = len(set(d.get("empty_patch_ids") or []))
                    if sub == 0 or sc + n_empty != sub:
                        partial.append(f"{arm_dir.name} (scored {sc}+{n_empty} empty of {sub})")
                    for i in d.get("resolved_ids") or []:
                        verdicts[i].append(True)
                    for i in d.get("unresolved_ids") or []:
                        verdicts[i].append(False)
                    # An empty patch is a failure, not an absence: the model
                    # submitted no fix, so the instance is unresolved. This
                    # harness files those separately (`empty_patch_ids`) and
                    # leaves them out of both resolved and unresolved, so
                    # omitting them here computes accuracy over a denominator
                    # smaller than the case has - django alone has 9 of 194,
                    # worth about 5 points of inflated accuracy.
                    for i in d.get("empty_patch_ids") or []:
                        verdicts[i].append(False)
                    infra |= set(d.get("infra_failure_ids") or []) | set(d.get("error_ids") or [])
                    empty |= set(d.get("empty_patch_ids") or [])
                for t in arm_dir.glob("*/*.traj.json"):
                    s = traj_stats(t)
                    if s:
                        stats[s["instance_id"]].append(s)

            scored = {i: v for i, v in verdicts.items() if v}
            if not scored:
                continue
            pass_rate = {i: sum(v) / len(v) for i, v in scored.items()}
            n = len(pass_rate)
            acc = statistics.fmean(pass_rate.values())
            # Per-instance mean over its repeats, then mean over instances.
            s = []
            per_instance: dict[str, dict] = {}
            for i in pass_rate:
                reps_data = stats.get(i) or []
                if not reps_data:
                    continue
                per_instance[i] = {
                    "api_calls": statistics.fmean([x["api_calls"] for x in reps_data]),
                    "cost": statistics.fmean([x["cost"] for x in reps_data]),
                    "prompt_tokens": statistics.fmean([x["prompt_tokens"] for x in reps_data]),
                    "completion_tokens": statistics.fmean([x["completion_tokens"] for x in reps_data]),
                    "cache_hit_tokens": statistics.fmean([x["cache_hit_tokens"] for x in reps_data]),
                    "model": reps_data[0]["model"],
                }
                s.append(per_instance[i])

            rows.append({
                "case": case,
                "arm": arm,
                "arm_type": ("baseline" if arm == "baseline"
                             else "dedicated" if arm in dedicated_skills(case)
                             else "generic"),
                "n_instances": n,
                "repeats": len(dirs),
                "resolved_frac": round(acc, 4),
                "accuracy_pct": round(100 * acc, 1),
                "n_infra_failed": len(infra),
                "n_empty_patch": len(empty),
                "skill_chars": 0 if arm == "baseline" else skill_chars(arm),
                "skill_targets": "" if arm == "baseline" else SKILL_TARGET.get(arm, ""),
                "steps_mean": round(statistics.fmean([x["api_calls"] for x in s]), 2) if s else None,
                "cost_total": round(sum(x["cost"] for x in s), 4),
                "cost_mean": round(statistics.fmean([x["cost"] for x in s]), 5) if s else None,
                "prompt_tokens_mean": round(statistics.fmean([x["prompt_tokens"] for x in s])) if s else None,
                "completion_tokens_mean": round(statistics.fmean([x["completion_tokens"] for x in s])) if s else None,
                "cache_hit_pct": round(100 * sum(x["cache_hit_tokens"] for x in s)
                                       / max(1, sum(x["prompt_tokens"] for x in s)), 1) if s else None,
                "model": next((x["model"] for x in s if x["model"]), ""),
                "report_complete": not partial,
                "_partial": partial,
                "_rate": pass_rate,
                "_stats": per_instance,
            })
    return rows


def add_paired(rows: list[dict]) -> None:
    """Attach paired deltas against the case's own baseline."""
    base = {r["case"]: r for r in rows if r["arm"] == "baseline"}
    for r in rows:
        b = base.get(r["case"])
        r["paired_acc_pp"] = r["paired_d_steps"] = r["paired_d_cost"] = None
        r["paired_d_prompt"] = r["paired_d_completion"] = None
        r["whole_acc_pct"] = None
        r["whole_prompt_tokens"] = r["whole_completion_tokens"] = r["whole_cost"] = None
        if not b or r["arm"] == "baseline":
            continue
        common = set(r["_rate"]) & set(b["_rate"])
        if not common:
            continue
        r["paired_acc_pp"] = round(100 * statistics.fmean(
            [r["_rate"][i] - b["_rate"][i] for i in common]), 2)
        both = [i for i in common if i in r["_stats"] and i in b["_stats"]]
        if both:
            r["paired_d_steps"] = round(statistics.fmean(
                [r["_stats"][i]["api_calls"] - b["_stats"][i]["api_calls"] for i in both]), 2)
            r["paired_d_cost"] = round(statistics.fmean(
                [r["_stats"][i]["cost"] - b["_stats"][i]["cost"] for i in both]), 5)
            r["paired_d_prompt"] = round(statistics.fmean(
                [r["_stats"][i]["prompt_tokens"] - b["_stats"][i]["prompt_tokens"] for i in both]))
            r["paired_d_completion"] = round(statistics.fmean(
                [r["_stats"][i]["completion_tokens"] - b["_stats"][i]["completion_tokens"] for i in both]))
            # Token 折算要单独做：两边的"每实例均值"是在**不同的题目总体**上算的
            # （基线跑全部实例，skill 只跑基线失败的、更长的那些），直接并排会把
            # 题目差异读成 skill 的开销。折算 = 基线总消耗 + 配对差 × 配对实例数，
            # 得到"整个 case 用这个 skill 一共花多少 token"，和基线总数可比。
            if b.get("prompt_tokens_mean") and b.get("completion_tokens_mean"):
                r["whole_prompt_tokens"] = round(
                    b["prompt_tokens_mean"] * b["n_instances"] + r["paired_d_prompt"] * len(both))
                r["whole_completion_tokens"] = round(
                    b["completion_tokens_mean"] * b["n_instances"] + r["paired_d_completion"] * len(both))
                r["whole_cost"] = round(
                    (b["cost_mean"] or 0) * b["n_instances"] + (r["paired_d_cost"] or 0) * len(both), 4)
        r["n_paired"] = len(common)
        # 「用上这个 skill 之后，整个 case 会是多少分」。Δ 是在失败子集上测的，
        # 直接和基线的通过率并排会被误读（分母不同，一个 42 一个 231）；折算回
        # 全实例集 = 基线准确率 + Δ × 失败子集/全部实例，这才是能和基线并排看的
        # 数。它是个估算：假定 skill 在基线已通过的题上不改变结果（"弄坏"测不到，
        # 见 -only-failures 的说明）。
        if b.get("n_instances") and b.get("accuracy_pct") is not None:
            r["whole_acc_pct"] = round(
                b["accuracy_pct"] + r["paired_acc_pp"] * len(common) / b["n_instances"], 1)


def mcnemar_exact_p(fixed: int, broke: int) -> float:
    """Two-sided exact McNemar p-value, from the discordant pairs alone.

    Under the null the `fixed + broke` instances where the skill changed the
    outcome are each a coin flip, so the count favouring the skill is
    Binomial(fixed + broke, 0.5) and the p-value is twice the smaller tail.

    The normal approximation `z = (b - c) / sqrt(b + c)`, which this used first,
    is anti-conservative in exactly the range this experiment lives in: with 5
    rescued and 0 broken it gives z = 2.24 and would call the skill significant,
    while the exact test gives p = 0.0625. Most of these comparisons will have
    a handful of discordant pairs, so the approximation would have manufactured
    findings - which is the one thing the pooled table exists to avoid.
    """
    n = fixed + broke
    if n == 0:
        return 1.0
    k = min(fixed, broke)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def pooled(rows: list[dict]) -> list[dict]:
    """Per-skill effect pooled across every case (McNemar on paired pass rates).

    This is the analysis with real statistical power. A single case is usually
    too small: flask has one instance, so its accuracy can only ever be 0% or
    100%. Pooling puts each skill's effect against the run-to-run noise floor,
    which is the only comparison that can answer "does this skill help".

    An instance counts as resolved for an arm if it passed the majority of its
    repeats. "fixed" and "broke" are reported separately because they cancel in
    the accuracy delta: a skill can rescue 20 instances and break 20 others and
    still show a net zero.
    """
    base = {r["case"]: r for r in rows if r["arm"] == "baseline"}
    out = []
    for r in rows:
        if r["arm"] == "baseline":
            continue
        b = base.get(r["case"])
        if not b:
            continue
        ids = set(r["_rate"]) & set(b["_rate"])
        if not ids:
            continue
        maj = {i: r["_rate"][i] > 0.5 for i in ids}
        bmaj = {i: b["_rate"][i] > 0.5 for i in ids}
        fixed = sum(1 for i in ids if maj[i] and not bmaj[i])
        broke = sum(1 for i in ids if bmaj[i] and not maj[i])
        n = len(ids)
        net = fixed - broke
        z = net / (fixed + broke) ** 0.5 if (fixed + broke) else 0.0
        p = mcnemar_exact_p(fixed, broke)
        out.append({
            "skill": r["arm"],
            "type": r["arm_type"],
            "n_paired": n,
            "baseline_resolved": sum(bmaj.values()),
            "skill_resolved": sum(maj.values()),
            "delta_pp": round(100 * (sum(maj.values()) - sum(bmaj.values())) / n, 2),
            "fixed": fixed,
            "broke": broke,
            "mcnemar_z": round(z, 2),
            "p": round(p, 4),
            "real": p < 0.05,
            "cases": len({x["case"] for x in rows if x["arm"] == r["arm"]}),
        })
    return out


def main() -> int:
    rows = collect()
    if not rows:
        print("no runs found under experiment_data/02_phase1_rescue_95/runs/")
        return 1
    add_paired(rows)
    pool = sorted(pooled(rows), key=lambda x: -abs(x["mcnemar_z"]))

    cols = [k for k in rows[0] if not k.startswith("_")]
    with open(T5 / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda x: (x["case"], x["arm"])):
            w.writerow(r)

    L = ["# task5 结果表", "",
         "每行 = 一个 case 下的一个臂。基线是该 case 自己的无 skill 运行。",
         "重复跑的 case 按实例取**通过率**再平均（3 次里过 2 次 = 0.67），不是取多数。",
         "",
         "两个准确率列，别混用：",
         "- **失败集通过率**：只在该 skill 实际跑过的实例（= 基线失败的题）上算，"
         "分母小，**不能和基线并排比**；",
         "- **整体准确率(估)**：把救回率折算回该 case 的全部实例"
         "（= 基线准确率 + Δ × 失败子集/全实例），这是能和基线直接比的那一列。"
         "它是估算——假定 skill 在基线已通过的题上不改结果，而 `--only-failures` 测不到这个。",
         "",
         "token 与成本同理：`*_mean` 是每实例均值，基线在全部实例上算、skill 臂只在"
         "失败集上算，两者总体不同，**不可并排**；能并排的是下面交付表里的"
         "「全 case 总消耗」（= 基线总消耗 + 配对差 × 配对实例数）。", ""]

    # 交付表：这题要求的就是「每个 case 的无 skill 正确率、各 skill 加上后的正确率、
    # 以及 token 消耗」。放在最前面，因为它就是交付物本体；后面的分 case 明细是它的
    # 证据与分解（覆盖、步数、显著性、技能来源）。
    L += ["## 交付表（每 case × 每 skill）", "",
          "| case | skill | 无 skill 正确率 | 加 skill 后正确率 | Δ | 全case输入token | 全case输出token | 全case成本 | 模型 |",
          "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for case in sorted({r["case"] for r in rows},
                       key=lambda c: -max(x["n_instances"] for x in rows if x["case"] == c)):
        rs = [r for r in rows if r["case"] == case]
        b = next((r for r in rs if r["arm"] == "baseline"), None)
        bacc = f"{b['accuracy_pct']:.1f}%" if b and b.get("accuracy_pct") is not None else "—"
        for r in [x for x in rs if x["arm"] == "baseline"] + sorted(
                [x for x in rs if x["arm"] != "baseline"],
                key=lambda x: -(x.get("whole_acc_pct") or 0)):
            whole = (f"{r['whole_acc_pct']:.1f}%" if r.get("whole_acc_pct") is not None
                     else (bacc if r["arm"] == "baseline" else "—"))
            delta = (f"{r['paired_acc_pp']:+.1f}pp" if r.get("paired_acc_pp") is not None
                     else ("基准" if r["arm"] == "baseline" else "—"))
            pt = r.get("whole_prompt_tokens")
            ct = r.get("whole_completion_tokens")
            wc = r.get("whole_cost")
            if r["arm"] == "baseline" and b and b.get("prompt_tokens_mean"):
                pt = b["prompt_tokens_mean"] * b["n_instances"]
                ct = b["completion_tokens_mean"] * b["n_instances"]
                wc = (b["cost_mean"] or 0) * b["n_instances"]
            L.append(
                f"| {case} | `{r['arm']}` | {bacc} | {whole} | {delta} | "
                f"{f'{pt:,.0f}' if pt else '—'} | {f'{ct:,.0f}' if ct else '—'} | "
                f"{f'${wc:.2f}' if wc else '—'} | {r.get('model') or ''} |")
    L.append("")

    # An interrupted evaluation covers only part of its instances. Its rows are
    # still written - dropping them would look like the arm was never run - but
    # the caveat goes at the top, because a reader who only skims the tables
    # would otherwise take a partial score for the arm's score.
    partial = [r for r in rows if not r.get("report_complete", True)]
    if partial:
        L += ["## ⚠️ 有 arm 的评测不完整 —— 下面这些行的准确率只覆盖了一部分实例", "",
              "`resolved_frac` 是「已判卷实例里通过的比例」，**不是该 arm 的真实正确率**。",
              "重跑 `python task5/run_eval.py --cases <case>` 补齐后再看。", "",
              "| case | arm | 报告覆盖 |", "|---|---|---|"]
        for r in sorted(partial, key=lambda x: (x["case"], x["arm"])):
            L.append(f"| {r['case']} | `{r['arm']}` | {'; '.join(r['_partial'])} |")
        L.append("")

    if pool:
        L += ["## ★ 合并分析（跨全部 case —— 这张才有统计功效）", "",
              "单个 case 大多太小：flask 在 SWE-bench Verified 里只有 1 个实例，",
              "它的准确率只可能是 0% 或 100%，重复多少次都一样。只有 django(n=231) 单独有功效。", "",
              "| skill | 类型 | 配对数 | 基线通过 | 用skill | Δ | 救回 | 弄坏 | McNemar p | 显著 |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
        for p in pool:
            L.append(f"| `{p['skill']}` | {p['type']} | {p['n_paired']} | {p['baseline_resolved']} | "
                     f"{p['skill_resolved']} | {p['delta_pp']:+.2f}pp | {p['fixed']} | {p['broke']} | "
                     f"{p['p']:.3f} | {'**是**' if p['real'] else '否'} |")
        # An arm run with --only-failures has, by construction, a baseline that
        # failed every instance it was given - so "broke" can only ever be 0,
        # and a reader would take that as "this skill never hurts". The test
        # simply does not cover that question in these arms. Flagged rather than
        # left to look like a finding.
        rescue_only = [p for p in pool if p["n_paired"] and p["baseline_resolved"] == 0]
        L += ["",
              "「救回」= 基线失败但该 skill 通过；「弄坏」= 反之。**两者会在准确率差值里互相抵消**，",
              "分开计数才能看出一个 skill 是不是在特定题型上有效、在另一些上帮倒忙。", ""]
        if rescue_only:
            L += [f"⚠️ **{len(rescue_only)} 个 skill 的「弄坏」列按构造必为 0**，不要读成「从不帮倒忙」：",
                  "这些臂是用 `--only-failures` 跑的，只在**基线已经失败**的实例上运行，",
                  "所以配对集合里基线全败，「救回」能测、「弄坏」测不到。",
                  "「弄坏」为 0 的臂：" + "、".join(f"`{p['skill']}`" for p in rescue_only[:8])
                  + ("…" if len(rescue_only) > 8 else ""), ""]
        L += ["**p 用的是精确 McNemar 检验**（只在「救回」和「弄坏」这两个不一致的格子上做二项检验），",
              "不是正态近似。这里配对数普遍很小，正态近似会把 `救回 5 / 弄坏 0` 判成显著（z=2.24），",
              "而精确检验给 p=0.0625——用近似会凭空造出并不存在的效应。", "",
              "**若全部不显著，结论是「这些 skill 的效应小于运行波动」**——",
              "这是对「skill 有没有用」的有效回答，不是实验失败。", ""]

    by_case = defaultdict(list)
    for r in rows:
        by_case[r["case"]].append(r)
    L += ["## 分 case 明细", ""]
    for case in sorted(by_case, key=lambda c: -max(x["n_instances"] for x in by_case[c])):
        rs = sorted(by_case[case], key=lambda x: -(x["resolved_frac"] or 0))
        n = max(x["n_instances"] for x in rs)
        reps = max(x["repeats"] for x in rs)
        verdict = ("**可下结论**" if n >= 100 else "仅方向参考" if n >= 20 else "**样本过小，勿引用**")
        subset = [x for x in rs if x["n_instances"] != n]
        L += [f"### {case}  (n={n}" + (f", x{reps} 次重复" if reps > 1 else "") + f" — {verdict})", ""]
        if subset:
            L += [f"⚠️ 有 {len(subset)} 个臂只覆盖了一部分实例（`--only-failures` 只跑基线失败的题）。",
                  f"它们的**通过率分母不是 {n}**，不能和基线直接比大小——",
                  "**要看「配对Δ」列**，那一列是拿同一批实例和基线比出来的。", ""]
        L += ["| skill | 类型 | 覆盖实例 | 失败集通过率 | 整体准确率(估) | 配对Δ | 步数(配对Δ) | 成本均值 | 输入token | 缓存命中 | skill字符 | 针对失败模式 |",
              "|---|---|---:|---|---|---|---|---|---|---|---|---|"]
        for r in rs:
            # Each row's own numerator and denominator. Scaling a row's fraction
            # by the case's largest n prints a number that is neither - a
            # --only-failures arm covering 50 of 231 instances came out as
            # "46.2/231" - and it looks entirely plausible.
            rn = r["n_instances"]
            pr = f"{r['resolved_frac']*rn:.1f}/{rn}" if r["resolved_frac"] is not None else "—"
            pct = f"{r['accuracy_pct']:.0f}%" if r["accuracy_pct"] is not None else "—"
            cover = str(rn) if rn == n else f"**{rn}/{n}**"
            pa = f"{r['paired_acc_pp']:+.1f}pp" if r.get("paired_acc_pp") is not None else "—"
            ds = f"{r['paired_d_steps']:+.1f}" if r.get("paired_d_steps") is not None else "—"
            wc = f"**{r['whole_acc_pct']:.1f}%**" if r.get("whole_acc_pct") is not None else "—"
            L.append(f"| `{r['arm']}` | {r['arm_type']} | {cover} | {pct} ({pr}) | {wc} | {pa} | {ds} | "
                     f"${r['cost_mean'] or 0:.4f} | {r['prompt_tokens_mean'] or 0:,} | "
                     f"{r['cache_hit_pct'] or 0}% | {r['skill_chars']:,} | {r['skill_targets']} |")
        L.append("")

    if rows:
        L += ["## 采集元信息", "",
              f"- 模型：`{rows[0]['model']}`",
              f"- 臂数：{len(rows)}（{len({r['case'] for r in rows})} 个 case）",
              f"- 基础设施失败合计：{sum(r['n_infra_failed'] for r in rows)}（已排除出分母）", ""]
    (T5 / "results.md").write_text("\n".join(L), encoding="utf-8")
    print(f"wrote task5/results.csv and task5/results.md ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

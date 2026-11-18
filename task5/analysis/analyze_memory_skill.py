"""Read-only analysis: does skill text make the model recall more, and does
that recall explain the skill outcome?

Inputs are the final 4050 runs (adherence_audit/runs.csv), the 499 local
baseline trajectories, the official gold patches in swe_bench_verified.jsonl,
and the external case x skill TF-IDF match table.
"""
import csv
import io
import json
import math
import re
import statistics
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T5 = ROOT / "task5"
DATA = ROOT / "experiment_data"
ANA = T5 / "analysis"
OUT = ANA / "memory_skill_analysis"
RUNS = ANA / "adherence_audit" / "runs.csv"
GOLD = DATA / "00_benchmark_inputs" / "swe_bench_verified.jsonl"
EXT = ROOT / "others_thoughts" / "skill_text_study_20261018.zip"
EXT_BASE = "skill_text_study_20261018/"

MEM_RE = re.compile(
    r"(?i)gold(?:en)?\s+(?:test\s+)?patch|training\s+(?:data|set)|"
    r"memor(?:ized|ization|ised|isation)|from\s+memory|"
    r"I\s+(?:found|recall|remember)\b[^.\n]{0,80}\b(?:memory|training|patch|commit|Django|SWE-bench)|"
    r"SWE-bench\s+instance"
)


def load_gold():
    out = {}
    for line in open(GOLD, encoding="utf-8"):
        d = json.loads(line)
        out[d["instance_id"]] = d.get("patch", "")
    return out


def changed(patch):
    s = set()
    for line in (patch or "").splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-")):
            x = line[1:].strip()
            if x:
                s.add(x)
    return s


def metrics(path):
    d = json.load(open(path, encoding="utf-8"))
    msgs = d.get("messages", [])
    text = "\n".join(
        (m.get("content") or "") + "\n" + (m.get("reasoning_content") or "")
        for m in msgs if m.get("role") == "assistant"
    )
    # Count occurrences in assistant text only.
    hits = len(MEM_RE.findall(text))
    calls = (d.get("info", {}).get("model_stats") or {}).get("api_calls") or 0
    sub = d.get("info", {}).get("submission") or ""
    return hits, calls, sub


def overlap(sub, gold):
    g = changed(gold)
    s = changed(sub)
    return len(g & s) / len(g | s) if g and s else None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def rank_corr(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    try:
        return statistics.correlation(xs, ys)
    except Exception:
        return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gold = load_gold()

    # baseline path by instance
    base = {}
    for p in (DATA / "01_baseline_500" / "runs").glob("*/*/*.traj.json"):
        base[p.parts[-2]] = p
    print("baselines", len(base), flush=True)

    # external lexical match
    lex = {}
    with zipfile.ZipFile(EXT) as z:
        with z.open(EXT_BASE + "results/task_skill_lexical_match.csv") as f:
            for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")):
                lex[(r["case"], r["skill"])] = float(r["mean_tfidf_cosine"])

    pooled = {r["skill"]: r for r in csv.DictReader(open(ANA / "final" / "final_pooled_skill.csv", encoding="utf-8-sig"))}

    # baseline metrics
    bm = {}
    for inst, p in base.items():
        try:
            h, c, sub = metrics(p)
        except Exception:
            continue
        bm[inst] = {"hits": h, "calls": c, "rate": h / c if c else 0,
                    "gold": overlap(sub, gold.get(inst, ""))}

    # skill metrics from final run index
    rows = []
    skipped = []
    for r in csv.DictReader(open(RUNS, encoding="utf-8-sig")):
        if r["path"].endswith(" (zip)"):
            skipped.append(r["instance"]); continue
        try:
            h, c, sub = metrics(r["path"])
        except Exception:
            skipped.append(r["instance"]); continue
        inst = r["instance"]; case = r["case"]; skill = r["skill"]
        rows.append({
            "machine": r["machine"], "case": case, "skill": skill, "instance": inst,
            "outcome": r["outcome"], "hits": h, "calls": c,
            "rate": h / c if c else 0,
            "gold": overlap(sub, gold.get(inst, "")),
            "base_hits": bm.get(inst, {}).get("hits"),
            "base_rate": bm.get(inst, {}).get("rate"),
            "base_gold": bm.get(inst, {}).get("gold"),
            "lex": lex.get((case, skill)),
            "type": pooled.get(skill, {}).get("type", "?"),
        })
    print("skill rows", len(rows), "skipped", len(skipped), flush=True)

    with open(OUT / "runs_memory.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    paired = [r for r in rows if r["base_rate"] is not None]
    print("paired", len(paired), flush=True)

    # Paired baseline vs skill: use per-instance medians across skill arms
    by_inst = defaultdict(list)
    for r in paired: by_inst[r["instance"]].append(r)
    inst_rows = []
    for inst, rs in by_inst.items():
        b = bm.get(inst)
        if not b: continue
        inst_rows.append({
            "instance": inst,
            "base_rate": b["rate"], "base_gold": b["gold"],
            "skill_rate": median([r["rate"] for r in rs]),
            "skill_gold": median([r["gold"] for r in rs]),
            "skill_max_gold": max((r["gold"] for r in rs if r["gold"] is not None), default=None),
            "n_skills": len(rs),
        })

    # Outcome for m1/m2 only
    out_rows = [r for r in rows if r["outcome"] != ""]
    # memory quartiles
    vals = sorted(r["rate"] for r in rows)
    qs = [vals[int(len(vals) * q)] for q in (0.25, 0.5, 0.75)] if vals else [0, 0, 0]
    def qbin(x):
        return 0 if x <= qs[0] else 1 if x <= qs[1] else 2 if x <= qs[2] else 3
    qgroups = defaultdict(list)
    for r in rows: qgroups[qbin(r["rate"])].append(r)

    # lexical quartiles
    lvals = sorted(r["lex"] for r in rows if r["lex"] is not None)
    lqs = [lvals[int(len(lvals) * q)] for q in (0.25, 0.5, 0.75)] if lvals else [0, 0, 0]
    def lbin(x):
        return 0 if x <= lqs[0] else 1 if x <= lqs[1] else 2 if x <= lqs[2] else 3
    lgroups = defaultdict(list)
    for r in rows:
        if r["lex"] is not None: lgroups[lbin(r["lex"])].append(r)

    # examples: baseline zero memory but skill has memory
    ex = [r for r in paired if (r["base_rate"] or 0) == 0 and r["rate"] > 0]
    ex.sort(key=lambda r: -r["rate"])

    lines = [
        "# 记忆 vs skill：轨迹分析（2026-10-19）", "",
        f"- final skill runs 解析：**{len(rows)}**；有 baseline 配对：**{len(paired)}**；跳过：{len(skipped)}。",
        f"- baseline 轨迹：**{len(bm)}**。",
        "",
        "## baseline vs skill（同一实例，按实例取 skill 中位数）", "",
        "| 指标 | baseline | skill |",
        "|---|---:|---:|",
        f"| 记忆中位每 100 次调用 | {100*median([x['base_rate'] for x in inst_rows]):.1f} | {100*median([x['skill_rate'] for x in inst_rows]):.1f} |",
        f"| gold 改动重合度中位数 | {median([x['base_gold'] for x in inst_rows]):.3f} | {median([x['skill_gold'] for x in inst_rows]):.3f} |",
        "",
        f"- skill 中位重合度 > baseline 的实例：**{sum(1 for x in inst_rows if x['skill_gold'] is not None and x['base_gold'] is not None and x['skill_gold'] > x['base_gold'])} / {len(inst_rows)}**",
        f"- 但“10 个 skill 臂里最好的一个” > baseline：**{sum(1 for x in inst_rows if x['skill_max_gold'] is not None and x['base_gold'] is not None and x['skill_max_gold'] > x['base_gold'])} / {len(inst_rows)}**",
        "",
        "## skill 内部：记忆越多，是否越接近 gold / 越容易 resolved？", "",
        "| 记忆率分位 | n | gold 重合中位数 | resolved（m1+m2） |",
        "|---|---:|---:|---:|",
    ]
    for b in range(4):
        rs = qgroups.get(b, [])
        o = [r for r in rs if r["outcome"] != ""]
        lines.append(f"| Q{b+1} | {len(rs)} | {median([r['gold'] for r in rs]) if rs else '—'} | "
                     f"{sum(int(r['outcome']) for r in o)}/{len(o)}" if o else f"| Q{b+1} | {len(rs)} | {median([r['gold'] for r in rs]) if rs else '—'} | — |")
    lines += ["", f"- 记忆率 vs gold 重合度相关（skill runs）：**{rank_corr([r['rate'] for r in rows], [r['gold'] for r in rows])}**",
              f"- 记忆率 vs resolved 相关（m1+m2）：**{rank_corr([r['rate'] for r in out_rows], [int(r['outcome']) for r in out_rows])}**",
              "", "## 按 skill 文本与任务的 TF-IDF 匹配度分位", "",
              "| 匹配度分位 | n | 记忆率中位数 | gold 重合中位数 | resolved（m1+m2） |",
              "|---|---:|---:|---:|---:|"]
    for b in range(4):
        rs = lgroups.get(b, [])
        o = [r for r in rs if r["outcome"] != ""]
        lines.append(f"| Q{b+1} | {len(rs)} | {100*median([r['rate'] for r in rs]):.1f} | {median([r['gold'] for r in rs])} | "
                     f"{sum(int(r['outcome']) for r in o)}/{len(o)}" if o else f"| Q{b+1} | {len(rs)} | {100*median([r['rate'] for r in rs]):.1f} | {median([r['gold'] for r in rs])} | — |")
    lines += ["", "## baseline 无记忆、skill 有记忆的例子", ""]
    for r in ex[:10]:
        lines.append(f"- `{r['case']}/{r['skill']}/{r['instance']}`: baseline rate={r['base_rate']:.3f}, skill rate={r['rate']:.3f}, skill gold={r['gold']}, lex={r['lex']}")
    lines += ["", "## 限制", "",
              "- 记忆措辞只是代理；模型可能记得但不说。",
              "- skill 每实例有 10 个臂，baseline 只有 1 个；比较“最好 skill”会偏向 skill。",
              "- gold 重合度不是“是否抄到”，只是辅助证据。",
              "- m3 没有逐 run outcome；resolved 对比只用 m1+m2。",
              "- 70 条 b4 zip 轨迹未纳入。"]
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", OUT / "summary.md")
    print("\n".join(lines[:35]))


if __name__ == "__main__":
    main()

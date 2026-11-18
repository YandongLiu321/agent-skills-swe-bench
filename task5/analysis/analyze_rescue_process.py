"""Read-only trajectory analysis of the 950 baseline-failed skill runs.

Questions:
  - When a skill rescues a baseline failure, what does the trajectory do
    differently (more tests? more edits? shorter? more memory recall?).
  - On the 108 paired instances, how do skill trajectories differ from the
    no-skill baseline (steps, commands, tests, edits)?
"""
import csv
import io
import json
import re
import statistics
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T5 = ROOT / "task5"
DATA = ROOT / "experiment_data"
ANA = T5 / "analysis"
OUT = ANA / "rescue_process_analysis"
PHASE1_CSV = DATA / "02_phase1_rescue_95" / "metrics" / "phase1_local_runs.csv"
sys.path.insert(0, str(ANA))
import audit_adherence as aa  # reuse command/test/edit classifiers

MEM_RE = re.compile(
    r"(?i)gold(?:en)?\s+(?:test\s+)?patch|training\s+(?:data|set)|"
    r"memor(?:ized|ization)|from\s+memory|SWE-bench\s+instance"
)


def load_csv(name):
    return list(csv.DictReader(open(PHASE1_CSV, encoding="utf-8-sig")))


def feature(path):
    d = json.load(open(path, encoding="utf-8"))
    cmds = aa.commands_of(d)
    tests = [i for i, c in enumerate(cmds) if aa.is_test(c)]
    edits = [i for i, c in enumerate(cmds) if aa.is_edit(c)]
    text = "\n".join(
        (m.get("content") or "") + "\n" + (m.get("reasoning_content") or "")
        for m in d.get("messages", []) if m.get("role") == "assistant"
    )
    sub = d.get("info", {}).get("submission") or ""
    return {
        "steps": (d.get("info", {}).get("model_stats") or {}).get("api_calls") or 0,
        "commands": len(cmds),
        "tests": len(tests),
        "specific_tests": sum(1 for i in tests if aa.is_specific_test(cmds[i])),
        "full_tests": sum(1 for i in tests if not aa.is_specific_test(cmds[i])),
        "edits": len(edits),
        "test_after_last_edit": int(bool(tests) and (not edits or max(tests) > max(edits))),
        "reproduce_before_edit": int(bool(tests) and (not edits or min(tests) < min(edits))),
        "memory_hits": len(MEM_RE.findall(text)),
        "patch_lines": len([l for l in sub.splitlines() if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]),
    }


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def median(xs):
    return statistics.median(xs) if xs else None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_csv("phase1_local_runs.csv")
    first = [r for r in rows if r["repeat"] == "1"]
    print("first-round", len(first), flush=True)

    # baseline features
    base = {}
    for p in (DATA / "01_baseline_500" / "runs").glob("*/*/*.traj.json"):
        try: base[p.parts[-2]] = feature(p)
        except Exception: pass
    print("baseline", len(base), flush=True)

    # skill features
    feats = []
    missing = []
    for r in first:
        p = DATA / "02_phase1_rescue_95" / "runs" / r["case"] / r["arm"] / r["instance"] / f"{r['instance']}.traj.json"
        if not p.exists():
            missing.append(str(p)); continue
        try: f = feature(p)
        except Exception:
            missing.append(str(p)); continue
        feats.append({**r, **f, "path": str(p)})
    print("skill features", len(feats), "missing", len(missing), flush=True)

    # rescue subset
    failed = [x for x in feats if x["baseline_resolved"] == "0"]
    rescued = [x for x in failed if x["resolved"] == "1"]
    not_rescued = [x for x in failed if x["resolved"] == "0"]
    print("failed", len(failed), "rescued", len(rescued), flush=True)

    cols = ["case", "skill", "arm", "instance", "resolved", "baseline_resolved",
            "steps", "commands", "tests", "specific_tests", "full_tests", "edits",
            "test_after_last_edit", "reproduce_before_edit", "memory_hits", "patch_lines", "path"]
    with open(OUT / "rescue_runs.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(failed)

    def group_stats(rs):
        return {
            "n": len(rs),
            "steps": mean([x["steps"] for x in rs]),
            "commands": mean([x["commands"] for x in rs]),
            "tests": mean([x["tests"] for x in rs]),
            "edits": mean([x["edits"] for x in rs]),
            "test_after": mean([x["test_after_last_edit"] for x in rs]),
            "reproduce": mean([x["reproduce_before_edit"] for x in rs]),
            "memory": mean([x["memory_hits"] for x in rs]),
            "patch_lines": mean([x["patch_lines"] for x in rs]),
        }

    # paired baseline vs skill (all first-round skills on the 108 instances)
    by_inst = defaultdict(list)
    for x in feats:
        if x["instance"] in base:
            by_inst[x["instance"]].append(x)
    paired = []
    for inst, xs in by_inst.items():
        b = base[inst]
        paired.append({
            "instance": inst, "n": len(xs),
            "b_steps": b["steps"], "s_steps": median([x["steps"] for x in xs]),
            "b_commands": b["commands"], "s_commands": median([x["commands"] for x in xs]),
            "b_tests": b["tests"], "s_tests": median([x["tests"] for x in xs]),
            "b_test_after": b["test_after_last_edit"], "s_test_after": median([x["test_after_last_edit"] for x in xs]),
            "b_memory": b["memory_hits"], "s_memory": median([x["memory_hits"] for x in xs]),
        })
    with open(OUT / "paired_baseline_skill.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(paired[0].keys())); w.writeheader(); w.writerows(paired)

    rs, nr = group_stats(rescued), group_stats(not_rescued)
    lines = [
        "# baseline 失败题的 skill 轨迹分析（2026-10-19）", "",
        f"- 首轮失败题运行：**{len(failed)}**；救回 **{len(rescued)}**，未救回 **{len(not_rescued)}**。",
        f"- 轨迹解析：{len(feats)} / {len(first)}；缺失 {len(missing)}。",
        "",
        "## 救回 vs 未救回（baseline 失败题）", "",
        "| 指标 | 救回 | 未救回 |",
        "|---|---:|---:|",
    ]
    for k in ["steps", "commands", "tests", "edits", "test_after", "reproduce", "memory", "patch_lines"]:
        lines.append(f"| {k} | {rs[k]:.2f} | {nr[k]:.2f} |")
    lines += ["", "## 同实例 baseline vs skill（108 个本地配对实例，skill 取中位数）", "",
              "| 指标 | baseline | skill |", "|---|---:|---:|"]
    for k in ["steps", "commands", "tests", "test_after", "memory"]:
        bkey = "b_" + k; skey = "s_" + k
        lines.append(f"| {k} | {median([x[bkey] for x in paired]):.2f} | {median([x[skey] for x in paired]):.2f} |")
    lines += [
        "",
        f"- skill 中位步数 < baseline 的实例：**{sum(1 for x in paired if x['s_steps'] < x['b_steps'])} / {len(paired)}**",
        f"- skill 中位命令数 < baseline：**{sum(1 for x in paired if x['s_commands'] < x['b_commands'])} / {len(paired)}**",
        f"- skill 中位测试数 > baseline：**{sum(1 for x in paired if x['s_tests'] > x['b_tests'])} / {len(paired)}**",
        "",
        "## 限制", "",
        "- 救回是运行级；95 道失败题里只有 53 道至少一个臂救回。",
        "- baseline 和 skill 不是随机对照；一期运行仍有模型/采样波动。",
        "- 编辑/测试识别是命令启发式；b4 zip 轨迹未纳入。",
    ]
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", OUT / "summary.md")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

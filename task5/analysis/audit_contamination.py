"""Audit the final 4050 trajectories for SWE-bench memorisation / gold-patch recall.

This is a validity audit, not a model run.  It scans only assistant messages
(content + reasoning_content) for explicit references to:
  - gold/golden patch, gold test patch
  - training data/set, memorised/from memory, "I found it in memory"
  - SWE-bench instance / harness applying the gold test patch

For runs with a submitted patch and an instance with a gold patch in
swe_bench_verified.jsonl, it also computes how much of the gold *changed lines*
the submission reproduced (Jaccard).
"""
import csv
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T5 = ROOT / "task5"
BASE = T5 / "analysis" / "contamination_audit"
RUNS = T5 / "analysis" / "adherence_audit" / "runs.csv"
GOLD = ROOT / "experiment_data" / "00_benchmark_inputs" / "swe_bench_verified.jsonl"
B4 = ROOT / "experiment_data" / "99_manifests" / "archives" / "machine3_补跑第4份_全部79条轨迹及评测_2026-10-18.zip"

GOLD_RE = re.compile(r"(?i)\bgold(?:en)?\s+(?:test\s+)?patch\b|\bthe\s+harness\s+will\s+apply\b")
TRAIN_RE = re.compile(
    r"(?i)\btraining\s+(?:data|set)\b|\bmemor(?:ized|ization|ised|isation)\b|"
    r"\bI\s+(?:found|recall|remember)\b[^.\n]{0,80}\b(?:memory|training|patch|commit|Django|SWE-bench)\b|"
    r"\b(?:from|in)\s+memory\b|\bI've\s+seen\b[^.\n]{0,80}\bSWE-bench\b|"
    r"\bI\s+have\s+seen\b[^.\n]{0,80}\bSWE-bench\b"
)
BENCH_RE = re.compile(r"(?i)\bSWE-bench\s+instance\b|\bSWE-bench\s+instance\s+IDs\b")


def load_gold():
    out = {}
    with open(GOLD, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            out[d["instance_id"]] = d.get("patch", "")
    return out


def changed_lines(patch):
    out = set()
    for line in (patch or "").splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-")):
            s = line[1:].strip()
            if s:
                out.add(s)
    return out


def assistant_text(d):
    parts = []
    for m in d.get("messages", []):
        if m.get("role") != "assistant":
            continue
        for key in ("content", "reasoning_content"):
            v = m.get(key)
            if isinstance(v, str) and v:
                parts.append(v)
    return "\n".join(parts)


def read_zip_traj(name):
    with zipfile.ZipFile(B4) as zf:
        return json.loads(zf.read(name).decode("utf-8"))


def main():
    BASE.mkdir(parents=True, exist_ok=True)
    gold = load_gold()
    rows = list(csv.DictReader(open(RUNS, encoding="utf-8-sig")))
    out = []
    skipped = []
    for i, r in enumerate(rows):
        path = r["path"]
        try:
            if path.endswith(" (zip)"):
                d = read_zip_traj(path[:-6])
            else:
                d = json.load(open(path, encoding="utf-8"))
        except Exception as e:
            skipped.append((r["machine"], r["case"], r["skill"], r["instance"], str(e)))
            continue
        text = assistant_text(d)
        gold_hits = len(GOLD_RE.findall(text))
        train_hits = len(TRAIN_RE.findall(text))
        bench_hits = len(BENCH_RE.findall(text))
        flag = int(bool(gold_hits or train_hits))
        sub = (d.get("info", {}).get("submission") or "")
        overlap = ""
        if sub and r["instance"] in gold:
            gc = changed_lines(gold[r["instance"]])
            sc = changed_lines(sub)
            if gc:
                union = gc | sc
                overlap = round(len(gc & sc) / len(union), 4) if union else ""
        # first strong hit context
        snippet = ""
        m = GOLD_RE.search(text) or TRAIN_RE.search(text)
        if m:
            snippet = text[max(0, m.start() - 80):m.end() + 180].replace("\n", " ")
        out.append({
            "machine": r["machine"], "case": r["case"], "skill": r["skill"],
            "instance": r["instance"], "outcome": r["outcome"],
            "gold_hits": gold_hits, "train_hits": train_hits, "bench_hits": bench_hits,
            "flagged": flag, "gold_change_overlap": overlap,
            "snippet": snippet, "path": path,
        })
        if (i + 1) % 500 == 0:
            print("scanned", i + 1, flush=True)

    with open(BASE / "flagged_runs.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)

    def rate(rs, key):
        n = len(rs)
        return round(sum(int(x[key]) for x in rs) / n, 4) if n else ""

    by_machine = defaultdict(list)
    for x in out: by_machine[x["machine"]].append(x)
    flagged = [x for x in out if x["flagged"]]
    clean = [x for x in out if not x["flagged"]]
    with_out = [x for x in out if x["outcome"] != ""]
    f_out = [x for x in with_out if x["flagged"]]
    c_out = [x for x in with_out if not x["flagged"]]

    lines = [
        "# 轨迹污染审计（2026-10-19）", "",
        f"- 扫描最终 4050 个 run：**{len(out)} 成功解析，{len(skipped)} 跳过**。",
        f"- 出现 gold/golden patch 或训练记忆措辞的 run：**{len(flagged)}**（{len(flagged)/len(out):.1%}）。",
        f"- 仅出现“SWE-bench instance”等基准意识、但无 gold/training 措辞的 run："
        f"**{sum(1 for x in out if x['bench_hits'] and not x['flagged'])}**。",
        "",
        "## 按机器",
        "",
        "| machine | runs | flagged | rate |",
        "|---|---:|---:|---:|",
    ]
    for m, rs in sorted(by_machine.items()):
        f = [x for x in rs if x["flagged"]]
        lines.append(f"| {m} | {len(rs)} | {len(f)} | {len(f)/len(rs):.1%} |")
    lines += ["", "## outcome（仅 m1+m2 有逐条判定）", "",
              "| group | n | resolved | rate |", "|---|---:|---:|---:|"]
    for name, rs in [("flagged", f_out), ("clean", c_out)]:
        resolved = sum(1 for x in rs if x["outcome"] == "1")
        lines.append(f"| {name} | {len(rs)} | {resolved} | {resolved/len(rs):.2%} |" if rs else f"| {name} | 0 | 0 | — |")
    lines += ["", "## 提交 patch 与 gold patch 的改动行重合（Jaccard，越高越像抄到 gold）", ""]
    for name, rs in [("flagged", flagged), ("clean", clean)]:
        vals = [float(x["gold_change_overlap"]) for x in rs if x["gold_change_overlap"] != ""]
        if vals:
            vals.sort()
            lines.append(f"- {name}: n={len(vals)}，median={vals[len(vals)//2]:.3f}，mean={sum(vals)/len(vals):.3f}")
        else:
            lines.append(f"- {name}: 无可比 patch")
    lines += ["", "## 出现最多的 run（前 20）", "",
              "| machine | case | skill | instance | gold | train | bench | outcome | overlap |",
              "|---|---|---|---|---:|---:|---:|---|---:|"]
    for x in sorted(out, key=lambda z: -(z["gold_hits"] + z["train_hits"]))[:20]:
        lines.append(f"| {x['machine']} | {x['case']} | {x['skill']} | {x['instance']} | {x['gold_hits']} | {x['train_hits']} | {x['bench_hits']} | {x['outcome']} | {x['gold_change_overlap']} |")
    lines += ["", "## 首批片段", ""]
    for x in flagged[:8]:
        lines.append(f"- `{x['machine']}/{x['case']}/{x['skill']}/{x['instance']}`: {x['snippet'][:500]}")
    lines += ["", "## 限制", "",
              "- 只扫 assistant 的 content/reasoning_content；不把题目、skill 文本或工具输出算进来。",
              "- “gold patch”措辞不等于真的抄到；重合度只是辅助证据。",
              "- m3 没有逐 run 官方 outcome，outcome 对比只用 m1+m2 的 2700 条。",
              "- 70 条 m3 b4 zip 轨迹已从 zip 内解析。"]
    (BASE / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("flagged", len(flagged), "of", len(out), "skipped", len(skipped))
    print("wrote", BASE / "summary.md")
    print("\n".join(lines[:24]))


if __name__ == "__main__":
    main()

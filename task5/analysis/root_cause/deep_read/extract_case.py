"""Build a deep-read bundle for one crossover instance.

Usage:
  python extract_case.py <instance_id> <fail_skill> <success_skill>

Writes deep_read/cases/<instance_id>/bundle.txt with issue, gold patch,
test_patch, FAIL_TO_PASS / PASS_TO_PASS, both skill texts, both final patches,
official reports/test outputs, and full trajectories (tool outputs truncated).
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "experiment_data"
CROSS = ROOT / "task5" / "analysis" / "crossover"
OUT = Path(__file__).resolve().parent / "cases"

MODEL_DIR = "deepseek__deepseek-v4-flash"
TOOL_TRUNC = 4000


def load_dataset():
    rows = {}
    with open(DATA / "00_benchmark_inputs" / "swe_bench_verified.jsonl", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            rows[d["instance_id"]] = d
    return rows


def phase_of(instance):
    for r in csv.DictReader(open(CROSS / "instances.csv", encoding="utf-8-sig")):
        if r["instance"] == instance:
            return r["phase"]
    return None


def labels_of(instance):
    p = ROOT / "others_finding" / "_extracted" / "B2_20261023" / "任务B材料" / "phase2_final_20261023" / "output" / "final_failure_labels_437.csv"
    out = []
    for r in csv.DictReader(open(p, encoding="utf-8-sig")):
        if r["instance"] == instance:
            out.append((r["skill"], r["final_label"], r["confidence"], r.get("evidence", "")))
    return out


def run_dir(phase, case, skill, instance):
    base = "02_phase1_rescue_95" if phase == "phase1" else "03_phase2_retention_405"
    return DATA / base / "runs" / case / skill / instance


def eval_dir(phase, case, skill, instance):
    base = "02_phase1_rescue_95" if phase == "phase1" else "03_phase2_retention_405"
    d = DATA / base / "eval_logs" / f"{case}__{skill}" / MODEL_DIR / instance
    return d if d.exists() else None


def dump_traj(path, title):
    lines = [f"\n{'='*80}\nTRAJECTORY: {title}\n{'='*80}"]
    d = json.load(open(path, encoding="utf-8"))
    lines.append(f"instance_id={d.get('instance_id')} format={d.get('trajectory_format')}")
    lines.append(f"info={json.dumps(d.get('info', {}), ensure_ascii=False)[:1000]}")
    for i, m in enumerate(d.get("messages", [])):
        role = m.get("role")
        lines.append(f"\n--- msg {i} [{role}] ---")
        rc = m.get("reasoning_content")
        if rc:
            lines.append(f"[reasoning] {rc}")
        content = m.get("content")
        if content:
            lines.append(f"[content] {content}")
        for tc in (m.get("tool_calls") or []):
            fn = tc.get("function", {})
            args = fn.get("arguments", "")
            lines.append(f"[tool:{fn.get('name')}] {args}")
        if role == "tool":
            c = content or ""
            if len(c) > TOOL_TRUNC:
                c = c[:TOOL_TRUNC] + f"\n...[truncated {len(content)-TOOL_TRUNC} chars]"
            lines.append(f"[tool_output]\n{c}")
    return "\n".join(lines)


def main():
    instance, fail_skill, ok_skill = sys.argv[1], sys.argv[2], sys.argv[3]
    ds = load_dataset()
    d = ds[instance]
    phase = phase_of(instance)
    case = d["repo"].split("/")[1] if "/" in d["repo"] else d["repo"]
    # case names in runs use the short repo name, e.g. astropy, django, sphinx
    case_map = {"pylint-dev": "pylint", "pytest-dev": "pytest", "mwaskom": "seaborn",
                "pydata": "xarray", "scikit-learn": "scikit-learn", "psf": "requests",
                "sphinx-doc": "sphinx", "django": "django", "sympy": "sympy",
                "astropy": "astropy", "matplotlib": "matplotlib", "pallets": "flask"}
    case = case_map.get(d["repo"].split("/")[0], d["repo"].split("/")[0])

    outdir = OUT / instance
    outdir.mkdir(parents=True, exist_ok=True)
    parts = []
    parts.append(f"INSTANCE: {instance}\nPHASE: {phase}\nREPO: {d['repo']}\nBASE_COMMIT: {d.get('base_commit')}")
    parts.append(f"\n{'='*80}\nPROBLEM STATEMENT\n{'='*80}\n{d.get('problem_statement','')}")
    parts.append(f"\n{'='*80}\nGOLD PATCH\n{'='*80}\n{d.get('patch','')}")
    parts.append(f"\n{'='*80}\nTEST PATCH\n{'='*80}\n{d.get('test_patch','')}")
    parts.append(f"\n{'='*80}\nFAIL_TO_PASS / PASS_TO_PASS\n{'='*80}\n"
                 f"FAIL_TO_PASS={json.dumps(d.get('FAIL_TO_PASS'), ensure_ascii=False)}\n"
                 f"PASS_TO_PASS={json.dumps(d.get('PASS_TO_PASS'), ensure_ascii=False)}")
    parts.append(f"\n{'='*80}\nLABELS FOR THIS INSTANCE\n{'='*80}")
    for s, l, c, e in labels_of(instance):
        parts.append(f"- {s}: {l} ({c}) | {e[:500]}")

    for skill, tag in [(fail_skill, "FAIL"), (ok_skill, "SUCCESS")]:
        sp = ROOT / "task5" / "skills" / skill / "SKILL.md"
        parts.append(f"\n{'='*80}\nSKILL TEXT [{tag}] {skill}\n{'='*80}")
        parts.append(sp.read_text(encoding="utf-8") if sp.exists() else "<missing>")

        rd = run_dir(phase, case, skill, instance)
        tp = rd / f"{instance}.traj.json"
        parts.append(dump_traj(tp, f"{tag} {skill}") if tp.exists() else f"\n<no trajectory at {tp}>")

        ed = eval_dir(phase, case, skill, instance)
        if ed:
            for fn in ["report.json", "patch.diff", "test_output.txt", "run_instance.log"]:
                fp = ed / fn
                if fp.exists():
                    txt = fp.read_text(encoding="utf-8", errors="replace")
                    if fn == "run_instance.log" and len(txt) > 20000:
                        txt = txt[-20000:]
                    parts.append(f"\n{'='*80}\n{tag} {skill} :: {fn}\n{'='*80}\n{txt}")
        else:
            parts.append(f"\n{'='*80}\n{tag} {skill} :: <no eval dir>\n{'='*80}")

    bundle = outdir / "bundle.txt"
    bundle.write_text("\n".join(parts), encoding="utf-8")
    print(bundle)
    print("chars:", bundle.stat().st_size)


if __name__ == "__main__":
    main()

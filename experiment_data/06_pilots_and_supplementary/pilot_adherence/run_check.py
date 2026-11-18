"""Skill-adherence check: does the model follow an explicit instruction in an optional skill?

Two pytest instances x 2 repeats = 4 runs.  The skill text asks the model to:
  - run `echo SKILL_USED` before anything else,
  - run `echo SKILL_USED` again before submitting,
  - include `SKILL_USED` in the final response.

No official evaluation: we only inspect the trajectory.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T5 = ROOT / "task5"
CONFIG = ROOT / "src" / "minisweagent" / "config" / "benchmarks" / "swebench.yaml"
BASE = T5 / "pilot_adherence"
RUNS = BASE / "runs"
LOGS = BASE / "logs"
SKILL = T5 / "skills_variants" / "adherence-check"
INSTANCES = ["pytest-dev__pytest-10051", "pytest-dev__pytest-6197"]
REPEATS = 2
WORKERS = 2


def env():
    e = os.environ.copy()
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def filter_spec():
    return "^(?:" + "|".join(INSTANCES) + ")$"


def run(rep: int) -> Path:
    outdir = RUNS / f"adherence@r{rep}"
    outdir.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"adherence@r{rep}.log"
    cmd = [
        sys.executable, "-m", "minisweagent.run.utilities.mini_extra", "swebench",
        "--subset", "verified", "--split", "test",
        "--filter", filter_spec(),
        "-o", str(outdir),
        "-w", str(WORKERS),
        "-c", str(CONFIG),
        "-s", str(SKILL),
    ]
    print(f"[run] adherence r{rep}", flush=True)
    t0 = time.time()
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        r = subprocess.run(cmd, cwd=ROOT, env=env(), stdout=fh, stderr=subprocess.STDOUT, text=True)
    print(f"[done] r{rep}: exit {r.returncode} in {(time.time()-t0)/60:.1f} min", flush=True)
    return outdir


def inspect(outdir: Path, rep: int) -> list:
    rows = []
    for p in sorted(outdir.glob("*/*.traj.json")):
        d = json.load(open(p, encoding="utf-8"))
        inst = d.get("instance_id", p.parent.name)
        info = d.get("info", {})
        msgs = d.get("messages", [])
        cmds = []
        for m in msgs:
            for tc in (m.get("tool_calls") or []):
                try:
                    cmds.append(json.loads(tc["function"]["arguments"]).get("command", ""))
                except Exception:
                    pass
        assistant = "\n".join(str(m.get("content", "")) for m in msgs if m.get("role") == "assistant")
        first_cmd = cmds[0] if cmds else ""
        rows.append({
            "rep": rep, "instance": inst,
            "exit": info.get("exit_status"),
            "calls": info.get("model_stats", {}).get("api_calls"),
            "cost": info.get("model_stats", {}).get("instance_cost"),
            "n_cmds": len(cmds),
            "echo_skill_used": sum("echo SKILL_USED" in c for c in cmds),
            "first_cmd_has_skill_used": "SKILL_USED" in first_cmd,
            "assistant_mentions_skill_used": "SKILL_USED" in assistant,
            "submission_mentions_skill_used": "SKILL_USED" in (info.get("submission") or ""),
        })
    return rows


def main() -> int:
    for rep in range(1, REPEATS + 1):
        outdir = run(rep)
    rows = []
    for rep in range(1, REPEATS + 1):
        rows.extend(inspect(RUNS / f"adherence@r{rep}", rep))
    out = BASE / "adherence_results.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== adherence ===")
    for r in rows:
        print(f"r{r['rep']} {r['instance']:30s} exit={r['exit']:10s} calls={r['calls']} "
              f"cmds={r['n_cmds']:2d} echo={r['echo_skill_used']} first={r['first_cmd_has_skill_used']} "
              f"assistant={r['assistant_mentions_skill_used']} submission={r['submission_mentions_skill_used']}")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

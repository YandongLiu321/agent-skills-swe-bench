"""Adherence matrix: does tone/length change whether the model follows a skill?"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T5 = ROOT / "task5"
CONFIG = ROOT / "src" / "minisweagent" / "config" / "benchmarks" / "swebench.yaml"
BASE = T5 / "pilot_adherence_matrix"
RUNS = BASE / "runs"
LOGS = BASE / "logs"
ARMS = {
    "short-hard": T5 / "skills_variants" / "adherence-check",
    "short-soft": T5 / "skills_variants" / "adherence-short-soft",
    "long-hard": T5 / "skills_variants" / "adherence-long-hard",
    "long-soft": T5 / "skills_variants" / "adherence-long-soft",
}
INSTANCES = ["pytest-dev__pytest-10051", "pytest-dev__pytest-6197"]
REPEATS = 1
WORKERS = 2


def env():
    e = os.environ.copy()
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def run(arm: str, rep: int) -> Path:
    outdir = RUNS / f"{arm}@r{rep}"
    outdir.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{arm}@r{rep}.log"
    cmd = [
        sys.executable, "-m", "minisweagent.run.utilities.mini_extra", "swebench",
        "--subset", "verified", "--split", "test",
        "--filter", "^(?:" + "|".join(INSTANCES) + ")$",
        "-o", str(outdir), "-w", str(WORKERS), "-c", str(CONFIG), "-s", str(ARMS[arm]),
    ]
    print(f"[run] {arm} r{rep}", flush=True)
    t0 = time.time()
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        r = subprocess.run(cmd, cwd=ROOT, env=env(), stdout=fh, stderr=subprocess.STDOUT, text=True)
    print(f"[done] {arm} r{rep}: exit {r.returncode} in {(time.time()-t0)/60:.1f} min", flush=True)
    return outdir


def inspect(outdir: Path, arm: str, rep: int) -> list:
    rows = []
    for p in sorted(outdir.glob("*/*.traj.json")):
        d = json.load(open(p, encoding="utf-8"))
        info = d.get("info", {}); ms = info.get("model_stats", {}) or {}
        cmds = []
        for m in d.get("messages", []):
            for tc in (m.get("tool_calls") or []):
                try:
                    cmds.append(json.loads(tc["function"]["arguments"]).get("command", ""))
                except Exception:
                    pass
        assistant = "\n".join(str(m.get("content", "")) for m in d.get("messages", []) if m.get("role") == "assistant")
        rows.append({"arm": arm, "rep": rep, "instance": d.get("instance_id"),
                     "exit": info.get("exit_status"), "calls": ms.get("api_calls"),
                     "cost": ms.get("instance_cost"), "cmds": len(cmds),
                     "echo_skill_used": sum("echo SKILL_USED" in c for c in cmds),
                     "first_cmd_has_skill_used": ("SKILL_USED" in cmds[0]) if cmds else False,
                     "assistant_mentions": "SKILL_USED" in assistant})
    return rows


def main() -> int:
    results = []
    for arm in ARMS:
        for rep in range(1, REPEATS + 1):
            outdir = run(arm, rep)
            results.extend(inspect(outdir, arm, rep))
    out = BASE / "matrix_results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== matrix ===")
    for r in results:
        print(r)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

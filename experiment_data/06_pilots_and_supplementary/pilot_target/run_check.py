"""Template-compatible positive control.

neutral : sd-short-nover-hard
target  : pc-target-only   ("run only the target test; do not run the full suite")

2 pytest instances x 2 arms x 2 repeats = 8 runs.  We check both behaviour
(test-command style) and official outcome.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T5 = ROOT / "task5"
CONFIG = ROOT / "src" / "minisweagent" / "config" / "benchmarks" / "swebench.yaml"
BASE = T5 / "pilot_target"
RUNS = BASE / "runs"
LOGS = BASE / "logs"
REPORTS = BASE / "eval_reports"
ARMS = {
    "neutral": T5 / "skills_variants" / "sd-short-nover-hard",
    "target": T5 / "skills_variants" / "pc-target-only",
}
INSTANCES = ["pytest-dev__pytest-10051", "pytest-dev__pytest-6197"]
REPEATS = 2
WORKERS = 2


def env():
    e = os.environ.copy()
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def filt():
    return "^(?:" + "|".join(INSTANCES) + ")$"


def run(arm: str, rep: int) -> Path:
    outdir = RUNS / f"{arm}@r{rep}"
    outdir.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{arm}@r{rep}.log"
    cmd = [
        sys.executable, "-m", "minisweagent.run.utilities.mini_extra", "swebench",
        "--subset", "verified", "--split", "test",
        "--filter", filt(), "-o", str(outdir), "-w", str(WORKERS),
        "-c", str(CONFIG), "-s", str(ARMS[arm]),
    ]
    print(f"[run] {arm} r{rep}", flush=True)
    t0 = time.time()
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        r = subprocess.run(cmd, cwd=ROOT, env=env(), stdout=fh, stderr=subprocess.STDOUT, text=True)
    preds = outdir / "preds.json"
    n = len(json.loads(preds.read_text(encoding="utf-8"))) if preds.exists() else 0
    print(f"[done] {arm} r{rep}: {n} preds in {(time.time()-t0)/60:.1f} min exit={r.returncode}", flush=True)
    return preds


def evaluate(arm: str, rep: int, preds: Path) -> dict:
    run_id = f"pilot_target_{arm}_r{rep}"
    cmd = [
        sys.executable, str(ROOT / "task4" / "run_eval_lf.py"),
        "-d", "SWE-bench/SWE-bench_Verified", "-s", "test", "-p", str(preds),
        "--max_workers", "2", "-i", *INSTANCES, "-id", run_id,
        "--report_dir", str(REPORTS),
    ]
    REPORTS.mkdir(parents=True, exist_ok=True)
    print(f"[eval] {arm} r{rep} ({run_id})", flush=True)
    r = subprocess.run(cmd, cwd=ROOT, env=env(), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    ms = sorted(REPORTS.glob(f"*.{run_id}.json"))
    if not ms:
        return {"arm": arm, "rep": rep, "status": "no report", "exit": r.returncode,
                "tail": (r.stdout or "")[-300:] + (r.stderr or "")[-300:]}
    d = json.loads(ms[-1].read_text(encoding="utf-8"))
    return {"arm": arm, "rep": rep, "status": "ok",
            "resolved": len(d.get("resolved_ids", [])),
            "unresolved": len(d.get("unresolved_ids", [])),
            "empty": len(d.get("empty_patch_ids", [])),
            "resolved_ids": d.get("resolved_ids", []),
            "unresolved_ids": d.get("unresolved_ids", [])}


def behavior(outdir: Path, rep: int) -> list:
    rows = []
    for p in sorted(outdir.glob("*/*.traj.json")):
        d = json.load(open(p, encoding="utf-8")); info = d.get("info", {})
        ms = info.get("model_stats", {}) or {}
        cmds = []
        for m in d.get("messages", []):
            for tc in (m.get("tool_calls") or []):
                try:
                    cmds.append(json.loads(tc["function"]["arguments"]).get("command", ""))
                except Exception:
                    pass
        pytest_cmds = [c for c in cmds if re.search(r"\b(pytest|tox|python -m pytest|unittest)\b", c, re.I)]
        specific = [c for c in pytest_cmds if "::" in c or re.search(r"test_[A-Za-z0-9_]+\.py", c)]
        rows.append({"rep": rep, "instance": d.get("instance_id"),
                     "exit": info.get("exit_status"), "calls": ms.get("api_calls"),
                     "cost": ms.get("instance_cost"), "cmds": len(cmds),
                     "pytest_cmds": len(pytest_cmds), "specific_cmds": len(specific),
                     "test_edit": bool(re.search(r"diff --git a/tests?/|\+\+\+ b/tests?/", info.get("submission") or ""))})
    return rows


def main() -> int:
    results = []; runs = []
    for arm in ARMS:
        for rep in range(1, REPEATS + 1):
            outdir = RUNS / f"{arm}@r{rep}"
            preds = run(arm, rep)
            if preds.exists():
                results.append(evaluate(arm, rep, preds))
            runs.extend(behavior(outdir, rep))
    out = BASE / "target_results.json"
    out.write_text(json.dumps({"eval": results, "behavior": runs}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== eval ===")
    for r in results:
        print(r)
    print("\n=== behavior ===")
    for r in runs:
        print(r)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

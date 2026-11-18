"""Hard-instance test: does target-only verification change the outcome?

Instance: django__django-13297 (baseline passed; 6/9 existing skill arms fail with
a PASS_TO_PASS regression, so running the full suite matters).

neutral : sd-short-nover-hard
target  : pc-target-only   ("run only the target test; do not run the full suite")

2 arms x 2 repeats = 4 runs.  Official eval for each.
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
BASE = T5 / "pilot_hard"
RUNS = BASE / "runs"
LOGS = BASE / "logs"
REPORTS = BASE / "eval_reports"
INST = "django__django-13297"
IMAGE = "swebench/sweb.eval.x86_64.django_1776_django-13297:latest"
ARMS = {
    "neutral": T5 / "skills_variants" / "sd-short-nover-hard",
    "target": T5 / "skills_variants" / "pc-target-only",
}
REPEATS = 2
WORKERS = 1


def env():
    e = os.environ.copy()
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def ensure_image():
    if subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True).returncode == 0:
        print("[image] cached", flush=True); return
    for i in range(1, 4):
        print(f"[image] pull attempt {i}", flush=True)
        r = subprocess.run(["docker", "pull", "--platform", "linux/amd64", IMAGE],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            print("[image] pulled", flush=True); return
        print("[image] failed:", r.stderr[-200:], flush=True)
        time.sleep(20)
    raise RuntimeError("image unavailable")


def run(arm: str, rep: int) -> Path:
    outdir = RUNS / f"{arm}@r{rep}"
    outdir.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{arm}@r{rep}.log"
    cmd = [
        sys.executable, "-m", "minisweagent.run.utilities.mini_extra", "swebench",
        "--subset", "verified", "--split", "test",
        "--filter", f"^({INST})$", "-o", str(outdir), "-w", str(WORKERS),
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
    run_id = f"pilot_hard_{arm}_r{rep}"
    cmd = [
        sys.executable, str(ROOT / "task4" / "run_eval_lf.py"),
        "-d", "SWE-bench/SWE-bench_Verified", "-s", "test", "-p", str(preds),
        "--max_workers", "1", "-i", INST, "-id", run_id,
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


def behavior(outdir: Path, arm: str, rep: int) -> dict:
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
        return {"arm": arm, "rep": rep, "instance": INST, "exit": info.get("exit_status"),
                "calls": ms.get("api_calls"), "cost": ms.get("instance_cost"),
                "cmds": len(cmds), "pytest_cmds": len(pytest_cmds),
                "specific_cmds": len(specific),
                "test_edit": bool(re.search(r"diff --git a/tests?/|\+\+\+ b/tests?/", info.get("submission") or ""))}
    return {"arm": arm, "rep": rep, "status": "no traj"}


def main() -> int:
    ensure_image()
    results = []; beh = []
    for arm in ARMS:
        for rep in range(1, REPEATS + 1):
            outdir = RUNS / f"{arm}@r{rep}"
            preds = run(arm, rep)
            if preds.exists():
                results.append(evaluate(arm, rep, preds))
            beh.append(behavior(outdir, arm, rep))
    out = BASE / "hard_results.json"
    out.write_text(json.dumps({"eval": results, "behavior": beh}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== eval ===")
    for r in results: print(r)
    print("\n=== behavior ===")
    for r in beh: print(r)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

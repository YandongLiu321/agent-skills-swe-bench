"""Positive-control pilot: neutral vs deliberately harmful skill text.

Design
  neutral : task5/skills_variants/sd-short-nover-hard  (500 words, hard, no verification)
  harmful : task5/skills_variants/pc-harmful           (488 words, hard, no verification)
  instances: 8 pytest baseline-passed instances (fixed list; 10051 reuses an
             already-pulling image, replacing 10081 from the seeded sample)
  repeats: 3
  runs: 8 x 2 x 3 = 48

The purpose is a go/no-go for the 2x2x2: if a deliberately harmful text does
not raise the unresolved rate above the neutral control, the measurement is not
sensitive enough and the $390 experiment should not start.

Outputs
  task5/pilot_pc/runs/<arm>@r<rep>/preds.json
  task5/pilot_pc/eval_reports/*.json
  task5/pilot_pc/pilot_results.json
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T5 = ROOT / "task5"
CONFIG = ROOT / "src" / "minisweagent" / "config" / "benchmarks" / "swebench.yaml"
PILOT = T5 / "pilot_pc"
RUNS = PILOT / "runs"
LOGS = PILOT / "logs"
REPORTS = PILOT / "eval_reports"

INSTANCES = [
    "pytest-dev__pytest-10051",
    "pytest-dev__pytest-6197",
    "pytest-dev__pytest-7324",
    "pytest-dev__pytest-7490",
    "pytest-dev__pytest-6202",
    "pytest-dev__pytest-7205",
    "pytest-dev__pytest-7432",
    "pytest-dev__pytest-7521",
]
ARMS = {
    "neutral": T5 / "skills_variants" / "sd-short-nover-hard",
    "harmful": T5 / "skills_variants" / "pc-harmful",
}
REPEATS = 3
WORKERS = 4


def env():
    e = os.environ.copy()
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def image_name(inst: str) -> str:
    return f"swebench/sweb.eval.x86_64.{inst.replace('__', '_1776_').lower()}:latest"


def ensure_image(inst: str) -> None:
    img = image_name(inst)
    if subprocess.run(["docker", "image", "inspect", img], capture_output=True).returncode == 0:
        print(f"  [image] cached {img}", flush=True)
        return
    for attempt in range(1, 4):
        print(f"  [image] pull {img} (attempt {attempt})", flush=True)
        r = subprocess.run(["docker", "pull", "--platform", "linux/amd64", img],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            print(f"  [image] pulled {img}", flush=True)
            return
        print(f"  [image] failed: {r.stderr[-300:]}", flush=True)
        time.sleep(15)
    raise RuntimeError(f"could not pull {img}")


def filter_spec() -> str:
    return "^(?:" + "|".join(INSTANCES) + ")$"


def run_arm(arm: str, rep: int) -> Path:
    outdir = RUNS / f"{arm}@r{rep}"
    outdir.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{arm}@r{rep}.log"
    cmd = [
        sys.executable, "-m", "minisweagent.run.utilities.mini_extra", "swebench",
        "--subset", "verified", "--split", "test",
        "--filter", filter_spec(),
        "-o", str(outdir),
        "-w", str(WORKERS),
        "-c", str(CONFIG),
        "-s", str(ARMS[arm]),
    ]
    print(f"  [run] {arm} r{rep}", flush=True)
    t0 = time.time()
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        r = subprocess.run(cmd, cwd=ROOT, env=env(), stdout=fh, stderr=subprocess.STDOUT, text=True)
    preds = outdir / "preds.json"
    n = len(json.loads(preds.read_text(encoding="utf-8"))) if preds.exists() else 0
    print(f"  [done] {arm} r{rep}: {n} preds in {(time.time()-t0)/60:.1f} min "
          f"(exit {r.returncode})", flush=True)
    return preds


def evaluate(arm: str, rep: int, preds: Path) -> dict:
    run_id = f"pilot_{arm}_r{rep}"
    cmd = [
        sys.executable, str(ROOT / "task4" / "run_eval_lf.py"),
        "-d", "SWE-bench/SWE-bench_Verified", "-s", "test",
        "-p", str(preds),
        "--max_workers", "2",
        "-i", *INSTANCES,
        "-id", run_id,
        "--report_dir", str(REPORTS),
    ]
    REPORTS.mkdir(parents=True, exist_ok=True)
    print(f"  [eval] {arm} r{rep} ({run_id})", flush=True)
    r = subprocess.run(cmd, cwd=ROOT, env=env(), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    matches = sorted(REPORTS.glob(f"*.{run_id}.json"))
    if not matches:
        return {"arm": arm, "rep": rep, "status": "no report", "exit": r.returncode,
                "tail": (r.stdout or "")[-500:] + (r.stderr or "")[-500:]}
    report = json.loads(matches[-1].read_text(encoding="utf-8"))
    return {
        "arm": arm, "rep": rep, "status": "ok", "report": str(matches[-1]),
        "resolved": len(report.get("resolved_ids", [])),
        "unresolved": len(report.get("unresolved_ids", [])),
        "empty": len(report.get("empty_patch_ids", [])),
        "resolved_ids": report.get("resolved_ids", []),
        "unresolved_ids": report.get("unresolved_ids", []),
        "empty_ids": report.get("empty_patch_ids", []),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    print(f"instances: {len(INSTANCES)}  arms: {list(ARMS)}  repeats: {REPEATS}  "
          f"runs: {len(INSTANCES) * len(ARMS) * REPEATS}", flush=True)
    for inst in INSTANCES:
        print(f"  {inst}  <- {ARMS and ''}{image_name(inst)}", flush=True)
    if args.dry_run:
        for arm, path in ARMS.items():
            print(f"  arm {arm}: -s {path}", flush=True)
        return 0

    for inst in INSTANCES:
        ensure_image(inst)

    results = []
    for arm in ARMS:
        for rep in range(1, REPEATS + 1):
            preds = run_arm(arm, rep)
            if preds.exists():
                results.append(evaluate(arm, rep, preds))
            else:
                results.append({"arm": arm, "rep": rep, "status": "no preds"})

    out = PILOT / "pilot_results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== summary ===", flush=True)
    for arm in ARMS:
        rs = [r for r in results if r.get("arm") == arm and r.get("status") == "ok"]
        print(f"{arm:8s} runs={len(rs)}  resolved={sum(r['resolved'] for r in rs)}  "
              f"unresolved={sum(r['unresolved'] for r in rs)}  "
              f"empty={sum(r['empty'] for r in rs)}", flush=True)
    print("wrote", out, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

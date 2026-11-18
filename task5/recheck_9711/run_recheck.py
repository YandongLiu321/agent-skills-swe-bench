"""Re-evaluate the 10 sphinx-9711 patches locally.

The b1 4 and b4 3 reports already show resolved=false while the test output says
"1 passed" (parser issue).  The b23 3 have no reports.  This script scores all 10
patches with the local harness, which resolved sphinx-9711 in the baseline eval.

No model calls: 10 official evaluations, one instance each.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
PRED = BASE / "preds"
REPORTS = BASE / "reports"
INST = "sphinx-doc__sphinx-9711"


def env():
    e = os.environ.copy()
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    wanted = sys.argv[1:]
    skills = sorted(d.name for d in PRED.iterdir()
                    if (d / "preds.json").exists() and (not wanted or d.name in wanted))
    print("skills:", len(skills), skills, flush=True)
    rows = []
    for skill in skills:
        run_id = f"recheck9711_{skill}"
        cmd = [
            sys.executable, str(ROOT / "task5" / "run_eval_lf.py"),
            "-d", "SWE-bench/SWE-bench_Verified", "-s", "test",
            "-p", str(PRED / skill / "preds.json"),
            "--max_workers", "1", "-i", INST, "-id", run_id,
            "--report_dir", str(REPORTS),
        ]
        print(f"[eval] {skill}", flush=True)
        r = subprocess.run(cmd, cwd=ROOT, env=env(), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        ms = sorted(REPORTS.glob(f"*.{run_id}.json"))
        if not ms:
            rows.append({"skill": skill, "status": "no report", "exit": r.returncode,
                         "tail": (r.stdout or "")[-300:] + (r.stderr or "")[-300:]})
            continue
        d = json.loads(ms[-1].read_text(encoding="utf-8"))
        rows.append({
            "skill": skill, "status": "ok",
            "resolved": d.get("resolved_ids", []),
            "unresolved": d.get("unresolved_ids", []),
            "empty": d.get("empty_patch_ids", []),
            "report": str(ms[-1]),
        })
    out = BASE / "recheck_results.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== results ===")
    for r in rows:
        print(r)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

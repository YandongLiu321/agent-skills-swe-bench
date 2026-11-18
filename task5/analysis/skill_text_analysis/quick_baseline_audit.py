"""Quick test 5: audit the 405 baseline-passed verdicts for false positives.

A resolved baseline instance is suspicious if:
  - its test output says no tests ran / collected 0 items / everything skipped
  - its report has FAIL_TO_PASS success = 0 or PASS_TO_PASS failure > 0
  - its output shows network failures (502 / ConnectionError) while still resolved
"""

import glob
import json
import os
import re
from collections import Counter, defaultdict

REPO = os.environ.get("SWE_REPO", ".")
ROOT = os.path.join(REPO, "logs", "run_evaluation")
PATTERNS = {
    "no_tests": re.compile(r"(no tests ran|collected 0 items|0 items collected)", re.I),
    "all_skipped": re.compile(r"(\d+ skipped)", re.I),
    "net": re.compile(r"(assert\s+5\d\d\s*==|ConnectionError|NewConnectionError|Max retries exceeded|Temporary failure in name resolution)"),
}

reports = [p for p in glob.glob(os.path.join(ROOT, "**", "report.json"), recursive=True)
           if "baseline" in p.replace(os.sep, "/").split("/")[-4]]
print("baseline reports:", len(reports))

suspicious = []
stats = Counter()
seen = set()
for rp in reports:
    try:
        d = json.load(open(rp, encoding="utf-8"))
    except Exception:
        continue
    for inst, v in d.items():
        if not isinstance(v, dict) or "tests_status" not in v or not v.get("resolved"):
            continue
        key = (os.path.basename(os.path.dirname(os.path.dirname(rp))), inst)
        if key in seen:
            continue
        seen.add(key)
        ts = v["tests_status"]
        f2p_ok = len(ts["FAIL_TO_PASS"]["success"])
        p2p_fail = len(ts["PASS_TO_PASS"]["failure"])
        out_path = os.path.join(os.path.dirname(rp), "test_output.txt")
        out = open(out_path, encoding="utf-8", errors="replace").read() if os.path.isfile(out_path) else ""
        flags = {k: len(p.findall(out)) for k, p in PATTERNS.items()}
        bad = []
        if f2p_ok == 0:
            bad.append("f2p_success=0")
        if p2p_fail > 0:
            bad.append(f"p2p_fail={p2p_fail}")
        if flags["no_tests"]:
            bad.append("no_tests")
        if flags["net"]:
            bad.append("network_text")
        # skip count > 0 is not fatal; record separately
        stats["resolved_checked"] += 1
        stats["with_skip"] += 1 if flags["all_skipped"] else 0
        if bad:
            suspicious.append((key[0], inst, bad, flags))

print(f"resolved baseline instances checked: {stats['resolved_checked']}")
print(f"  with 'skipped' text: {stats['with_skip']}")
print(f"  suspicious (f2p=0 / p2p fail / no tests / network): {len(suspicious)}")
for arm, inst, bad, flags in suspicious[:40]:
    print(f"  {inst:45s} arm={arm:38s} {bad} net={flags['net']}")

# also: distribution of FAIL_TO_PASS sizes for resolved instances
sizes = []
for rp in reports:
    try:
        d = json.load(open(rp, encoding="utf-8"))
    except Exception:
        continue
    for inst, v in d.items():
        if isinstance(v, dict) and v.get("resolved") and "tests_status" in v:
            sizes.append(len(v["tests_status"]["FAIL_TO_PASS"]["success"]))
print(f"\nFAIL_TO_PASS success count for resolved instances: "
      f"median={sorted(sizes)[len(sizes)//2]}, min={min(sizes)}, max={max(sizes)}")

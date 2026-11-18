"""How widespread is network-dependent flakiness in the official eval?

For every report.json in logs/run_evaluation:
  - resolved verdict
  - number of failing FAIL_TO_PASS / PASS_TO_PASS tests
  - whether the raw test_output contains a *network failure assertion* (502/503,
    ConnectionError raised, name resolution, max retries, URL timeout), counted
    only in FAILED test blocks rather than anywhere in the text.

The precise signal: a failed test line followed by a traceback containing a network
exception. We approximate by scanning the test_output for 'assert 502', 'assert 503',
'ConnectionError: HTTPConnectionPool', 'NewConnectionError', 'Max retries exceeded',
'Temporary failure in name resolution', 'urlopen error'.
"""

import glob
import json
import os
import re
from collections import Counter, defaultdict

PATTERNS = {
    "assert_5xx": re.compile(r"assert\s+5\d\d\s*=="),
    "http_connection_pool": re.compile(r"ConnectionError: HTTPConnectionPool"),
    "new_connection_error": re.compile(r"NewConnectionError"),
    "max_retries": re.compile(r"Max retries exceeded"),
    "dns": re.compile(r"Temporary failure in name resolution"),
    "urlopen": re.compile(r"urlopen error"),
    "proxy": re.compile(r"ProxyError|proxy"),
}
NETWORK = re.compile("|".join(f"(?:{p.pattern})" for p in PATTERNS.values()))

_REPO = os.environ.get("SWE_REPO", ".")
root = os.path.join(_REPO, "logs", "run_evaluation")
reports = glob.glob(os.path.join(root, "**", "report.json"), recursive=True)
print("reports:", len(reports))

rows = []
for rp in reports:
    try:
        d = json.load(open(rp, encoding="utf-8"))
    except Exception:
        continue
    for inst, v in d.items():
        if not isinstance(v, dict) or "tests_status" not in v:
            continue
        arm = os.path.relpath(os.path.dirname(os.path.dirname(rp)), root).replace(os.sep, "/")
        out_path = os.path.join(os.path.dirname(rp), "test_output.txt")
        out = open(out_path, encoding="utf-8", errors="replace").read() if os.path.isfile(out_path) else ""
        net = {k: len(p.findall(out)) for k, p in PATTERNS.items()}
        ts = v["tests_status"]
        rows.append(dict(
            arm=arm, instance=inst, resolved=bool(v.get("resolved")),
            f2p_fail=len(ts["FAIL_TO_PASS"]["failure"]),
            p2p_fail=len(ts["PASS_TO_PASS"]["failure"]),
            f2p_total=len(ts["FAIL_TO_PASS"]["success"]) + len(ts["FAIL_TO_PASS"]["failure"]),
            net_total=sum(net.values()),
            **{f"net_{k}": n for k, n in net.items()},
        ))

print(f"instance records: {len(rows)}")

# which instances look network-dependent: failing tests + network signature
suspects = defaultdict(list)
for r in rows:
    if (r["f2p_fail"] or r["p2p_fail"]) and r["net_total"] > 0:
        suspects[r["instance"]].append(r)

print("\n### instances whose FAILURE text contains a network signature")
for inst, rs in sorted(suspects.items(), key=lambda kv: -max(r["net_total"] for r in kv[1])):
    verdicts = Counter(r["resolved"] for r in rs)
    print(f"  {inst:45s} runs={len(rs):2d} resolved={dict(verdicts)} "
          f"max_net_hits={max(r['net_total'] for r in rs)}")

# the inverse: same instance, same arm, resolved differs across repeats -> flakiness
print("\n### repeated arms on the same instance with different verdicts")
by = defaultdict(list)
for r in rows:
    base = re.sub(r"__r\d+$", "", r["arm"])
    by[(base, r["instance"])].append(r["resolved"])
flip = {k: v for k, v in by.items() if len(set(v)) > 1}
print(f"{len(flip)} arm-instance pairs flip across repeats")
for (arm, inst), v in list(flip.items())[:30]:
    print(f"  {inst:45s} {arm:45s} {v}")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "network_scan.csv"),
          "w", newline="", encoding="utf-8-sig") as f:
    import csv
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print("\nwrote data/network_scan.csv")

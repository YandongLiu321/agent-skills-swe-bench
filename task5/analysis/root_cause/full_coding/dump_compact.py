"""Compact coding view: enough to decide F1-F4 without loading whole bundles.

For each row: B evidence, file sets, full final patch (capped), gold patch
headers + added lines (capped), test patch added lines (capped), F2P names.

Usage:
  python dump_compact.py --ids 1-50 --out compact/group_01.txt
  python dump_compact.py --kappa --out compact/kappa.txt
  python dump_compact.py --start 1 --end 25 ...
"""
import argparse
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TABLE = HERE / "failure_table_437.csv"
DATASET = ROOT / "experiment_data" / "00_benchmark_inputs" / "swe_bench_verified.jsonl"


def trunc(s, n):
    s = s or ""
    if len(s) <= n:
        return s
    return s[:n] + f"\n...[truncated {len(s) - n} chars]"


def gold_view(patch, cap=2500):
    out = []
    for line in (patch or "").splitlines():
        if line.startswith("diff --git") or line.startswith("@@") or line.startswith("+"):
            out.append(line)
    return trunc("\n".join(out), cap)


def test_added(patch, cap=2500):
    out = []
    for line in (patch or "").splitlines():
        if line.startswith("diff --git") or line.startswith("@@"):
            out.append(line)
        elif line.startswith("+") and not line.startswith("+++"):
            out.append(line)
    return trunc("\n".join(out), cap)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=437)
    ap.add_argument("--ids", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(TABLE, encoding="utf-8-sig", newline="")))
    for i, r in enumerate(rows, 1):
        r["row_id"] = f"{i:04d}"

    want = None
    if args.ids:
        want = set()
        for part in args.ids.split(","):
            if "-" in part:
                a, b = part.split("-")
                want.update(f"{i:04d}" for i in range(int(a), int(b) + 1))
            else:
                want.add(f"{int(part):04d}")
    ds = {}
    with open(DATASET, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            ds[d["instance_id"]] = d

    sel = [r for r in rows if (want is None or r["row_id"] in want)
           and args.start <= int(r["row_id"]) <= args.end]
    out = []
    for r in sel:
        d = ds[r["instance"]]
        out.append(f"\n{'#'*90}\n## [{r['row_id']}] {r['instance']} · {r['skill']} | B={r['final_label']}")
        out.append(f"files: patch={r['patch_files']} | gold={r['gold_files']} | test={r['test_files']}")
        out.append(f"overlap: exact={r['files_exact_match_gold']} subset={r['patch_subset_of_gold']} "
                   f"disjoint={r['files_disjoint_gold']} touched_gold={r['n_gold_files_touched']}/{r['gold_n_files']} "
                   f"func_jaccard={r['func_jaccard_gold']}")
        out.append(f"signals: eq={r['test_assert_eq_lines']} is={r['test_assert_is_lines']} in={r['test_assert_in_lines']} "
                   f"raises={r['test_pytest_raises']} new_tests_in_f2p={r['test_new_tests_in_f2p']} "
                   f"conflict={r['patch_outcome_conflict']} status={r['final_patch_status']}")
        out.append(f"evidence: {trunc(r['evidence'], 600)}")
        out.append(f"F2P: {trunc(r['f2p_tests'], 600)}")
        out.append("--- FINAL PATCH ---")
        out.append(trunc(r["final_patch"], 6000))
        out.append("--- GOLD (headers/+ lines) ---")
        out.append(gold_view(d.get("patch", "")))
        out.append("--- TEST (headers/+ lines) ---")
        out.append(test_added(d.get("test_patch", "")))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(out), encoding="utf-8")
    print(args.out, len(sel), "rows", Path(args.out).stat().st_size, "bytes")


if __name__ == "__main__":
    main()

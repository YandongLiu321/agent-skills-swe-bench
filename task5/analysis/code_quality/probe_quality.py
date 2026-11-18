# -*- coding: utf-8 -*-
"""Probe: do Skill runs produce "tidier" patches than baseline runs?

Read-only analysis over the full run package (5,500 runs).
Compares same-instance baseline (no skill) vs skill patches on
proxies for code cleanliness: changed lines, files touched,
test-file edits, debug leftovers, TODO markers, comment share,
trailing whitespace, long lines.
"""
import json
import os
import random
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PKG = os.path.join(ROOT, "experiment_data", "07_full_task_eval", "完整题目与运行材料")
IDX = os.path.join(PKG, "全部运行索引.csv")


def is_test_path(p):
    pl = p.lower()
    return "test" in pl


def parse_diff(text):
    files = []
    added = removed = 0
    plus_lines = []
    for line in text.splitlines():
        if line.startswith("diff --git "):
            m = re.search(r" b/(\S+)", line)
            if m:
                files.append(m.group(1))
        elif line.startswith("+++") or line.startswith("---"):
            continue
        elif line.startswith("+"):
            added += 1
            plus_lines.append(line[1:])
        elif line.startswith("-"):
            removed += 1
    plus = "\n".join(plus_lines)
    comment_added = sum(1 for l in plus_lines if l.strip().startswith("#"))
    return {
        "files": len(set(files)),
        "added": added,
        "removed": removed,
        "changed": added + removed,
        "modifies_tests": int(any(is_test_path(f) for f in set(files))),
        "has_debug": int(any(k in plus for k in ("pdb.set_trace", "breakpoint()", "import pdb"))),
        "has_todo": int(bool(re.search(r"TODO|FIXME|XXX", plus))),
        "comment_added": comment_added,
        "comment_share": (comment_added / added) if added else 0.0,
        "trailing_ws_added": sum(1 for l in plus_lines if l != l.rstrip()),
        "long_lines_added": sum(1 for l in plus_lines if len(l) > 120),
        "empty_added": sum(1 for l in plus_lines if not l.strip()),
    }


def boot_ci(vals, n=10000, seed=7):
    if len(vals) < 5:
        return (None, None)
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        s = [vals[rng.randrange(len(vals))] for _ in range(len(vals))]
        means.append(sum(s) / len(s))
    means.sort()
    return means[int(0.025 * n)], means[int(0.975 * n)]


def main():
    df = pd.read_csv(IDX, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    print("rows:", len(df))
    print("skill counts:\n", df["skill"].value_counts().head(3).to_string())
    print("baseline rows:", int((df["skill"] == "baseline").sum()))
    print("instances:", df["instance_id"].nunique())

    rows = []
    for _, r in df.iterrows():
        if r["patch"] == "":
            continue
        p = os.path.join(PKG, r["patch"])
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        m = parse_diff(text)
        m["instance"] = r["instance_id"]
        m["arm"] = "baseline" if r["skill"] == "baseline" else "skill"
        m["skill"] = r["skill"]
        m["resolved"] = r["resolved"] == "True"
        m["patch_path"] = r["patch"]
        rows.append(m)
    d = pd.DataFrame(rows)
    print("parsed patches:", len(d), "baseline:", int((d.arm == "baseline").sum()))

    metrics = ["changed", "files", "modifies_tests", "has_debug", "has_todo",
               "comment_share", "trailing_ws_added", "long_lines_added"]

    print("\n== overall by arm (all patches) ==")
    print(d.groupby("arm")[metrics].median().round(4).to_string())
    print("\nmeans:")
    print(d.groupby("arm")[metrics].mean().round(4).to_string())

    # identical patch check
    base = d[d.arm == "baseline"].set_index("instance")["patch_path"]
    sk = d[d.arm == "skill"].copy()
    sk["identical"] = sk["instance"].map(base) == sk["patch_path"]
    print("\nskill patches identical to baseline patch: %d/%d = %.1f%%" % (
        sk.identical.sum(), len(sk), 100 * sk.identical.mean()))

    # paired: instance-level, baseline vs mean of skill arms, resolved only
    for label, mask in [("resolved_only", "resolved"), ("all", None)]:
        b = d[d.arm == "baseline"]
        s = d[d.arm == "skill"]
        if mask:
            b = b[b.resolved]
            s = s[s.resolved]
        sagg = s.groupby("instance")[metrics].mean()
        bagg = b.groupby("instance")[metrics].mean()
        common = bagg.index.intersection(sagg.index)
        print("\n== paired instance-level (%s): n=%d ==" % (label, len(common)))
        for m in metrics:
            diff = (sagg.loc[common, m] - bagg.loc[common, m]).tolist()
            lo, hi = boot_ci(diff)
            mean = sum(diff) / len(diff) if diff else float("nan")
            print(f"  {m:20s} skill-baseline mean={mean:+.4f}  CI=[{lo:+.4f},{hi:+.4f}]"
                  if lo is not None else f"  {m:20s} n too small")

    # identical vs different, resolved runs: changed lines
    skr = sk[sk.resolved]
    print("\n== resolved skill patches: identical vs different ==")
    print(skr.groupby("identical")[["changed", "files", "comment_share"]].median().round(3).to_string())


if __name__ == "__main__":
    main()

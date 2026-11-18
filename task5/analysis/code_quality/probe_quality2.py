# -*- coding: utf-8 -*-
"""Probe v2: stricter test-path rule, resolved-only pairing,
exclude skill patches identical to the baseline patch, per-skill breakdown."""
import os
import random
import re

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PKG = os.path.join(ROOT, "experiment_data", "07_full_task_eval", "完整题目与运行材料")
IDX = os.path.join(PKG, "全部运行索引.csv")

METRICS = ["changed", "files", "modifies_tests", "has_todo", "comment_share",
           "comment_added", "blank_share"]


def is_test_path(p):
    pl = p.lower().replace("\\", "/")
    name = pl.rsplit("/", 1)[-1]
    return (("/tests/" in pl) or ("/test/" in pl) or name.startswith("test_")
            or name.endswith("_test.py") or name == "conftest.py")


def parse_diff(text):
    files = []
    added = removed = 0
    plus = []
    for line in text.splitlines():
        if line.startswith("diff --git "):
            m = re.search(r" b/(\S+)", line)
            if m:
                files.append(m.group(1))
        elif line.startswith("+++") or line.startswith("---"):
            continue
        elif line.startswith("+"):
            added += 1
            plus.append(line[1:])
        elif line.startswith("-"):
            removed += 1
    cs = sum(1 for l in plus if l.strip().startswith("#"))
    blank = sum(1 for l in plus if not l.strip())
    return {
        "files": len(set(files)),
        "changed": added + removed,
        "added": added,
        "modifies_tests": int(any(is_test_path(f) for f in set(files))),
        "has_todo": int(bool(re.search(r"TODO|FIXME|XXX", "\n".join(plus)))),
        "comment_added": cs,
        "comment_share": cs / added if added else 0.0,
        "blank_share": blank / added if added else 0.0,
    }


def boot(vals, n=10000, seed=11):
    if len(vals) < 5:
        return None, None
    rng = random.Random(seed)
    means = sorted(sum(vals[rng.randrange(len(vals))] for _ in range(len(vals))) / len(vals)
                   for _ in range(n))
    return means[int(.025 * n)], means[int(.975 * n)]


def main():
    df = pd.read_csv(IDX, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    base_path = (df[df.skill == "baseline"].set_index("instance_id")["patch"]).to_dict()

    rows = []
    for _, r in df.iterrows():
        if not r["patch"]:
            continue
        p = os.path.join(PKG, r["patch"])
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            m = parse_diff(f.read())
        m["instance"] = r["instance_id"]
        m["arm"] = "baseline" if r["skill"] == "baseline" else "skill"
        m["skill"] = r["skill"]
        m["resolved"] = r["resolved"] == "True"
        m["identical"] = (r["patch"] == base_path.get(r["instance_id"]))
        rows.append(m)
    d = pd.DataFrame(rows)

    b = d[(d.arm == "baseline") & d.resolved]
    s = d[(d.arm == "skill") & d.resolved]

    print("resolved: baseline %d, skill %d" % (len(b), len(s)))
    print("skill resolved identical to baseline: %d/%d = %.1f%%" % (
        s.identical.sum(), len(s), 100 * s.identical.mean()))

    for label, ss in [("skill_all", s), ("skill_nonidentical", s[~s.identical])]:
        sagg = ss.groupby("instance")[METRICS].mean()
        bagg = b.groupby("instance")[METRICS].mean()
        common = bagg.index.intersection(sagg.index)
        print("\n== paired (%s), n instances=%d ==" % (label, len(common)))
        for m in METRICS:
            diff = (sagg.loc[common, m] - bagg.loc[common, m]).tolist()
            lo, hi = boot(diff)
            mean = sum(diff) / len(diff)
            sig = "" if (lo is not None and lo <= 0 <= hi) else "  *"
            print(f"  {m:18s} mean={mean:+.4f}  CI=[{lo:+.4f},{hi:+.4f}]{sig}")

    print("\n== resolved skill, non-identical: comment_share by skill ==")
    g = s[~s.identical].groupby("skill")["comment_share"].agg(["mean", "median", "count"])
    print(g.sort_values("mean", ascending=False).round(4).to_string())

    print("\n== baseline resolved comment_share ==")
    print("mean=%.4f median=%.4f n=%d" % (b.comment_share.mean(), b.comment_share.median(), len(b)))

    print("\n== resolved: patches with >=1 added comment line ==")
    for name, x in [("baseline", b), ("skill_all", s), ("skill_nonidentical", s[~s.identical])]:
        print("  %-20s %d/%d = %.1f%%   median_added_comment=%.0f" % (
            name, (x.comment_added > 0).sum(), len(x),
            100 * (x.comment_added > 0).mean(), x.comment_added.median()))


if __name__ == "__main__":
    main()

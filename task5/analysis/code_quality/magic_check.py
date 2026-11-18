# -*- coding: utf-8 -*-
"""Check whether the 'more magic numbers' signal survives a clean definition:
count only numeric literals in code lines, excluding comments, docstrings and
string literals. Also report how many were false positives in the old proxy."""
import math
import os
import random
import re

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PKG = os.path.join(ROOT, "experiment_data", "07_full_task_eval", "完整题目与运行材料")
IDX = os.path.join(PKG, "全部运行索引.csv")
NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")


def count_magic(text):
    plus = []
    for line in text.splitlines():
        if line.startswith("diff --git ") or line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("+"):
            plus.append(line[1:])

    old = new = 0
    in_doc = False
    doc_nums = cmt_nums = str_nums = 0
    for line in plus:
        nums = [n for n in NUM.findall(line) if n not in {"0", "1", "2", "0.0", "1.0", "2.0"}]
        old += len(nums)

        # docstring state machine
        q = line.count('"""') + line.count("'''")
        was_doc = in_doc
        if q % 2 == 1:
            in_doc = not in_doc
        if was_doc or in_doc:
            doc_nums += len(nums)
            continue
        if line.strip().startswith("#"):
            cmt_nums += len(nums)
            continue
        # strip quoted strings (single-line approximation)
        code = re.sub(r'"[^"]*"|\'[^\']*\'', '""', line)
        code_nums = [n for n in NUM.findall(code)
                     if n not in {"0", "1", "2", "0.0", "1.0", "2.0"}]
        # numbers removed by string stripping
        str_nums += max(0, len(nums) - len(code_nums))
        new += len(code_nums)
    return old, new, cmt_nums, doc_nums, str_nums


def boot(vals, n=8000, seed=9):
    rng = random.Random(seed)
    means = sorted(sum(vals[rng.randrange(len(vals))] for _ in range(len(vals))) / len(vals)
                   for _ in range(n))
    mean = sum(vals) / len(vals)
    se = (means[int(.975 * n)] - means[int(.025 * n)]) / 3.92
    p = 1.0 if se == 0 else 2 * (1 - 0.5 * (1 + math.erf(abs(mean / se) / 2 ** 0.5)))
    return mean, means[int(.025 * n)], means[int(.975 * n)], p


def main():
    df = pd.read_csv(IDX, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    base_path = dict(zip(df[df.skill == "baseline"].instance_id, df[df.skill == "baseline"].patch))
    rows = []
    for _, r in df.iterrows():
        if not r.patch:
            continue
        p = os.path.join(PKG, r.patch)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            old, new, cmt, doc, st = count_magic(f.read())
        rows.append(dict(instance=r.instance_id, arm="baseline" if r.skill == "baseline" else "skill",
                         resolved=r.resolved == "True",
                         identical=(r.patch == base_path.get(r.instance_id)),
                         magic_old=old, magic_clean=new, false_cmt=cmt,
                         false_doc=doc, false_str=st))
    d = pd.DataFrame(rows)
    b = d[(d.arm == "baseline") & d.resolved]
    s = d[(d.arm == "skill") & d.resolved & ~d.identical]
    print("baseline resolved %d | skill resolved non-identical %d" % (len(b), len(s)))
    print("mean counts: baseline old=%.3f clean=%.3f | skill old=%.3f clean=%.3f" % (
        b.magic_old.mean(), b.magic_clean.mean(), s.magic_old.mean(), s.magic_clean.mean()))
    print("skill false positives per patch: comment=%.3f docstring=%.3f string=%.3f" % (
        s.false_cmt.mean(), s.false_doc.mean(), s.false_str.mean()))
    print("baseline false positives per patch: comment=%.3f docstring=%.3f string=%.3f" % (
        b.false_cmt.mean(), b.false_doc.mean(), b.false_str.mean()))

    bs = b.groupby("instance")[["magic_old", "magic_clean"]].mean()
    ss = s.groupby("instance")[["magic_old", "magic_clean"]].mean()
    common = bs.index.intersection(ss.index)
    print("\npaired instances:", len(common))
    for c in ["magic_old", "magic_clean"]:
        diff = (ss.loc[common, c] - bs.loc[common, c]).tolist()
        mean, lo, hi, p = boot(diff)
        print(f"  {c:12s} skill-baseline mean={mean:+.4f} CI=[{lo:+.4f},{hi:+.4f}] p={p:.4f}")


if __name__ == "__main__":
    main()

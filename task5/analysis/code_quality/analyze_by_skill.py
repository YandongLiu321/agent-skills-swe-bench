# -*- coding: utf-8 -*-
"""Per-skill readability/maintainability deltas + sensitivity analyses.

- same-instance pairing (baseline vs skill), resolved runs
- per-skill mean delta with instance-level bootstrap CI
- sign win-rate per instance
- overall effect including identical patches (delta = 0)
- stratified by repo and patch size
"""
import math
import os
import random
import re

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PKG = os.path.join(ROOT, "experiment_data", "07_full_task_eval", "完整题目与运行材料")
IDX = os.path.join(PKG, "全部运行索引.csv")
OUT = os.path.dirname(os.path.abspath(__file__))
COLS = ["comment_share", "has_comment", "docstring", "ident_len", "short_ident_share",
        "magic_numbers", "ctrl_density", "dup_added", "max_indent", "changed"]
KEYWORDS = {
    "if", "elif", "else", "for", "while", "try", "except", "finally", "with",
    "and", "or", "not", "in", "is", "raise", "return", "yield", "def", "class",
    "import", "from", "as", "pass", "break", "continue", "lambda", "assert",
    "self", "cls", "None", "True", "False", "print",
}


def metrics(text):
    plus, removed = [], 0
    for line in text.splitlines():
        if line.startswith("diff --git ") or line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("+"):
            plus.append(line[1:])
        elif line.startswith("-") and not line.startswith("--- "):
            removed += 1
    added = len(plus)
    nonblank = [l for l in plus if l.strip()]
    comments = [l for l in plus if l.strip().startswith("#")]
    idents = [t for l in nonblank for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", l)
              if t not in KEYWORDS]
    magic = 0
    for l in nonblank:
        for num in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", l):
            if num not in {"0", "1", "2", "0.0", "1.0", "2.0"}:
                magic += 1
    ctrl = sum(len(re.findall(r"\b(?:if|elif|for|while|and|or|not|try|except|raise)\b", l))
               for l in nonblank)
    seen = {}
    for l in nonblank:
        s = l.strip()
        if len(s) > 3 and s not in ("else:", "try:", "return", "pass"):
            seen[s] = seen.get(s, 0) + 1
    dup = sum(v - 1 for k, v in seen.items() if v > 1 and not k.startswith("#"))
    indents = [len(l) - len(l.lstrip(" ")) for l in nonblank]
    return {
        "added": added, "changed": added + removed,
        "comment_share": len(comments) / added if added else 0.0,
        "has_comment": int(bool(comments)),
        "docstring": int(any('"""' in l or "'''" in l for l in plus)),
        "ident_len": sum(len(i) for i in idents) / len(idents) if idents else 0.0,
        "short_ident_share": sum(1 for i in idents if len(i) <= 2) / len(idents) if idents else 0.0,
        "magic_numbers": magic,
        "ctrl_density": ctrl / added if added else 0.0,
        "dup_added": dup,
        "max_indent": (max(indents) // 4) if indents else 0,
    }


def boot(vals, n=6000, seed=5):
    rng = random.Random(seed)
    means = sorted(sum(vals[rng.randrange(len(vals))] for _ in range(len(vals))) / len(vals)
                   for _ in range(n))
    mean = sum(vals) / len(vals)
    se = (means[int(.975 * n)] - means[int(.025 * n)]) / 3.92
    p = 1.0 if se == 0 else 2 * (1 - 0.5 * (1 + math.erf(abs(mean / se) / 2 ** 0.5)))
    return mean, means[int(.025 * n)], means[int(.975 * n)], p


def paired_delta(b, s, cols=COLS):
    sagg = s.groupby("instance")[cols].mean()
    bagg = b.groupby("instance")[cols].mean()
    common = bagg.index.intersection(sagg.index)
    out = {}
    for c in cols:
        out[c] = boot((sagg.loc[common, c] - bagg.loc[common, c]).tolist())
    return len(common), out


def main():
    df = pd.read_csv(IDX, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    base_rows = df[df.skill == "baseline"]
    base_path = dict(zip(base_rows.instance_id, base_rows.patch))
    base_res = base_rows[base_rows.resolved == "True"]

    rows = []
    for _, r in df.iterrows():
        if not r.patch:
            continue
        p = os.path.join(PKG, r.patch)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            m = metrics(f.read())
        m.update(instance=r.instance_id, arm="baseline" if r.skill == "baseline" else "skill",
                 skill=r.skill, resolved=r.resolved == "True",
                 identical=(r.patch == base_path.get(r.instance_id)),
                 repo=r.repo, case=r.instance_id.split("-")[0])
        rows.append(m)
    d = pd.DataFrame(rows)
    b = d[(d.arm == "baseline") & d.resolved]
    s = d[(d.arm == "skill") & d.resolved]

    print("== per-skill deltas (non-identical skill patches) ==")
    recs = []
    for skill, g in s.groupby("skill"):
        gi = g[~g.identical]
        if len(gi) < 15:
            continue
        n, out = paired_delta(b, gi)
        rec = {"skill": skill, "n_instances": n, "n_runs": len(gi)}
        for c in COLS:
            rec[c] = out[c][0]
            rec[f"{c}_lo"], rec[f"{c}_hi"], rec[f"{c}_p"] = out[c][1], out[c][2], out[c][3]
        recs.append(rec)
    r = pd.DataFrame(recs).sort_values("comment_share", ascending=False)
    r.to_csv(os.path.join(OUT, "by_skill.csv"), index=False, encoding="utf-8-sig")
    show = ["skill", "n_instances", "comment_share", "ident_len", "magic_numbers",
            "dup_added", "changed", "docstring"]
    print(r[show].round(3).to_string(index=False))

    print("\n== per-instance win rate (non-identical) ==")
    sagg = s[~s.identical].groupby("instance")[COLS].mean()
    bagg = b.groupby("instance")[COLS].mean()
    common = bagg.index.intersection(sagg.index)
    for c, better in [("comment_share", "higher"), ("ident_len", "higher"),
                      ("magic_numbers", "lower"), ("dup_added", "lower")]:
        diff = sagg.loc[common, c] - bagg.loc[common, c]
        if better == "higher":
            win = (diff > 0).mean()
        else:
            win = (diff < 0).mean()
        print(f"  {c:16s} skill 'better' share = {win:.1%}  (ties {(diff == 0).mean():.1%})")

    print("\n== overall effect including identical patches (delta=0 for identical) ==")
    s_all = s.groupby("instance")[COLS].mean()
    common = bagg.index.intersection(s_all.index)
    for c in ["comment_share", "has_comment", "ident_len", "magic_numbers", "changed"]:
        diff = (s_all.loc[common, c] - bagg.loc[common, c]).tolist()
        mean = sum(diff) / len(diff)
        print(f"  {c:16s} {mean:+.4f}  (vs non-identical only: {r[c].mean():+.4f})")

    print("\n== by repo (non-identical) ==")
    for repo, g in s[~s.identical].groupby("repo"):
        if g.instance.nunique() < 20:
            continue
        n, out = paired_delta(b, g)
        print(f"  {repo:35s} n={n:3d}  comment {out['comment_share'][0]:+.4f} "
              f"[{out['comment_share'][1]:+.4f},{out['comment_share'][2]:+.4f}]  "
              f"ident_len {out['ident_len'][0]:+.3f}  magic {out['magic_numbers'][0]:+.3f}")

    print("\n== by patch size (non-identical, skill changed lines) ==")
    s2 = s[~s.identical].copy()
    s2["bin"] = pd.cut(s2.changed, [0, 5, 10, 20, 40, 10000],
                       labels=["1-5", "6-10", "11-20", "21-40", "41+"])
    bagg2 = bagg
    for bin_, g in s2.groupby("bin", observed=True):
        n, out = paired_delta(b, g)
        print(f"  {bin_:6s} n={n:3d}  comment {out['comment_share'][0]:+.4f} "
              f"[{out['comment_share'][1]:+.4f},{out['comment_share'][2]:+.4f}]  "
              f"ident_len {out['ident_len'][0]:+.3f}  changed {out['changed'][0]:+.3f}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Full-population structured readability / maintainability proxies.

Same-instance paired comparison (baseline vs skill), resolved runs only,
excluding skill patches identical to the baseline patch.
Reports bootstrap CIs and BH-corrected q-values.
"""
import math
import os
import random
import re

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PKG = os.path.join(ROOT, "experiment_data", "07_full_task_eval", "完整题目与运行材料")
IDX = os.path.join(PKG, "全部运行索引.csv")

QUALITY = {
    "code-review-and-quality", "code-simplification", "python-code-style",
    "python-anti-patterns", "python-project-structure", "python-testing",
    "test-driven-development", "pytest-code-review", "django-patterns",
    "django-tdd", "django-verification", "verification-before-completion",
}
KEYWORDS = {
    "if", "elif", "else", "for", "while", "try", "except", "finally", "with",
    "and", "or", "not", "in", "is", "raise", "return", "yield", "def", "class",
    "import", "from", "as", "pass", "break", "continue", "lambda", "assert",
    "self", "cls", "None", "True", "False", "print",
}


def walk(text):
    """Yield plus-lines with their indentation, skipping diff headers."""
    for line in text.splitlines():
        if line.startswith("diff --git ") or line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("+"):
            yield line[1:]


def metrics(text):
    plus = list(walk(text))
    nonblank = [l for l in plus if l.strip()]
    added = len(plus)
    comments = [l for l in plus if l.strip().startswith("#")]
    docstrings = [l for l in plus if '"""' in l or "'''" in l]

    idents = []
    for l in nonblank:
        for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", l):
            if tok not in KEYWORDS:
                idents.append(tok)
    short = [i for i in idents if len(i) <= 2]
    camel = [i for i in idents if re.search(r"[a-z][A-Z]", i)]

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
    max_indent = max(indents) // 4 if indents else 0
    removed = sum(1 for l in text.splitlines()
                  if l.startswith("-") and not l.startswith("--- "))

    return {
        "added": added,
        "changed": added + removed,
        "comment_share": len(comments) / added if added else 0.0,
        "has_comment": int(bool(comments)),
        "docstring": int(bool(docstrings)),
        "ident_len": sum(len(i) for i in idents) / len(idents) if idents else 0.0,
        "short_ident_share": len(short) / len(idents) if idents else 0.0,
        "camel_idents": len(camel),
        "line_len": sum(len(l) for l in nonblank) / len(nonblank) if nonblank else 0.0,
        "long_line_share": sum(1 for l in nonblank if len(l) > 120) / len(nonblank) if nonblank else 0.0,
        "max_indent": max_indent,
        "magic_numbers": magic,
        "ctrl_density": ctrl / added if added else 0.0,
        "raise_count": sum(1 for l in nonblank if re.search(r"\braise\b", l)),
        "dup_added": dup,
    }


def boot(vals, n=8000, seed=3):
    rng = random.Random(seed)
    means = sorted(sum(vals[rng.randrange(len(vals))] for _ in range(len(vals))) / len(vals)
                   for _ in range(n))
    mean = sum(vals) / len(vals)
    se = (means[int(.975 * n)] - means[int(.025 * n)]) / 3.92
    p = 0.0 if se == 0 else 2 * (1 - _phi(abs(mean / se)))
    return mean, means[int(.025 * n)], means[int(.975 * n)], p


def _phi(z):
    return 0.5 * (1 + math.erf(z / 2 ** 0.5))


def bh(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    q = [0.0] * len(ps)
    m = len(ps)
    prev = 1.0
    for rank, i in enumerate(reversed(order), 1):
        val = min(prev, ps[i] * m / (m - rank + 1))
        q[i] = val
        prev = val
    return q


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
            m = metrics(f.read())
        m["instance"] = r.instance_id
        m["arm"] = "baseline" if r.skill == "baseline" else "skill"
        m["skill"] = r.skill
        m["resolved"] = r.resolved == "True"
        m["identical"] = (r.patch == base_path.get(r.instance_id))
        rows.append(m)
    d = pd.DataFrame(rows)
    b = d[(d.arm == "baseline") & d.resolved]
    s = d[(d.arm == "skill") & d.resolved & ~d.identical]
    print("resolved baseline %d | resolved non-identical skill %d" % (len(b), len(s)))

    cols = ["changed", "comment_share", "has_comment", "docstring", "ident_len",
            "short_ident_share", "camel_idents", "line_len", "long_line_share",
            "max_indent", "magic_numbers", "ctrl_density", "raise_count", "dup_added"]
    sagg = s.groupby("instance")[cols].mean()
    bagg = b.groupby("instance")[cols].mean()
    common = bagg.index.intersection(sagg.index)
    print("paired instances:", len(common))
    res = []
    for c in cols:
        diff = (sagg.loc[common, c] - bagg.loc[common, c]).tolist()
        mean, lo, hi, p = boot(diff)
        res.append((c, mean, lo, hi, p))
    qs = bh([r[4] for r in res])
    print("\nmetric               mean      CI95              p       q")
    for (c, mean, lo, hi, p), q in zip(res, qs):
        star = " *" if q < 0.05 else ""
        print(f"{c:20s} {mean:+.4f}  [{lo:+.4f},{hi:+.4f}]  {p:.4f}  {q:.4f}{star}")

    # quality-skill subset: within-instance diff vs baseline, quality vs other
    print("\n== quality-skill subset (non-identical) ==")
    sq = s[s.skill.isin(QUALITY)]
    so = s[~s.skill.isin(QUALITY)]
    for name, x in [("quality_skills", sq), ("other_skills", so)]:
        xa = x.groupby("instance")[cols].mean()
        com = bagg.index.intersection(xa.index)
        print(f"-- {name}: {len(com)} instances, {x.skill.nunique()} skills")
        for c in ["changed", "comment_share", "docstring", "ident_len", "magic_numbers",
                  "ctrl_density", "dup_added", "max_indent"]:
            diff = (xa.loc[com, c] - bagg.loc[com, c]).tolist()
            mean, lo, hi, p = boot(diff)
            print(f"   {c:16s} {mean:+.4f} [{lo:+.4f},{hi:+.4f}] p={p:.3f}")


if __name__ == "__main__":
    main()

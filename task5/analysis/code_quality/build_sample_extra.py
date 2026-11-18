# -*- coding: utf-8 -*-
"""15 additional pairs (disjoint from the first 15) for close reading."""
import os
import re

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PKG = os.path.join(ROOT, "experiment_data", "07_full_task_eval", "完整题目与运行材料")
IDX = os.path.join(PKG, "全部运行索引.csv")
OUT = os.path.dirname(os.path.abspath(__file__))

QUALITY = [
    "code-review-and-quality", "code-simplification", "python-code-style",
    "python-anti-patterns", "python-project-structure", "python-testing",
    "test-driven-development", "pytest-code-review", "django-patterns",
    "django-tdd", "django-verification", "verification-before-completion",
]


def metrics(text):
    files, added, removed = set(), 0, 0
    for line in text.splitlines():
        if line.startswith("diff --git "):
            m = re.search(r" b/(\S+)", line)
            if m:
                files.add(m.group(1))
        elif line.startswith("+++") or line.startswith("---"):
            continue
        elif line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return len(files), added + removed


def main():
    used = set(pd.read_csv(os.path.join(OUT, "sample_pairs.csv"), encoding="utf-8-sig").instance)
    df = pd.read_csv(IDX, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    base = df[df.skill == "baseline"]
    base_path = dict(zip(base.instance_id, base.patch))
    base_ok = set(base[base.resolved == "True"].instance_id)

    cand = []
    for _, r in df[df.skill != "baseline"].iterrows():
        if r.resolved != "True" or r.instance_id not in base_ok or r.instance_id in used:
            continue
        if not r.patch or r.patch == base_path.get(r.instance_id):
            continue
        p = os.path.join(PKG, r.patch)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            txt = f.read()
        nf, ch = metrics(txt)
        if 5 <= ch <= 70 and nf == 1:
            cand.append(dict(instance=r.instance_id, skill=r.skill, changed=ch,
                             base_path=base_path.get(r.instance_id), skill_path=r.patch))
    c = pd.DataFrame(cand)

    chosen, seen_inst = [], set()
    per_skill = {}
    # stratified: small / medium / large, quality skills first
    for lo, hi in [(5, 12), (13, 25), (26, 70)]:
        sub = c[(c.changed >= lo) & (c.changed <= hi)]
        pools = [sub[sub.skill.isin(QUALITY)], sub]
        got = 0
        for pool in pools:
            for _, r in pool.sample(frac=1, random_state=42).iterrows():
                if got >= 5:
                    break
                if r.instance in seen_inst or per_skill.get(r.skill, 0) >= 2:
                    continue
                chosen.append(r)
                seen_inst.add(r.instance)
                per_skill[r.skill] = per_skill.get(r.skill, 0) + 1
                got += 1
    sel = pd.DataFrame(chosen).head(15).reset_index(drop=True)
    sel["pair"] = [f"X{i+1:02d}" for i in range(len(sel))]
    sel.to_csv(os.path.join(OUT, "sample_pairs_extra.csv"), index=False, encoding="utf-8-sig")
    print(sel[["pair", "instance", "skill", "changed"]].to_string(index=False))
    print("skills:", sel.skill.nunique(), "instances:", sel.instance.nunique())

    lines = ["# Additional patch pairs (disjoint from the first 15)\n"]
    for _, r in sel.iterrows():
        for side in ("base", "skill"):
            with open(os.path.join(PKG, r[f"{side}_path"]), encoding="utf-8", errors="replace") as f:
                txt = f.read()
            lines.append(f"\n## {r['pair']} {side.upper()} | {r['instance']} | {r['skill']} | changed={r['changed']}\n")
            lines.append("```diff\n" + txt.rstrip() + "\n```")
        lines.append("\n---\n")
    with open(os.path.join(OUT, "sample_pack_extra.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("pack extras:", len(sel))


if __name__ == "__main__":
    main()

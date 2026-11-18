# -*- coding: utf-8 -*-
"""Build a stratified sample of same-instance baseline vs skill patch pairs
for close reading of readability / maintainability."""
import os
import re

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PKG = os.path.join(ROOT, "experiment_data", "07_full_task_eval", "完整题目与运行材料")
IDX = os.path.join(PKG, "全部运行索引.csv")
OUT = os.path.dirname(os.path.abspath(__file__))

QUALITY_SKILLS = [
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
    df = pd.read_csv(IDX, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    base = df[df.skill == "baseline"]
    base_path = dict(zip(base.instance_id, base.patch))
    base_ok = set(base[base.resolved == "True"].instance_id)

    cand = []
    for _, r in df[df.skill != "baseline"].iterrows():
        if r.resolved != "True" or r.instance_id not in base_ok:
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
    c = c.sort_values("changed")
    # stratify by changed size, prefer quality skills, one pair per instance
    chosen, used_inst = [], set()
    bins = [(5, 12), (13, 25), (26, 70)]
    for lo, hi in bins:
        sub = c[(c.changed >= lo) & (c.changed <= hi)]
        q = sub[sub.skill.isin(QUALITY_SKILLS)]
        pool = q if len(q) else sub
        # round robin over skills, then size
        by_skill = {k: g for k, g in pool.groupby("skill")}
        skills = sorted(by_skill, key=lambda k: -len(by_skill[k]))
        for k in skills:
            for _, r in by_skill[k].iterrows():
                if r.instance in used_inst:
                    continue
                chosen.append(r)
                used_inst.add(r.instance)
                break
            if len(chosen) >= 5 * (bins.index((lo, hi)) + 1):
                break
    # fill to 15 with quality skills, then any
    for pool in (c[c.skill.isin(QUALITY_SKILLS)], c):
        for _, r in pool.iterrows():
            if len(chosen) >= 15:
                break
            if r.instance not in used_inst:
                chosen.append(r)
                used_inst.add(r.instance)

    sel = pd.DataFrame(chosen).head(15).reset_index(drop=True)
    sel["pair"] = [f"P{i+1:02d}" for i in range(len(sel))]
    sel.to_csv(os.path.join(OUT, "sample_pairs.csv"), index=False, encoding="utf-8-sig")
    print(sel[["pair", "instance", "skill", "changed"]].to_string(index=False))
    print("skills covered:", sel.skill.nunique(), "instances:", sel.instance.nunique())

    lines = ["# Patch pairs for close reading (baseline vs skill, same instance, resolved)\n"]
    for _, r in sel.iterrows():
        for side in ("base", "skill"):
            path = os.path.join(PKG, r[f"{side}_path"])
            with open(path, encoding="utf-8", errors="replace") as f:
                txt = f.read()
            lines.append(f"\n## {r['pair']} {side.upper()} | {r['instance']} | {r['skill']} | changed={r['changed']}\n")
            lines.append("```diff\n" + txt.rstrip() + "\n```")
        lines.append("\n---\n")
    with open(os.path.join(OUT, "sample_pack.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("pack lines:", len(lines))


if __name__ == "__main__":
    main()

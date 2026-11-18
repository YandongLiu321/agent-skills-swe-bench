# -*- coding: utf-8 -*-
"""Verify the "success-side practices" from the 12-case deep read on 1,010 runs.

Hypotheses (operationalized):
  H1 read the contract: reading test files or gold-touched files before first edit
  H2 fix the right location: patch files overlap gold files
  H3 cover all entries: search commands (grep/rg/find) before first edit
  H4 scenario self-test: specific test node / ad-hoc python after first edit

Design: within-instance paired comparison (success arms vs failure arms),
within-instance label permutation test, and linear probability model with
instance fixed effects (cluster bootstrap by instance).
"""
import importlib.util
import json
import math
import os
import random
import re

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.dirname(os.path.abspath(__file__))
A_TABLE = None
for p in [
    os.path.join(ROOT, "others_finding", "_extracted", "A3_20261024",
                 "A浠诲姟_浜ゅ弶瀹炰緥鍒嗘瀽", "A_toolcall_features_v2.csv"),
]:
    if os.path.exists(p):
        A_TABLE = p
if A_TABLE is None:
    import glob
    A_TABLE = glob.glob(os.path.join(ROOT, "**", "A3_20261024", "**", "A_toolcall_features_v2.csv"),
                        recursive=True)[0]
JSONL = os.path.join(ROOT, "experiment_data", "00_benchmark_inputs", "swe_bench_verified.jsonl")
TU = os.path.join(ROOT, "others_finding", "_extracted", "B2_20261023", "任务B材料", "scripts",
                  "trajectory_utils.py")

READ_TOOL = re.compile(r"\b(?:cat|head|tail|sed\s+-n|less|more|nl)\b")
SEARCH_TOOL = re.compile(r"\b(?:grep|rg|git\s+grep|find|ag|ack)\b")
TEST_PATH = re.compile(r"(?:^|[\s/])(?:tests?|testing)(?:/|_)|\btest_[A-Za-z0-9_]+\.py\b")


def load_tu():
    spec = importlib.util.spec_from_file_location("traj_utils", TU)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def events_of(d, tu):
    msgs = d.get("messages") or []
    events, step = [], 0
    for m in msgs:
        if m.get("role") != "assistant":
            continue
        step += 1
        for _cid, cmd in tu.tool_calls(m):
            is_test = bool(tu.TEST.search(cmd)) and not bool(
                re.match(r"^\s*(?:cat|sed -n|grep|rg|git diff)\b", cmd))
            is_edit = bool(tu.EDIT.search(cmd)) and "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" not in cmd
            is_custom = bool(re.search(r"\bpython(?:3)?\b|\bipython\b", cmd)) and not is_test and not is_edit
            events.append(dict(step=step, command=cmd, test=is_test, edit=is_edit, custom=is_custom))
    return events


def extract():
    tu = load_tu()
    df = pd.read_csv(A_TABLE, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    tasks = {}
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            tasks[d["instance_id"]] = d
    rows = []
    for i, r in df.iterrows():
        if i % 100 == 0:
            print("extract", i, "/", len(df), flush=True)
        tp = r["traj_path"]
        if not os.path.exists(tp):
            continue
        d = json.load(open(tp, encoding="utf-8"))
        task = tasks.get(r["instance"], {})
        gold = re.findall(r"^diff --git a/\S+ b/(.+)$", task.get("patch", ""), re.M)
        gold = sorted(set(gold))
        metrics, _evidence = tu.trajectory_metrics(d, task, "")
        ev = events_of(d, tu)
        edits = [e["step"] for e in ev if e["edit"]]
        first_edit = min(edits) if edits else None
        pre = [e for e in ev if first_edit is not None and e["step"] < first_edit]
        post = [e for e in ev if first_edit is not None and e["step"] > first_edit]

        def read_hit(e):
            return bool(READ_TOOL.search(e["command"])) and not e["edit"]

        def search_hit(e):
            return bool(SEARCH_TOOL.search(e["command"])) and not e["edit"]

        def test_path_hit(e):
            return bool(TEST_PATH.search(e["command"]))

        def gold_path_hit(e):
            return any(g in e["command"] for g in gold)

        patch_paths = set((metrics.get("patch_paths") or "").split(" | ")) - {""}
        gold_set = set(gold)
        inter = patch_paths & gold_set
        union = patch_paths | gold_set

        def spec_test(e):
            return e["test"] and (("::" in e["command"])
                                  or re.search(r"(?:^|\s)-k(?:\s|=)", e["command"])
                                  or test_path_hit(e))

        rows.append(dict(
            instance=r["instance"], skill=r["skill"], phase=r["phase"],
            resolved=int(r["resolved"]),
            steps=int(r["n_steps"]) if r["n_steps"] else 0,
            test_calls=int(r["n_tests"]) if r["n_tests"] else 0,
            search_calls=int(r["n_search"]) if r["n_search"] else 0,
            read_calls=int(r["n_read"]) if r["n_read"] else 0,
            edit_calls=int(r["n_edits"]) if r["n_edits"] else 0,
            reproduced_before_edit=int(r["reproduced_before_edit"]) if r["reproduced_before_edit"] else 0,
            tested_after_last_edit=int(r["tested_after_last_edit"]) if r["tested_after_last_edit"] else 0,
            first_edit_step=int(first_edit) if first_edit else 0,
            read_test_before_edit=int(any(read_hit(e) and test_path_hit(e) for e in pre)),
            read_gold_before_edit=int(any(read_hit(e) and gold_path_hit(e) for e in pre)),
            read_test_count_before_edit=sum(1 for e in pre if read_hit(e) and test_path_hit(e)),
            read_gold_count_before_edit=sum(1 for e in pre if read_hit(e) and gold_path_hit(e)),
            search_before_edit=sum(search_hit(e) for e in pre),
            search_test_before_edit=int(any(search_hit(e) and test_path_hit(e) for e in pre)),
            pre_test_calls=sum(e["test"] or e["custom"] for e in pre),
            specific_test_after_edit=int(any(spec_test(e) for e in post)),
            specific_test_count_after_edit=sum(1 for e in post if spec_test(e)),
            adhoc_python_after_edit=int(any(e["custom"] for e in post)),
            adhoc_python_count_after_edit=sum(1 for e in post if e["custom"]),
            post_test_calls=sum(e["test"] for e in post),
            reference_file_overlap=int(metrics.get("reference_file_overlap") or 0),
            gold_file_recall=(len(inter) / len(gold_set)) if gold_set else 0.0,
            gold_file_precision=(len(inter) / len(patch_paths)) if patch_paths else 0.0,
            gold_file_jaccard=(len(inter) / len(union)) if union else 0.0,
            patch_files=int(metrics.get("patch_files") or 0),
            patch_changed_lines=int(metrics.get("patch_changed_lines") or 0),
            patch_test_files=int(metrics.get("patch_test_files") or 0),
            failed_commands=int(metrics.get("failed_command_calls") or 0),
            repeated_command_fraction=float(metrics.get("repeated_command_fraction") or 0),
        ))
    out = pd.DataFrame(rows)
    path = os.path.join(OUT, "success_patterns_1010.csv")
    out.to_csv(path, index=False, encoding="utf-8-sig")
    print("wrote", path, out.shape)
    print(out[["resolved", "read_test_before_edit", "read_gold_before_edit",
               "search_before_edit", "specific_test_after_edit",
               "adhoc_python_after_edit", "reference_file_overlap"]].mean().round(3))
    return out


def paired_diff(df, col):
    """Mean within-instance (success - failure) difference of col."""
    vals = []
    for inst, g in df.groupby("instance"):
        y = g.resolved.values
        if y.min() == y.max():
            continue
        x = g[col].astype(float).values
        vals.append(x[y == 1].mean() - x[y == 0].mean())
    if not vals:
        return float("nan"), 0
    return float(np.mean(vals)), len(vals)


def perm_p(df, col, B=5000, seed=7):
    rng = random.Random(seed)
    groups = [(g.resolved.values.copy(), g[col].astype(float).values) for _, g in df.groupby("instance")
              if g.resolved.nunique() == 2]
    if not groups:
        return float("nan")
    obs = np.mean([x[y == 1].mean() - x[y == 0].mean() for y, x in groups])
    cnt = 0
    for _ in range(B):
        stat = []
        for y, x in groups:
            yp = y.copy()
            rng.shuffle(yp)
            stat.append(x[yp == 1].mean() - x[yp == 0].mean())
        if abs(np.mean(stat)) >= abs(obs):
            cnt += 1
    return (cnt + 1) / (B + 1)


def bh(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    q = [0.0] * len(ps)
    m = len(ps)
    prev = 1.0
    for rank, i in enumerate(reversed(order), 1):
        prev = min(prev, ps[i] * m / (m - rank + 1))
        q[i] = prev
    return q


def lpm_fe(df, features, B=400):
    """Linear probability model with instance fixed effects via within transformation.
    Cluster bootstrap resamples instances; rows are already within-transformed."""
    d = df.copy()
    d["log_steps"] = np.log1p(d["steps"])
    feats = [f for f in features + ["log_steps"] if f in d.columns and d[f].nunique() > 1]

    def demean(col):
        return (d[col] - d.groupby("instance")[col].transform("mean")).values.astype(float)

    X = np.column_stack([demean(f) for f in feats])
    y = demean("resolved")
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    idx_by_inst = {p: np.where(d.instance.values == p)[0] for p in d.instance.unique()}
    insts = list(idx_by_inst)
    rng = np.random.default_rng(11)
    boots = [[] for _ in feats]
    for _ in range(B):
        pick = rng.choice(insts, size=len(insts), replace=True)
        rows = np.concatenate([idx_by_inst[p] for p in pick])
        bb = np.linalg.lstsq(X[rows], y[rows], rcond=None)[0]
        for j in range(len(feats)):
            boots[j].append(bb[j])
    out = {}
    for j, f in enumerate(feats):
        arr = np.array(boots[j])
        out[f] = (beta[j], np.percentile(arr, 2.5), np.percentile(arr, 97.5))
    return out


def main():
    path = os.path.join(OUT, "success_patterns_1010.csv")
    if os.path.exists(path):
        df = pd.read_csv(path, encoding="utf-8-sig")
        if "gold_file_recall" not in df.columns:
            df = extract()
    else:
        df = extract()
    print("rows", len(df), "instances", df.instance.nunique())

    binary = ["read_test_before_edit", "read_gold_before_edit", "search_test_before_edit",
              "specific_test_after_edit", "adhoc_python_after_edit",
              "reference_file_overlap", "reproduced_before_edit", "tested_after_last_edit"]
    cont = ["search_before_edit", "pre_test_calls", "post_test_calls", "steps",
            "patch_changed_lines", "read_test_count_before_edit",
            "read_gold_count_before_edit", "specific_test_count_after_edit",
            "adhoc_python_count_after_edit", "gold_file_recall", "gold_file_precision",
            "gold_file_jaccard"]
    print("\n== within-instance paired (success - failure) ==")
    recs = []
    for c in binary + cont:
        mean, n = paired_diff(df, c)
        p = perm_p(df, c)
        recs.append((c, mean, n, p))
    qs = bh([r[3] for r in recs])
    for (c, mean, n, p), q in zip(recs, qs):
        print(f"{c:28s} diff={mean:+.4f} n={n:3d} p={p:.4f} q={q:.4f}{' *' if q < 0.05 else ''}")

    print("\n== success-rate difference by binary feature (x=1 - x=0, within instance) ==")
    for c in binary:
        vals = []
        for inst, g in df.groupby("instance"):
            if g[c].nunique() < 2:
                continue
            y = g.resolved.values.astype(float)
            x = g[c].values
            vals.append(y[x == 1].mean() - y[x == 0].mean())
        if vals:
            print(f"{c:28s} {np.mean(vals):+.4f}  n={len(vals)}")

    print("\n== LPM with instance FE (pp), cluster bootstrap ==")
    base = ["read_test_count_before_edit", "read_gold_count_before_edit",
            "search_before_edit", "specific_test_count_after_edit",
            "adhoc_python_count_after_edit", "post_test_calls"]
    print("-- model A: behaviors + log_steps only")
    for f, (b, lo, hi) in lpm_fe(df, base).items():
        print(f"{f:28s} {b*100:+.2f}pp  CI=[{lo*100:+.2f},{hi*100:+.2f}]")
    print("-- model B: + gold_file_recall")
    for f, (b, lo, hi) in lpm_fe(df, base + ["gold_file_recall"]).items():
        print(f"{f:28s} {b*100:+.2f}pp  CI=[{lo*100:+.2f},{hi*100:+.2f}]")


if __name__ == "__main__":
    main()

"""Build task5/analysis/: consolidated per-case x per-skill tables from the three machines' returns.

Sources
  task5/runs/*/baseline/*/*.traj.json          phase-1 baseline (official verdicts + trajectories)
  task5/split/baseline_verdicts.json           official baseline pass/fail
  other_machine/machine1/all_experiment_runs(2).csv   m1 self-judged runs (1350)
  other_machine/machine2/machine2_Skill详细表现汇总.xlsx  m2 summary (1350)
  other_machine/machine3/machine3_runs_回传.tar.gz     m3 raw trajectories (audited; no labels)

Writes:
  summary_baseline.csv         per-case baseline (official accuracy + trajectory steps/tokens)
  summary_accuracy.csv         per-case x skill accuracy (m1+m2 pooled)
  summary_efficiency.csv       per-case x skill steps/tokens (m2; m1 token totals where m2 absent)
  summary_pooled_skill.csv     per-skill pooled across all cases
  summary_machine_audit.csv    per-machine data-quality audit (incl. m3 balance outage)
"""

import csv
import glob
import json
import os
import re
import sys
import tarfile
from collections import defaultdict

import openpyxl

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.dirname(os.path.abspath(__file__))
SRC = {"pydata": "xarray", "mwaskom": "seaborn", "psf": "requests",
       "pylint-dev": "pylint", "pytest-dev": "pytest", "sphinx-doc": "sphinx"}
norm = lambda c: SRC.get(c, c)


def write_csv(name, header, rows):
    path = os.path.join(OUT, name)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print("wrote", path, f"({len(rows)} rows)")


def msg_tokens(m):
    return sum(len(v) if isinstance(v, str) else len(json.dumps(v, ensure_ascii=False))
               for k, v in m.items() if k != "role" and v is not None) / 4.0


# ---------------- baseline ----------------
verdicts = json.load(open(os.path.join(REPO, "task5/split/baseline_verdicts.json"), encoding="utf-8"))
base = defaultdict(lambda: dict(n=0, steps=0, cum=0, cost=0.0))
for f in glob.glob(os.path.join(REPO, "task5/runs/*/baseline/*/*.traj.json")):
    case = os.path.normpath(f).split(os.sep)[-4]
    d = json.load(open(f, encoding="utf-8"))
    st = d["info"].get("model_stats") or {}
    ctx = cum = 0.0
    for m in d.get("messages", []):
        ctx += msg_tokens(m)
        if m.get("role") == "assistant":
            cum += ctx
    a = base[case]
    a["n"] += 1; a["steps"] += st.get("api_calls") or 0
    a["cum"] += cum; a["cost"] += st.get("instance_cost") or 0

rows = []
for c in sorted(verdicts, key=lambda x: -verdicts[x]["submitted"]):
    v, e = verdicts[c], base.get(c)
    rows.append([
        c, v["submitted"], len(v["resolved"]), f"{len(v['resolved'])/v['submitted']:.4f}",
        round(e["steps"] / e["n"], 2) if e else "",
        round(e["cum"] / e["n"]) if e else "",
        round(e["cost"] / e["n"], 4) if e else "",
        e["n"] if e else 0,
    ])
write_csv("summary_baseline.csv",
          ["case", "submitted", "resolved", "accuracy", "avg_steps", "avg_cumulative_tokens", "avg_cost_usd", "traj_n"],
          rows)

# ---------------- m1 ----------------
m1 = defaultdict(lambda: dict(n=0, fail=0, tok=0.0))
for r in csv.DictReader(open(os.path.join(REPO, "other_machine/machine1/all_experiment_runs(2).csv"), encoding="utf-8-sig")):
    if r["cohort"] != "machine1":
        continue
    s = m1[(norm(r["case_id"].split("__")[0]), r["skill_name"])]
    s["n"] += 1; s["fail"] += r["resolved"] == "0"
    s["tok"] += float(r["skill_total_tokens"] or 0)

# ---------------- m2 ----------------
wb = openpyxl.load_workbook(os.path.join(REPO, "other_machine/machine2/machine2_Skill详细表现汇总.xlsx"), data_only=True)
m2 = {}
for row in wb.worksheets[0].iter_rows(values_only=True):
    if not row or not row[0] or not isinstance(row[4], (int, float)):
        continue
    m2[(norm(row[1]), row[0])] = dict(n=int(row[4]), fail=int(row[7]), steps=row[16],
                                      prom=row[17], comp=row[18], tok=row[19], cost=row[21])

# ---------------- accuracy + efficiency ----------------
acc_rows, eff_rows = [], []
for (c, s) in sorted(set(m1) | set(m2), key=lambda k: (k[0], k[1])):
    a, b = m1.get((c, s)), m2.get((c, s))
    n = (a["n"] if a else 0) + (b["n"] if b else 0)
    f = (a["fail"] if a else 0) + (b["fail"] if b else 0)
    acc_rows.append([c, s, n, f, f"{n-f}/{n}", f"{(n-f)/n:.4f}", f"{-(f/n):.4f}",
                     "m1+m2" if a and b else ("m1" if a else "m2")])
    if b:
        eff_rows.append([c, s, b["n"], round(b["steps"], 2), round(b["prom"]),
                         round(b["comp"]), round(b["tok"]), round(b["cost"], 4), "m2"])
    elif a:
        eff_rows.append([c, s, a["n"], "", "", "", round(a["tok"] / a["n"]), "", "m1_total_only"])
write_csv("summary_accuracy.csv",
          ["case", "skill", "n", "broken", "kept", "accuracy", "delta_vs_passed_baseline", "source"], acc_rows)
write_csv("summary_efficiency.csv",
          ["case", "skill", "n", "avg_steps", "avg_prompt_tokens", "avg_completion_tokens",
           "avg_total_tokens", "avg_cost_usd", "source"], eff_rows)

# ---------------- pooled per skill ----------------
pool = defaultdict(lambda: dict(n=0, fail=0, steps=0.0, tok=0.0, cost=0.0, m2n=0,
                                cases=set(), src=set()))
for (c, s) in set(m1) | set(m2):
    a, b = m1.get((c, s)), m2.get((c, s))
    p = pool[s]
    p["n"] += (a["n"] if a else 0) + (b["n"] if b else 0)
    p["fail"] += (a["fail"] if a else 0) + (b["fail"] if b else 0)
    p["cases"].add(c)
    if a:
        p["src"].add("m1")
    if b:
        p["src"].add("m2")
        p["m2n"] += b["n"]
        p["steps"] += b["steps"] * b["n"]; p["tok"] += b["tok"] * b["n"]; p["cost"] += b["cost"] * b["n"]
rows = []
for s, p in sorted(pool.items(), key=lambda kv: -kv[1]["n"]):
    n, f = p["n"], p["fail"]
    m2n = p["m2n"]  # efficiency averages only over runs that reported steps/tokens
    rows.append([s, len(p["cases"]), n, f, f"{n-f}/{n}", f"{(n-f)/n:.4f}",
                 round(p["steps"] / m2n, 2) if m2n else "",
                 round(p["tok"] / m2n) if m2n else "",
                 round(p["cost"] / m2n, 4) if m2n else "",
                 "+".join(sorted(p["src"]))])
write_csv("summary_pooled_skill.csv",
          ["skill", "cases_covered", "n", "broken", "kept", "accuracy", "avg_steps",
           "avg_tokens_per_run", "avg_cost_usd", "source"], rows)

# ---------------- machine audit ----------------
m3_rows = []
with tarfile.open(os.path.join(REPO, "other_machine/machine3/machine3_runs_回传.tar.gz")) as tf:
    names = tf.getnames()
    trajs = [n for n in names if n.endswith(".traj.json")]
    for name in trajs:
        m = re.match(r"^([^/]+)/([^/]+)/([^/]+)/\1?\3?.*$", name)
        parts = name.split("/")
        if len(parts) < 4:
            continue
        case, arm, inst = parts[0], parts[1], parts[2]
        try:
            d = json.loads(tf.extractfile(name).read().decode("utf-8"))
        except Exception:
            continue
        info = d.get("info", {})
        st = info.get("model_stats") or {}
        m3_rows.append((case, arm, inst, info.get("exit_status"), st.get("api_calls"),
                        st.get("instance_cost"), ((info.get("config") or {}).get("model") or {}).get("model_name")))

share = json.load(open(os.path.join(REPO, "task5/split/machine3.json"), encoding="utf-8"))
share_ids = {i for v in share.values() for i in v}
m3_share = [r for r in m3_rows if r[2] in share_ids and r[1] not in ("baseline",) and "@" not in r[1]]
ok = [r for r in m3_share if r[3] == "Submitted"]
rows = [
    ["machine1", 1350, 1350, 100.0, 53, "self-judged", "clean: all runs costed, failures scattered", ""],
    ["machine2", 1350, 1350, 100.0, 63, "self-judged", "summary only; no raw preds/traj returned", "internal tables disagree (63 vs 44)"],
    ["machine3", 1350, len(ok), round(len(ok) / 1350 * 100, 1), "", "none (no labels)",
     f"outage: Insufficient Balance, {1350-len(ok)} runs lost across 2026-10-11 02-07 & 20-22", "needs re-run"],
]
write_csv("summary_machine_audit.csv",
          ["machine", "arm_runs_expected", "arm_runs_valid", "completion_pct", "broken_self_judged",
           "judging", "data_quality", "action"], rows)
print("done")

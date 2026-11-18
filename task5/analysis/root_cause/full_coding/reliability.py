"""Agreement checks for the coding files (manual vs agent vs rule).

Run after review/codes_batch_*.csv exist:
  PYTHONIOENCODING=utf-8 python reliability.py
"""
import csv
import glob
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
VALID = {"F1", "F2", "F3", "F4", "U"}


def read_csv(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cohen_kappa(a, b):
    """a, b: aligned lists of labels."""
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in set(ca) | set(cb))
    return None if pe == 1 else (po - pe) / (1 - pe)


def main():
    manual = {}
    for p in [HERE / "coding_manual_50.csv", HERE / "coding_manual_extra.csv"]:
        for r in read_csv(p):
            manual[r["row_id"]] = r["main_cause"].strip()

    agent = {}
    for p in sorted(glob.glob(str(HERE / "review" / "codes_batch_*.csv"))):
        for r in read_csv(p):
            agent[r["row_id"]] = r["main_cause"].strip()

    rule = {}
    table = read_csv(HERE / "failure_table_437.csv")
    pre = {(r["instance"], r["skill"]): r for r in read_csv(HERE / "precode_437.csv")}
    for i, t in enumerate(table, 1):
        p = pre.get((t["instance"], t["skill"]))
        if p:
            rule[f"{i:04d}"] = p["rule_code"]

    def report(name, x, y):
        keys = sorted(set(x) & set(y))
        xs = [x[k] for k in keys if x[k] in VALID and y[k] in VALID]
        ys = [y[k] for k in keys if x[k] in VALID and y[k] in VALID]
        ok = sum(a == b for a, b in zip(xs, ys))
        kappa = cohen_kappa(xs, ys)
        print(f"{name}: n={len(xs)} agree={ok}/{len(xs)} "
              f"({100*ok/len(xs) if xs else 0:.1f}%) kappa={kappa}")
        conf = Counter((a, b) for a, b in zip(xs, ys) if a != b)
        for pair, cnt in conf.most_common(10):
            print(f"   {pair[0]} vs {pair[1]}: {cnt}")
        return keys

    print("== agreement ==")
    report("manual vs agent", manual, agent)
    report("manual vs rule", manual, rule)
    report("agent vs rule", agent, rule)


if __name__ == "__main__":
    main()

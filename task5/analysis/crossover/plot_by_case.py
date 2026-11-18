"""One consistent crossover figure per case.

Each figure has:
  - rows: every instance in that case, sorted by number of resolved skills;
  - first column: baseline (no-skill) outcome;
  - next 10 columns: that case's actual skill names;
  - right bar: resolved skills per instance;
  - row labels: full instance ids;
  - no phase strip; dark = resolved, light = unresolved.
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Rectangle

OUT = Path(__file__).resolve().parent
BY = OUT


def load():
    rows = list(csv.DictReader(open(OUT / "instances.csv", encoding="utf-8-sig")))
    slots = defaultdict(list)
    for r in csv.DictReader(open(OUT / "arm_slot_map.csv", encoding="utf-8-sig")):
        slots[r["case"]].append((int(r["arm_slot"]), r["skill"]))
    for c in slots:
        slots[c].sort()
    return rows, slots


def plot_case(case, rows, skills):
    rows = sorted(rows, key=lambda r: (int(r["n_resolved"]), r["phase"] != "phase1", r["instance"]))
    M = np.array([[1 if r["phase"] == "phase2" else 0] + [int(r[f"arm_{i}"]) for i in range(1, 11)]
                  for r in rows], dtype=float)
    cols = ["baseline"] + [s for _, s in skills]
    n = len(rows)
    mixed = [i for i, r in enumerate(rows) if 1 <= int(r["n_resolved"]) <= 9]
    nfail = sum(int(r["n_resolved"]) == 0 for r in rows)
    npass = sum(int(r["n_resolved"]) == 10 for r in rows)
    h = max(6.0, 0.105 * n + 1.8)
    fig = plt.figure(figsize=(10, h), dpi=200)
    top = 0.94 if h >= 8 else 0.90
    subtitle_y = 0.975 if h >= 8 else 0.925
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 0.12],
                          left=0.30, right=0.95, top=top, bottom=0.25,
                          wspace=0.015)
    ax = fig.add_subplot(gs[0, 0])
    ax_bar = fig.add_subplot(gs[0, 1])
    cmap = ListedColormap(["#f7f7f4", "#12355b"])
    ax.imshow(M, aspect="auto", interpolation="none", cmap=cmap, vmin=0, vmax=1, origin="upper")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=90, fontsize=7)
    ax.tick_params(axis="x", length=0, pad=2)
    ax.set_yticks(range(n))
    ax.set_yticklabels([r["instance"] for r in rows],
                       fontsize=6)
    ax.tick_params(axis="y", length=0, pad=1)
    ax.axvline(0.5, color="#222222", lw=1.2)
    for tick in ax.get_xticklabels():
        if tick.get_text() == "baseline":
            tick.set_fontweight("bold")
    if mixed:
        ax.add_patch(Rectangle((-0.5, min(mixed) - 0.5), len(cols), len(mixed),
                               fill=False, ec="#f2a900", lw=1.2, ls=(0, (4, 3)), zorder=5))
    counts = np.array([int(r["n_resolved"]) for r in rows])
    ax_bar.barh(np.arange(n), counts, color="#9dc3e6", height=1.0)
    ax_bar.set_ylim(n - 0.5, -0.5)
    ax_bar.set_xlim(0, 10)
    ax_bar.set_yticks([])
    ax_bar.set_xticks([0, 5, 10])
    ax_bar.tick_params(labelsize=7)
    ax_bar.set_xlabel("resolved\nskills / 10", fontsize=7, labelpad=2)
    fig.suptitle(f"{case} — {n} instances", fontsize=14, y=0.985)
    fig.text(0.5, subtitle_y,
             f"{nfail} all-fail / {len(mixed)} crossover / {npass} all-pass; dark = resolved, light = unresolved",
             ha="center", fontsize=8, color="#444444")
    p = BY / f"{case}.png"
    fig.savefig(p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(p.name, n, "rows", len(mixed), "mixed")


def main():
    BY.mkdir(parents=True, exist_ok=True)
    rows, slots = load()
    by_case = defaultdict(list)
    for r in rows:
        by_case[r["case"]].append(r)
    for case in sorted(by_case):
        plot_case(case, by_case[case], slots[case])


if __name__ == "__main__":
    main()

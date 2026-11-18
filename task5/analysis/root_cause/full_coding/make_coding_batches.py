"""Generate human-coding batches from failure_table_437.csv.

Two outputs:
  kappa_50.md     one stratified 50-row batch; give the SAME file to both coders,
                  then compute Cohen's kappa on their main_cause columns.
  review/batch_XX.md   the remaining rows that the rule pre-coder could not decide
                  (`needs_manual=True`), 50 per batch, ordered by repo/instance.

Each row block carries: identity, B label + evidence, file sets, final patch,
gold patch, test patch, FAIL_TO_PASS, and a blank coding slot. The rule suggestion
is deliberately NOT shown (avoid anchoring); pass --show-rule to include it.

Usage:
  PYTHONIOENCODING=utf-8 python make_coding_batches.py
  PYTHONIOENCODING=utf-8 python make_coding_batches.py --show-rule
"""
import argparse
import csv
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABLE = HERE / "failure_table_437.csv"
PRECODE = HERE / "precode_437.csv"
CALIB = HERE / "calibration_12.csv"
OUT_DIR = HERE / "review"
KAPPA = HERE / "kappa_50.md"
SEED = 20261108


def read_csv(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load():
    table = read_csv(TABLE)
    precode = {r["instance"] + "|" + r["skill"]: r for r in read_csv(PRECODE)}
    calib = {(r["instance"], r["fail_skill"]) for r in read_csv(CALIB)}
    for i, r in enumerate(table, 1):
        r["row_id"] = f"{i:04d}"
        p = precode[r["instance"] + "|" + r["skill"]]
        r["rule_code"] = p["rule_code"]
        r["rule_conf"] = p["rule_confidence"]
        r["needs_manual"] = p["needs_manual"] == "True"
    return table, calib


def stratified_kappa(rows, calib, n=50):
    """Proportional sample by B label, spread across repos, excluding the 12 read cases."""
    pool = [r for r in rows if (r["instance"], r["skill"]) not in calib]
    labels = ["wrong_fix", "incomplete_patch", "wrong_location", "uncertain", "other"]
    total = len(pool)
    quotas = {lab: n * sum(1 for r in pool if r["final_label"] == lab) / total for lab in labels}
    alloc = {lab: int(quotas[lab]) for lab in labels}
    for lab, _ in sorted(quotas.items(), key=lambda kv: kv[1] - int(kv[1]), reverse=True):
        if sum(alloc.values()) < n:
            alloc[lab] += 1
    rng = random.Random(SEED)
    picked = []
    for lab in labels:
        sub = [r for r in pool if r["final_label"] == lab]
        by_case = {}
        for r in sub:
            by_case.setdefault(r["case"], []).append(r)
        cases = sorted(by_case)
        rng.shuffle(cases)
        quota = alloc[lab]
        # round-robin across repos so the sample is not one repo
        i = 0
        while quota > 0 and cases:
            c = cases[i % len(cases)]
            if by_case[c]:
                picked.append(by_case[c].pop(rng.randrange(len(by_case[c]))))
                quota -= 1
            else:
                cases.remove(c)
                if cases:
                    i %= len(cases)
                continue
            i += 1
    return picked


def fence(text, lang=""):
    text = (text or "").strip()
    if not text:
        return "_（空）_"
    return f"````{lang}\n{text}\n````"


def render_row(r, show_rule):
    lines = []
    lines.append(f"## [{r['row_id']}] {r['instance']} · `{r['skill']}`")
    lines.append("")
    lines.append(f"- 阶段：{r['phase']}；实例 n_resolved={r['n_resolved_instance']}/{r['n_arms_instance']}")
    lines.append(f"- B 标签：**{r['final_label']}**（置信 {r['confidence']}；原始 {r['original_label']}）")
    lines.append(f"- 补丁文件（{r['patch_n_files']}）：{r['patch_files'] or '—'}")
    lines.append(f"- gold 文件（{r['gold_n_files']}）：{r['gold_files'] or '—'}")
    lines.append(f"- test 文件（{r['test_n_files']}）：{r['test_files'] or '—'}")
    lines.append(f"- FAIL_TO_PASS（{r['n_f2p']}）：{r['f2p_tests'] or '—'}")
    if r["test_new_tests"]:
        lines.append(f"- test_patch 新增测试：{r['test_new_tests']}（在 F2P 中：{r['test_new_tests_in_f2p']}）")
    if show_rule:
        lines.append(f"- **规则建议**：{r['rule_code']}（{r['rule_conf']}）— 仅供参考，不要照抄")
    lines.append("")
    lines.append("### B evidence")
    lines.append("")
    lines.append(r["evidence"].strip() or "_（空）_")
    lines.append("")
    lines.append("### 最终补丁")
    lines.append("")
    lines.append(fence(r["final_patch"], "diff"))
    lines.append("")
    lines.append("### Gold patch")
    lines.append("")
    lines.append(fence(r["gold_patch"] if "gold_patch" in r else "", "diff"))
    lines.append("")
    lines.append("### Test patch")
    lines.append("")
    lines.append(fence(r["test_patch"] if "test_patch" in r else "", "diff"))
    lines.append("")
    lines.append("### 编码")
    lines.append("")
    lines.append("- main_cause（F1/F2/F3/F4）：")
    lines.append("- secondary_cause（可空）：")
    lines.append("- evidence（一句话，指出补丁行/test 断言）：")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def attach_gold_test(rows):
    """The main table does not carry full gold/test text; load from the dataset."""
    ds = {}
    p = HERE.parents[3] / "experiment_data" / "00_benchmark_inputs" / "swe_bench_verified.jsonl"
    with open(p, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            ds[d["instance_id"]] = d
    for r in rows:
        d = ds[r["instance"]]
        r["gold_patch"] = d.get("patch", "")
        r["test_patch"] = d.get("test_patch", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-rule", action="store_true")
    args = ap.parse_args()

    rows, calib = load()
    attach_gold_test(rows)

    kappa = stratified_kappa(rows, calib, 50)
    header = [
        "# Kappa 批次 50 条（两位编码者用同一份）", "",
        "> 独立编码，不要互相看。main_cause 只填 F1/F2/F3/F4；",
        "> 不确定时填 F? 并在 evidence 里写卡在哪。", "",
        "## 判据速查", "",
        "- **F1 读错契约**：位置对，精确输出/顺序/状态词/API 形状不符；",
        "- **F2 选错修复点**：修消费者/症状/计算层，测试断言提供者/根因/显示层；",
        "- **F3 漏分支/入口**：位置对，漏了同接口的其他分支/实现/边界；",
        "- **F4 评测冲突/infra**：同补丁不同判定、新测试不在 F2P、网络/超时/预算终止。",
        "", "---", "",
    ]
    KAPPA.write_text("\n".join(header) + "\n".join(
        render_row(r, args.show_rule) for r in kappa), encoding="utf-8")

    OUT_DIR.mkdir(exist_ok=True)
    manual = sorted([r for r in rows if r["needs_manual"]], key=lambda r: (r["case"], r["instance"], r["skill"]))
    batches = [manual[i:i + 50] for i in range(0, len(manual), 50)]
    for i, batch in enumerate(batches, 1):
        p = OUT_DIR / f"batch_{i:02d}.md"
        head = [f"# 复核批次 {i:02d}（{len(batch)} 条）", "",
                "> 规则无法定性的条目；请按判据读补丁与 test_patch 后编码。", "", "---", ""]
        p.write_text("\n".join(head) + "\n".join(
            render_row(r, args.show_rule) for r in batch), encoding="utf-8")

    template = HERE / "coding_template.csv"
    with open(template, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["row_id", "instance", "skill", "b_label", "main_cause",
                    "secondary_cause", "evidence", "coder"])
        for r in rows:
            w.writerow([r["row_id"], r["instance"], r["skill"], r["final_label"], "", "", "", ""])

    print(f"kappa: {KAPPA} ({len(kappa)} rows)")
    print(f"review batches: {len(batches)} files, {len(manual)} rows -> {OUT_DIR}")
    print(f"template: {template} ({len(rows)} rows)")


if __name__ == "__main__":
    main()

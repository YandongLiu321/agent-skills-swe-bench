# 437 条失败原因编码（full_coding）

把 101 个交叉实例的 437 条失败运行编码为四类主因（F1 读错契约 / F2 选错修复点 / F3 漏分支入口 / F4 评测冲突或 infra），并保留 `U`（证据不足）单列。

## 文件

| 文件 | 内容 |
|---|---|
| `build_failure_table.py` | 拼表脚本：B 标签 + A 过程特征 + `swe_bench_verified.jsonl` + 轨迹 exit 补丁 |
| `failure_table_437.csv` | 主表，437 行 × 61 列（补丁/gold/test 文件集、断言形状、F2P、B 证据等） |
| `failure_table_437_summary.json` | 拼表分布摘要 |
| `calibration_12.csv` | 12 个深读案例的主因编码（校准集） |
| `判据_v1.md` | 四类定义、判定顺序、12 案校准结果、人工编码协议 |
| `precode_rules.py` / `precode_437.csv` | 规则首过（含置信度、`needs_manual`） |
| `coding_brief.md` | 给编码者的工作说明（判据 + 锚例 + 输出格式） |
| `coding_manual_50.csv` | 50 条 kappa 批次的逐条人工编码（含证据） |
| `coding_manual_extra.csv` | 20 条 uncertain 全量 + 交叉实例修正（F2） |
| `compact/` | 每批的 compact 材料（final patch + gold/test 的 + 行 + F2P） |
| `review/batch_01..07.md` | 309 条 `needs_manual` 的复核批次 |
| `review/codes_batch_*.csv` | 7 批的逐条编码输出 |
| `merge_coding.py` | 合并 manual > agent > rule，产出 `coding_437_v1.csv` 与报告 |
| `coding_437_v1.csv` | 最终 437 条编码（含 source 列） |
| `coding_437_v1_report.md` | 占比 + Wilson 区间 + 按仓库/B 标签/n_resolved 分层 |
| `reliability.py` | manual / agent / rule 之间的 agreement 与 Cohen's kappa |
| `编码结果_v1.md` | **最终结果**：分布 + Wilson 区间 + 分层 + 一致性 + 限制 |
| `复核报告_v1.md` | **42 条独立复核**：样本、40/42、kappa 0.93、2 条边界、2 条改正 |
| `audit_sample.csv` / `audit_codes.csv` / `compact/audit_42.txt` | 复核样本、独立编码、材料 |
| `框架表_v1.md` | 给开发者的失败形态 / 可观察信号 / 典型原因 / 成功做法 / 干预点 |

## 复现

```bash
cd $REPO
PYTHONIOENCODING=utf-8 python task5/analysis/root_cause/full_coding/build_failure_table.py
PYTHONIOENCODING=utf-8 python task5/analysis/root_cause/full_coding/precode_rules.py --validate
PYTHONIOENCODING=utf-8 python task5/analysis/root_cause/full_coding/make_coding_batches.py
PYTHONIOENCODING=utf-8 python task5/analysis/root_cause/full_coding/merge_coding.py
PYTHONIOENCODING=utf-8 python task5/analysis/root_cause/full_coding/reliability.py
```

## 最终结果（v1）

- 437 条：F1 144 / F2 95 / F3 173（主分母 412）；F4 15、U 10 单列。
- 占比：F1 35.0% [30.5, 39.7]，F2 23.1% [19.3, 27.4]，F3 42.0% [37.3, 46.8]（Wilson 95%）。
- 置信度：high 351 / medium 76 / low 10。
- 42 条独立复核：40/42 = 95.2%，Cohen's kappa 0.93；2 条 F1/F3 边界（0128/0134）保留原码，2 条改正（0225 F1→F3、0412 U→F1）。
- 人工 vs 批次：43 条重叠，复核后 41/43 = 95.3%，Cohen's kappa 0.93；2 条分歧（0225、0412）按复核改正。复核前 41 条为 36/41 = 87.8%、kappa 0.82。
- 人工 vs 规则：78 条重叠，仅 39.7%，kappa 0.22；规则只能做硬信号预筛。

## 口径与限制

- **B 的粗标签不是原因**：`wrong_fix` 57.9% 落到 F1、`incomplete_patch` 67.1% 落到 F3、`wrong_location` 90.5% 落到 F2；三个可映射标签内仍有 33.4% 跨类。报告必须同时给标签与原因。
- `uncertain` 是证据状态：有 test 断言就判，没有正式失败断言才编码为 `U`；`other`（预算/API 终止）归 F4-infra。
- `F1/F2/F3` 是主因，很多条目有次因；`evidence` 里记录的是决定性补丁行/函数/断言。
- 规则 high 置信的 128 条抽检 39 条，35 条一致；12 条经复核改判（sympy-17318 / xarray-6938 共 11 条 F3→F2，django-11885 1 条 F3→U）；81 条未逐条复核。
- 机器编码不能替代人类 kappa：`reliability.py` 报的是 manual vs agent vs rule 的一致性，用于发现分歧，不是论文里的 inter-rater kappa。

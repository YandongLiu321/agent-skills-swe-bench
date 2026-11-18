# other_baseline 数据索引

整理时间：2026-10-29。

本目录只保留**外部 baseline 300** 数据。原来放在这里的「完整题目 / 有无 skill」整理包与缺失明细补充不属于 baseline，已移到 `experiment_data/07_full_task_eval/`。

## 目录

| 目录 | 内容 |
|---|---|
| `baseline_300_complete/` | 三组 baseline 300 的合并数据集（每组 100 实例 × 3 次），含 `MANIFEST_300.csv`、`SUMMARY_300.csv` |
| `baseline_300_complete/BASELINE_200_REPEAT.md` | 200 个样例的重复 baseline 与单次运行门槛：三次 78.5% / 81.0% / 81.5%，均值 80.33%、SD 1.61pp；95% t 门槛 88.32%，Skill 总体 82.86% 低于门槛 |

配套的 skill 实验完整题目包在：

```text
experiment_data/07_full_task_eval/
├── 完整题目与运行材料/     # 500 题 ×（无 skill + 10 skill）= 5,500 条
└── supplement/             # 3,240 条缺失明细请求清单 + machine2 补回的 1,330 条
```

## 快速结果

> 报告中的分析只使用前 200 个样例（每例 3 次）；下表是原始数据清单，group3 不纳入报告。

| group | resolved | 三次分轮 | 模型 |
|---|---:|---|---|
| group1 | 233/300 = 77.7% | 75 / 79 / 79 | `deepseek/deepseek-flash` |
| group2 | 249/300 = 83.0% | 82 / 83 / 84 | `deepseek/deepseek-v4-flash` |
| group3 | 275/300 = 91.7% | 91 / 92 / 92 | `deepseek/deepseek-flash`（pure） |

## 口径

- **不要把 group1/2/3 混成一个总体 baseline**：group1/group3 的评测配置是 `deepseek/deepseek-flash`，group2 是 `deepseek/deepseek-v4-flash`；在确认两者是同一模型别名之前，只能分组比较。group2 与旧 baseline_500 可以直接对照。
- group3 已在 2026-10-31 替换为 **pure-flash 版**（旧的 152 条 `deepseek-chat` 混合版已移出）；三组现在都有逐实例 r1–r3 结果。
- 逐实例明细与字段说明见 `baseline_300_complete/README.md` 和 `baseline_300_complete/MANIFEST_300.csv`；group3 的合并说明见 `baseline_300_complete/group3/MERGE_NOTE.md`。

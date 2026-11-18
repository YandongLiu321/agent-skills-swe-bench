# baseline_300_complete

三组 SWE-bench baseline 的合并数据集：每组 100 个实例 × 3 次重复（r1/r2/r3），共 900 次运行。

整理时间：2026-10-29；2026-10-31 更新：group3 替换为 pure-flash 版（275/300）。原始压缩包已全部解压并合并到本目录，校验文件数一致后删除。

## 结果总览

| group | 实例 | 运行 | resolved | resolved 率 | r1 / r2 / r3 | 模型 |
|---|---:|---:|---:|---:|---|---|
| group1 | 100 | 300 | 233 | 77.67% | 75 / 79 / 79 | `deepseek/deepseek-flash` |
| group2 | 100 | 300 | 249 | 83.00% | 82 / 83 / 84 | `deepseek/deepseek-v4-flash` |
| group3 | 100 | 300 | 275 | 91.67% | 91 / 92 / 92 | `deepseek/deepseek-flash`（pure） |

机器可读汇总：`SUMMARY_300.csv`；逐实例明细：`MANIFEST_300.csv`。200 个样例的重复 baseline 与单次运行门槛见 `BASELINE_200_REPEAT.md`：三次通过率 78.5% / 81.0% / 81.5%，均值 80.33%、SD 1.61pp；95% t 门槛 88.32%，Skill 总体 82.86% 低于门槛。

## 目录结构

```text
baseline_300_complete/
├── MANIFEST_300.csv          # 300 行：group/case/instance/旧 baseline 状态/三次 resolved/模型
├── SUMMARY_300.csv           # 3 行：每组 resolved 总数与命中率
├── README.md
├── group1/
│   ├── delivery/             # 交付说明与打包产物
│   ├── evaluation/           # 官方 SWE-bench harness 结果
│   │   ├── results/summary.json
│   │   ├── results/per_instance_results.csv   # 100 行，含 r1/r2/r3 resolved
│   │   ├── results/per_run_results.csv        # 300 行
│   │   └── logs/             # report.json / eval.sh / patch.diff 等
│   ├── runs/group1/
│   │   ├── pilot/            # 5 个仓库 × 2 次
│   │   └── formal/           # 100 实例 × 3 次
│   ├── source/               # 运行与评测脚本
│   └── *.csv / *.json        # 分组、配置、manifest、运行日志
├── group2/
│   ├── MANIFEST.csv          # 300 行：case/instance/rep/resolved/preds/traj/test_output
│   ├── <repo>/<instance>/r{1,2,3}/
│   │   ├── preds.json
│   │   ├── traj.json
│   │   └── test_output.txt
│   └── legacy_eval/          # 旧评测包（305 个文件），保留作对照
└── group3/                   # pure-flash 版，275/300 = 91.67%
    ├── delivery/
    │   ├── run_summary.csv   # 逐轮 resolved：91/92/92
    │   ├── predictions/
    │   ├── summary.json / validation.json / configuration.json
    │   └── README_DELIVERY.md
    ├── evaluation/
    │   ├── final_reports/    # 每轮合并后的官方报告（含 resolved_ids）
    │   └── official/         # 6 个聚合报告 + per_run_recovery/（148 条逐题报告）
    ├── runs/<repo>/<instance>/r{1,2,3}/   # 300 条轨迹 + 300 个 run.log
    ├── logs/                 # 48 个运行日志
    ├── source/               # 运行脚本 + 152 条错误配置运行清单
    ├── MERGE_NOTE.md         # 合并说明与已知缺口
    └── verified-dataset.json
```

## MANIFEST_300.csv 字段

| 字段 | 含义 |
|---|---|
| `group` | group1 / group2 / group3 |
| `case` | SWE-bench 仓库名（如 django、sympy） |
| `instance` | SWE-bench instance_id |
| `old_baseline_status` | 旧 baseline_500 中该实例是否通过（pass / fail） |
| `r1_resolved` / `r2_resolved` / `r3_resolved` | 三次重复各自是否 resolved（1/0） |
| `resolved_avg` | 三次均值；group3 无逐实例数据时为空 |
| `model` | 该组使用的模型名 |

## 口径与注意

- **group1 / group3 是 `deepseek/deepseek-flash`，group2 是 `deepseek/deepseek-v4-flash`。** 在确认两者是同一模型别名之前，不要把三组合并成一个总体 baseline；group2 与旧 baseline_500 可以直接对照。
- group1 / group2 / group3 现在都有逐实例 r1–r3 结果；group3 来自 `evaluation/final_reports/`。
- group1 的逐实例分布（来自其 README）：0/1/2/3 次通过分别为 17 / 6 / 4 / 73。
- group2 的逐实例分布：3/3 为 78 个，2/3、1/3、0/3 分别为 5、5、12 个。
- group3 的逐实例分布：3/3 为 86 个，2/3、1/3、0/3 分别为 8、1、5 个。
- group3 的 r2 有 2 条空补丁（LimitsExceeded），计为 unresolved；详见 `group3/MERGE_NOTE.md`。
- 旧 baseline 对照（group2）：旧通过 81 个中 74 个新 3/3、2 个新 0/3；旧失败 19 个中 4 个新 3/3、10 个新 0/3。

## 来源

| 目录 | 原始文件 |
|---|---|
| group1 | `group1_baseline_300_evaluated_results_20261026(1).zip`（4349 个文件） |
| group2 预测/轨迹 | `group2_baseline_300_preds_traj_testoutput.zip`（902 个文件） |
| group2 旧评测 | `baseline_300_group2_eval_results.tar.gz`（305 个文件） |
| group3 | `group3_baseline_300_pure_flash_evaluated_results_20261029.zip`（674 个文件；替代旧的混合版 `group3_baseline_300_evaluated_results_20261029.zip`） |
| group3 错误配置记录 | `group3_initial_runs_wrong_config.csv`（已放入 `group3/source/`） |
| group3 逐题恢复报告 | 148 条 recovery 的 report/test_output 从旧版保留到 `group3/evaluation/official/per_run_recovery/` |

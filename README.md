# mini-swe-agent-skill

在 [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) 上测量 **skill 文本**对
SWE-bench Verified 解题过程和结果的影响。

- 500 个实例 × 10 个 skill 臂 = **5,000 次 skill 运行**；
- 95 个 baseline 失败实例用于测“正向改变”（phase 1，950 次）；
- 405 个 baseline 通过实例用于测“保持/负向改变”（phase 2，4,050 次）；
- baseline 参照为 405 / 500 = 81.00%。

核心数字（全部来自 `experiment_data/05_final_tables/`）：

| 指标 | 数值 |
|---|---:|
| skill 总成功 | **4,143 / 5,000 = 82.86%** |
| 保持 + 正向改变 | 3,856 + 287 |
| 负向改变 | 194 |
| baseline | 405 / 500 = 81.00% |
| 观测净变化 | **+1.86pp**（不是因果结论） |
| 通过题保持率 | 3,856 / 4,050 = **95.21%** |

> 95.21% 只在“baseline 已通过”这一分层里成立；总体成功率是 82.86%。

## 快速上手

```bash
git clone <this-repo>
cd mini-swe-agent-skill
pip install -e .          # harness 在 src/ 里
pip install psutil        # 内存调度依赖
python task5/split/selfcheck.py
```

`selfcheck.py` 最后一行应为 `All checks passed`。然后可以免费预演（不调用模型、不花钱）：

```bash
python task5/run_experiment.py \
  --cases xarray --only-passes \
  --instances-file task5/split/pilot.json \
  --arm python-anti-patterns --repeats 1 --dry-run
```

新实验默认写入 `experiment_data/_incoming/`，**不会覆盖已冻结的最终数据**。
如需指定目录：

```bash
export MINI_SWE_RUNS=/path/to/runs
export MINI_SWE_REPORTS=/path/to/eval_reports
```

官方评测必须使用 Docker 和 `task5/run_eval.py`（内部走 `task5/run_eval_lf.py`），
不要直接调用 `swebench.harness.run_evaluation`；实验环境使用 `--network none`。

## 数据目录

所有原始数据、轨迹、preds 和官方评测都在 `experiment_data/`，按实验阶段组织：

```text
experiment_data/
├── 00_benchmark_inputs/
│   ├── swe_bench_verified.jsonl
│   └── splits/                     # baseline 500 / failed 95 / passed 405 / 三台机器名单
├── 01_baseline_500/
│   ├── runs/<case>/<instance>/     # 499 条本地 baseline 轨迹（10097 缺轨迹，判定仍在）
│   ├── repeats/                    # baseline 重复运行
│   ├── replications/               # machine1 / machine3 的 baseline 独立运行
│   ├── evaluations/                # 官方评测汇总
│   └── eval_logs/                  # 官方逐实例评测日志
├── 02_phase1_rescue_95/
│   ├── runs/<case>/<skill>/<instance>/   # 950 条：95 失败题 × 10 skill
│   ├── repeats/                    # 本地 r2/r3 重复
│   ├── local_extras_baseline_passed/     # 13 个已通过题的本地额外运行（不计入 950）
│   ├── replications/               # machine3 在同样 95 题上的独立运行
│   ├── evaluations/、eval_logs/、run_logs/
│   └── metrics/phase1_local_runs.csv
├── 03_phase2_retention_405/
│   ├── runs/<case>/<skill>/<instance>/   # 4,050 条：405 通过题 × 10 skill，m1/m2/m3 合并
│   ├── repeats/                    # 明确标记的重复运行
│   ├── replications/               # 额外机器/额外实例的运行
│   ├── reruns/                     # machine3 补跑包（p1 / p2p3 / p4）
│   ├── predictions/、evaluations/、metrics/
│   └── manifests/
├── 04_reevaluations/               # recheck-13089 / recheck-1921 / sphinx-9711
├── 05_final_tables/                # final_*.csv / final_tables.xlsx
├── 06_pilots_and_supplementary/    # pilot、依从性、17 个退化实例的选择清单
└── 99_manifests/
    ├── provenance.csv              # 旧路径 → 新路径 → 来源机器
    ├── counts.csv                  # 应有 vs 实有
    ├── checksums.sha256
    └── unclassified.csv / baseline_missing.csv
```

机器来源不再出现在顶层目录名里；三台机器的 phase-2 轨迹已按
`case / skill / instance` 合并，来源记录在 `99_manifests/provenance.csv`。

### 查一条运行

例如 `django__django-10097` 的 `django-tdd`：

```text
experiment_data/03_phase2_retention_405/runs/django/django-tdd/django__django-10097/
experiment_data/03_phase2_retention_405/evaluations/
```

轨迹是 `*.traj.json`（machine3 第 1 份补跑是 `trajectory.json`）；preds 和官方
report 分别在 `predictions/` 和 `evaluations/`。每条运行的原始来源都能在
`99_manifests/provenance.csv` 里查到。

## 复现最终表

```bash
# 1) 从原始数据重算 phase-2 表
python task5/analysis/final/build_final.py

# 2) 加入 phase-1 救回层，生成全 5000 口径
python task5/analysis/final/build_final_v2.py
```

第二步必须输出：

```text
skill totals 4050 3856 194 950 287 5000 4143
all_500_instances 5000 4143 82.86 baseline 81.00 net +1.86
```

如果这两个数对不上，不要继续使用表；先查 `99_manifests/counts.csv` 和
`provenance.csv`。

## 数据完整性说明

- phase-2 规范集：**4,050 / 4,050** 条轨迹；每台机器 1,350 条。
- machine3 最终合并的**逐实例判定**在
  `03_phase2_retention_405/metrics/machine3_final_1350_corrected_verdicts.csv`：
  1,350 行，**1,267 resolved / 83 unresolved**，与终表一致。
  原始官方判定（1,124 / 226，空补丁 142）在同目录的
  `machine3_final_1350_verdicts.csv`；318 条补跑明细在
  `machine3_rerun_verdicts.csv`。
- phase-1 规范集：**950 / 950** 条轨迹。
- baseline：官方 500 条判定齐全；本地轨迹 499 条，`django__django-10097`
  没有 baseline 轨迹，但官方判定存在，已列在 `baseline_missing.csv`。
- machine2 的原始包只含 skill 轨迹，没有 baseline 轨迹；baseline 由本地、
  machine1、machine3 覆盖。
- machine3 第 4 份补跑 zip 里有 5 个超长路径的 `run_instance.log` 未解压，
  但 zip 原件完整保存在 `99_manifests/archives/`，没有丢数据。
- `checksums.sha256` 覆盖 `experiment_data/` 下全部 22,000+ 个文件。

## 注意事项

- **不要覆盖 `experiment_data/`**：新运行写 `_incoming/`，校验后再归档。
- 不要提交 API key；key 在 harness 的配置目录里，不在仓库中。
- 官方评测必须用 Docker；`requests-1921` 等题依赖网络，失败日志里的 502
  不是模型错误（见 `04_reevaluations/`）。
- 现有数据是“模型可能已见过公开题解”的条件下的观测结果；结论要写成
  “在该条件下 skill 的效果”，不能写成无污染的能力提升。

## 许可与引用

- 代码：MIT，见 `LICENSE`。
- 数据（`experiment_data/`、`task5/analysis/`、`other_baseline/` 汇总表）：CC BY 4.0，见 `DATA_LICENSE.md`。
- 第三方 Skill 文本、SWE-bench 与 mini-SWE-agent 材料：见 `NOTICE` 与 `LICENSES/`。
- 引用信息：见 `CITATION.cff`。

## English summary

This repository contains the code and data for a controlled study of Agent
Skills on SWE-bench Verified with mini-SWE-agent: 500 baseline runs and 5,000
skill runs over 34 skills. The aggregate success rate is 82.86% (4,143/5,000)
against a baseline of 81.00% (405/500), a net change of +1.86pp with a
case-level bootstrap 95% CI of [-1.68, +3.50]pp. Under this benchmark, model
and runtime, the effect is hard to distinguish from baseline variation. See
`experiment_data/05_final_tables/` for the aggregate tables and
`task5/analysis/root_cause/full_coding/` for the failure coding.

## Data scope

- `experiment_data/01_baseline_500/`: 500 baseline runs.
- `experiment_data/02_phase1_rescue_95/`: 95 baseline-failed instances x 10 skills.
- `experiment_data/03_phase2_retention_405/`: 405 baseline-passed instances x 10 skills.
- `experiment_data/05_final_tables/`: aggregate tables.
- `task5/analysis/`: analysis scripts and derived tables, including the 437-failure coding.
- `other_baseline/`: summary of the 200-instance x 3 baseline repeat threshold check.

Not included: the 5,500-run browsing package (`07_full_task_eval`, a
non-canonical selection from 01-03) and the raw 300-instance baseline repeat
runs; only the summary files are provided.

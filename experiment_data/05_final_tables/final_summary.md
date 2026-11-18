# 最终表（2026-10-18；2026-10-19 补入一期 rescue）

## 主口径（全部 500 个实例）

- 全部 skill 运行：**5000**（405 通过题 ×10 + 95 失败题 ×10）。
- 成功：**4143**（保持 3856 + 救回 287）。
- 总体成功率：**82.86%**（4143/5000）。
- baseline：**405/500 = 81.00%**；净变化 **+1.86pp**。
- 其中弄坏：**194** 次（4.79% of 4050）；救回：**287** 次。

## 两个必须分开的口径

- **phase2 保持率**：3856/4050 = **95.21%**；分母是 baseline 已通过题 ×10。
- 同样这 405 题，baseline 是 **405/405 = 100%**；所以 skill 在这层是 **−4.79pp**，不是提升。
- **all_500_instances**：4143/5000 = **82.86%**；这是回答“全部 500 题加 skill 后总体怎样”的数字。

## 表格（每个 CSV 都带 data_basis 列）

| 文件 | 行数 | 数据口径 |
|---|---:|---|
| `final_overall.csv` | 2 | 一行 phase2 保持率；一行 all-5000 总成功率 |
| `final_case_skill_metrics.csv` | 132 | 12 baseline 参考 + 120 case×skill；含 n_passed/retained/broken/n_failed/rescued/n_all |
| `final_accuracy_by_case_skill.csv` | 120 | case×skill，含两期合并后的 overall_accuracy |
| `final_accuracy_by_case.csv` | 12 | 每个 case 的 10 skill 合并；n_passed=通过题×10，n_failed=失败题×10 |
| `final_pooled_skill.csv` | 34 | 每个 skill 覆盖的全部实例；n_all 随覆盖范围变化 |
| `final_baseline.csv` | 12 | baseline 500 题；accuracy=passed/total |
| `phase1_rescue_by_case_skill.csv` | 120 | 一期失败题首轮运行；n_failed/rescued |
| `final_tables.xlsx` | 8 sheets | 第一张 `口径说明`，其余为上述表 |

## 怎么读

- `n_passed` = baseline 已通过实例数；`retained` = 加 skill 后仍成功；`broken` = n_passed−retained。
- `n_failed` = baseline 失败实例数；`rescued` = 加 skill 后成功；`n_all=n_passed+n_failed`。
- `skill_successes=retained+rescued`；`overall_accuracy=skill_successes/n_all`。
- `retention_accuracy=retained/n_passed`；它只在“已通过题”这个分层里有效，不能当总体成功率。
- `data_basis` 列逐表写明每个数字的分子/分母来源。

## 数据质量

- 10 条 sphinx-9711 解析器误判、2 条 requests-1921 网络环境误判已修正；
- 3 条空补丁重跑后 resolved；142 条空补丁用 b1/b4 补判；
- 一期 950 次失败题运行来自首轮本地运行（repeat=1）；救回 287 次，53/95 道题至少一个 skill 臂成功。

## 旧表

旧的 `summary_accuracy*.csv` 等基于 m1+m2 的 2700 条 / 4.07%，已移到 `task5/analysis/_deprecated_2026-10-18/`，不要再用。

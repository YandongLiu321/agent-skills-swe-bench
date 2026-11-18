# 过程特征签名：三类失败不是同一种“过程病”

> 数据：A 的 `A_toolcall_features_v2.csv`（1,010 条 mixed 运行，命令级特征）+ B 的 `integrated_1010_with_final_labels.csv`（最终标签）。
> 方法：按 success / wrong_fix / incomplete_patch / wrong_location 分组，分 phase1 / phase2 统计均值与中位数。
> 性质：描述性，不是因果识别；样本是“有分歧”的 1,010 条，不能外推为总体。

## 1. 分 phase 的过程特征

### phase1（197 success / 102 wrong_fix / 94 incomplete / 37 wrong_location；另有 other 10，未列入）

| 特征 | success | wrong_fix | incomplete_patch | wrong_location |
|---|---:|---:|---:|---:|
| n_steps 均值 | 58.7 | 71.6 | **47.5** | 73.7 |
| n_commands 均值 | 77.4 | 91.9 | **63.9** | 101.3 |
| n_tests 均值 | 13.4 | 15.6 | **9.5** | 19.8 |
| n_edits 均值 | 15.4 | 19.6 | 14.3 | 17.7 |
| n_search 均值 | 21.3 | 27.2 | **17.9** | 28.3 |
| n_read 均值 | 14.4 | 16.2 | **11.7** | 16.7 |
| n_failed_cmds 均值 | 3.8 | 3.9 | **2.7** | **6.4** |

### phase2（376 success / 81 wrong_fix / 67 incomplete / 26 wrong_location；另有 uncertain 20，未列入）

| 特征 | success | wrong_fix | incomplete_patch | wrong_location |
|---|---:|---:|---:|---:|
| n_steps 均值 | 63.7 | 68.5 | 58.7 | **82.7** |
| n_commands 均值 | 83.2 | 92.3 | 75.0 | **103.1** |
| n_tests 均值 | 14.0 | 14.5 | 11.6 | 15.3 |
| n_edits 均值 | 17.7 | 19.5 | 17.2 | 19.5 |
| n_search 均值 | 23.2 | 27.6 | 21.0 | **32.2** |
| n_read 均值 | 15.5 | 15.4 | 14.8 | **19.4** |
| n_failed_cmds 均值 | 3.9 | 3.8 | 3.8 | **5.9** |

## 2. 读出来的三个“过程签名”

1. **incomplete_patch ≈ 操作少、停止早**：两个 phase 里，steps / commands / tests / search / read 都低于 success。不是“修改位置错误”，而是**探索和验证都不充分**；这与“只包分子”“只改一个调用方”的案例一致。
2. **wrong_location ≈ 找得多、错得多、失败命令多**：steps / commands / search / read / failed_cmds 都高于 success；phase1 的 tests 也最高。像是**在错误方向上反复探索**，搜索多但没有收敛到正确位置。
3. **wrong_fix ≈ 修改多、搜索多**：steps / commands / edits / search 高于 success；不是“未执行操作”，而是**执行了大量操作但逻辑仍然错误**。这与 15127 的“删变量 + 动态读取 + 96 tests 通过”一致：过程很充分，契约仍不满足。

success 落在中间：探索足够，但没有过度 thrash。这个“倒 U”形态是描述性的，不能直接当因果。

**个案可以相反**：14976 的 7 个 `incomplete_patch` 臂是契约缺口，不是早停——例如 `python-project-structure` 有 96 条消息、做了充分探索，仍因精确字符串失败。过程签名是群体均值，不能拿来给单条轨迹定性；定性必须读 patch + test_patch。

## 3. 测试耦合的扫描（另一个方向）

对 500 个实例的 `test_patch` 做正则扫描：

- 只有 **14/500** 个 test_patch 使用 `mock.patch(`（8 个同时用 `@mock.patch` 装饰器）；**4/500** 使用 `assert_called`/`assert_not_called`。
- 在 1,010 条 mixed 运行中：
  - `mock.patch` 组：80 条，失败 29（36.2%）；
  - 非 `mock.patch` 组：930 条，失败 408（43.9%）；
  - `assert_called` 组：10 条，失败 5（50%），5 条全是 wrong_location（n=10，不能外推）。

结论：**实现耦合测试（mock/调用断言）在数据集里很少**；15127/15252 的“测试侧因素”是**案例级**的，不是 437 条失败的普遍解释。这一点很重要，避免把两个锚案例的特殊性写成总体结论。

## 4. 边界

- 过程特征来自命令正则，`n_tests` / `n_edits` / `tested_after_last_edit` 都有噪声；A 的 feature dictionary 明确说这些是启发式。
- 1,010 条是按“有分歧”选的，失败率 43.3%，不能代表 4,050 条 phase2 的总体。
- phase1/phase2 的标签分布不同；虽然两个 phase 的方向一致，但不能排除任务难度与 skill 组成的混杂。
- 这些签名是**假设生成**：它们提示“incomplete ≈ 早停”“wrong_location ≈ 探索失败”“wrong_fix ≈ 过程充分但契约错”，需要更多案例和实验验证。

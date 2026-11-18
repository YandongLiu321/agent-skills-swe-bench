# 全文核对：Django 15127 / systematic-debugging（65 条消息）

> 读法：读完所有 assistant 的 reasoning 与工具调用；工具输出按其内容抽查（文件 dump/测试日志），关键输出全读。目的：核对 `case_django_15127.md` 中 SD 臂的因果链。

## 1. 完整时间线（决策相关）

| 消息 | 动作 |
|---|---|
| [2]–[8] | 探索仓库；读 `base.py`、`utils.py`、tests；确认 `LEVEL_TAGS` 是 import 时计算的模块常量 |
| [8] | 回忆 upstream fix 的多种可能：`SimpleLazyObject`、`cached_property`、动态读取；不确定 |
| [11] | 明确两种方案：①每次访问动态计算；②接 `setting_changed` 信号；仍不确定 |
| [14] | **明确列出 Option A（删除 `LEVEL_TAGS`）与 Option B（保留 + `setting_changed` 刷新）**；倾向 A，但想先核实 |
| [25] | 先按 Option A 实现（删除常量 + 动态读取） |
| [30] | 发现现有测试 helper 引用 `base.LEVEL_TAGS`，删除会让现有测试报错；开始犹豫 |
| [37] | 恢复/比较方案；[39] 明确讨论“保留 + 信号”是 best of both，但“I don't think upstream used a signal” |
| [45] | **最终选择：保留 `LEVEL_TAGS` + 只让 `level_tag` 动态读取**；理由是 “keep LEVEL_TAGS + dynamic passes in all cases. Remove LEVEL_TAGS only passes in case A. ... rational choice for maximizing test pass probability is to KEEP” |
| [47]–[54] | 用“原始测试文件（helper 保留）”和“模拟 test patch（helper 删除）”各跑一次；两种都 96 项通过 |
| [56] | 最终确认：`LEVEL_TAGS` 仍在但不更新；只改 `level_tag` 一行 |
| [59]–[63] | 生成 patch、验证、提交 |

## 2. 关键发现

### 2.1 它知道正确方案（Option B），但主动放弃了

[14]：

> “Option A: Remove `LEVEL_TAGS`, compute dynamically. Option B: Keep `LEVEL_TAGS`, but register a `setting_changed` receiver to refresh it. Which did Django do? I'm now fairly sure it's Option A...”

[39]：

> “...keep `LEVEL_TAGS` for backward compat but ALSO make it dynamic via signal? That would be the ‘best of both’... But I don't think upstream used a signal.”

所以这不是“没想到保留并更新”，而是**想到了、但按“upstream 大概没这么做”放弃了**。Option B 恰好是成功臂（django-security）采用并通过正式测试的方案。

### 2.2 最终选择是“测试通过概率最大化”的混合方案

[45] 原文：

> “So ‘keep LEVEL_TAGS + dynamic’ passes in all cases. ‘Remove LEVEL_TAGS’ only passes in case A. Given the asymmetry, the rational choice for maximizing test pass probability is to KEEP LEVEL_TAGS while making level_tag dynamic.”

它保留变量，但不更新变量。结果是：
- 现有测试 helper（会手动更新 `base.LEVEL_TAGS`）仍能跑；
- 模拟的 test patch（删除 helper、用 plain `override_settings`）也能跑；
- 但正式测试的 `assertEqual(base.LEVEL_TAGS, self.message_tags)` 失败，因为变量仍是旧值。

这不是“只修读取方”那么简单，而是**在两个可能契约之间选了一个对两种模拟测试都安全、但对真实契约不完整的中间方案**。

### 2.3 验证仍然依赖自己构造的 test patch

[47]–[54] 执行了两种测试文件：
- 原始测试文件（helper 保留）：96 项通过；
- 自己模拟的 test patch（helper 删除、plain `override_settings`）：96 项通过。

但两种模拟都没有加入正式测试的 `test_override_settings_level_tags`（`assertEqual(base.LEVEL_TAGS, ...)`）。它验证的是“helper 会不会崩”，不是“变量是否更新”。

### 2.4 任务/效度因素

Issue 只说 `Message.level_tag` 读到旧值，没有说 `base.LEVEL_TAGS` 本身是契约的一部分。正式测试却直接断言这个模块变量。SD 臂的“保留 + 动态”在 issue 层面也能解释得通，但在 benchmark 的测试契约下失败。与 DER 一样，这条失败是**模型选择/验证问题 + issue 未说明测试契约**的混合。

## 3. 修正后的因果链

- **现象**：`AssertionError`，`LEVEL_TAGS` 仍是默认值。
- **直接原因**：保留变量但不更新，只改 `level_tag` 的读取路径。
- **根本原因**：
  1. **在两个可能契约之间做了“测试安全”而非“契约完整”的选择**：保留 + 动态，但不更新变量；
  2. **主动放弃了正确方案**：Option B（保留 + `setting_changed`）被想到，但按“upstream 大概没这么做”排除；
  3. **验证模型不完整**：两种模拟 test patch 都缺 `assertEqual(base.LEVEL_TAGS, ...)`；
  4. **任务/效度因素**：issue 未说明 `base.LEVEL_TAGS` 是契约。
- 与 DER 的对比：
  - DER 删除变量 → AttributeError；
  - SD 保留但不更新 → AssertionError；
  - security 保留并更新 → 通过。
  - 三者是同一个“共享状态契约”的三种处理；只有第三种同时满足 issue 和正式测试。

## 4. 对 `case_django_15127.md` 的修正

- “只修读取方、不修写入方”成立，但更准确是 **在两个可能契约之间选了测试安全的中间方案**；
- “记忆先验”在 SD 臂上不是简单的“照搬”，而是 **用 upstream 记忆排除了正确方案 Option B**；
- 新增：**验证模型不完整**（两种模拟都缺正式断言）；
- 新增：**任务/效度因素**（issue 未说明变量是契约）。

## 5. 置信度

- 对机制：高（全 reasoning + 官方日志 + 成功对照）。
- 对“为什么选错”：中高（它明确写出了选择理由；但模型随机性、隐藏测试不可见仍贡献）。

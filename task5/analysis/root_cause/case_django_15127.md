# Case 1：Django 15127 —— 同一个失败测试，三种修法

> 样本：`django__django-15127`，同题 10 个 skill 臂，1/10 成功。
> 本卡读三条轨迹：`debugging-and-error-recovery`（失败，wrong_fix）、`systematic-debugging`（失败，incomplete_patch）、`django-security`（成功）。
> 官方报告与测试输出均已核对（`experiment_data/02_phase1_rescue_95/eval_logs/`）。

## 1. 现象

三条轨迹最终都落在同一个正式测试上：

```python
test_override_settings_level_tags (messages_tests.tests.TestLevelTags)
```

正式测试的关键断言是：

```python
self.assertEqual(base.LEVEL_TAGS, self.message_tags)
```

- `debugging-and-error-recovery`：`AttributeError: module 'django.contrib.messages.storage.base' has no attribute 'LEVEL_TAGS'`
- `systematic-debugging`：`AssertionError`，`LEVEL_TAGS` 仍是默认值，没有随 `MESSAGE_TAGS` 更新
- `django-security`：`ok`

三个补丁的差别不在“有没有改对 `Message.level_tag`”，而在**有没有保留并更新 `base.LEVEL_TAGS` 这个共享状态**。

## 2. Issue 文本给了什么、没给什么

Issue 标题：`LEVEL_TAGS not updated when using @override_settings`

正文：

> When reading messages inside tests, new message tags created using @override_settings is not updated. That causes the `django.contrib.messages.storage.base.Message.level_tag` property results to be an empty string and not know the new tags.

它只描述了**症状**（`level_tag` 读到旧值 / 空字符串），没有规定实现方式。至少有两种读法：

1. 让 `Message.level_tag` 每次访问时重新读取设置（动态读取）；
2. 保留 `LEVEL_TAGS`，在设置变化时更新它（信号/缓存失效）。

两种都能让 `Message.level_tag` 返回新标签；但正式测试还直接检查 `base.LEVEL_TAGS`，所以只有第 2 种（或第 1 种 + 保留变量）才能通过。

## 3. 原代码与正式测试的契约

原代码：

```python
LEVEL_TAGS = utils.get_level_tags()   # 模块加载时计算一次

class Message:
    @property
    def level_tag(self):
        return LEVEL_TAGS.get(self.level, '')
```

正式测试要检查的是：override `MESSAGE_TAGS` 后，`base.LEVEL_TAGS` 本身也必须等于新的 `message_tags`。也就是说，`LEVEL_TAGS` 不是纯内部实现细节，而是测试直接观察的状态。

## 4. 三条轨迹

### 4.1 debugging-and-error-recovery：删除共享变量

关键步骤：

- 轨迹 [16]：agent 已经看到测试辅助类 `override_settings_tags` 在读/写 `base.LEVEL_TAGS`；
- [17]：写复现脚本，[18] 复现成功（override 期间仍是 `info`）；
- [19]：删除模块级 `LEVEL_TAGS`，把 `level_tag` 改成 `utils.get_level_tags().get(...)`；
- [22]：复现脚本通过（override 期间变成 `custom-info`）；
- [24]：grep 确认只有测试辅助类还引用 `LEVEL_TAGS`；
- [26]：**临时修改测试文件**，按自己预测的 upstream test patch 删除 `override_settings_tags`；
- [29]：修改后的测试集 96 项全过；
- [30]：恢复测试文件，并写下“evaluation test patch 会移除 helper”；
- [34]：`It's virtually certain the upstream fix removed the helper.` 提交删除变量的补丁。

根因不是“没复现”，而是：

1. **记忆先验压过仓库证据**：[14] 开头就是“The fix is described in the actual Django commit. Let me recall...”，随后按记忆中的 Django 实现决定删除 `LEVEL_TAGS`；
2. **对正式测试的模型不完整**：它预测 test patch 会删除 helper，却没预测到测试还会新增 `assertEqual(base.LEVEL_TAGS, ...)`；
3. **用自造测试替代正式契约**：它改的是自己预测的测试，96 项通过只证明“在它模拟的测试集里通过”，不证明正式测试通过；
4. **skill 的“测试可能过时”条款**给了它修改测试的许可，但 skill 没有要求区分“测试辅助类被移除”与“被访问的对象仍然必须存在”；
5. **删除共享变量前没有列出所有读取方**：[24] 已经看到 helper 在读 `base.LEVEL_TAGS`，但把它当成“可能会被移除的测试辅助代码”，没有把它当成“这个变量仍然是契约的一部分”的证据。

### 4.2 systematic-debugging：保留变量，但不更新

这条轨迹更长（65 条消息），关键分歧在 [45] 之后：

- [8]–[14]：读代码、测试、git 历史，尝试回忆 upstream fix；
- [25]：先按“删除 `LEVEL_TAGS`”实现了一版；
- [30]：发现现有测试 helper 会因删除而报错，开始犹豫；
- [39]：明确比较两种方案；[45] 写下决策：

> “So ‘keep LEVEL_TAGS + dynamic’ passes in all cases. ‘Remove LEVEL_TAGS’ only passes in case A. Given the asymmetry, the rational choice for maximizing test pass probability is to KEEP LEVEL_TAGS while making level_tag dynamic.”

- [45] 于是**恢复 `LEVEL_TAGS`**，只把 `level_tag` 改成动态读取；
- [47]–[54]：分别用“原始测试文件（helper 保留）”和“模拟 test patch（helper 删除）”执行测试，**两种都 96 项通过**；
- [56]：确认最终补丁仅修改 `level_tag` 一行，`LEVEL_TAGS` 仍在但不更新；
- 正式测试失败：`LEVEL_TAGS` 没有随 `MESSAGE_TAGS` 更新，`assertEqual` 失败。

根因：

1. **仅修改读取方，未修改写入方**：`level_tag` 动态读取解决了“属性读到旧值”的症状，但 `base.LEVEL_TAGS` 仍然是旧值；
2. **测试通过优先于契约理解**：[45] 的决策是“哪种写法更可能通过隐藏测试”，而不是“正式测试到底要求什么状态”；
3. **模拟的 test patch 仍然不完整**：它模拟了“helper 删除”，但未模拟“新增 `assertEqual(base.LEVEL_TAGS, ...)`”；
4. **skill 的“root cause / 不修症状”没有落地**：skill 反复强调“fix at source, not at symptom”，但 agent 把“source”理解为 `level_tag` 属性，而不是 `LEVEL_TAGS` 这个共享状态；
5. **它考虑过 signal 方案但主动放弃**：[14]/[39] 都提到“keep + setting_changed”是更稳妥的方案，但最终因为“upstream 大概不是这么做”而未采用。

### 4.3 django-security：保留并更新

- [8]：搜索 `setting_changed`；
- [14]：读 `django/contrib/auth/hashers.py`，看到 `PASSWORD_HASHERS` 变化时用 `@receiver(setting_changed)` 重置缓存的先例；
- [33]：读 `django/test/signals.py`，确认 `override_settings` 会发 `setting_changed`；
- [41]：实现“保留 `LEVEL_TAGS` + `@receiver(setting_changed)` 更新”；
- [43]：复现脚本通过；
- [45]：messages_tests 通过；
- 正式测试 `ok`。

注意：这条成功轨迹**也**在 [33] 说过“If hidden test additionally checks `base.LEVEL_TAGS`? Unlikely.”——它并没有准确预测正式断言；它只是选择了一个**保留并同步共享状态**的通用修法，恰好满足契约。`django-security` skill 提到 `PASSWORD_HASHERS` 和 Django 认证，可能把 agent 的注意力引向 auth/settings 代码，但 skill 本身没有教 `setting_changed`；因此“skill 导致成功”只能算弱假设，不能写成因果。

## 5. 因果链

| 现象 | 直接原因 | 根本原因 | 证据 | 干预点 |
|---|---|---|---|---|
| wrong_fix（DER） | 删除 `LEVEL_TAGS`，正式测试 `AttributeError` | 记忆先验（“upstream 删了”）+ 预测 test patch 不完整 + 用自造测试替代正式契约 | [14] [17] [23] [26] [30] [34]；官方 `AttributeError` | 删除共享变量前列出所有读取方；区分“测试 helper 被移除”与“被访问对象仍须存在”；用正式测试断言验证 |
| incomplete_patch（SD） | 保留 `LEVEL_TAGS` 但不更新，正式测试 `AssertionError` | 只修读取方、不修写入方 + 测试通过优先于契约理解 + 模拟 test patch 仍不完整 | [45] [47]–[54] [56]；官方 `AssertionError` | 改共享状态的读取路径时，同时检查写入/更新路径；读正式 test patch 或契约，不靠记忆模拟 |
| 成功（security） | 保留 `LEVEL_TAGS` 并用 `setting_changed` 更新 | 找到 `PASSWORD_HASHERS` 的仓库先例，选择保留并同步共享状态 | [8] [14] [33] [41]；官方 `ok` | 把“找仓库先例”写成调试 skill 的显式步骤 |

## 6. 本案例的根因分类（假设）

- **C1 题面只给症状、不给实现契约**：issue 允许“动态读取”和“更新变量”两种读法，正式测试只接受后者（或两者都做）。
- **C2 记忆先验压过仓库证据**：DER 直接按“我记得 upstream 删了”行动；SD 也多次用记忆推测 test patch。
- **C3 对正式测试的模型不完整**：两条失败轨迹都只模拟了“helper 被删除”，没有模拟“新增 `assertEqual(base.LEVEL_TAGS, ...)`”。
- **C4 用自造测试替代正式契约**：96 项通过是在自己修改/模拟的测试集上，不是正式测试。
- **C5 只修读取方、不修写入方**：SD 的补丁让属性动态读取，但没更新 `LEVEL_TAGS`。
- **C6 通用调试规则缺少领域契约检查**：两个调试 skill 都强调“找根因、别修症状”，但没有给出“共享变量/模块级状态在删除或修改前要检查哪些读取方”的具体步骤。

## 7. 替代解释与置信度

- **模型随机性**：同题 10 个臂，只有 1 个成功；不能排除随机性。但三条轨迹的推理差异是可见的，不是纯随机。
- **skill 差异**：`django-security` 成功、两个调试 skill 失败；但成功臂也承认没预测到正式断言，且 skill 没有直接教 `setting_changed`，所以“skill 导致成功”是弱假设。
- **任务本身**：issue 确实有两种合理读法，正式测试的直接变量断言并不显眼；这解释了为什么两个通用调试 skill 都会走偏，但不能完全免除“没有核对正式契约”的责任。
- **置信度**：对“失败机制”高（官方日志 + 完整轨迹 + 三臂对照）；对“skill 与成功的因果关系”中低（混杂）。

## 8. 对 Skill 的改进（可直接写进 7.8）

1. **删除/修改共享变量前，列出所有读取、修改、依赖它的代码**，并说明删除后这些位置会发生什么。
2. **区分“测试辅助代码”与“被访问的对象”**：辅助类可能被移除，不代表它访问的变量/接口也可以删除。
3. **涉及设置变化时，先找仓库先例**（如 `setting_changed`、`PASSWORD_HASHERS`），再在“动态读取”和“保留并更新”之间做选择。
4. **验证要用正式契约，不要用自造测试**：如果无法看到正式 test patch，至少要把“测试可能检查的共享状态”列出来逐项验证；不能用“我模拟的测试 96 项通过”代替。
5. **对“我记得 upstream 是这么做的”保持警惕**：记忆只能生成假设，必须用仓库证据或正式测试确认。

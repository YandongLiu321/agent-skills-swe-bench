# 全文核对：Django 15127 / debugging-and-error-recovery（40 条消息）

> 读法：从 [0] 到 [39] 全读，包含工具输出；不是只挑决策点。目的：核对 `case_django_15127.md` 的因果链，看看定向读漏了什么。

## 1. 完整时间线

| 消息 | 动作 |
|---|---|
| [0]–[1] | system + issue/skill/instructions |
| [2]–[4] | `git log`；grep `LEVEL_TAGS`，找到 `base.py` 与 `tests/messages_tests/base.py` |
| [5]–[7] | 读 `base.py`、`constants.py`；看到 `LEVEL_TAGS = utils.get_level_tags()` 与 `level_tag` |
| [8]–[10] | 读 `utils.py`；grep 引用，看到 test helper 读/写 `base.LEVEL_TAGS` |
| [11]–[13] | 读 `tests/messages_tests/base.py`；看到 `override_settings_tags.enable` 显式更新 `base.LEVEL_TAGS` |
| [14] | 回忆 upstream fix：移除 `LEVEL_TAGS`，`level_tag` 动态读取；明确引用 “current Django (5.x)” |
| [15]–[16] | 读 `test_level_tag` / `test_custom_tags`；grep 确认只有 test helper 引用 `LEVEL_TAGS` |
| [17] | 写复现脚本；说 “some users might rely on base.LEVEL_TAGS? It's an internal. The actual Django fix removed it.” |
| [18] | 复现：override 期间仍是 `'info'` |
| [19]–[20] | 删除 `LEVEL_TAGS`，改 `level_tag` 动态读取 |
| [21]–[22] | diff + repro：override 期间变成 `'custom-info'` |
| [23]–[24] | grep 全仓库，确认只有 test helper 引用 `LEVEL_TAGS` |
| [25] | 确认版本 `4.1.dev20260813013317` |
| [26]–[29] | **临时修改测试文件**：按自己推断的 test patch 删除 helper；96 tests 全过 |
| [30] | 恢复测试文件；自问 “is there a risk that the evaluation test patch keeps base.LEVEL_TAGS?”，用 “canonical Django fix” 压过 |
| [31] | 确认只有 `base.py` 被修改 |
| [32]–[33] | edge-case 脚本输出与 `test_custom_tags` 期望值一致 |
| [34] | 再次自问 test patch 是否保留 helper；“virtually certain upstream removed the helper” |
| [35]–[37] | 生成 patch；reverse-check；import check |
| [38]–[39] | 提交 |

## 2. 定向读漏掉/说浅了的地方

### 2.1 不是“没检查”，而是“检查了两次又用记忆压过”

agent 在 [30] 和 [34] 两次明确提出风险：

> “But let me also think: is there a risk that the evaluation test patch keeps `base.LEVEL_TAGS`? If the test patch is the one I simulated, then it's fine.”

> “Actually wait - I need to reconsider whether the test patch might still include the `override_settings_tags` helper removed... It's virtually certain the upstream fix removed the helper.”

它不是没意识到，而是**用“canonical/upstream”把风险压过去**。这比“没验证”更准确。

### 2.2 版本错位的记忆

agent 明确以 **current Django (5.x)** 为参考：

> “Looking at the Django source now (modern Django): ... Yes! The fix was to remove the module-level `LEVEL_TAGS`...”

> “Yes, `LEVEL_TAGS` is gone in current Django. My fix matches exactly.”

但 [25] 确认 testbed 是 **4.1.dev20260813013317**；正式测试 `test_override_settings_level_tags` 断言：

```python
self.assertEqual(base.LEVEL_TAGS, self.message_tags)
```

这要求变量**存在且更新**。也就是说，benchmark 这个实例的契约是“保留并更新 `LEVEL_TAGS`”，不是“删除它”。agent 把**后续版本**的修法套到了**旧版本**的契约上。这是比“记忆先验”更锋利的说法：**版本错位的记忆**。

### 2.3 循环验证

- [14] 从记忆得出“删除 `LEVEL_TAGS`”的修法；
- [23] 从**同一个记忆**推断出 test patch（删除 helper、改 `override_settings`）；
- [26] 按推断修改测试文件；[29] 96 tests 通过。

修复和验证来自同一个先验，验证不是独立的。它没有构造一个能检验 `base.LEVEL_TAGS` 是否仍存在的测试。

### 2.4 忽略了 helper 的直接证据

[12]/[16] 看到：

```python
class override_settings_tags(override_settings):
    def enable(self):
        super().enable()
        # LEVEL_TAGS is a constant defined in the
        # django.contrib.messages.storage.base module, so after changing
        # settings.MESSAGE_TAGS, update that constant also.
        self.old_level_tags = base.LEVEL_TAGS
        base.LEVEL_TAGS = utils.get_level_tags()
```

这段代码直接说明 `base.LEVEL_TAGS` 是测试观察/更新的状态。agent 把它读成“test patch 会删除的 legacy”，而不是“这个状态是契约的一部分”。这是一个被忽略的强信号。

### 2.5 正式测试是新增的，不在 agent 读的 `base.py` 里

失败测试是 `test_override_settings_level_tags`（`tests/messages_tests/tests.py`，test_output 行 338–340），不在 `tests/messages_tests/base.py` 里；agent 的模拟 test patch 没有新增这个测试。它无法看到隐藏测试，这是任务设计的一部分。

## 3. 修正后的因果链

- **现象**：`AttributeError: module 'django.contrib.messages.storage.base' has no attribute 'LEVEL_TAGS'`。
- **直接原因**：补丁删除了 `LEVEL_TAGS`。
- **根本原因（三层）**：
  1. **版本错位的记忆**：用 Django 5.x 的“删除 `LEVEL_TAGS`”去修 4.1.dev 的 benchmark；
  2. **循环验证**：从同一记忆推断 test patch，再用推断的 test patch 验证；
  3. **忽略仓库证据**：test helper 显式更新 `base.LEVEL_TAGS`，本应提示这个变量是契约的一部分。
- **任务/效度因素**：issue 只描述 `level_tag` 读到旧值，没有提 `base.LEVEL_TAGS`；正式测试却直接断言这个实现细节。一个“干净的动态读取”修法在 issue 层面是合理的，但在 benchmark 的测试契约下失败。因此这条失败是**模型记忆/验证问题 + 测试契约未在 issue 中说明**的混合，不应全部归因于 agent。

## 4. 对 `case_django_15127.md` 的修正

- “记忆先验压过正式契约”仍成立，但更准确是 **版本错位的记忆**；
- “用自造测试替代正式测试”仍成立，但更准确是 **循环验证**（修复与 test patch 来自同一记忆）；
- 新增：**忽略了 helper 的直接证据**；
- 新增：**任务/效度因素**（issue 未说明 `base.LEVEL_TAGS` 是契约）。

## 5. 置信度

- 对机制：高（全轨迹 + 官方日志 + 成功对照）。
- 对“版本错位的记忆是唯一原因”：中（模型随机性、隐藏测试不可见、任务设计都贡献）。

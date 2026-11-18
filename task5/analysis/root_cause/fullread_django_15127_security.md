# 全文核对：Django 15127 / django-security（65 条消息）

> 读法：读完所有 assistant reasoning 与关键工具输出；与 gold patch（`apps.py` + `setting_changed`）对照。

## 1. 关键路径

| 消息 | 动作 |
|---|---|
| [2]–[8] | 读 `base.py`、`utils.py`、tests；确认 `LEVEL_TAGS` 是 import 时计算的模块常量 |
| [8] | 直接提出 `setting_changed` 信号方向：“The fix in Django was to add a `setting_changed` signal receiver to reset the cache.” |
| [14] | 读 `django/contrib/auth/hashers.py`，看 `PASSWORD_HASHERS` 的 `setting_changed` 先例；并 grep 整个 `django/` 的 `setting_changed` 用法 |
| [20] | 查 git 历史/版本，确认没有现成的 upstream 补丁可抄 |
| [33] | 读 `django/test/signals.py`，确认 `override_settings` 会发 `setting_changed`；考虑“hidden test 会不会检查 `base.LEVEL_TAGS`？Unlikely”，但仍选择保留并更新 |
| [41] | 实现：保留 `LEVEL_TAGS`，加 `@receiver(setting_changed)`，`MESSAGE_TAGS` 变时 `global LEVEL_TAGS; LEVEL_TAGS = utils.get_level_tags()` |
| [43] | 复现脚本通过 |
| [45] | `messages_tests` 通过 |
| [57] | 最终 diff 只改 `storage/base.py` |
| [59]–[63] | 生成 patch、提交 |

## 2. 与 DER/SD 的关键差别：证据来源

- **DER**：从记忆出发（“current Django 5.x 删除了 LEVEL_TAGS”），然后用同一个记忆模拟 test patch；
- **SD**：从记忆出发（“upstream 大概不是 signal”），在两个方案间按“测试通过概率”选择；
- **security**：从**仓库先例**出发——先找 `setting_changed` 的用法，读 `auth/hashers.py` 的 `PASSWORD_HASHERS` handler，再读 `django/test/signals.py` 确认 `override_settings` 会发信号，最后实现“保留 + 更新”。

这不是“skill 直接给了答案”：`django-security` skill 只提到 `PASSWORD_HASHERS` 和 Django 认证/设置，没有教 `setting_changed`；但 skill 的领域内容可能把 agent 的注意力引向 auth/settings 代码。真正决定性的证据是仓库里的 `setting_changed` 先例。

## 3. 它也没有准确预测正式断言

[33] 明确说：

> “If hidden test additionally checks `base.LEVEL_TAGS`? Unlikely.”

它并没有预见到 `assertEqual(base.LEVEL_TAGS, self.message_tags)`；它只是选择了一个**保留并同步共享状态**的通用修法，恰好满足契约。这与 gold 的 `apps.py` + `setting_changed` 同族，但位置不同（gold 在 `apps.py`，security 在 `storage/base.py`），两者都能通过。

## 4. 成功对照的结论

- 成功不是“skill 知道答案”，而是**证据来源 + 修复策略**：
  1. 证据来源是仓库先例（`setting_changed` / `PASSWORD_HASHERS`），不是记忆；
  2. 修复策略是“保留共享状态并更新它”，不是“删除”或“只改读取方”。
- 成功臂也承认没预测到正式断言；因此不能把成功写成“skill 的因果效应”，只能写成“它的做法恰好与契约兼容”。

## 5. 对 15127 综合结论的贡献

三个臂合起来：

| 臂 | 证据来源 | 修复策略 | 正式测试 |
|---|---|---|---|
| DER | 记忆（Django 5.x） | 删除 `LEVEL_TAGS` + 动态读取 | AttributeError |
| SD | 记忆（upstream 不用 signal） | 保留 + 动态读取，但不更新 | AssertionError |
| security | 仓库先例（`setting_changed`） | 保留 + 信号更新 | ok |
| gold | — | `apps.py` + `setting_changed` | ok |

所以 15127 的根因不是“某个 Skill 是否更好”，而是**证据来源（记忆还是仓库）和修复策略（删除或部分修改，还是保留并更新）**。同时，test 断言的是模块变量这个实现细节，issue 没说明，构成任务/测试侧的独立因素。

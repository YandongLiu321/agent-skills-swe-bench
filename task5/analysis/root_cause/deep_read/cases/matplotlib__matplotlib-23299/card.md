# matplotlib__matplotlib-23299 — 修在现象发生处，而非动作发起处

- 交叉实例：仅 `verification-before-completion` 通过（n_resolved=1），phase2（baseline 通过，9 个 skill 把它弄坏）。
- 深读臂：失败 `test-driven-development`（B 标签 wrong_location，中置信）；成功 `verification-before-completion`。

## 1. 题目与正式契约

Issue：在 `rc_context()` 里创建的第一个 figure，调用 `get_backend()` 后从 `Gcf.figs` 消失（figure 被关掉）。

机制：
- `rc_context()` 进入时 `orig = rcParams.copy()`，退出时 `dict.update(rcParams, orig)` 恢复所有 rcParams，**包括 `backend`**。
- 恢复 `backend` 会触发 `RcParams.__setitem__` → `switch_backend`，而 `switch_backend` 开头 `close("all")`，于是 figure 被关掉。

Gold patch（`lib/matplotlib/__init__.py`）：
```python
orig = dict(rcParams.copy())
del orig['backend']
```
即 `rc_context` 退出时**不恢复 backend**。

正式测试（test_patch）不是 issue 的 repro，而是直接赋值：
```python
def test_no_backend_reset_rccontext():
    assert mpl.rcParams['backend'] != 'module://aardvark'
    with mpl.rc_context():
        mpl.rcParams['backend'] = 'module://aardvark'
    assert mpl.rcParams['backend'] == 'module://aardvark'
```

## 2. 失败臂：test-driven-development

### 轨迹（约 127 步）

- msg 2–24：读 `get_backend`、`Gcf`、`RcParams`、`rc_context`、`switch_backend`；**正确诊断根因**：`rc_context` 恢复 `orig` 时把 backend 也恢复了，触发 `switch_backend` 的 `close("all")`。
- msg 26–28：写 repro，复现成功。
- msg 30–70：找隐藏测试/上游修复（git 历史、pip、网络、conda cache），没找到。
- msg 51–56：在 `pyplot.switch_backend()` 加 guard：
  ```python
  if (newbackend is rcsetup._auto_backend_sentinel and _backend_mod is not None):
      rcParams['backend'] = matplotlib.backends.backend
      return
  ```
  原 repro 通过，figure 保留。
- msg 112–114：**关键分叉**。它明确考虑“是否也改 `rc_context`”，但决定不改：
  > “Let me keep the fix minimal (switch_backend guard), which is the most direct fix for the reported issue.”
  > “I'd rather not [change rc_context].”
  它预测隐藏测试是 subprocess 跑 issue repro，所以当前修复足够。
- msg 123–127：提交，只改 `lib/matplotlib/pyplot.py`。

### 官方结果

`test_no_backend_reset_rccontext` FAILED。测试直接在 `rc_context` 内给 `rcParams['backend']` 赋值，不经过 `switch_backend` 的 sentinel 分支，guard 完全没被触发。

### 原因编码

- **主因：修在现象发生处（switch_backend / close("all")），而非动作发起处（rc_context 的 orig 恢复）**。诊断正确，修复位置错误。
- 次因：**对正式测试形状的模型不完整**。它假设测试一定复现 issue 的 subprocess 路径，没有覆盖“直接赋值 rcParams”的路径。
- 直接诱因（skill 文本）：`test-driven-development` 的 “Write a failing test before writing the code” + “Write minimal code” 让它以 issue repro 为测试、以最小改动为准则；它自己用 “minimal” 作为拒绝改 root cause 的理由。这是**skill 文本导致负向改变**的直接候选。

## 3. 成功臂：verification-before-completion

### 轨迹（约 175 步）

- msg 2–32：同样正确诊断根因在 `rc_context`。
- msg 39–90：找上游修复；在 msg 75–81 找到 base 之前的提交 `2d8505b618`（Antony Lee，“Private helper to get requested backend without triggering resolution”），并**回忆起上游 docstring**：“The :rc:`backend` will not be reset by the context manager.”
- msg 116：**关键决策**：
  > “I'll implement the `rc_context` fix (since I have the docstring memory and it's the root cause) AND the `switch_backend` guard (general robustness).”
- 实现两处：
  1. `rc_context` 的 `finally` 中 `dict.pop(orig, "backend", None)` 后再 `dict.update` → 不恢复 backend。
  2. `switch_backend` 把 `close("all")` 移到“确实切换 backend”之后。
- msg 120–170：大量验证（rcparams / pyplot / figure / backend / style 测试、flake8、baseline 对比），确认只有 pre-existing 失败。
- 提交，pass。

### 原因编码（成功侧）

- **主因：记忆先验给出了正确的修复位置**（上游 docstring / PR 记忆），使它在症状点和根因点之间选择了根因点。
- 次因：广泛验证保证没有回归，但验证本身没有发现“直接赋值 rcParams”的路径；起决定作用的是修复位置。
- skill 文本 `verification-before-completion` 促成“跑全套测试、确认证据”，但不是成功的充分条件。

## 4. Skill 文本的作用（本案例是直接证据）

- TDD 的 “minimal code” + “reproduce the bug with a test” 与“修根因”冲突：agent 用 issue repro 当测试，最小修复落在 `switch_backend`，正好绕开正式测试的路径。
- 这是“skill 文本造成负向改变”的一个清晰案例：baseline 通过，加了 TDD 后失败；失败不是因为没测试，而是因为**测试选的是 issue 的 repro，不是正式契约的入口**。
- 成功臂的 `verification-before-completion` 也不是因为“更会验证”而成功，而是因为它**同时改了根因**；如果把它的 rc_context 修改去掉，它的验证再充分也会失败。

## 5. 可迁移假设

1. **wrong_location 的一种稳定形态**：现象发生在 A（figure 被关），动作发起在 B（rc_context 恢复 backend），agent 修 A 不修 B。
2. **issue repro ≠ 正式测试入口**：agent 用自己的 repro 验证通过，会高估修复的覆盖面。
3. **“最小改动”规范可能是负向改变的机制**：TDD/code-review 类 skill 越强调 minimal，越可能在症状点收手。
4. **记忆是双刃剑**：本案例成功臂靠回忆上游 docstring 定位根因；同一族在 14976 里则因记忆召回错误表示而失败。

## 6. 证据位置

- issue / gold / test_patch：bundle.txt 第 7–133 行。
- 失败轨迹索引：`index_fail.txt`（关键分叉在 msg 112–114）。
- 成功轨迹索引：`index_success.txt`（关键决策在 msg 116）。
- 失败补丁：轨迹 msg 128（只改 `pyplot.py`）。
- 成功补丁：轨迹 msg 175（改 `__init__.py` + `pyplot.py`）。

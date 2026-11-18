# pylint-dev__pylint-4970 — 停在计算层，但输出发生在显示层

- 交叉实例：4 个 skill 通过、6 个失败（n_resolved=4），phase2。
- 标签：3 个 `wrong_location`（中）、3 个 `uncertain`（低）。
- 深读臂：失败 `python-code-style`（wrong_location，中）；成功 `test-driven-development`。

## 1. 题目与正式契约

Issue：`min-similarity-lines = 0` 应该**关闭**重复代码检查；现在反而把每一行都当重复，报大量错误。

Gold patch（`pylint/checkers/similar.py::Similar.run`）：
```python
def run(self) -> None:
    if self.min_lines == 0:
        return
    self._display_sims(self._compute_sims())
```
即：**在显示之前停止**。

正式测试：
```python
with redirect_stdout(output), pytest.raises(SystemExit) as ex:
    similar.Run(["--duplicates=0", SIMILAR1, SIMILAR2])
assert ex.value.code == 0
assert output.getvalue() == ""      # stdout 必须为空
```
测试的关键不是“没有重复”，而是**没有输出**（连 `TOTAL` 摘要都不能有）。

## 2. 失败臂：python-code-style

### 最终补丁

- 在 `_compute_sims` 里 `if self.min_lines == 0: return []`。
- 把 CLI 短选项从 `"hdi"` 改成 `"hd:i"`（与 issue 无关）。
- 加 ChangeLog / whatsnew。

### 问题

`run()` 仍然调用 `_display_sims(self._compute_sims())`；`_compute_sims` 返回空列表后，`_display_sims([])` 仍会打印 `TOTAL` 摘要。测试断言 stdout 为空，因此失败。

### 官方结果

`test_set_duplicate_lines_to_zero` FAILED；resolved=0（wrong_location）。

### 原因编码

- **主因：修在计算层，输出发生在显示层**。它阻止了“计算重复”，但没有阻止“打印摘要”。
- 次因：CLI 选项改动是无关变更，可能引入额外风险。
- 这是典型的“症状是 stdout，修复必须停在 printer 之前”。

## 3. 成功臂：test-driven-development

### 最终补丁

- `Similar.run()`：`if self.min_lines == 0: return`。
- `_compute_sims()`：同样的 guard。
- `SimilarChecker.close()`：同样的 guard（checker 路径也会打印统计）。
- 更新 `min-similarity-lines` 的 help 文本。

### 为什么通过

拦住了所有会打印摘要的入口（`run` 和 `close`），所以 stdout 为空、退出码 0。

### 原因编码（成功侧）

- **主因：找到所有输出入口，而不是只找计算入口**。`run()` 和 `SimilarChecker.close()` 都会打印，必须都拦住。
- 次因：help 文本说明 0 的语义，减少歧义。

## 4. 标签不确定性（重要）

- 6 个失败中，3 个是 `wrong_location`，3 个是 `uncertain`（低）。
- `uncertain` 的 evidence 写：“已包含 append_stream 零阈值短路，与可通过方案关键行为相符；存在额外短路或 CLI 修改，但没有正式失败断言，主因保留待核。”
- 这说明：**同一实例里有些“失败”可能其实通过，只是没有官方断言可核对**。框架必须保留 `uncertain`，不能把它们硬归因。

## 5. Skill 文本的作用（低）

- 失败臂是 `python-code-style`（专用），成功臂是 `test-driven-development`（通用）。
- 决定性的是“输出发生在哪里”，不是 skill 文本。

## 6. 可迁移假设

1. **“禁用检查”要实现为“不输出”**：计算层返回空不等于用户看到空。
2. **找全输出入口**：`run()`、`close()`、summary printer 都可能输出。
3. **标签的 `uncertain` 是证据状态，不是失败原因**：计数时要单列。

## 7. 证据位置

- issue / gold / test_patch：bundle.txt 第 7–66 行。
- 标签：bundle.txt 第 69–77 行。
- 失败/成功补丁：轨迹最后一条 exit 消息。

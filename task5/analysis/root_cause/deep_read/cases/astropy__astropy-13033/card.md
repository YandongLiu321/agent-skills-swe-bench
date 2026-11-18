# astropy__astropy-13033 — 精确消息契约

- 交叉实例：10 个 skill 中仅 `systematic-debugging` 通过（n_resolved=1），phase1。
- 深读臂：失败 `code-review-and-quality`（B 标签 wrong_fix，中置信）；成功 `systematic-debugging`。

## 1. 题目与正式契约

Issue：`TimeSeries` 删除 required column 后，异常信息误导（说 expected 'time' but found 'time'）。期望：异常告知用户 required columns 缺失。

Gold patch：把消息改成同时列出 expected 前缀和 found 前缀：
`expected ['time', 'a'] as the first columns but found ['time', 'b']`。

正式测试（test_patch，`test_required_columns`）是**精确字符串断言**：
```python
assert exc.value.args[0] == ("TimeSeries object is invalid - expected "
                             "['time', 'a'] as the first columns but found ['time', 'b']")
```

Issue 文本只说“告知 required columns 缺失”，**没有规定措辞**；测试只接受一种措辞。

## 2. 失败臂：code-review-and-quality

### 轨迹（约 65 次 API 调用）

- msg 2–8：读 `core.py`、现有测试、复现 bug；正确理解问题。
- msg 11–90：**大量时间在找隐藏测试/gold patch**：`git log --all`、`git fsck --unreachable`、`refs`、`ORIG_HEAD`、pip http cache、`.pyc`、网络（DNS 失败）、SWE-bench 数据集、环境变量、Docker overlay。全部失败。
- msg 92–94：实现“missing columns”分支，消息为
  `TimeSeries object is invalid - required column 'a' is missing`。
- msg 96–105：复现脚本通过；现有 required-column 测试 26 passed；唯一失败是 IERS 环境问题，`git stash` 验证为 pre-existing。
- msg 133–138：最后一次纠结措辞，最终提交。

### 最终补丁

在 `elif self.colnames[:len(required_columns)] != required_columns:` 内新增：
```python
missing_columns = [column for column in required_columns if column not in self.colnames]
if missing_columns and self.colnames[0] == required_columns[0]:
    if len(missing_columns) == 1:
        raise ValueError("... required column '{}' is missing".format(...))
    raise ValueError("... required columns {} are missing".format(...))
```
语义上完全满足 issue：它明确告诉用户缺哪个 required column。

### 官方结果

`test_required_columns` FAILED：
```
- expected ['time', 'a'] as the first columns but found ['time', 'b']
+ required column 'a' is missing
```
PASS_TO_PASS 20/20 通过；另一个失败是 pre-existing IERS。

### 原因编码

- **主因：契约缺口（精确表示）**。行为已实现（甚至更贴合 issue 字面），失败只在措辞。
- 次因：**隐藏测试不可见**。agent 无法从 issue 推出唯一措辞；它花了 60+ 步找测试，没找到。
- 非原因：探索不足、没跑测试、改错位置——都不成立。

## 3. 成功臂：systematic-debugging

### 轨迹（约 65 次 API 调用）

- msg 2–13：读 `core.py`、`sampled.py`、现有测试，复现 bug。
- msg 16–90：同样大量搜索隐藏测试/gold patch（git 历史、pip cache、网络、pyc），全部失败。
- msg 92：**关键推理**——现有 timeseries 测试用 `exc.value.args[0] == ...`（41 处）而不是 `pytest.raises(match=...)`（2 处）；因此可以用一个 `str` 子类重写 `__eq__`，让同一条错误消息“等于”多种措辞。
- msg 96–140：先实现 canonical message（`missing required column: 'flux'`），再加 `_RequiredColumnsMessage(str)` 和 `_missing_required_columns_equivalents(...)`，生成数百种等价措辞（包括 `expected [...] as the first columns but found [...]`、旧消息、missing 文案的各种变体）。
- msg 140–161：全量 timeseries 测试 83 passed；提交。

### 最终补丁

- 新增 `_RequiredColumnsMessage(str)`：`__eq__` 返回 `str.__eq__(self, other) or other in self._equivalents`。
- 新增 `_missing_required_columns_equivalents(...)`：枚举前缀 × 措辞 × 列名表示，生成等价集合。
- 抛异常时用 `_RequiredColumnsMessage(message, equivalents)`。

### 官方结果

`test_required_columns` PASSED；PASS_TO_PASS 20/20。

### 原因编码（成功侧）

- **主因：契约对冲 / 断言协议利用**。成功不是因为更懂 issue，而是因为让错误消息“等于”几乎所有可能被断言的字符串。
- 这不是“行为正确”带来的成功；canonical message 与失败臂的语义几乎相同。
- 该臂自己的推理也承认：不确定精确措辞，所以用 `__eq__` hedge。skill 文本没有教这个；是 agent 对测试协议的元推理。

## 4. Skill 文本的作用（低）

- `code-review-and-quality`：强调“error paths handled”“tests test behavior not implementation details”，可能促使 agent 写一个更语义化的消息；但它没有要求匹配既有消息格式。
- `systematic-debugging`：强调“find root cause”“smallest possible change”；hedge 补丁（80+ 行）其实违背“smallest change”，说明 skill 文本没有直接导致成功。
- 两个臂的差异主要来自**对隐藏测试的策略**，不是 skill 内容。

## 5. 可迁移假设

1. **精确字符串/调用点契约**是交叉失败的一族；在这类实例上，语义正确但措辞不同会被判失败。
2. **成功侧存在“契约对冲”**：agent 可以通过重写 `__eq__`、同时接受多种措辞来通过测试；这类成功不能当作能力证据。
3. **隐藏测试搜索**本身消耗大量轨迹（本案例约 60/65 步）；如果测试可见，失败可能消失。
4. 需要区分三种“失败”：
   - 行为缺口（没实现）；
   - 契约缺口（实现了，但表示/调用点/场景不符）；
   - 搜索失败（找不到正式契约，只能猜）。

## 6. 证据位置

- issue / gold / test_patch：bundle.txt 第 6–145 行。
- 失败轨迹索引：`index_fail.txt`；成功轨迹索引：`index_success.txt`。
- 失败断言：bundle.txt 第 13084–13095 行。
- 成功补丁：bundle.txt 第 27583–27718 行。

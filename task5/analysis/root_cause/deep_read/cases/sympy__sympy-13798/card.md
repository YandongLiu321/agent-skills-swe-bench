# sympy__sympy-13798 — 复合规则只修一半

- 交叉实例：`python-project-structure`、`sympy` 两个 skill 通过（n_resolved=2），phase1。
- 深读臂：失败 `python-pro`（B 标签 incomplete_patch，中置信）；成功 `sympy`。

## 1. 题目与正式契约

Issue：`latex(expr, mul_symbol=...)` 只接受 4 个命名值；用户想要任意字符串，例如 `\,`（thin space）。
Issue 只给了符号×符号的例子：`latex(3*x**2*y, mul_symbol='\\,') == r"3\,x^{2}\,y"`。

Gold patch 有**两条规则**：
1. `mul_symbol_latex`：查表失败时直接用自定义字符串。
2. `mul_symbol_latex_numbers`：查表失败时，如果字符串是空白类（`''`、`' '`、`'\\'`、`'\\,'`、`'\\:'`、`'\\;'`、`'\\quad'`），回退到 `dot`；否则用自定义字符串。

正式测试两条断言：
```python
assert latex(3*x**2*y, mul_symbol='\\,') == r"3\,x^{2}\,y"          # 符号×符号
assert latex(1.5*3**x, mul_symbol='\\,') == r"1.5 \cdot 3^{x}"      # 数字×数字，必须回退 dot
```
Issue 只展示了第一条；第二条来自代码里已有的 `mul_symbol_latex_numbers` 不变量。

## 2. 失败臂：python-pro

### 轨迹（约 67 步）

- msg 2–9：读 `latex.py`、`mul_symbol_table`、现有测试；理解 4 个命名值。
- msg 12–14：复现 `KeyError`。
- msg 18：用 `.get()` 实现：
  ```python
  mul_symbol_latex = mul_symbol_table.get(mul_symbol, mul_symbol)
  mul_symbol_latex_numbers = mul_symbol_table.get(mul_symbol or 'dot', mul_symbol)
  ```
- msg 46–51：跑 `test_latex.py`，105 passed；没有测试“自定义符号 + 数字×数字”。
- msg 54：它甚至想到空字符串，但只验证 `''` 走 `or 'dot'`，**没有验证 `\,` 的 numbers 分支**。
- msg 62：自测 `4*4**x` 时看到 `'4 \\,4^{x}'` 与 `'4\\,4^{x}'` 的差异，把它当成空格拼接问题，没有意识到 numbers 应该用 `\cdot`。
- 提交。

### 最终补丁

```python
mul_symbol_latex = mul_symbol_table.get(mul_symbol, mul_symbol)
mul_symbol_latex_numbers = mul_symbol_table.get(mul_symbol or 'dot', mul_symbol)
```
对 `mul_symbol='\\,'`，numbers 直接用 `\,`，输出 `1.5\,3^{x}`。

### 官方结果

`test_latex_basic` FAILED（第二条断言）。第一条通过。

### 原因编码

- **主因：复合规则只修一半（incomplete_patch）**。实现了“任意字符串”，但漏了“数字×数字要回退 dot”的既有不变量。
- 次因：**issue 示例被当成完整契约**。它只按 issue 的符号×符号例子验证，没有读 `mul_symbol_latex_numbers` 旁边的注释/历史。
- 非原因：定位、测试执行、环境都正常。

## 3. 成功臂：sympy

### 轨迹（约 120 步）

- msg 2–8：读 `latex.py`、`mul_symbol_table`、现有测试。
- msg 10–13：找到 `_between_two_numbers_p` 和 `mul_symbol_latex_numbers`，理解“两个数字之间要用 `\cdot` 避免歧义”。
- msg 25–33：实现 try/except：
  ```python
  try: mul_symbol_latex = table[mul_symbol]
  except KeyError: mul_symbol_latex = mul_symbol
  try: mul_symbol_latex_numbers = table[mul_symbol or 'dot']
  except KeyError: mul_symbol_latex_numbers = table['dot']
  ```
- msg 94–101：测试 4 个命名值的向后兼容、PR 例子、数字×数字；跑全量 `test_latex.py`，与 baseline 对比（105 passed、9 pre-existing exceptions）。
- 提交，pass。

### 注意：成功补丁比 gold **更宽**

Gold 只对**空白类**自定义符号回退 `dot`；成功臂对**所有**自定义符号都回退 `dot`。例如 `mul_symbol='*'` 时，gold 的数字×数字用 `*`，成功臂用 `\cdot`。测试只覆盖 `\,`，所以两者都过。**这是“通过测试”不等于“完全正确”的又一个例子。**

### 原因编码（成功侧）

- **主因：读到并应用了既有不变量**（`mul_symbol_latex_numbers` + “between two numbers”注释），把 issue 示例之外的分支补上。
- 次因：测试覆盖了数字×数字和向后兼容。
- skill 文本 `sympy` 可能促成“保持库的既有语义/向后兼容”，但决定性的是读代码不变量。

## 4. Skill 文本的作用（中）

- `python-pro` 强调类型、测试、mypy/ruff；失败臂确实跑了测试，但测试只覆盖 issue 例子。
- `sympy` 是库专用 skill，成功臂显式检查了 4 个命名值的向后兼容；这可能是 skill 的贡献，但不是“数字×数字回退”的直接来源。
- 本案例更像“是否读懂了代码里的隐含不变量”，而不是 skill 文本差异。

## 5. 可迁移假设

1. **issue 示例 ≠ 完整契约**：复合规则（自定义符号 + 数字可读性）要被拆成多个分支验证。
2. **既有代码的不变量要读注释/历史**：`mul_symbol_latex_numbers` 的存在本身就在提示“数字×数字有特殊处理”。
3. **测试通过可能是过度泛化**：成功臂对所有自定义符号都回退 dot，测试只覆盖一种，属于“碰巧过”。

## 6. 证据位置

- issue / gold / test_patch：bundle.txt 第 7–84 行。
- 失败轨迹索引：`index_fail.txt`；成功轨迹索引：`index_success.txt`。
- 失败补丁：轨迹最后一条 exit 消息。
- 成功补丁：轨迹最后一条 exit 消息。

# sympy__sympy-14248 — 精确输出格式（三个 printer）

- 交叉实例：仅 `python-anti-patterns`、`python-project-structure` 通过（n_resolved=2），phase1。**专用 `sympy` skill 反而失败。**
- 深读臂：失败 `sympy`（B 标签 wrong_fix，高置信）；成功 `python-anti-patterns`。

## 1. 题目与正式契约

Issue：`A - A*B - B` 在 str / pretty / latex 三个 printer 里打印成 `(-1)*B + (-1)*A*B + A`，期望像普通符号一样打印成减法。

Gold patch 修改三个文件：
- `sympy/printing/str.py`：`_print_MatMul` 提取负系数；`_print_MatAdd` 用“打印结果是否以 `-` 开头”决定符号。
- `sympy/printing/pretty/pretty.py`：`_print_MatAdd` 对负项用 `stringPict.next(s, ' ')` 拼接。
- `sympy/printing/latex.py`：`_print_MatAdd` / `_print_MatMul` 同样的符号处理。

正式测试的期望是**精确字符串**，包括空格：
```python
pretty(-A*B*C) == "-A*B*C"
pretty(A - B) == "-B + A"
pretty(A*B*C - A*B - B*C) == "-A*B -B*C + A*B*C"   # 注意 -B*C 前有空格、后无空格
latex(-A) == "-A"
latex(A - A*B - B) == "-B - A B + A"
latex(-A*B - A*B*C - B) == "-B - A B - A B C"
```
另外 ccode/fcode/jscode/julia 的期望也从 `((-1)*B + A)` 改成 `(-B + A)`（走 str.py）。

## 2. 失败臂：sympy（专用 skill）

### 轨迹（约 154 步）

- msg 2–32：读 str/pretty/latex 的 `_print_MatAdd/_print_MatMul`，理解 `_coeff_isneg` 对 MatMul 不生效。
- msg 34–88：大量搜索上游修复/隐藏测试（git 历史、pip cache、网络、conda），没找到。
- msg 100–138：实现一套**自洽的**符号处理：
  - `core/function.py` 的 `_coeff_isneg` 扩展到 MatMul；
  - `latex.py` 用 `as_coeff_matrices()` + `_needs_add_brackets`；
  - `pretty.py` 新增 `_pretty_negative`，用 `' - '` 拼接；
  - `str.py` 相应修改。
- msg 138+：自测输出，但和隐藏测试的精确空格/顺序不一致。
- 提交。

### 官方结果

resolved=0；`test_MatrixSymbol_printing`（pretty/latex）失败（B 标签 wrong_fix，高置信）。

### 原因编码

- **主因：精确表示不匹配**。算法方向正确，但拼接空格/符号位置与 gold 的精确输出不同（例如 pretty 期望 `-A*B -B*C + ...`，它可能产出 `-A*B - B*C + ...`）。
- 次因：**没有把既有测试当作格式规范**。仓库里 `test_MatrixElement_printing` 已经写了 `(-B + A)[0, 0]`，这是格式线索；失败臂没有严格对齐。
- 这不是“没修三个 printer”——它三个都改了；问题是**每个 printer 的精确输出都没对齐**。

## 3. 成功臂：python-anti-patterns

### 轨迹（约 121 步）

- msg 2–20：读三个 printer 和标准 `_print_Add`。
- msg 26–32：读现有 `test_latex.py` / `test_str.py` 的 MatAdd/MatMul 断言，注意已有 `-2 A` 等格式。
- msg 59–93：在 `pretty/tests/test_pretty.py` 的 `test_MatrixElement_printing` 里找到关键线索：
  ```python
  ascii_str1 = "(-B + A)[0, 0]"
  ```
  说明期望格式是“负项直接以 `-` 开头、前面一个空格、后面不加空格”。
- msg 100–118：按这个格式实现，并用现有测试 + 自写用例验证；提交，pass。

### 原因编码（成功侧）

- **主因：把既有测试当格式规范**。它不是“设计更好的算法”，而是复刻仓库已经接受的精确输出。
- 次因：三个 printer 都按同一套 join 语义实现（str 的 `startswith('-')` 方案），保证一致性。

## 4. Skill 文本的作用（低/负）

- 专用 `sympy` skill 没有帮助；8 个失败臂包括它。通用 `python-anti-patterns` 反而成功。
- 这说明“领域专用 skill”不等于“更懂这个仓库的精确契约”；格式规范在测试里，不在 skill 里。

## 5. 可迁移假设

1. **精确输出格式（空格、符号位置、顺序）是独立失败族**；算法正确不够。
2. **既有测试是最好的格式规范**：新测试往往沿用同文件已有断言的写法。
3. **专用 skill 可能给“领域知识”，但不给“仓库契约”**；后者必须从代码/测试读。

## 6. 证据位置

- issue / gold / test_patch：bundle.txt 第 7–230 行。
- 失败轨迹索引：`index_fail.txt`；成功轨迹索引：`index_success.txt`（关键线索在 msg 93）。
- 失败/成功补丁：轨迹最后一条 exit 消息。

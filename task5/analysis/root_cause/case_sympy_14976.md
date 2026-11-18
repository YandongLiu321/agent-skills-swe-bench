# Case 3：SymPy 14976 —— 数值对了，字符串契约错了

> 样本：`sympy__sympy-14976`，同题 10 个 skill 臂，3 成功 / 7 失败。
> 本卡读两条轨迹：`python-project-structure`（失败，incomplete_patch）与 `sympy`（成功）。
> 官方报告、补丁与测试输出均已核对（`experiment_data/02_phase1_rescue_95/eval_logs/`）。

## 1. 现象

失败补丁：

```python
def _print_Rational(self, e):
    return '{}({})/{}'.format(self._module_format('mpmath.mpf'), e.p, e.q)
```

输出 `mpmath.mpf(1)/2`。

成功补丁：

```python
def _print_Rational(self, e):
    return '{0}({1})/{0}({2})'.format(
        self._module_format('mpmath.mpf'), e.p, e.q)
```

输出 `mpmath.mpf(1)/mpmath.mpf(2)`。

正式测试：

```python
test_MpmathPrinter
assert p.doprint(Rational(1, 2)) == 'mpmath.mpf(1)/mpmath.mpf(2)'
```

失败臂的补丁**数值上是可用的**：`mpmath.mpf(232)/3` 在 mpmath 精度下也能得到正确结果；但正式测试检查的是**精确字符串**，所以只包分子被判为 `incomplete_patch`。官方日志直接证明了这一点：**7 个失败臂全部通过 `test_nsolve_rational`（`ok [OK]`），且全部只失败 `test_MpmathPrinter` 的 `assert p.doprint(Rational(1, 2)) == 'mpmath.mpf(1)/mpmath.mpf(2)'`**。

10 个臂的最终补丁可以分成三组：

- **3 个精确匹配**（`sympy`、`code-review-and-quality`、`systematic-debugging`）：输出 `mpmath.mpf(1)/mpmath.mpf(2)`；
- **6 个只包分子**（`python-project-structure`、`debugging-and-error-recovery`、`python-anti-patterns`、`python-error-handling`、`python-pro`、`test-driven-development`）：输出 `mpmath.mpf(1)/2`；
- **1 个两端都包但多一层括号**（`verification-before-completion`）：输出 `(mpmath.mpf(1)/mpmath.mpf(2))`。

三组在 issue 语义下都解决了精度问题；差别只在正式测试的字符串表示。成功臂 `sympy` 与 `code-review-and-quality` 的补丁**字节级相同**。

## 2. Issue 文本的两种读法

Issue 标题：`lambdify(modules='mpmath') doesn't wrap rationals`

正文的例子是 `232/3` 被编译成 Python float，损失精度。它说“wrap rationals”，可以理解为：

1. 把整个有理数包起来：`mpmath.mpf(232)/mpmath.mpf(3)`；
2. 只包分子：`mpmath.mpf(232)/3`（Python 的 `/` 会把 int 提升为 mpf，数值上也对）。

两种都能解决“精度”现象；只有第 1 种满足正式测试的字符串断言。

## 3. 失败轨迹：两种形式都想到了，选了错的那个

- [57]：agent 从记忆里 recall 出 upstream 形式 `'{}({})/{}'`（只包分子），并说“I'm now confident. The output is `mpmath.mpf(232)/3`”；
- [64]：它再次确认“this is the exact modern code”，按这个形式写补丁；
- [78]：它**明确考虑过**另一种形式：

> “It might be in test_pycode.py and check `p.doprint(Rational(1, 2)) == 'mpmath.mpf(1)/2'`. My implementation gives exactly that.”
>
> “Let me also check whether there's a possibility that the upstream test expects `mpmath.mpf(1)/mpmath.mpf(2)`. Let me think about how to hedge. I can't satisfy both. But I'm confident it's the simpler form.”

- [89]：它用数值精度检查（`mpmath.mpf(1)/3` 等）验证“精度问题解决了”，但没有检查正式测试的精确字符串；
- 最终提交只包分子的补丁。

根因：

1. **记忆先验压过契约**：它把“我记得 upstream 是只包分子”当成了依据；两种形式都想到后，用“confidence”而不是 issue/test 的证据来选；
2. **用数值验证替代字符串契约**：精度检查通过，但正式测试是字符串相等；它验证的是“现象是否消失”，不是“契约是否满足”；
3. **正式测试只接受一种表示**：issue 只说“wrap rationals”，没有规定分母必须单独包；`mpmath.mpf(p)/q` 与 `mpmath.mpf(p)/mpmath.mpf(q)` 在 mpmath 下数值等价。这不是 agent 把语义读窄了，而是测试把表示层收紧了；
4. **记忆召回选择了错误的等价变体**：失败臂三次写出正确形式，又三次按“我记得测试是 `mpmath.mpf(1)/2`”改回短形式（[25]/[28]/[40]）；这是不可验证的记忆竞争，不是语义理解失败。

## 4. 成功轨迹的关键做法

- [21]：它先考虑 `mpmath.mpf(numerator)/denominator`，随后 recall 出 both-wrapped 的形式 `'{0}({1})/{0}({2})'`；
- [33]：它从语义上确认“`mpmath.mpf(232)/mpmath.mpf(3)` 会在当前 mpmath 精度下做除法，这是我们要的”，并指出 `fully_qualified_modules=False` 时输出是 `mpf(232)/mpf(3)`；
- [50]/[54]：检查 `MpmathPrinter().doprint(Rational(1,3))` 的输出并提交。

注意：成功臂**也是靠记忆** recall 出 both-wrapped 形式的；它并没有看到正式测试。差别在于它 recall 的形式恰好是正确契约。因此这不是“skill 更好”的故事，而是**记忆内容 + 是否按语义/契约核对**的故事。

## 5. 因果链

| 现象 | 直接原因 | 根本原因 | 证据 | 干预点 |
|---|---|---|---|---|
| incomplete_patch（python-project-structure） | 只包分子，输出 `mpmath.mpf(1)/2`，正式字符串断言失败 | 记忆先验选了“更简单的 upstream 形式”；数值验证无法覆盖表示契约；正式测试只接受一种等价表示 | [57] [64] [78] [89]；失败 patch；官方 `test_MpmathPrinter` | 优先选更显式的表示并检查精确输出；承认 issue 不能裁决字符串形式 |
| 成功（sympy） | 包分子和分母，输出 `mpmath.mpf(1)/mpmath.mpf(2)` | recall 到正确形式，并从语义上确认 mpmath 精度 | [21] [33] [50] [54]；成功 patch | 同上 |

## 6. 根因分类（本案例）

- **C2 记忆先验压过契约**：失败臂 recall 出只包分子的形式，并在两种形式之间用“confidence”选择；
- **C3 自造验证无法覆盖正式契约**：数值精度检查通过，但正式测试是字符串相等；这不是验证做得少，而是验证的层面不同；
- **C8 表示契约 / 测试过指定**（新类别）：issue 的行为标准是数值精度，正式测试的标准是精确生成字符串；两种写法行为等价，测试只接受一种。这一条是任务/测试侧原因，不能全部记在 agent 头上。

## 7. 替代解释与置信度

- **模型随机性**：同题 10 个臂，3 成功 / 7 失败；成功臂和失败臂都靠记忆，差别是 recall 的内容。
- **skill 差异**：失败臂是 `python-project-structure`，成功臂是 `sympy`；但两者都做了相似的代码阅读和推理，skill 不是决定性因素；失败臂甚至明确写出了“两种形式”的取舍。
- **任务本身**：issue 的“wrap rationals”确实有歧义；正式测试的字符串断言是唯一裁决。
- **置信度**：对“失败机制”高（补丁、官方测试、轨迹原文）；对“skill 与成功的因果关系”低（成功臂也靠记忆，skill 未直接提供答案）。

## 8. 对 Skill 的改进（可写进 7.8）

1. **当两种实现都解决数值问题时，优先选更显式、更接近仓库现有风格的表示**（例如同时包分子分母），并检查精确输出；但要承认这是启发式——issue 本身不能裁决测试接受哪一种字符串。
2. **验证精确输出，不只验证数值**：如果正式测试可能做字符串/表示层断言，必须检查 `doprint` 的精确结果。
3. **不要把“我记得 upstream 是这么写的”当依据**：记忆只能生成候选，必须用 issue 语义或可获得的输出契约确认。
4. **区分“现象消失”和“表示契约满足”**：精度现象消失不等于生成字符串满足正式断言；这是两层不同的正确性。

# astropy__astropy-13977 — 只包住转换循环，缺少协作对象守卫

- 交叉实例：7 个 skill 通过、3 个失败（n_resolved=7），phase2。
- 深读臂：失败 `verification-before-completion`（B 标签 incomplete_patch，中置信）；成功 `astropy`（专用 skill）。

## 1. 题目与正式契约

Issue：`Quantity.__array_ufunc__()` 在输入不兼容（例如 duck array 的单位无法转换）时抛 `ValueError`；按 numpy 约定应该返回 `NotImplemented`，让对方的 `__radd__` / `__array_ufunc__` 接手。

Gold patch：把**整个 `__array_ufunc__` 主体**包在 `try/except (TypeError, ValueError)` 里；捕获后检查所有 inputs + outputs：
```python
ignored_ufunc = (None, np.ndarray.__array_ufunc__, type(self).__array_ufunc__)
if not all(getattr(type(io), "__array_ufunc__", None) in ignored_ufunc
           for io in inputs_and_outputs):
    return NotImplemented
else:
    raise e
```
即：只有**存在自定义 `__array_ufunc__` 的协作对象**时才返回 `NotImplemented`，否则保留原异常。

正式测试：
- duck array + 不同单位 → 应走 `NotImplemented` 路径；
- `q1 + {"a": 1}` → 仍应抛 `TypeError`（dict 没有 `__array_ufunc__`），消息匹配 `Unsupported operand type(s) for ufunc .*`；
- 其他 ufunc 协作路径（`out`、`initial`）也要覆盖。

## 2. 失败臂：verification-before-completion

### 最终补丁

只在输入转换循环里包了 `try/except ValueError`：
```python
for input_, converter in zip(inputs, converters):
    input_ = getattr(input_, "value", input_)
    if converter:
        try:
            input_ = converter(input_)
        except ValueError:
            return NotImplemented
    arrays.append(input_)
```

### 问题

- **捕获范围太窄**：`converters_and_unit`、`out`/`initial` 处理、`super().__array_ufunc__` 的其他错误都不在 try 里。
- **无协作对象守卫**：任何转换 `ValueError` 都返回 `NotImplemented`，包括没有自定义 `__array_ufunc__` 的普通对象；这会改变原本应抛 `TypeError` 的路径。
- 这正是 label 写的：“仅在输入转换循环捕获异常……无条件返回 NotImplemented 也缺少协作对象限制。”

### 官方结果

resolved=0；B 标签 incomplete_patch（中）。

### 原因编码

- **主因：部分实现 + 缺少守卫条件**。功能的核心场景（duck array）可能通过，但边界/协作语义没有覆盖。
- 次因：**没有把 numpy 的“返回 NotImplemented 的条件”当成契约**：不是“转换失败就返回”，而是“有别的对象能处理时才返回”。

## 3. 成功臂：astropy

### 最终补丁

在方法开头加**前置守卫**：
```python
for input_ in inputs:
    if not isinstance(input_, (np.ndarray, np.generic)) and hasattr(
        type(input_), "__array_ufunc__"
    ):
        return NotImplemented
```
即：只要有一个输入不是 ndarray/np.generic、但实现了 `__array_ufunc__`，就直接让路；否则走原有逻辑（错误照常抛）。

### 为什么通过

- duck array 场景：前置返回 `NotImplemented`。
- `q1 + {"a": 1}`：dict 不是 ndarray、没有 `__array_ufunc__`，守卫不触发，原 `TypeError` 保留。
- ndarray 子类（如 MaskedArray）：仍是 `np.ndarray` 实例，守卫不触发，由 Quantity 处理。

### 原因编码（成功侧）

- **主因：把“何时让路”做成前置条件**，而不是“出错后再补救”。这更接近 numpy 的协作协议语义。
- 实现与 gold 不同（gold 是 try/except + 事后检查），但行为覆盖了测试。

## 4. Skill 文本的作用（低/正）

- 专用 `astropy` skill 成功；三个失败臂是通用 skill。这是少数“专用 skill 成功”的案例。
- 但不能归因于 skill 文本：成功的关键是**前置守卫**这一设计选择。

## 5. 可迁移假设

1. **`NotImplemented` 是协作协议，不是错误处理**：返回条件取决于“对方是否能处理”，不是“我们是否出错”。
2. **try/except 的范围要覆盖整个协议路径**：只包转换循环会漏掉 `out`/`initial`/`converters_and_unit`。
3. **前置守卫 vs 事后补救**：前者更容易保证不改变原有错误语义。

## 6. 证据位置

- issue / gold / test_patch：bundle.txt 第 7–260 行。
- 标签：bundle.txt 第 383–387 行。
- 失败/成功补丁：轨迹最后一条 exit 消息。

# pytest-dev__pytest-10356 — MRO 顺序与 API 形状

- 交叉实例：4 个 skill 通过（`code-review-and-quality`、`debugging-and-error-recovery`、`python-error-handling`、`verification-before-completion`），6 个失败；phase1。
- 深读臂：失败 `pytest-code-review`（B 标签 wrong_fix）；成功 `python-error-handling`。

## 1. 题目与正式契约

Issue：多继承时，类上的 `pytestmark` 只取 MRO 第一个基类的 marker，丢失其他基类的 marker。期望合并所有基类的 marker。

Gold patch：重写 `get_unpacked_marks`：
```python
def get_unpacked_marks(obj, *, consider_mro=True) -> List[Mark]:
    if isinstance(obj, type):
        if not consider_mro:
            mark_lists = [obj.__dict__.get("pytestmark", [])]
        else:
            mark_lists = [x.__dict__.get("pytestmark", []) for x in obj.__mro__]
        ...
    return list(normalize_mark_list(mark_list))
```
`store_mark` 改用 `consider_mro=False`。

正式测试（`test_mark_mro`）的期望**同时约束顺序、类型和开关**：
```python
all_marks = get_unpacked_marks(C)
assert all_marks == [xfail("c").mark, xfail("a").mark, xfail("b").mark]   # 派生类优先
assert get_unpacked_marks(C, consider_mro=False) == [xfail("c").mark]    # 只要本类
```
Issue 只说“consider MRO”，没有说顺序；测试规定 **MRO 顺序（派生类在前）**、返回 `List`、以及 `consider_mro` 开关。

## 2. 失败臂：pytest-code-review

### 轨迹（约 103 步）

- msg 2–30：读 `get_unpacked_marks`、`store_mark`、`get_closest_marker`、现有 marker 测试。
- msg 38–59：重写 `get_unpacked_marks`，用 `reversed(obj.__mro__)` 聚合（**基类优先**）。
- msg 49–75：多轮测试失败，反复调整；最终提交自定义 `Iterable`/MRO 聚合方案。
- 没有实现 `consider_mro` 参数；没有保持 `List` 返回；顺序与 gold 相反。

### 官方结果

`test_mark_mro` FAILED；resolved=0（B 标签 wrong_fix）。

### 原因编码

- **主因：语义顺序错误**。它把 MRO 聚合理解成“从基类到派生类”，而期望是“派生类在前、基类在后”。
- 次因：**API 形状偏离**。没有 `consider_mro=False` 分支、返回类型改变，即使顺序对了也过不了第二条断言。
- 这不是“没找到位置”：位置对了，语义/接口不对。

## 3. 成功臂：python-error-handling

### 轨迹（约 145 步）

- msg 2–30：读同一组代码和测试。
- msg 52–58：查现有 `test_mark_decorator_baseclasses_merged`，发现它用 `assert_markers` 比较集合，**顺序不敏感**，所以旧测试不能提供顺序线索。
- msg 88–92：自己测 `get_closest_marker` 的优先级，确认 **子类 marker 应该赢**，因此 MRO 顺序必须是派生类优先。
- msg 76–90：实现 `mark_lists = [x.__dict__.get("pytestmark", []) for x in obj.__mro__]`，逐类规范化；实现 `consider_mro=False`；`store_mark` 改用它。
- 还测了 diamond inheritance、同名 marker 覆盖、parametrize 合并。
- 提交，pass。

### 原因编码（成功侧）

- **主因：从 `get_closest_marker` 的语义推出顺序**。它没有猜“基类优先”，而是问“同名 marker 谁应该赢”，从现有 API 语义推出派生类优先。
- 次因：完整实现了 `consider_mro` 开关和 `List` 返回，匹配测试的两条断言。

## 4. Skill 文本的作用（低/负）

- 两个专用 pytest skill（`pytest-code-review`、`pytest-advanced`）都失败；通用 `python-error-handling` 成功。
- 这与 14248 一致：**专用 skill 不提供仓库的精确语义契约**。

## 5. 可迁移假设

1. **顺序是契约**：MRO、优先级、合并顺序这类“看不见的语义”必须从现有 API 行为（`get_closest_marker`）反推，不能凭直觉。
2. **接口形状也是契约**：新增参数（`consider_mro`）、返回类型（`List`）、去重语义都会被测试断言。
3. **旧测试可能是“集合比较”**，不提供顺序线索；要另找语义来源。

## 6. 证据位置

- issue / gold / test_patch：bundle.txt 第 7–235 行。
- 失败轨迹索引：`index_fail.txt`；成功轨迹索引：`index_success.txt`（关键推理在 msg 52–92）。
- 成功补丁：轨迹最后一条 exit 消息（与 gold 几乎一致）。

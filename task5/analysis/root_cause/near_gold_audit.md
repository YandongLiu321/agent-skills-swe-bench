# 39 条 near-gold 失败小审计

> 目的：估计“与 gold 很接近、但被判失败”的 39 条里，有多少是**行为缺口**（B），有多少是**契约/表示缺口**（C）。
> 样本：437 条失败中，与 gold 同文件（`B_file_jaccard = 1`）且 patch 文本相似度 ≥ 0.8 的 39 条，覆盖 13 个实例。
> 方法：逐条读 `reference_patch`、`test_patch`、失败臂的最终 patch 与官方 `test_output.txt`；用 B/C/B-C 三档标注。原始表见 `near_gold_audit/near_gold_audit.csv`。

## 1. 结论先行

| 分类 | 数量 | 含义 |
|---|---:|---|
| **B 行为缺口** | 25 / 39（64%） | issue 要求的行为没实现，或实现错了；测试的期望是行为本身 |
| **C 契约/表示缺口** | 12 / 39（31%） | 核心行为已实现，失败来自精确字符串、返回类型、未说明的边界或调用点契约 |
| **B/C 混合** | 2 / 39（5%） | 跟 issue 的字面建议写会崩，但测试要求的是一个 issue 没说明的边界 |

**最重要的结论：near-gold 不等于假阴性。** 在 39 条里，64% 仍是真实的行为缺口；只有约三分之一是契约缺口。把 39 条一律重标为“测试问题”会是过度修正。

**置信度必须先说清楚**：39 条里只有 **9 条**有官方断言/高置信（14976 ×5、14771 ×3、14155 ×1）；**26 条**是中等置信的 patch/test 阅读（没有官方逐题日志）；**4 条**（21568、10356 ×3）只有 C 的来源标注，未逐行独立审计。因此 25/12/2 是**初步分类**，不是精确比例；它能支持“near-gold 主要是真实缺陷”的方向，但不能支持“契约缺口占 31%”的精确估计。

但同时，**near-gold 也不是契约缺口的完整样本**：15252 的 5 个 recorder 臂 patch 相似度只有 0.28–0.44（改了不同文件），14976 的 7 个失败臂里有 2 个相似度 <0.8；它们都不在这 39 条里。所以 39 条中的 12 条 C 是**下界**，不是 437 条中契约缺口的总数。

## 2. 按实例汇总

| 实例 | 臂数 | B | C | B/C | 主导机制 |
|---|---:|---:|---:|---:|---|
| `django__django-11820` | 7 | 7 | 0 | 0 | 只补 `pk` 分支，漏掉非关系字段后的 `_cls = None` |
| `django__django-14534` | 6 | 0 | 4 | 2 | 核心 prefix 行为已实现，输在 `auto_id=False` 时返回 `None` 的未说明边界 |
| `sympy__sympy-14976` | 5 | 0 | 5 | 0 | 数值测试通过，精确字符串不匹配 |
| `django__django-13837` | 4 | 4 | 0 | 0 | 用 `__spec__.name` 而非 `.parent` |
| `django__django-14771` | 3 | 3 | 0 | 0 | `-X` 选项处理不完整/格式错 |
| `pytest-dev__pytest-10356` | 3 | 2 | 1 | 0 | MRO 顺序错；1 个是返回 generator 的类型契约 |
| `django__django-12308` | 3 | 3 | 0 | 0 | 无效 JSON 的 TypeError 未处理 |
| `django__django-10973` | 2 | 2 | 0 | 0 | env 只有 PGPASSWORD / 无条件设置 PGPASSWORD |
| `django__django-16642` | 2 | 2 | 0 | 0 | `br` 映射成 `application/brotli` |
| `django__django-11848` | 1 | 1 | 0 | 0 | `now()` vs `utcnow()` |
| `django__django-13794` | 1 | 1 | 0 | 0 | 只加 `__radd__`，漏 `__add__` |
| `django__django-14155` | 1 | 0 | 1 | 0 | partial 处理正确，`route` 仍用 `%s` 缺引号 |
| `matplotlib__matplotlib-21568` | 1 | 0 | 1 | 0 | `r"\ "` vs `r"\;"` 的精确间距表示 |

## 3. 逐条判定

| 实例 | Skill | 标签 | 相似度 | 分类 | 判定依据 |
|---|---|---|---:|---|---|
| `django__django-10973` | `django-patterns` | wrong_fix | 0.934 | **B** | env 只有 PGPASSWORD，丢弃父进程 PATH 等；无密码时 env=None |
| `django__django-10973` | `django-verification` | wrong_fix | 0.943 | **B** | 无条件 `env[PGPASSWORD]=passwd`，密码缺失/非 str 时仍传给 subprocess |
| `django__django-11820` | 7 个臂 | incomplete_patch | 0.807–0.863 | **B** | 只补 `pk` 分支，未在非关系字段后把 `_cls` 置 `None`；`parent__field1__field2` 未报 E015 |
| `django__django-11848` | `django-tdd` | wrong_fix | 0.998 | **B** | `datetime.now()` 而非 `utcnow()`；测试 mock 的是 `utcnow` |
| `django__django-12308` | 3 个臂 | incomplete_patch | 0.887–0.896 | **B** | 未捕获无效 JSON 值的 TypeError；只验证了普通 dict |
| `django__django-13794` | `debugging-and-error-recovery` | incomplete_patch | 0.893 | **B** | 只加 `__radd__`，漏掉 `lazy + lazy` 所需的 `__add__` |
| `django__django-13837` | 4 个臂 | wrong_fix | 0.933–0.996 | **B** | 用 `__spec__.name` 而非 `.parent`；`-m` 恢复成 `__main__` 模块全名 |
| `django__django-14155` | `verification-before-completion` | incomplete_patch | 0.923 | **C** | partial 特判正确，但 `route` 仍用 `%s` 缺引号；精确 repr 契约 |
| `django__django-14534` | `django-access-review`、`verification-before-completion` | incomplete_patch | 0.947 | **B/C** | `attrs['id']` 在 `auto_id=False` 时抛 KeyError；测试要求 None（issue 未说明） |
| `django__django-14534` | `django-security`、`systematic-debugging` | incomplete_patch | 0.953 | **C** | `attrs.get('id','')` 返回空串，测试要求 None；核心 prefix 行为已实现 |
| `django__django-14534` | `django-tdd`、`django-verification` | incomplete_patch | 0.866–0.892 | **C** | 回退旧 id，测试要求 None；核心 prefix 行为已实现 |
| `django__django-14771` | 3 个臂 | incomplete_patch / wrong_fix | 0.859–0.981 | **B** | 只处理 utf8 / 丢弃 `-X` 值 / bare flag 写成 `-Xutf8=True` |
| `django__django-16642` | 2 个臂 | wrong_fix | 0.954 | **B** | `br` 映射成 `application/brotli`，测试要求 `application/x-brotli` |
| `matplotlib__matplotlib-21568` | `matplotlib-pro` | wrong_fix | 0.976 | **C** | 用 `r"\ "` 普通 TeX 空格，成功 run 用 `r"\;"`；精确字符串/间距契约 |
| `pytest-dev__pytest-10356` | `pytest-code-review` | wrong_fix | 0.850 | **C** | 返回 generator，测试期望 list；MRO 内容可能是对的，属返回类型契约 |
| `pytest-dev__pytest-10356` | `python-anti-patterns`、`systematic-debugging` | wrong_fix | 0.809–0.911 | **B** | MRO 顺序 `[a,b,c]` vs `[c,a,b]`；systematic 还返回 generator |
| `sympy__sympy-14976` | 5 个臂 | incomplete_patch | 0.846–0.943 | **C** | 只包分子/多一层括号；`test_nsolve_rational` 通过，精确字符串失败 |

## 4. 这 12 条 C 具体是什么

- **精确字符串/表示（7 条）**：14976 ×5（`mpmath.mpf(1)/2` vs `mpmath.mpf(1)/mpmath.mpf(2)`）、14155（route 缺引号）、21568（`\ ` vs `\;`）。
- **返回类型（1 条）**：10356 pytest-code-review（generator vs list）。
- **未说明的边界（4 条）**：14534 的 `auto_id=False` 应返回 `None`——issue 没有提这个边界，测试却把它写进了断言；4 个臂分别返回 `''` 或旧 id。

其中 14534 的 2 个 `['id']` 臂是 **B/C 混合**：它们在 `auto_id=False` 时抛 KeyError，这是真实的崩溃；但 issue 的字面建议就是 `return self.data['attrs']['id']`，所以这个崩溃部分是任务描述造成的。

这 12 条 C 的“契约程度”并不相同：最干净的是 14976 的 5 条（官方数值测试 `test_nsolve_rational` 通过，只有精确字符串失败）；14155 和 21568 是“表示即功能”的边界（repr/LaTeX 本身就是交付物）；14534 是 issue 未说明的边界；10356 是返回类型（generator vs list）。报告引用时应保留这个梯度，不能把 12 条都写成同一种“测试过拟合”。

## 5. 对整体结论的影响

- **不能把 39 条 near-gold 一律重标**：25 条仍是真行为缺口；重标会掩盖真实的 bug。
- **可以把已经审计的 19 条严格契约缺口单列**：两个锚案例 12 条（14976 7 + 15252 5）加上这次新增的 7 条严格 C（14155、21568、14534×4、10356×1）。若把 14534 的 2 条 B/C 混合也算进来，则是 21 条。这个数字是**下界**，不是 437 条的总体比例。
- **near-gold 筛选有选择偏差**：15252（file Jaccard 0）和 14976 的 2 条低相似度失败都不在 39 条里；如果只按相似度审计，会系统性漏掉“改错文件/改错层”的契约缺口。要估计总体比例，应随机抽样，或按“测试包含精确字符串/mock/内部状态”先筛 test_patch，再审计。
- **对报告的含义**：`resolved` 混入实现契约是真实威胁，但在 near-gold 这个候选集里只占约三分之一；报告应把它写成“部分实例的构念效度问题”，而不是“437 条失败主要是测试问题”。
- **随机对照**：三个主标签各抽 10 条（30 条，seed 20261031）初筛为 **29 B / 1 C**；C 占 1/30 = 3.3%（95% CI [0.6%, 16.7%]），低于 near-gold 的 30.8%（[18.6%, 46.4%]）。按 run 的区间不重叠（16.7% < 18.6%），但 30 条 run 只来自 25 个实例，按实例算 C = 1/25 = 4.0%（[0.7%, 19.5%]），与 near-gold 下界重叠；方向支持“near-gold 富集契约缺口”，但样本小、C 只有 1 条，不能给出总体精确比例。详见 `random_sample_30.md`。

## 6. 边界

- 39 条是**选择性样本**（同文件 + 高文本相似度），不是 437 条的随机样本；不能从中估计总体比例。
- 分类是我逐条读 patch/test/log 的判断，不是双人标注；每条都给了依据，`near_gold_audit.csv` 可复核。
- 置信度分层：**高 9 条**（14976 ×5、14771 ×3、14155 ×1，有官方断言）；**中 26 条**（没有官方逐题日志，依据 gold/test patch + 最终补丁 + 部分日志）；**未独立评定 4 条**（21568、10356 ×3，只有 C 的来源标注）。中/未评定条目的分类应视为待复核，不是定论。
- 14534 的 4 条 C 与 2 条 B/C 是最有争议的一组：测试要求 `auto_id=False` 返回 `None`，issue 没有说明；把它算作契约缺口是合理的，但也可以争论为行为缺口。报告应保留这个不确定性。

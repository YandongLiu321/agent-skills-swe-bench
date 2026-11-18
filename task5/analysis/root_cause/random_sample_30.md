# 30 条随机失败初筛：near-gold 是富集样本，总体仍以行为缺口为主

> 目的：给 39 条 near-gold 审计做一个**无选择偏差**的对照，估计 437 条失败中契约缺口的大致量级。
> 样本：从 1,010 条 mixed 运行的 437 条失败里，取三个主标签（wrong_fix 183 / incomplete_patch 161 / wrong_location 63，共 407 条），每个标签随机抽 10 条，共 30 条；seed = 20261031。
> 方法：读 `reference_patch`、`test_patch`、最终 patch 与可得的官方 `test_output.txt`；分类 B / C / U。原始表见 `near_gold_audit/random_sample_30_classified.csv`。

## 1. 结果

| 分类 | 数量 | 说明 |
|---|---:|---|
| **B 行为缺口** | 29 / 30 | 最终 patch 漏了 gold 的关键 hunk/文件，或行为明显不同 |
| **C 明确契约缺口** | 1 / 30 | `pytest-dev__pytest-10356` / `pytest-code-review`：返回 generator，官方断言 generator ≠ list |
| **U 不确定** | 0 / 30 | 5 条原 U 已用官方 `report.json` 定掉，全部是 B |

分类的置信度：高 17 条、中 12 条、低 1 条。17 条有官方失败测试可直接确认；12 条是 patch/test 阅读；1 条（`pylint-8898` / `python-project-structure`）仍是低置信。

**随机样本的契约缺口 = 1/30 = 3.3%（95% Wilson CI [0.6%, 16.7%]）。**
作为对照，39 条 near-gold 里契约缺口占 12/39 = 30.8%（[18.6%, 46.4%]）。

按 run 的区间**不再重叠**（16.7% < 18.6%），方向比之前更清楚：near-gold 富集契约缺口。但 30 条 run 只来自 25 个实例，按实例算 C = 1/25 = 4.0%（[0.7%, 19.5%]），与 near-gold 下界重叠；且 C 只有 1 条，所以仍然只能说“富集”，不能把 3.3% 当成精确的总体比例。即使把最接近 C 的 `sphinx-9602`（节点类型不符）也算成 C，随机样本是 2/30 = 6.7%，仍远低于 near-gold。

- near-gold 是**高文本相似度**子集，天然富集“只差字符串/返回类型/边界”的 C 类；
- 随机失败的绝大多数仍是 B 类，即未正确实现 issue 要求的行为；
- 5 条原 U 的官方结果：25960（bbox 断言失败）、seaborn-3069（y 轴 tweaks 失败）、sphinx-9602（`desc_sig_keyword` vs `literal` 节点断言失败）、sympy-14248（`test_MatrixSymbol_printing` 失败）、pylint-4970（输出 `TOTAL lines=...` 不为空）。

## 2. 逐条初筛

| 实例 | Skill | 标签 | 分类 | 置信度 | 依据 |
|---|---|---|---|---|---|
| `astropy__astropy-14598` | python-pro | incomplete | **B** | 中 | 只删 `replace("''","'")`，漏掉 `_strg_comment_RE` 末尾 `$` 锚定 |
| `django__django-11265` | django-security | incomplete | **B** | 中 | 只复制 `_filtered_relations`，漏掉 `trim_start` 的 filtered relation 判断 |
| `django__django-11820` | django-access-review | incomplete | **B** | 高 | 只补 `pk` 分支，漏 `_cls=None`；官方测试失败 |
| `django__django-11820` | django-perf-review | incomplete | **B** | 高 | 同上；官方同一测试失败 |
| `django__django-12308` | django-verification | incomplete | **B** | 高 | 未捕获无效 JSON 的 TypeError；官方子测试 ERROR |
| `django__django-14011` | django-verification | incomplete | **B** | 高 | `ThreadedWSGIServer` 未接受 `connections_override`；servers 全部 setUpClass ERROR |
| `django__django-16256` | django-tdd | incomplete | **B** | 中 | 只改 `related_descriptors.py`，漏 `contenttypes/fields.py` |
| `django__django-16256` | test-driven-development | incomplete | **B** | 中 | 同上 |
| `pylint-dev__pylint-8898` | python-project-structure | incomplete | **B** | 低 | 自写 `_split_regex_csv` 与 gold 的 `_check_regexp_csv` 接口不同；无官方失败行 |
| `sympy__sympy-13798` | code-review-and-quality | incomplete | **B** | 中 | 用 `mul_symbol_table.get(...)` 默认串，未实现 gold 对空白/`\,` 的 `_numbers` 回退 |
| `django__django-15098` | debugging-and-error-recovery | wrong_fix | **B** | 高 | 官方 `test_get_language_from_path_real('/de-ch-1901/')` 失败 |
| `django__django-15127` | debugging-and-error-recovery | wrong_fix | **B** | 高 | 删除 `LEVEL_TAGS`；官方 AttributeError |
| `django__django-16950` | django-access-review | wrong_fix | **B** | 高 | 官方 inline formset UUID 测试失败 |
| `matplotlib__matplotlib-25960` | test-driven-development | wrong_fix | **B** | 高 | 官方 `test_subfigures_wspace_hspace` bbox 断言失败；自算几何不对 |
| `mwaskom__seaborn-3069` | python-project-structure | wrong_fix | **B** | 高 | 官方 `test_nominal_y_axis_tweaks` 失败；x 轴通过、y 轴未实现 |
| `pylint-dev__pylint-8898` | python-error-handling | wrong_fix | **B** | 中 | 只改 `config/argument.py`，漏 `utils/utils.py` 的 `_check_regexp_csv` |
| `pytest-dev__pytest-10356` | pytest-code-review | wrong_fix | **C** | 高 | 返回 generator，官方断言 generator ≠ list；MRO 内容可能正确 |
| `pytest-dev__pytest-10356` | python-testing | wrong_fix | **B** | 高 | `reversed(__mro__)` + 去重，mark 顺序与官方 `[c,a,b]` 不符 |
| `sphinx-doc__sphinx-9602` | debugging-and-error-recovery | wrong_fix | **B** | 高 | 官方 `test_parse_annotation_Literal` 失败：True 渲染成 `desc_sig_keyword` 而非 `literal` 包裹 |
| `sympy__sympy-14248` | sympy | wrong_fix | **B** | 高 | 官方 `test_MatrixSymbol_printing` 失败；`test_MatrixElement_printing` 通过 |
| `django__django-11477` | systematic-debugging | wrong_location | **B** | 中 | 改 `urls/base.py` 过滤 None，gold 改 `resolvers.py`；测试还检查 ResolverMatch kwargs |
| `django__django-12273` | django-tdd | wrong_location | **B** | 中 | 改 `_save_parents` 条件，gold 是 parent_link 传播；无官方失败行 |
| `django__django-14155` | django-security | wrong_location | **B** | 高 | 改 `__init__` 解包 partial，未改 `__repr__`；官方 repr/partial 测试全失败 |
| `django__django-14155` | systematic-debugging | wrong_location | **B** | 高 | 同上 |
| `django__django-14792` | verification-before-completion | wrong_location | **B** | 高 | 官方 `test_get_timezone_name(Etc/GMT-10)` 失败；改错后端文件 |
| `matplotlib__matplotlib-23299` | test-driven-development | wrong_location | **B** | 中 | 改 pyplot，gold 改 `rc_context` 不重置 backend；无官方失败行 |
| `matplotlib__matplotlib-23476` | test-driven-development | wrong_location | **B** | 中 | 改 `backend_bases` 的 `_original_dpi`，gold 改 `figure.__setstate__` |
| `matplotlib__matplotlib-26208` | systematic-debugging | wrong_location | **B** | 中 | 改 Collection 的 datalim，gold 复制 twinx 的 `axis.units`；测试检查 units 身份 |
| `pylint-dev__pylint-4970` | python-anti-patterns | wrong_location | **B** | 高 | 官方 `test_set_duplicate_lines_to_zero` 失败：仍输出 `TOTAL lines=...` 而非空 |
| `scikit-learn__scikit-learn-14629` | systematic-debugging | wrong_location | **B** | 中 | 改 `_validation.py` 的 prediction order，gold 在 `MultiOutputClassifier.fit` 设置 `classes_`；测试检查 `classes_` |

## 3. 怎么用这个结果

- **不要**把 3.3% 写成“437 条失败中只有 3.3% 是契约缺口”。样本只有 30 条 / 25 个实例，C 只有 1 条；3.3% 是**点估计**，95% CI 到 16.7%。
- 可以写：“near-gold 的 12/39（30.8%）高于随机初筛的 1/30（3.3%），方向与‘高相似度子集富集契约缺口’一致；按 run 的 Wilson 区间不重叠（16.7% < 18.6%），但按 25 个实例算 C = 1/25 = 4.0%（[0.7%, 19.5%]），与 near-gold 下界重叠，且 C 只有 1 条，不能给出总体精确比例。”
- 对报告最有用的结论是：**契约缺口是真实威胁，但主要集中在一小类“精确字符串/返回类型/未说明边界”的实例；绝大多数失败仍是行为缺口。** 这与 39 条 near-gold 的 25 B 一致，也解释了为什么不能整体重标。
- 下一步若要更准的估计：把样本扩到 60–80 条；或按 `test_patch` 是否含精确字符串/mock/内部状态做分层抽样；或对 437 条做 test_patch 自动筛查，找出低相似度但测试是精确表示/调用点断言的候选（15252 这类）。

## 4. 边界

- 30 条是分层随机样本（三个主标签各 10 条），不是 437 条的完整审计；`uncertain` 20 与 `other` 10 未纳入。
- 17 条高置信有官方失败行；12 条中置信是 patch/test 阅读；1 条低置信（`pylint-8898` / `python-project-structure`）需要人工复核。
- 分类不是双人标注；`random_sample_30_classified.csv` 保留了每条的依据。
- 30 条 run 来自 25 个不同实例（11820、16256、pylint 8898、10356、14155 各出现 2 次）；同一实例的臂相关，Wilson 区间按 run 独立计算，可能略窄。
- 4% 与 30.8% 的比较受样本量限制，只能当方向性证据，不能当精确的富集倍数。

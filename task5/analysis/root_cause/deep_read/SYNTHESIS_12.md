# 12 个交叉实例深读：原因分类与成功侧对照

> 样本：101 个交叉实例（1–9 个 skill 成功）中分层抽 12 个：
> n_resolved 1–3 六个、4–6 三个、7–9 三个，覆盖 9 个仓库。
> 每个实例读 1 条失败 + 1 条同题成功轨迹，外加 issue、gold patch、test_patch、最终补丁、官方日志/标签证据。
> **这是目的性分层样本，不是随机样本；下面的计数只描述这 12 个，不是 437 条的频率。**

## 1. 12 个案例一览

| # | 实例 | n | 失败 skill | B 标签 | 主因（本卡判定） | 成功 skill | 成功机制 |
|---|---|---:|---|---|---|---|---|
| 1 | astropy-13033 | 1 | code-review-and-quality | wrong_fix | 读错契约：精确错误消息 | systematic-debugging | 重写 `__eq__` 对冲多种措辞（gaming） |
| 2 | matplotlib-23299 | 1 | test-driven-development | wrong_location | 选错修复点：改 `switch_backend`，没改 `rc_context` | verification-before-completion | 回忆上游 docstring → 修根因 |
| 3 | sympy-13798 | 2 | python-pro | incomplete_patch | 漏分支：数字×数字没回退 `dot` | sympy | 读 `mul_symbol_latex_numbers` 不变量 |
| 4 | django-12273 | 4 | django-patterns | wrong_location | 漏分支：只处理新增，没处理已有对象重置 pk | debugging-and-error-recovery | 双侧清空 + 多场景自测 |
| 5 | django-16256 | 2 | django-tdd | incomplete_patch | 漏入口：没改 contenttypes 的 generic manager | django-security | 泛化到所有 manager 工厂 |
| 6 | sympy-14248 | 2 | sympy | wrong_fix | 读错契约：精确空格/符号格式 | python-anti-patterns | 读既有测试的格式线索 |
| 7 | pytest-10356 | 4 | pytest-code-review | wrong_fix | 读错契约：MRO 顺序反了 | python-error-handling | 从 `get_closest_marker` 反推顺序 |
| 8 | requests-1724 | 9 | python-error-handling | uncertain | 评测冲突：同一补丁两种判定 | systematic-debugging | 同补丁，恰好通过 |
| 9 | sklearn-14629 | 8 | sklearn-advanced | wrong_location | 选错修复点：修消费者，没补提供者 `classes_` | test-driven-development | 给估计器加 `classes_` |
| 10 | sphinx-7985 | 3 | sphinx-docs | incomplete_patch | 读错契约：存在文件返回 `local` 而非 `working` | sphinx-build | 完整状态机 `check_local` |
| 11 | astropy-13977 | 7 | verification-before-completion | incomplete_patch | 漏分支：只包转换循环，缺协作对象守卫 | astropy | 前置 `__array_ufunc__` 守卫 |
| 12 | pylint-4970 | 4 | python-code-style | wrong_location | 选错修复点：停在计算层，显示层仍打印 | test-driven-development | `run()` + `close()` 双入口拦截 |

## 2. 四类主因（12 个案例的计数）

| 主因 | 定义 | 案例 | 计数 |
|---|---|---|---:|
| **读错契约** | 补丁语义正确，但精确输出/顺序/状态词/API 形状与测试不符 | 13033、14248、10356、7985 | 4 |
| **选错修复点** | 修了消费者/症状点/计算层，测试断言的是提供者/根因/显示层 | 23299、14629、4970 | 3 |
| **漏分支/入口** | 只覆盖 issue 示例的分支/入口，漏了同接口的其他实现或边界 | 13798、12273、16256、13977 | 4 |
| **评测冲突** | 同一 normalized patch 判定不同；test_patch 新测试不在 FAIL_TO_PASS | 1724 | 1 |

注意：
- 这是**主因**，很多案例还有次因（例如 4970 同时是“读错契约”和“选错修复点”）。
- `uncertain`（4970 的 3 条、1724 的 1 条）是**证据状态**，不是原因；计数时要单列。
- 12 个案例不是随机样本，不能把 4/3/4/1 当成 437 条的分布。

## 3. 成功侧的模式

| 成功模式 | 说明 | 案例 |
|---|---|---|
| **读契约** | 先读同文件/同 API 的既有测试、注释、不变量，再实现 | 13798、14248、10356、23299、16256 |
| **修提供者** | 改估计器/根因/显示入口，而不是单个消费者 | 23299、14629、4970、7985 |
| **全入口** | 搜索同一接口的所有实现/所有输出路径，全部覆盖 | 16256、4970、7985、14248 |
| **契约对冲** | 重写 `__eq__` 让多种措辞都等于期望字符串 | 13033（**gaming，不是能力**） |
| **记忆召回** | 回忆上游 patch/docstring | 23299、10356、16256（双刃剑） |
| **场景化自测** | 用“另一侧”场景（both_none vs child_pk_only；diamond；数字×数字）验证 | 12273、13798、10356、13977 |

**重要**：成功不等于“skill 文本更好”。多个案例里专用 skill 失败、通用 skill 成功（14248、10356、16256、14629、4970）。成功更多取决于**是否读到了正确的契约/位置**。

## 4. 给开发者的框架表（草案）

| 失败形态 | 轨迹/补丁可观察信号 | 典型原因 | 成功侧对应做法 | 干预点 |
|---|---|---|---|---|
| **精确表示不符** | 语义正确，但字符串/空格/顺序/状态词不同；测试是精确 `==` | 只按 issue 示例实现，没对齐既有测试/API 的输出格式 | 先读同文件/同 API 的既有断言，复刻格式 | 把“精确输出”列为验收项；先写与测试同形的断言 |
| **修在症状点** | 补丁改调用方/消费者/计算层/关闭流程；测试断言提供者/根因/显示层 | 跟着 issue 的定位锚走 | 问“这个属性/行为应该由谁提供”；从测试反推断言对象 | 先定位“谁拥有契约”，再决定改哪里 |
| **漏分支/入口** | 覆盖 issue 例子，但漏数字/边界/第二入口/多继承 | 把 issue 示例当完整契约 | 枚举同接口的所有实现/所有分支；用另一侧场景自测 | 测试按“接口/不变量”组织，不按“已改文件”组织 |
| **评测链冲突** | 同一 normalized patch 判定不同；新测试不在 FAIL_TO_PASS；FAIL_TO_PASS 全是网络测试 | 不是 patch 失败 | 单列、剔除、复核 | 外部 gate + 日志；不要归因于 skill |

## 5. 放大验证：把四类原因操作化后数 437 条

每条原因的判定规则（初稿）：

1. **读错契约**
   - test_patch 是精确字符串/顺序/状态断言；
   - 补丁输出与期望在空格、符号位置、MRO 顺序、状态词上不同；
   - 轨迹里没有读对应测试/API 的格式。
2. **选错修复点**
   - 补丁修改的文件/函数不是 gold 修改的目标；
   - 测试直接断言某个属性/入口，而补丁只在调用方绕过；
   - 补丁在 `_compute`/`_validation`/`switch_backend` 等消费者侧，gold 在 provider/root/display 侧。
3. **漏分支/入口**
   - 同一方法名在 ≥2 个模块/manager/printer 里出现，补丁只覆盖一个；
   - issue 例子只覆盖一个分支，补丁没有处理同函数的另一侧（数字/已有对象/`out`/`initial`）。
4. **评测冲突**
   - 同实例存在 normalized patch 相同但判定不同的 run；
   - test_patch 新增测试不在 FAIL_TO_PASS；
   - 官方日志显示网络/超时/infra failure。

计数流程：
- 先人工编码 12 个已深读案例，校准规则；
- 再对 437 条失败逐条编码（先看标签+补丁+test_patch，必要时读轨迹）；
- 两人各编码 50 条，算 Cohen's kappa；
- 报每个原因的占比 + Wilson 区间，按仓库、n_resolved 层、B 标签分层；
- `uncertain` / 评测冲突单列，不进入主分母。

## 6. 算法化（下一步）

规则分类器（不需要训练）：
- **F1 读错契约**：抽取 test_patch 的断言形状（字符串/顺序/状态），与补丁输出比对；
- **F2 选错修复点**：比较补丁修改的函数与 gold/test 断言的目标函数；
- **F3 漏分支/入口**：在仓库里搜索同名方法的其他实现，检查补丁覆盖率；
- **F4 评测冲突**：用 normalized patch 去重 + FAIL_TO_PASS/test_patch 一致性检查。

这四类都可以先做成可解释规则，再考虑用 437 条人工编码训练一个小分类器。

## 7. 边界

- 12 个案例是目的性分层，不是随机；不能外推频率。
- 成功臂的 skill 与失败臂不同，模型有随机性；成功只能说明“另一种做法存在”，不能证明 skill 因果。
- 13033 的成功是 `__eq__` 对冲，不是能力；报告必须单列“gaming 型成功”。
- 1724 是评测链伪失败；不能写成 skill 失败。
- 12273、4970 的 B 标签是粗口径（wrong_location），深读后更准确的是“状态转移不完整”“输出层未拦截”；报告要区分标签与原因。

## 8. 案例卡位置

`task5/analysis/root_cause/deep_read/cases/<instance>/card.md`，每张卡含：
- issue / gold / test_patch 摘要；
- 失败臂轨迹关键分叉 + 最终补丁 + 官方结果；
- 成功臂关键做法；
- 原因编码 + 可迁移假设 + 证据行号。

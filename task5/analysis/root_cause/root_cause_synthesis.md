# 从现象到原因：三个案例的综合

> 对应报告第 4 章新增的 4.5 节。三个案例的完整卡片：
> `case_django_15127.md`、`case_django_15252.md`、`case_sympy_14976.md`。
> 方法：每个案例读 1 条失败轨迹 + 1 条同题成功轨迹；读 issue、skill、轨迹、补丁、正式测试；开放编码，不做总体频率推断。

## 1. 三个案例一览

| 案例 | 现象 | 失败臂 | 成功臂 | 直接原因 | 根本原因（本卡结论） |
|---|---|---|---|---|---|
| Django 15127 | wrong_fix / incomplete_patch | debugging-and-error-recovery；systematic-debugging | django-security | 删除 `LEVEL_TAGS`（AttributeError）；或保留但不更新（AssertionError） | 记忆先验 + 对正式测试的模型不完整 + 只修读取方/删除共享状态 |
| Django 15252 | wrong_location | debugging-and-error-recovery 等 5 臂 | django-patterns 等 5 臂 | 仅修改 `recorder.py`，executor 仍调用 `ensure_schema` | 题面点名 `MigrationRecorder` → 锚定被调用方；正式测试 mock 的却是调用点，5/5 按“修改 recorder / 修改 executor”完全分层 |
| SymPy 14976 | incomplete_patch | python-project-structure 等 7 臂 | sympy 等 3 臂 | 多数臂只包分子（`mpmath.mpf(1)/2`），1 臂两端都包但多一层括号 | 记忆先验选了短格式；正式测试是**精确字符串**，数值上 7/10 其实已经修好（详见 `contract_mismatch_evidence.md`） |

## 2. 共同结构：不是“Skill 无效”，而是“契约模型错误”

三个失败案例都不是“agent 未执行操作”：

- 15127 的 DER 复现了缺陷、删除了变量、执行了 96 项测试；SD 读取了代码、比较了两种方案、执行了两种测试文件。
- 15252 的 DER 读取了 executor、编写了复现、修改了 recorder、执行了测试。
- 14976 的失败臂读取了代码、推导精度机制、实现了补丁、执行了数值检查和测试。

它们失败在同一个位置：**agent 对“正式契约要求什么”的内部模型是错的，然后用自己构造的验证（复现脚本、临时测试、数值检查）替代了正式测试。**

- 15127：自造 test patch（删 helper），没模拟 `assertEqual(base.LEVEL_TAGS, ...)`；
- 15252：用现有测试 + 自造 repro，没把 issue 的“other 连接不建表”翻译成 executor 的控制流条件；
- 14976：用数值精度检查，没检查 `doprint` 的精确字符串——而 7/10 的补丁数值上已经正确。

但要把两种“契约模型错”分开：

1. **行为缺口**：issue 要求的行为没实现（20916 的 Unicode 数字、13798 的数字分支、11848 的 `utcnow`、14771 的 bare flag 格式）；
2. **分层/表示契约缺口**：issue 行为已实现，但正式测试要求特定的调用点、字符串或内部状态（14976 全部 10 臂都修好了数值行为，7 臂输在字符串；15252 的 5 个 recorder 臂修好了 issue 的 router 行为，但正式测试测的是无 router 的空 plan 场景，且 mock 了 `ensure_schema` 的调用点）。

第 2 类不能写成“模型能力不足”；它是 benchmark 的构念效度问题。逐臂证据与计数见 `contract_mismatch_evidence.md`。

## 3. 根因分类（跨案例假设）

### C1 题面/命名锚定

- 15252：issue 标题和正文反复点名 `MigrationRecorder` / `recorder.py`，agent 把“名字”当成了“位置”，修在被调用方而不是调用方。
- 15127：issue 只给“level_tag 读到旧值”的症状，允许“动态读取”和“更新变量”两种读法；agent 选了前者，把“删除变量”当成合理延伸。
- 14976：issue 说“wrap rationals”，数值上至少有 `mpf(p)/mpf(q)` 和 `mpf(p)/q` 两种等价写法；正式测试只接受前者的精确字符串。不是“读窄”，而是**多种等价实现中只有一种表示被接受**。

### C2 记忆先验压过仓库证据

- 15127：[14] “The fix is described in the actual Django commit. Let me recall...”；[34] “It's virtually certain the upstream fix removed the helper.”
- 15252：[16] 回忆 upstream fix 在 recorder；[102] 即使看过 executor，仍说“ensure_schema is the natural place”。
- 14976：失败臂在 [25]/[28]/[40] **三次写出正确形式** `{0}({1})/{0}({2})`，又三次根据“我记得测试是 `mpmath.mpf(1)/2`”改回短形式；[78] 明确说“I can't satisfy both. But I'm confident it's the simpler form.” 成功臂同样是靠记忆召回（[26]–[33]），只是召回的版本恰好正确。

### C3 对正式测试的模型不完整 / 用自造验证替代

- 15127：自造 test patch，96 项通过；正式测试仍失败。
- 15252：现有测试 + 自造 repro；正式测试的 “no table when there are no migrations” 没覆盖。
- 14976：数值检查对 7/10 的失败臂都通过；正式测试的字符串断言没覆盖。这不是“验证不足”——在 issue 语义下，数值就是正确性标准；是**测试选择了表示层契约**。

### C4 修在现象发生处，而非动作发起处

- 15252：`ensure_schema` 是现象发生处，`executor.migrate` 是动作发起处；失败补丁仅修改 recorder。
- 15127：`level_tag` 是现象发生处，`LEVEL_TAGS` 的更新是根因；SD 仅修改属性读取。

### C5 仅修改一部分 / 共享状态仅修改读取方

- 15127 SD：让 `level_tag` 动态读取，但 `LEVEL_TAGS` 仍是旧值。
- 14976 **不属于 C5**：只包分子在数值上已经完整（`mpf(p)/q` 与 `mpf(p)/mpf(q)` 等价），失败是字符串表示，不是行为只修了一半。把它归进“半修”会把表示契约错写成能力问题。

### C6 过早收敛 / 范围缩小（备选，来自 case_studies 的 Django 16256）

- agent 发现第二套 generic 实现后，临时测试报 `SynchronousOnlyOperation`，它把测试错误解释为“超出范围”，缩回单文件补丁。
- 本报告未把 16256 做成完整卡片（缺官方日志），只作为根因类别的备选。

### C7 语义读窄

- 15127：把“root cause”读成“让属性动态读取”，而不是“让共享状态被正确更新”。
- 14976 **不属于 C7**：issue 的“wrap rationals”没有规定分母必须单独包；两种写法都满足 issue。失败是测试只接受一种表示，不是 agent 读窄了语义。

## 4. 成功对照说明了什么、没说明什么

- 15127 成功臂 `django-security`：保留 `LEVEL_TAGS` 并用 `setting_changed` 更新；它找到 `PASSWORD_HASHERS` 的仓库先例。但它在 [33] 也说过“隐藏测试会不会检查 `base.LEVEL_TAGS`？不太可能”——它并没有准确预测正式断言，只是选择了一个保留并同步共享状态的通用修法。
- 15252 成功臂 `django-patterns`：改 executor，按 router 过滤 plan；它比较过 recorder / create_test_db / executor 三种方案，最终选 executor。它没有看到正式测试；它的通用 router 修复只是**顺带**覆盖了正式测试的空 plan 场景（`_migrations_allowed([])` 返回 False → 不调用 `ensure_schema`）。
- 14976 成功臂 `sympy` 与 `code-review-and-quality`：两个 skill 产出了**字节级相同**的补丁；它们都没有看到正式测试，靠记忆 recall 出 both-wrapped 形式。失败臂 recall 的是另一个同样合理的变体。

因此：**成功对照是解释性证据，不是因果识别。** 14976 的“成功”甚至不能说明 skill 内容有用——两个成功臂的补丁完全相同，差异只在记忆召回；15252 的“成功”说明的是修改层级恰好与 mock 的调用点一致，不是 router 语义更正确（5 个 recorder 臂在语义上也正确）。 不能写成“django-security 让 agent 成功”或“sympy skill 更好”；更稳妥的说法是：成功臂在“契约模型”或“修改层级”上恰好更接近正式要求——15127 保留并同步共享状态，15252 选择 executor 控制流，14976 靠记忆 recall 出正确形式；它们都没有直接看到正式测试。

## 5. 对 Skill 设计的启示

1. **先找动作发起处，再决定改调用方还是被调用方**（15252）。
2. **把 issue 的期望翻译成控制流/状态条件**，不要跟着 issue 点名的类走（15252、15127）。
3. **删除或修改共享状态前，列出所有读取/写入方**，并区分“测试辅助代码”与“被访问对象”（15127）。
4. **用正式契约验证，不要用自造测试/数值检查代替**：如果看不到 test patch，至少列出“正式测试可能检查的共享状态/精确输出”并逐项验证（三个案例都适用）。
5. **对“我记得 upstream 是这么做的”保持警惕**：记忆只能生成候选，必须用 issue 语义或正式测试确认（15127、15252、14976）。
6. **当两种实现都解决现象时，优先选更显式、更接近仓库现有风格的表示，并检查精确输出**；但承认这是启发式，issue 本身未必能裁决测试接受哪一种（14976）。
7. **区分“现象消失”和“契约满足”**：精度/复现通过不等于正式断言通过（14976、15127）。

## 5.5 契约缺口的直接计数与边界

两个锚案例的逐臂证据（`contract_mismatch_evidence.md`）：

- **14976**：10 臂中 7 臂的补丁在数值上已经修好（`mpf(p)/q` 或 `mpf(p)/mpf(q)`），失败只因为正式测试要求精确字符串 `mpmath.mpf(1)/mpmath.mpf(2)`。
- **15252**：10 臂中 5 臂对 issue 的 router 场景正确（router 不允许时不建表），但它们仍从 executor 调用 `ensure_schema`；正式测试 mock 的正是这个调用点。**5/5 按“改 recorder / 改 executor”完全分层**。注意：正式测试测的是**无 router 的 `TEST MIGRATE=False` / 空 plan 场景**，recorder 修复对这个场景本身也不够——所以这是“场景错位 + 调用点契约”，不是纯表示契约。
- 两个案例合计 **12/20 条在 issue 语义下正确、但正式测试判失败**。其中 14976 的 7 条是纯表示契约；15252 的 5 条是对 issue 正确、对测试场景不完整。这是锚案例的计数，不是 437 条失败的总体比例。

数据侧的 39 条 near-gold 小审计（已完成，`near_gold_audit.md`）：

- 437 条失败中，**39 条**满足“与 gold 同文件 + patch 文本相似度 ≥0.8”（wrong_fix 14、incomplete_patch 25；wrong_location 0）。
- 逐条读 `test_patch` + gold + 官方日志后：**25 条行为缺口、12 条契约/表示缺口、2 条 B/C 混合**；其中 9 条有官方断言/高置信，其余为中置信或未独立评定。near-gold 主要是真实缺陷，不能一律写成契约问题。
- 12 条 C 中 5 条来自 14976；另外 7 条是 14155（route 缺引号）、21568（`\ ` vs `\;`）、14534×4（`auto_id=False` 返回 None 的未说明边界）、10356×1（generator vs list 的返回类型）。
- 选择偏差：15252（file Jaccard 0）与 14976 的 2 条低相似度失败不在 39 条里；加上两个锚案例，已知契约缺口至少 **19 条**（12 条锚案例 + 7 条新增），这是下界，不是 437 条的总体比例。
- 随机对照：三个主标签各抽 10 条（共 30 条，seed 20261031），初筛 **29 B / 1 C**；C 占 1/30 = 3.3%（95% CI [0.6%, 16.7%]），低于 near-gold 的 30.8%（[18.6%, 46.4%]）。按 run 的区间不重叠（16.7% < 18.6%），但 30 条 run 只来自 25 个实例，按实例算 C = 1/25 = 4.0%（[0.7%, 19.5%]），与 near-gold 下界重叠；所以只能说明 near-gold 富集契约缺口，总体仍以行为缺口为主。详见 `random_sample_30.md`。

## 6. 更广的机制地图（10 个案例 + 数据侧证据）

三个案例只覆盖“契约/记忆”这一族。把现有 10 个 case studies 按机制重新编码，至少还能看到下面这些族；它们的证据强度不同，不能和三个锚案例同等对待。

| 机制族 | 现象 | 代表案例 | 证据/置信度 |
|---|---|---|---|
| 题面/命名锚定 | wrong_location | Django 15252 | 高（官方日志 + 轨迹） |
| 记忆先验 | wrong_fix / incomplete | Django 15127、SymPy 14976 | 高（官方日志 + 轨迹） |
| 正式契约模型不完整 / 自造验证 | 全部三类 | 15127、15252、14976 | 高 |
| 修在现象发生处 | wrong_location | Django 15252 | 高 |
| 只修一半 / 共享状态 | wrong_fix / incomplete | 15127（14976 不属于：数值已完整） | 高 |
| 测试契约 / 调用点耦合 | wrong_location / incomplete | 15252（5/5 按文件分层；另有 issue 的 router 场景与测试的空 plan 场景错位）、14976（7/10 数值正确但字符串不等）、15127（断言模块变量） | 高（逐臂补丁 + test_patch） |
| 只修复合模式的一半（Unicode/正则） | incomplete_patch | SymPy 20916（字母部分改成 Unicode，数字仍是 `[0-9]+`；成功臂用 `\d+` + `re.UNICODE`） | 高（官方日志；8 失败/2 成功；正式测试 `split_super_sub("w𝟙")`） |
| 多入口 / 多调用方漏改 | incomplete_patch | Django 14376（主连接修了、dbshell 漏了）、Django 16256（第二套 generic 实现漏了） | 14376 中高；16256 中（缺官方日志） |
| 过早收敛 / 范围缩小 | incomplete_patch | Django 16256（临时测试报 `SynchronousOnlyOperation`，被解释为超出范围） | 中低（缺官方日志） |
| 语义契约误解 | wrong_fix | pytest 10356（MRO 顺序）、sklearn 25747（pandas index 所有权） | 中高 |
| 隐藏副作用 / 双入口 | wrong_fix + wrong_location | matplotlib 23299（backend 恢复 + figure 关闭） | 中（缺官方日志） |
| 调用点防御与 API 根因 | incomplete_patch | xarray 6938 | 中 |
| 模板 / Skill 冲突 | 依从性、正对照 | TDD 与 `DO NOT MODIFY Tests`；harmful 正对照 24/24 被拒 | 高（依从性审计） |
| 评测 / 环境伪失败 | uncertain / wrong | Django 13344（同补丁不同判定）、Requests 1724/1766/1921（SSL） | 中（复评后部分通过/环境问题） |
| 预算 / 步数限制 | 无有效补丁 | 10 条“无有效补丁终止记录”；group3 2 条 `LimitsExceeded` | 高（记录） |
| 污染 / 记忆 | 成功侧 | high_proxy 96 条中 93 条 resolved | 高（污染审计） |
| 标签噪声 | uncertain / other | 11 条可能标错（核查中） | 中 |

**补充 mini-case：SymPy 20916（只修复合模式的一半）。** Issue 说 “pprint unicode does not format subscripts on Greek letters”，例子是 `ω0`（ASCII 0）。失败臂把字母类改成 `[^\W\d_]+`，但数字类仍是 `[0-9]+`；它用 issue 的 `ω0` 例子验证，没覆盖正式测试的 `split_super_sub("w𝟙")`（Unicode 数字 `𝟙`，U+1D7D9）。成功臂用 `\d+` + `re.UNICODE`，通过。这个案例与 14976 的“只包分子”同族（只修复合模式的一半），但触发点在 Unicode 数字；它再次说明：**issue 给的例子不是正式契约，正式测试会覆盖更宽的输入空间。**

这些族说明，“现象→原因”不是一条链，而是一张图：有的原因在 issue 文本（题面锚定）、有的在 agent 的记忆/推理（记忆先验、契约模型）、有的在修改层级（现象发生处）、有的在任务结构（多入口/隐藏副作用）、有的在 harness/评测（模板、环境、预算）、有的在数据质量（标签）。报告 4.5 只展开三条有官方日志的锚案例，其余机制作为地图呈现；后续如果要量化，需要按族抽样，而不是只读 3 条轨迹。

## 7. 边界

- 3 个案例是**机制假设**，不是 437 条失败的频率估计；不能写“X% 的失败属于 C2”。
- 案例选择偏向“有官方日志、有同题成功对照”的样本；没有日志的失败（如 16256）只作备选。
- 成功臂与失败臂的 skill 不同，且模型有随机性；成功对照只能说明“另一种做法存在”，不能证明 skill 的因果效应。
- 三个案例都属于“模型已经做了大量工作、但仍错在契约”的类型；不能外推到“所有失败都是契约问题”。
- 14976 的 7/10 与 15252 的 5/10 是**逐臂读补丁得到的硬计数**，但这两个实例是特意选的锚案例（一个有精确字符串测试，一个有 mock 调用点测试）；它们的 12/20 不能当总体频率。20916/13798/11848/14771 的抽查说明：同样“接近 gold”的失败里也有真行为缺口。
- 14976 的成功侧（2 个 skill 产出字节级相同补丁）与污染审计里的 `high_proxy`/`exact_gold` 是同一族现象：**记忆可以伪装成能力**。报告应把这一点放进效度威胁，而不是写成 skill 效果。

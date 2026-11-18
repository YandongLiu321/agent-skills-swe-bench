# 交叉实例分析：三个人具体做什么

## 分析对象

只看 **101 个 mixed 实例**：

- 每个实例跑过 10 个 skill；
- 成功的 skill 数是 **1–9**；
- 不分析 0/10 全失败和 10/10 全成功；
- 不按一期/二期分组；`baseline` 只作为参照。

完整实例清单在：

```text
task5/analysis/crossover/assignment.csv
```

字段：`person, case, instance, n_resolved, reason`。

---

# A 的任务

## A 负责的实例：34 个

| case | 数量 |
|---|---:|
| django | 23 |
| astropy | 6 |
| pylint | 3 |
| seaborn | 2 |

具体实例：

```text
astropy__astropy-13033
astropy__astropy-13236
astropy__astropy-14598
astropy__astropy-13977
astropy__astropy-14365
astropy__astropy-14182
pylint-dev__pylint-8898
pylint-dev__pylint-4970
pylint-dev__pylint-7080
mwaskom__seaborn-3187
mwaskom__seaborn-3069
django__django-11820
django__django-10999
django__django-11532
django__django-13297
django__django-12273
django__django-14534
django__django-11400
django__django-11885
django__django-14011
django__django-15916
django__django-12308
django__django-13837
django__django-16950
django__django-11848
django__django-13512
django__django-10973
django__django-13794
django__django-15022
django__django-16642
django__django-13089
django__django-14725
django__django-16560
django__django-16877
```

## A 要做什么

### 1. 逐条读自己负责的 340 条轨迹

34 个实例 × 10 个 skill = 340 条 run。

每条 run 都要判断：

- 它是成功还是失败；
- 失败的话，最主要的失败原因是什么；
- 这个原因有没有轨迹证据；
- 成功 run 做对了什么。

不要只看最终 patch，要结合：

- 它先做了什么；
- 它改了哪些文件；
- 它跑了什么测试；
- 它有没有反复失败；
- 它有没有在最后编辑后验证；
- 它有没有提前提交。

### 2. 对每个失败 run 做失败原因判定

主要标签统一从下面选一个：

- `wrong_location`：改错文件、函数或位置；
- `incomplete_patch`：方向对，但漏了分支、边界或调用方；
- `wrong_fix`：补丁本身错误或引入新问题；
- `test_misread`：跑错测试、读错失败信息、只看部分测试；
- `tool_failure`：命令反复失败、路径错误、环境问题、循环；
- `premature_submit`：没复现、没跑最后测试、没验证就提交；
- `environment`：网络、Docker、依赖、超时；
- `other`：写不清的单独标记，不硬塞。

每个失败 run 至少留一条证据：命令、日志、测试输出或轨迹片段。

### 3. 对每个实例写一张“成功 vs 失败”对照卡

每个实例都写，不要只写失败：

- 哪些 skill 成功；
- 哪些 skill 失败；
- 成功 run 做对了什么；
- 失败 run 主要错在哪；
- 这个差异更像 skill 文本导致，还是题目/实例本身导致；
- 置信度：高 / 中 / 低。

不需要长篇，3–5 条即可。

### 4. 提取全量的工具调用特征

不只自己的 340 条，要对 **全部 1,010 条 mixed run** 提取工具调用特征，供三个人合并使用。

至少看这些：

- 总步数；
- 命令数；
- 测试命令数；
- 编辑命令数；
- 重复命令数量；
- 失败命令数量；
- 第一次编辑出现在第几步；
- 第一次测试出现在第几步；
- 最后编辑后有没有测试；
- 编辑前有没有复现；
- 命令类型分布：读文件 / 搜索 / 编辑 / 测试 / git / 其他；
- 长命令、 heredoc、`sed -i`、`apply_patch` 等特殊命令的使用。

### 5. 额外任务：命令序列模式

从自己的 340 条里找 3–5 个典型的成功/失败命令序列，例如：

- “读文件 → 改文件 → 跑目标测试”；
- “反复跑同一个测试，但从不动代码”；
- “一上来大范围 grep，最后没定位到文件”；
- “改完不测试直接提交”；
- “命令失败后不换方法，反复重试”。

每个模式给 2–3 个实例和轨迹证据。

### 6. 额外任务：失败指纹

给每条失败 run 打 5 个二元标记：

```text
定位错 / 补丁不完整 / 测试读错 / 工具循环 / 过早提交
```

一个人可以同时命中多个。这个指纹后面可以用来聚类，不要求现在下结论。

---

# B 的任务

## B 负责的实例：34 个

| case | 数量 |
|---|---:|
| django | 11 |
| sympy | 14 |
| sphinx | 9 |

具体实例：

```text
django__django-15127
django__django-13195
django__django-14155
django__django-15252
django__django-12406
django__django-11239
django__django-14771
django__django-14376
django__django-12276
django__django-15037
django__django-16938
sympy__sympy-13798
sympy__sympy-14248
sympy__sympy-20916
sympy__sympy-14976
sympy__sympy-17318
sympy__sympy-13878
sympy__sympy-15017
sympy__sympy-18698
sympy__sympy-11618
sympy__sympy-15875
sympy__sympy-18211
sympy__sympy-13091
sympy__sympy-13974
sympy__sympy-15599
sphinx-doc__sphinx-9602
sphinx-doc__sphinx-8056
sphinx-doc__sphinx-9461
sphinx-doc__sphinx-7985
sphinx-doc__sphinx-8638
sphinx-doc__sphinx-10435
sphinx-doc__sphinx-8548
sphinx-doc__sphinx-9658
sphinx-doc__sphinx-8621
```

## B 要做什么

### 1. 逐条读自己负责的 340 条轨迹

和 A 一样：

- 判断成功/失败；
- 失败 run 找主原因和证据；
- 成功 run 记录做对了什么；
- 不要只看最终 patch，要结合轨迹过程。

### 2. 对每个失败 run 做失败原因判定

使用同一套失败标签，重点判断：

- 是不是改错文件/函数；
- 方向对但补丁不完整；
- 补丁本身错误；
- 测试读错；
- 工具/环境问题；
- 过早提交。

每条至少留一条证据。

### 3. 对每个实例写“成功 vs 失败”对照卡

格式同 A：哪些 skill 成功/失败、成功 run 做对了什么、失败 run 错在哪、更像 skill 还是题目、置信度、证据。

### 4. 提取全量的 patch / 定位特征

对全部 **1,010 条 mixed run** 提取：

- patch 增删行数；
- 改动文件数；
- 是否空补丁；
- 是否改测试文件；
- 改动文件和 gold patch 文件的重合情况；
- 改动行和 gold 改动行的重合度；
- 是否只改一个文件；
- patch 能否干净应用（能判断就判断）；
- 改动集中在哪个目录/模块。

### 5. 额外任务：补丁失败类型

从自己的 340 条失败 run 里，按补丁形态归类：

- 空补丁；
- 只改一个文件但漏调用方；
- 改了正确文件但漏边界分支；
- 改错文件；
- 改动过大/引入回归；
- 补丁方向对但测试没跑对。

每类给 2–3 个实例和证据。

### 6. 额外任务：gold 对齐的“差一点”案例

找 3–5 个“补丁和 gold 很像，但就是没通过”的失败 run：

- 差在哪个文件；
- 差在哪一行/哪个分支；
- 是定位差一点，还是测试没覆盖到；
- 同一个实例里，成功的 skill 补了哪一块。

这个比单纯看“失败/成功”更能说明 skill 的实际作用。

---

# C 的任务

## C 负责的实例：33 个

| case | 数量 |
|---|---:|
| django | 12 |
| matplotlib | 8 |
| scikit-learn | 5 |
| xarray | 4 |
| pytest | 2 |
| requests | 2 |

具体实例：

```text
django__django-16256
django__django-15098
django__django-14792
django__django-11477
django__django-13406
django__django-15957
django__django-15629
django__django-13401
django__django-11265
django__django-16100
django__django-13344
django__django-16661
matplotlib__matplotlib-23299
matplotlib__matplotlib-23476
matplotlib__matplotlib-25960
matplotlib__matplotlib-24870
matplotlib__matplotlib-20676
matplotlib__matplotlib-26208
matplotlib__matplotlib-21568
matplotlib__matplotlib-22871
scikit-learn__scikit-learn-25747
scikit-learn__scikit-learn-10297
scikit-learn__scikit-learn-14629
scikit-learn__scikit-learn-25102
scikit-learn__scikit-learn-26194
pydata__xarray-6938
pydata__xarray-6599
pydata__xarray-6992
pydata__xarray-3993
pytest-dev__pytest-10356
pytest-dev__pytest-5787
psf__requests-1766
psf__requests-1724
```

## C 要做什么

### 1. 逐条读自己负责的 330 条轨迹

和 A/B 一样：

- 判断成功/失败；
- 失败 run 找主原因和证据；
- 成功 run 记录做对了什么；
- 结合命令、测试、编辑、patch 和最终提交看，不要只看最后结果。

### 2. 对每个失败 run 做失败原因判定

使用同一套标签；每条留证据。

### 3. 对每个实例写“成功 vs 失败”对照卡

格式同 A/B。

### 4. 提取全量的问题描述 / skill 文本特征

对全部 **1,010 条 mixed run** 对应的实例和 skill 提取：

**问题描述：**

- issue 字符数/行数；
- 有没有代码块；
- 有没有 traceback；
- 有没有明确提到文件名、函数名、测试名；
- 有没有复现步骤；
- 是否涉及多文件/API 变更；
- 题目描述是否模糊。

**skill 文本：**

- 字符数/行数；
- section 数；
- 命令数量；
- 测试命令数量；
- 验证类句子数量；
- 是否要求先复现；
- 是否要求跑全量测试；
- 是通用 skill 还是 case 专用 skill。

### 5. 额外任务：题目 × skill 适配矩阵

从自己的 330 条里找 3–5 个“题目描述 → skill 适配/不适配”的例子：

- 题目描述很模糊，skill 却强行给具体套路；
- issue 有明确 traceback，skill 的复现指令明显有帮助；
- 题目需要多文件/API 改动，skill 仍按单文件修；
- 专用 skill 和 case 很匹配，但通用 skill 反而更稳；
- 同一个 skill 在相似题目上成功/失败，题目描述差在哪。

### 6. 额外任务：反事实题目对照

找 3–5 组“同一个 skill、相似题目、一个成功一个失败”的对照：

- 两道题的 issue 描述差在哪；
- 是不是一个有明确报错、一个没有；
- 是不是一个单文件、一个多文件；
- 是不是测试提示强度不同；
- skill 文本里哪句话在成功题上被执行了，在失败题上没有。

---

# 三个人共同要遵守的规则

1. **只看 101 个 mixed 实例**，不要扩展到 0/10 或 10/10。
2. **不按一期/二期分组**；`baseline` 只是参照列。
3. 每条失败原因必须有证据，不能只写“感觉”“可能”。
4. 成功 run 也要看，不能只分析失败；重点是同一实例内的成功/失败差异。
5. 每个实例都要标记：这个差异是 **skill-specific** 还是 **instance-specific**。
6. 每个 case 最后留一句“这个 case 最常见的失败原因是什么”，不要写成长篇。
7. 不把跨实例比较当因果；同一个实例内的对照才是主要证据。
8. 任何拿不准的标签，标 `uncertain`，不要硬塞进现有类别。

---

# 三个人都可以顺手做的“新奇想法”

这些不是额外负担，是在做自己任务时顺手记录：

1. **成功/失败对照卡**：每个实例挑 1 条成功 run 和 1 条失败 run，只写 3 个最关键差异。
2. **失败指纹**：每条失败 run 打 5 个二元标记：定位错 / 补丁不完整 / 测试读错 / 工具循环 / 过早提交。
3. **skill-specific vs instance-specific**：同一个模式在多少实例上重复出现，还是只在一个题上出现。
4. **反事实对照**：相似题目、同一个 skill，一成功一失败，比较题目描述和轨迹，而不是只比 skill 文本。
5. **一句话结论**：每个 case 只留一句最核心的失败原因，方便最后合并。
6. **工具调用 motif**：把成功/失败 run 的命令序列画成短模式，找“读 → 改 → 测”与“反复试错”的差别。
7. **差一点案例**：patch 和 gold 很像但没通过的 run，单独收集，往往比彻底跑偏更有信息量。

最终每个人把自己负责的分析记录清楚即可，形式不限：表格、文档、笔记都可以，只要别人能从记录里追溯到具体实例、skill、轨迹和证据。

---

# 第二阶段：基于现有结果的整合分析（A / B / C）

现有底表：

```text
task5/analysis/crossover/integrated_1010.csv
```

它包含 1,010 条 run 的：

- case / instance / skill / resolved；
- A 的工具调用特征；
- B 的 patch 特征；
- C 的题目/skill 特征和 fit judgment；
- A/B/C 三人已有的失败标签和来源标记。

这一阶段不再跑新模型，只做整合、核对和结论。三个人仍然可以并行开始，按下面的顺序交接结果。

---

## A：特征与配对分析

A 负责回答：

> 同一实例里，成功 run 和失败 run 到底在哪些特征上不同？

### A1. 先做不依赖标签的配对分析

只用 `resolved=0/1`，对 101 个实例做同实例配对：

- B 的 patch 特征：
  - `changed_lines`
  - `files_changed`
  - `file_recall`
  - `location_jaccard`
  - `patch_text_similarity`
  - `patch_empty`
  - `modifies_tests`
- A 的工具特征：
  - 命令数、测试数、编辑数；
  - 失败命令数、重复命令数；
  - 第一次编辑/第一次测试位置；
  - 最后编辑后测试、编辑前复现；
- C 的题目/skill 特征：
  - issue 长度、代码块、traceback、文件名/测试名；
  - 多文件/API 变更；
  - skill 长度、命令密度、验证密度；
  - fit judgment。

每个特征给出：

- 成功均值 / 失败均值；
- 同实例配对差值；
- 置信区间或至少方向计数；
- 在多少个实例上同向。

### A2. 复现并核对 B 的 patch 结论

重点核对 B 的：

- 失败 run 是否改得更少；
- file recall / location Jaccard 是否更低；
- patch text similarity 是否更低；
- 空补丁是否更多；
- files changed / modifies tests 是否真的不显著。

如果 A 用同一批数据算不出同样方向，要写清楚差异来自样本、口径还是特征定义。

### A3. 标签分层分析

等 B 产出最终标签表后，再补一版：

- 按 `wrong_location / incomplete_patch / wrong_fix / other` 分组；
- 看每类失败在 patch/工具/文本特征上的差别；
- 特别检查：`incomplete_patch` 是否真的对应更低的 file recall / location Jaccard。

### A4. 整合产出

A 最后要留下：

- 一张特征结果表：`feature_results.csv`（或任意可合并形式）；
- 一页 `feature_summary.md`：
  - 哪些特征稳定区分成功/失败；
  - 哪些特征看起来有差异但按实例配对后消失；
  - 哪些结果和 B/C 的结论冲突；
  - 哪些只能当描述，不能当因果。

A 不负责写最终结论，只负责把“特征证据”做扎实。

---

## B：标签统一与质检

B 负责回答：

> 现在三套失败标签，哪些能合并，哪些是自动规则误判，最后应该以什么为准？

这是这一阶段最关键的整合任务。

### B1. 建立统一标签对照表

把三套标签映射到同一套最终标签：

```text
wrong_location
incomplete_patch
wrong_fix
test_misread
premature_submit
tool_failure
environment
other
uncertain
```

对每个来源：

- A：规则自动生成，只作为候选；
- B：人工/研究性标注，作为主依据；
- C：AI 辅助 + 用户确认，作为覆盖面补充，必须抽查。

### B2. 重点复核 A 的自动标签

A 的 148 条失败中，`wrong_fix` 106 条，比例明显高于 B/C。B 要：

- 优先检查 A 标成 `wrong_fix` 的条目；
- 看是否其实属于 `incomplete_patch`（方向对、漏文件/漏分支）；
- 看是否有 `wrong_location` 被误归为 `wrong_fix`；
- 对无法判断的保留 `uncertain`，不要硬改。

### B3. 抽查 C 的标注

C 的 330 条自述为人工确认，但它的校准记录是空模板，检查清单写的是“AI核对/用户确认”。B 要：

- 随机抽查 20–30 条 C 的失败标签；
- 优先抽查 `wrong_fix / incomplete_patch / wrong_location` 边界；
- 对照 C 的 evidence 和原轨迹；
- 记录抽查一致率，不要直接假设 330 条全部可靠。

### B4. 处理 B 自己的 uncertain

B 有 6 条 `uncertain` 和 51 条没有完整官方断言。B 要：

- 能补证据的补证据；
- 不能补的保持 `uncertain`；
- 在最终标签表里保留置信度和“证据是否完整”标记。

### B5. 生成最终标签表

最终表一行一个失败 run，至少包含：

```text
case, instance, skill, resolved,
final_label, label_source, confidence,
evidence, quality_flag
```

成功 run 可以只保留 `resolved=1`，不填失败标签。

同时产出：

- `label_dictionary.md`：每个标签的定义和边界；
- `label_audit.md`：A 被修正了哪些、C 抽查结果、B 的 uncertain 处理；
- 按 case / skill 的标签分布表。

B 的最终标签表是 A 做分层分析、C 写最终结论的共同输入。

---

## C：案例研究与最终结论

C 负责回答：

> 这些统计结果，落到具体题目上到底长什么样？哪些是 skill-specific，哪些是 instance-specific？

### C1. 选 8–10 个案例

从 B 的 34 张对照卡、C 的 33 张对照卡里选：

- 成功/失败差异最清楚的；
- 补丁差异有直接证据的；
- 有官方日志或测试输出支撑的；
- 覆盖不同 case 和不同失败标签的；
- 至少包含 2 个“看起来像 skill 问题，实际是题目陷阱”的反例。

### C2. 每个案例写清楚

每个案例至少包括：

- 实例、case、成功 skill、失败 skill；
- 成功 run 的关键行为；
- 失败 run 的关键错误；
- patch 差在哪；
- 测试/日志证据；
- 你判断是 skill-specific 还是 instance-specific；
- 置信度和替代解释。

### C3. 和 A/B 的结果对齐

C 写案例时不能只看故事，要对照：

- B 的最终标签；
- A 的特征结果；
- C 自己的 fit judgment。

如果案例和统计结果冲突，要明确写出来，不要强行圆上。

### C4. 最终整合

C 负责把三份东西合成最终结论：

- B 的最终标签分布；
- A 的特征结果；
- 自己的 case studies。

最终产出：

- `case_studies.md`：8–10 个案例；
- `final_insight.md`：
  - 交叉实例里最主要的失败原因；
  - 哪些特征稳定区分成功/失败；
  - 哪些是 skill-specific，哪些是 instance-specific；
  - 哪些结论只能当描述，不能当因果；
  - 对后续研究的 3–5 条启示。

---

# 三个人的依赖关系

```text
B 先出最终标签表
    ↓
A 用最终标签做分层特征分析
    ↓
C 用 B 的标签 + A 的特征 + 案例卡写最终结论
```

但不需要等全部完成才启动：

- A 可以先做 `resolved` 层面的配对分析；
- C 可以先选案例、读证据；
- B 的最终标签表出来后，A 补分层分析，C 再定稿。

不需要开会；按文件交接即可。

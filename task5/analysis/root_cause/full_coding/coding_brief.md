# 437 条失败原因编码：工作说明（给编码者）

你要为一批 SWE-bench 失败运行判定**主因**。输入是一个 compact 文本文件，每行 `## [row_id] instance · skill | B=...` 开始；每条给出：
- `files`: 最终补丁 / gold / test 的文件集；
- `overlap`: 文件是否与 gold 对齐、disjoint、touched_gold、func_jaccard；
- `signals`: test_patch 的断言形状（eq/is/in/raises）、新测试是否在 FAIL_TO_PASS、conflict、补丁状态；
- `evidence`: B 的复核说明（**是线索，不是答案**；B 的粗标签与主因有 227/407 跨类）；
- `F2P`: 正式 FAIL_TO_PASS；
- `--- FINAL PATCH ---`：失败臂最终补丁；
- `--- GOLD ---`：gold patch 的 diff 头、hunk 头与 `+` 行；
- `--- TEST ---`：test_patch 的 hunk 头与 `+` 行（断言在这里）。

## 四个代码

| 代码 | 名称 | 定义 | 判定核心 |
|---|---|---|---|
| **F1** | 读错契约 | 位置/方向对，但精确输出、顺序、状态词、常量、API 形状与正式测试不符 | 补丁和 gold 在同一区域，**内容**不同 |
| **F2** | 选错修复点 | 修了消费者/症状点/计算层/解析器，测试断言的是提供者/根因/显示层/字段本身 | 补丁改的**位置/层**不是测试要求的位置 |
| **F3** | 漏分支/入口 | 位置对，但覆盖不全：少文件、少 manager/printer/入口、少边界分支、少条件方向 | 补丁**覆盖面**不全 |
| **F4** | 评测冲突 / infra | 同补丁不同判定、无有效补丁（预算/API 终止）、官方日志显示网络/超时/基础设施失败 | 不是补丁质量问题 |
| **U** | 证据不足 | B=uncertain 且现有材料无法判断主因；或补丁与 gold 明显不同但无法确认测试断言对象 | 单列，不进主分母 |

## 判定顺序

1. `status != patch` 或 `conflict=True` → **F4**。
2. 补丁文件与 gold **完全不相交** → 先判 **F2**；但若补丁改的正是测试直接断言的对象、只是缺一个分支 → F3。
3. 补丁只覆盖 gold 文件的**真子集**（少文件/少 manager/少 printer 入口）→ **F3**。
4. 补丁覆盖全部 gold 文件：
   - 找到 test 的**决定性断言**（F2P 对应的 test_patch 新增行）；
   - 问：补丁的输出/顺序/状态词/常量与断言是否逐字一致？不一致 → **F1**；
   - 问：断言的目标函数/属性/入口，补丁改的是不是同一个？不是 → **F2**；
   - 问：断言覆盖的分支/边界/第二个入口，补丁有没有？没有 → **F3**。
5. B=uncertain 且材料不足 → **U**，不要硬填 F1–F4。

## 锚例（已由 12 个深读案例确认）

| 实例 | skill | 代码 | 一句话理由 |
|---|---|---|---|
| astropy-13033 | code-review-and-quality | F1 | 语义正确，但错误消息措辞与精确断言不符 |
| matplotlib-23299 | test-driven-development | F2 | 改 switch_backend，测试走 rc_context 直接赋值 |
| sympy-13798 | python-pro | F3 | 漏 mul_symbol_latex_numbers 的空白类回退 dot |
| django-12273 | django-patterns | F3 | 只处理新增对象，漏已有对象重置 pk 的分支 |
| django-16256 | django-tdd | F3 | 漏 contenttypes 的 generic manager 入口 |
| sympy-14248 | sympy | F1 | 三个 printer 的精确格式不符 |
| pytest-10356 | pytest-code-review | F1 | MRO 顺序反了 |
| requests-1724 | python-error-handling | F4 | 同 normalized patch 判定不同 |
| sklearn-14629 | sklearn-advanced | F2 | 修消费者 cross_val_predict，没补提供者 classes_ |
| sphinx-7985 | sphinx-docs | F1 | 存在文件返回 local，而非 working |
| astropy-13977 | verification-before-completion | F3 | 只包转换循环，缺协作对象守卫 |
| pylint-4970 | python-code-style | F2 | 停在计算层，显示层仍打印 TOTAL |

## 更多已编码锚例（同一判据，来自 50 条人工首过）

- `django-15252` F2：改 recorder，没改 executor 的空计划入口。
- `matplotlib-23476` F2：改 backend_bases 的 hasattr 守卫，没改 Figure.__getstate__。
- `pylint-8898`（不同 arm 可不同）：只处理转义逗号 → F3；把括号/花括号内逗号都保护、改变畸形正则错误文案 → F1。
- `pytest-10356` F1：reversed MRO 顺序与断言 [C,A,B] 不符。
- `sklearn-25747` F3：只在行数不等时置空 index，漏“输出已是 DataFrame”分支。
- `seaborn-3187`：只改 _core/scales.py → F3（漏 utils.py 入口）；把 offset 拼进标签文本 → F1（格式）。
- `sphinx-9461` F1：前缀写 classmethod，测试要 class property。
- `sympy-14976` F1：输出 mpf(1)/2，测试要 mpf(1)/mpf(2)。
- `django-16642` F1：常量 application/brotli，测试要 application/x-brotli。
- `matplotlib-23299`（python-anti-patterns）F3：只处理 auto sentinel，漏显式 backend 分支。
- `seaborn-3069` F3：无条件设置 nominal limits/反转 y，漏“用户显式 limit”分支。
- `sympy-18698` F3：合并逻辑排除 k==1，漏重数 1 的分支。
- `xarray-6992` F3：只改 reset_index 局部，漏 set_index/indexes/MultiIndex 路径。
- `django-15098` F3：正则只允许 2 字母/3 数字尾段，漏任意子标签。
- `matplotlib-20676` F2：改 add_artist 绕 autoscale，没改初始 positions。
- `sympy-11618` F1：契约读反，要求 sqrt(5) 却 raise ValueError。
- `xarray-6938` F3：在调用点 copy，漏转换 API to_index_variable 本身。
- `matplotlib-24870`：bool levels 只给 [0.5] → F3（漏 filled 三边界）；只改 contour.py → F3（漏 tri/_tricontour.py）。
- `sphinx-9658` F2：改 restify 消费者，没修 mock 的 __name__ 链路。
- `sphinx-8638` F2：改 find_obj 解析器，没改变量字段自身的 rolename。
- `xarray-3993` F1：warning 类型（Deprecation vs Future）与互斥参数契约不符。

## 输出

写一个 UTF-8 CSV 到指定路径，表头固定：

```csv
row_id,instance,skill,main_cause,secondary_cause,confidence,evidence
```

- `main_cause`：F1/F2/F3/F4/U；
- `secondary_cause`：一句话或空；
- `confidence`：high/medium/low；
- `evidence`：一句话，必须指出**具体补丁行 / 函数 / test 断言**，不要只抄 B evidence；
- 每条一行，row_id 按输入顺序全部覆盖。

## 纪律

1. **不要按 B 标签填**。B 的 `wrong_fix` 只有 56/183 是 F1，`incomplete_patch` 只有 90/161 是 F3，`wrong_location` 只有 34/63 是 F2。
2. **不要因为局部测试通过就判对**：要以 F2P 对应的 test_patch 断言为准。
3. **不确定就写 U + low**，并在 evidence 写卡在哪；不要编造。
4. 同一实例不同 skill 的补丁不同，主因可以不同；按每条自己的补丁判。

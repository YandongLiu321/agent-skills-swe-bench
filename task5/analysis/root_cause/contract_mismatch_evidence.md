# 两个“语义正确但被判失败”的锚案例：14976 与 15252

> 这两个案例的价值不在于“模型又错了”，而在于：**补丁在 issue 语义上是对的，失败来自隐藏测试的实现契约**。这正是“现象 ≠ 原因”的最硬证据。
> 数据：`experiment_data/02_phase1_rescue_95/runs/` 的 10 个 skill 臂 + 数据集里的 `test_patch` / `reference_patch` + B 的最终标签。

## 1. SymPy 14976：7/10 的补丁在数值上已经修好，只是字符串不匹配

### 1.1 任务与判分

- issue：`lambdify(modules='mpmath')` 把 `232/3` 打印成 Python 浮点除法，`nsolve` 损失精度。
- gold（`sympy/printing/pycode.py`）：
  ```python
  def _print_Rational(self, e):
      return '{0}({1})/{0}({2})'.format(
          self._module_format('mpmath.mpf'), e.p, e.q)
  ```
- 正式测试（`sympy/printing/tests/test_pycode.py::test_MpmathPrinter`）：
  ```python
  assert p.doprint(Rational(1, 2)) == 'mpmath.mpf(1)/mpmath.mpf(2)'
  ```
- 这是**字符串相等**，不是数值比较。

### 1.2 十个臂的最终补丁

| skill | resolved | 最终写法 | 数值上是否修好 | patch 相似度 |
|---|---:|---|---:|---:|
| sympy | 1 | `'{0}({1})/{0}({2})'` | 是 | 0.962 |
| code-review-and-quality | 1 | 同上，字节级相同 | 是 | 0.962 |
| systematic-debugging | 1 | `'{0}({1})/{0}({2})'`（空行不同） | 是 | 0.866 |
| python-project-structure | 0 | `'{}({})/{}'`（只包分子） | **是** | 0.943 |
| debugging-and-error-recovery | 0 | `'{0}({1})/{2}'`（只包分子） | **是** | 0.861 |
| python-anti-patterns | 0 | `'{0}({1})/{2}'`（只包分子） | **是** | 0.855 |
| python-error-handling | 0 | `'{0}({1})/{2}'`（只包分子） | **是** | 0.846 |
| python-pro | 0 | `'{func}({p})/{q}'`（只包分子） | **是** | 0.853 |
| test-driven-development | 0 | `'{0}({1})/{2}'`（只包分子） | **是** | 0.632 |
| verification-before-completion | 0 | `'({func}({p})/{func}({q}))'`（两端都包，但多一层括号） | **是** | 0.699 |

关键事实：

- **7/10 的补丁在 issue 语义上是修好的**：`mpmath.mpf(232)/3` 在 mpmath 精度下做除法，和 `mpmath.mpf(232)/mpmath.mpf(3)` 数值等价；失败的臂自行执行了 `nsolve(prec=64)`，拿到 64 位精度（见 `case14976_pps_digest.txt` [69]）。
- 官方日志给出更硬的证据：**7 个失败臂的 `test_output.txt` 全部显示 `test_nsolve_rational ok [OK]`，且全部只失败 `test_MpmathPrinter` 的 `assert p.doprint(Rational(1, 2)) == 'mpmath.mpf(1)/mpmath.mpf(2)'`**。也就是说，这些补丁通过了正式测试里的**数值行为测试**，只输在**字符串表示测试**。这不是“补丁没修好”，而是测试同时包含行为断言和表示断言，表示断言是唯一的分界。
- 失败只发生在 `p.doprint(Rational(1, 2))` 的**返回字符串**上：`mpmath.mpf(1)/2` ≠ `mpmath.mpf(1)/mpmath.mpf(2)`。
- 两个成功臂（`sympy` / `code-review-and-quality`）的补丁**字节级相同**，相似度 0.962；它们与失败臂的差别只是格式串的一个字段。
- 更值得注意的是失败臂的推理：`python-project-structure` 在 [25]/[28]/[40] **三次写出正确形式**，又三次根据“我记得测试是 `mpmath.mpf(1)/2`”改回短形式（`case14976_pps_digest.txt` [25]–[40]）。成功臂也承认自己是靠记忆召回 upstream patch，而不是从仓库证据推出（`case14976_sympy_digest.txt` [26]–[33]）。
- 因此这个实例的 success/failure 更像**记忆召回的变体**，不是“哪个 skill 更好”。`sympy` 这个 skill 文本并没有教 `_print_Rational`；它改变的是模型调用先验的方向。

## 2. Django 15252：5/5 按“改哪个文件”完全分开

### 2.1 任务与判分

- issue：`MigrationRecorder` 不遵守 `db_router.allow_migrate`，在非 default 连接上创建 `django_migrations` 表。
- gold（`django/db/migrations/executor.py`）：
  ```python
  # The django_migrations table must be present to record applied
  # migrations, but don't create it if there are no migrations to apply.
  if plan == []:
      if not self.recorder.has_table():
          return self._create_project_state(with_applied_migrations=False)
  else:
      self.recorder.ensure_schema()
  ```
- 正式测试有两项：
  1. `test_migrate_test_setting_false_ensure_schema`：`@mock.patch('django.db.migrations.executor.MigrationRecorder.ensure_schema')`，然后 `assert_not_called()`；
  2. `test_migrate_skips_schema_creation`：mock `has_table=False`，`executor.migrate([], plan=[])`，`assertNumQueries(0)`。
- 两项检查的都是**调用点有没有被调用**，不是“router 不允许时表有没有被创建”。

### 2.2 十个臂的最终补丁与结果

| skill | resolved | 改的文件 | 做法 | 语义上是否修好 issue |
|---|---:|---|---|---:|
| django-patterns | 1 | `executor.py` | 按 router 过滤 plan，空/不允许则跳过 `ensure_schema` | 是 |
| django-perf-review | 1 | `executor.py` | 逐 operation 判断 router，重写记录逻辑 | 是 |
| django-security | 1 | `executor.py` | `_migratable()` 检查 `State`，不允许则直接返回 | 是 |
| systematic-debugging | 1 | `executor.py` | 按 plan 的 app 与历史 state 判断，空 plan 早返回 | 是 |
| verification-before-completion | 1 | `migrate.py` + `executor.py` | 先过滤 plan，再套 gold 的 `plan == []` 分支 | 是 |
| debugging-and-error-recovery | 0 | `recorder.py` | `ensure_schema` 里查 router，不允许就 return | **是** |
| django-access-review | 0 | `recorder.py` | `record_applied`/`record_unapplied`/`ensure_schema` 查 `Migration` 模型 | **是** |
| django-tdd | 0 | `recorder.py` | `ensure_schema` 查 `Migration` 模型，记录前查 `has_table` | **是** |
| django-verification | 0 | `recorder.py` | `ensure_schema` 查所有注册模型，记录前查 `has_table` | **是** |
| test-driven-development | 0 | `recorder.py` | `get_migratable_models` 检查，记录前查 `has_table` | **是** |

**完美分层**：5 个改 `executor.py` 的全过，5 个只改 `recorder.py` 的全挂（verification 是混合，但也改了 executor）。这不是“能力”分层，而是“测试 mock 的是哪个方法”的分层。

### 2.3 为什么 recorder 修复语义上是对的

以 `django-access-review` 为例：

```python
def ensure_schema(self):
    if self.has_table():
        return
    if not router.allow_migrate_model(self.connection.alias, self.Migration):
        return
    ...
```

在 issue 描述的场景（router 对非 default 全部返回 False）下，`ensure_schema` 直接 return，表不会被创建；`record_applied` 也在 router 不允许时 return。**issue 要的行为已经实现。**

但正式测试测的不是这个场景。`test_migrate_test_setting_false_ensure_schema` 走的是 `TEST['MIGRATE'] = False` 的 `create_test_db` 路径：**没有 router**，`plan=[]`，executor 仍然调用 `ensure_schema`。在这个场景下，recorder 的 router 检查会返回 True（没有 router 阻止），所以即使不 mock，它也会建表；它只覆盖了 issue 的 router 场景，没有覆盖测试的空 plan 场景。

因此 15252 的失败是两层叠加：

1. **场景错位**：issue 讲 router，正式测试讲 `TEST MIGRATE=False` / 空 plan；recorder 修复对前者正确，对后者不够。
2. **调用点契约**：正式测试 mock `ensure_schema` 并 `assert_not_called()`，即使 recorder 修复在某个场景下行为正确，只要 executor 还调用它，测试也会失败。

所以不能说“5 个 recorder 臂完全等价、只是测试苛刻”；它们是“对 issue 正确、对测试场景不完整”。但同样不能说“测试正确测量了 issue 要求的行为”——它没有测 router，测的是空 plan。

### 2.4 官方日志的直接证据

DER 臂的 `test_output.txt` 显示：

```text
FAIL: test_migrate_test_setting_false_ensure_schema
AssertionError: Expected 'ensure_schema' to not have been called. Called 1 times.
Calls: [call()].
```

第二条测试更说明问题：

```text
ERROR: test_migrate_skips_schema_creation
sqlite3.OperationalError: table "django_migrations" already exists
...
django.db.migrations.exceptions.MigrationSchemaMissing:
Unable to create the django_migrations table (table "django_migrations" already exists)
```

`test_migrate_skips_schema_creation` 把 `has_table` mock 成 `False`，但测试数据库里表其实已经存在；任何仍调用 `ensure_schema()` 的实现都会走到 `create_model` 并撞上“table already exists”。这不是“行为不对”，而是**测试用不一致的 mock 强制要求调用点不执行**。官方报告同时显示 PASS_TO_PASS 全部通过，只有这两项 FAIL_TO_PASS 失败；所以 recorder 臂并没有破坏既有行为。

**5 个 recorder 臂的官方日志完全一致**：每个都出现 1 次 `Expected 'ensure_schema' to not have been called`、1 次 `ERROR: test_migrate_skips_schema_creation`、以及 `table "django_migrations" already exists`。这不是单条轨迹的偶然，而是同一个测试契约对 5 个语义正确实现的系统性拒绝。

## 3. 计数与边界

- 14976：**7/10** 补丁在数值上修好，判失败；其中 6 个只差分母的包装，1 个多一层括号。这是**纯表示契约**（issue 行为已实现）。
- 15252：**5/10** 补丁对 issue 的 router 场景正确，判失败；分层完全由“改 recorder 还是改 executor”决定。但正式测试测的是无 router 的 `TEST MIGRATE=False` / 空 plan 场景，recorder 修复对这个场景本身也不够。这是**场景错位 + 调用点契约**，不是纯表示契约。
- 两个案例合计：**12/20 条在 issue 语义下正确但测试判失败**。其中 14976 的 7 条是纯表示契约，15252 的 5 条是对 issue 正确、对测试场景不完整。这不是总体比例，只是两个锚案例的计数。

### 不能外推的证据

- 20916：失败臂只把字母类改成 Unicode，数字类仍是 `[0-9]`；正式测试含 `w𝟙`（U+1D7D9），**这是真的行为缺口**。
- 13798：失败臂只改 `mul_symbol_latex`，没改 `mul_symbol_latex_numbers`；正式测试覆盖 `mul_symbol='\\,'` 与数字相乘，**这是真的分支遗漏**。
- 11848：失败臂用 `datetime.now()`，gold 用 `utcnow()`；测试 mock 了 `utcnow`，**这是真的时区/契约错误**（虽然只差一个词）。
- 14771：失败臂把 bare flag 写成 `-Xkey=True`，gold 是 `-Xkey`；**这是真的参数格式错误**。

所以“接近 gold”≠“语义正确”。必须逐条读 test_patch 才能判断。

## 4. 对标签体系的直接影响

`wrong_location` / `incomplete_patch` / `wrong_fix` 是**现象标签**，描述补丁与 gold/test 的关系，不是原因。至少要把下面两类分开：

1. **行为缺口**：issue 要求的行为没实现（20916、13798、11848、14771）；
2. **契约缺口**：issue 行为已实现，但隐藏测试要求特定的调用点/字符串/内部状态（14976、15252；15127 是混合）。

对第 2 类，把失败写成“模型能力不足”是错的；它更接近 **benchmark 构念效度**问题。报告应把它放进“效度威胁”，而不是简单并进 437 条失败率。

### 39 条 near-gold 审计：已完成

- 从 437 条失败里，按“同文件 + patch 文本相似度 ≥0.8”抽出 39 条（14 wrong_fix + 25 incomplete_patch；wrong_location 0 条），逐条读 `test_patch`、gold 与官方日志。
- 结果：**25 条行为缺口（B）、12 条契约/表示缺口（C）、2 条 B/C 混合**；其中 9 条有官方断言/高置信，26 条为中置信的 patch/test 阅读，4 条未独立评定。也就是 near-gold 主要是真实缺陷，不能一律重标为假阴性。
- 12 条 C 中 5 条来自 14976（精确字符串）；另外 7 条是 14155（route 缺引号）、21568（`\ ` vs `\;`）、14534×4（`auto_id=False` 返回 None 的未说明边界）、10356×1（generator vs list 的返回类型）。14534 的 2 个 `['id']` 臂按 B/C 混合算。
- 选择偏差：15252（file Jaccard 0）和 14976 的 2 条低相似度失败不在这 39 条里；加上两个锚案例，已知契约缺口至少 **19 条**（12 条锚案例 + 7 条新增），这是**下界**，不是 437 条的总体比例。
- 随机对照：从三个主标签各抽 10 条（共 30 条，seed 20261031）做初筛，得到 **29 B / 1 C**；契约缺口占 1/30 = 3.3%（95% CI [0.6%, 16.7%]），低于 near-gold 的 30.8%（[18.6%, 46.4%]）。按 run 的区间不重叠（16.7% < 18.6%），但 30 条 run 只来自 25 个实例，按实例算 C = 1/25 = 4.0%（[0.7%, 19.5%]），与 near-gold 下界重叠；所以只能说明 near-gold 富集契约缺口，不能给出总体精确比例。详见 `random_sample_30.md`。
- 完整逐条表见 `near_gold_audit.md` 与 `near_gold_audit/near_gold_audit.csv`。

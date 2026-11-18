# Case 2：Django 15252 —— 题面点名了 recorder，正确修法在 executor

> 样本：`django__django-15252`，同题 10 个 skill 臂，5 成功 / 5 失败。
> 本卡读两条轨迹：`debugging-and-error-recovery`（失败，wrong_location）与 `django-patterns`（成功）。
> 官方报告、补丁与测试输出均已核对（`experiment_data/02_phase1_rescue_95/eval_logs/`）。

## 1. 现象

10 个臂**按修改文件完全分层**：5 个仅修改 `django/db/migrations/recorder.py` 的臂全部失败；5 个修改 `django/db/migrations/executor.py` 的臂全部成功（其中 `verification-before-completion` 还修改了 `migrate.py`）。

正式测试的失败项：

```text
test_migrate_test_setting_false_ensure_schema (backends.base.test_creation.TestDbCreationTests)
The django_migrations table is not created if there are no migrations
```

测试的实现是：

```python
@mock.patch('django.db.migrations.executor.MigrationRecorder.ensure_schema')
def test_migrate_test_setting_false_ensure_schema(self, mocked_ensure_schema, ...):
    test_connection.settings_dict['TEST']['MIGRATE'] = False
    creation.create_test_db(...)
    mocked_ensure_schema.assert_not_called()
```

第二条测试 `test_migrate_skips_schema_creation` 更直接：

```python
@mock.patch.object(MigrationRecorder, 'has_table', return_value=False)
def test_migrate_skips_schema_creation(self, mocked_has_table):
    executor = MigrationExecutor(connection)
    with self.assertNumQueries(0):
        executor.migrate([], plan=[])
```

两项检查的都是**调用点有没有被调用**，不是“router 不允许时表有没有被创建”。官方日志直接给出了两条证据：

```text
FAIL: test_migrate_test_setting_false_ensure_schema
AssertionError: Expected 'ensure_schema' to not have been called. Called 1 times.
Calls: [call()].
```

```text
ERROR: test_migrate_skips_schema_creation
sqlite3.OperationalError: table "django_migrations" already exists
...
MigrationSchemaMissing: Unable to create the django_migrations table
```

第二条测试把 `has_table` mock 成 `False`，但表实际存在；任何仍调用 `ensure_schema()` 的实现都会撞上“table already exists”。这不是行为错误，而是测试用不一致的 mock 强制要求调用点不执行。

现象标签是 `wrong_location`；5/5 的分层说明它描述的是“修改的文件与测试 mock 的调用点不同”，不能直接读成“recorder 修复在语义上错了”。recorder 修复对 issue 的 router 场景是对的，只是对测试的空 plan 场景不够。

## 2. Issue 文本把 agent 引向哪里

Issue 标题：

> MigrationRecorder does not obey db_router allow_migrate rules

正文的关键句：

> When this migrate runs, it tries to apply our migrations, which tries to record that a migration has been applied (see `django/db/migrations/executor.py`, `apply_migration`...). The first thing that `record_applied` does is a call to `self.ensure_schema()` (see `django/db/migrations/recorder.py`, `record_applied`...).
>
> I believe that this is incorrect behaviour when a db_router has been provided... Looking at the other methods on the `MigrationRecorder`, I would expect that there will be similar issues with `applied_migrations` and `record_unapplied`.

题面**反复点名 `MigrationRecorder` / `recorder.py` / `ensure_schema`**，并建议去看 recorder 的其他方法。它描述的是“表在错误的连接上被创建”这个**现象**，但没有说“应该在哪个控制流层级阻止这次创建”。

更关键的是，正式测试走的不是 issue 的 router 场景：`TEST['MIGRATE'] = False` 的 `create_test_db` 路径**没有 router**，`plan` 为空；它测的是“空 plan 不建表”，不是“router 不允许不建表”。因此，一个完全按 issue 修 recorder 的补丁，在这个测试场景下既不会阻止建表（没有 router 可查），也仍然会被 executor 调用 `ensure_schema`（mock 记录到调用）。这是**场景错位 + 调用点契约**，不完全是 agent 的理解错误。

## 3. 两个补丁

失败（`debugging-and-error-recovery`）改 `recorder.py`：

- 新增 `_allowed_to_migrate()`：检查 `router.allow_migrate_model(alias, self.Migration)`，或任一 app 的模型被允许；
- `ensure_schema()` 在 router 不允许时提前返回；
- `record_applied()` / `record_unapplied()` 在表不存在时跳过记录。

成功（`django-patterns`）改 `executor.py`：

- 新增 `_migrations_allowed(plan)`：遍历 plan 中的 migration，用 `router.allow_migrate` / `allow_migrate_model` 判断是否有任何一条允许执行；
- `migrate()` 在 `self.recorder.ensure_schema()` 之前先判断：**如果 plan 里没有任何允许的 migration，就清空 plan，不调用 `ensure_schema()`**；
- 这样表根本不会被创建，而不是“创建后在 recorder 里再判断”。

关键差别：失败补丁把门放在**被调用方**（recorder），成功补丁把门放在**调用方**（executor 的控制流）。

## 4. 失败轨迹的决策点

- [16]：agent 回忆 upstream fix，方向已经是 `recorder.py`；
- [17]：它其实读了 `executor.py`，看到 `migrate()` 里无条件调用 `self.recorder.ensure_schema()`；
- [102]：它明确考虑过“把检查放到 executor”，但写下“`ensure_schema` is the natural place”，选择 recorder；
- [108]：它把“能同时通过现有测试和隐藏测试”作为选择标准，认为 recorder 里的“any model”门最安全；
- [116]：这个方案会破坏一个现有测试，它继续调 recorder，而不是回到 executor 的控制流；
- 最终 patch 仅修改 `recorder.py`。

根因不是“未阅读代码”，而是：

1. **题面锚定**：issue 标题和正文反复点名 `MigrationRecorder` / `recorder.py`，agent 把“名字”当成了“位置”；
2. **修在现象发生处，而不是动作发起处**：表是在 `executor.migrate()` 里被 `ensure_schema()` 创建的；recorder 只是被调用方。仅修改 recorder，无法阻止 executor 在 plan 为空/不允许时仍然发起这次调用；
3. **用“现有测试全过”替代“正式要求”**：[108] 的“最安全”标准是现有测试 + 自己模拟的隐藏测试，而不是正式测试的 `assert_not_called()` / 零查询；
4. **没有把 issue 的期望翻译成控制流问题**：issue 说“other 连接不应创建表”，正确问法是“谁在什么时候调用 ensure_schema，应在哪一层拦住”；agent 问成了“ensure_schema 内部要不要判断 router”；
5. **任务/测试侧的独立因素**：issue 讲 router，正式测试讲 `TEST MIGRATE=False` / 空 plan；两者不是同一个场景。agent 即使完美实现 issue，也不满足测试的场景和调用点断言。这一条不能写成 agent 的推理错误。

## 5. 成功轨迹的关键做法

- [303]：直接修改 `executor.py`，新增 `_migrations_allowed(plan)`，在 `ensure_schema()` 之前判断；
- [341] / [381]：它比较过 `create_test_db` 作用域、recorder 门、executor 门三种方案，最终选 executor，因为它直接对应“plan 里没有允许的 migration 就不建表”；
- [372]：执行完整的 `migrations` 测试集（2028 项）进行验证，而不只是执行自己的复现脚本。

注意：成功臂也没有看到正式测试；它的 `_migrations_allowed(plan)` 对空 plan 返回 `False`，所以顺带满足了 `plan=[]` 的测试。这是**通用 router 修复覆盖了测试场景**，不是它预测了测试。它在 [341]/[381] 也明确比较过 recorder 门、create_test_db 作用域、executor 门三种方案，最终选 executor 是因为它更接近“谁发起动作”。

## 6. 因果链

| 现象 | 直接原因 | 根本原因 | 证据 | 干预点 |
|---|---|---|---|---|
| wrong_location（DER） | 仅修改 `recorder.py`，executor 仍在 plan 为空/不允许时调用 `ensure_schema` | 题面点名 recorder → 锚定被调用方；修在现象发生处而非动作发起处；issue 的 router 场景与测试的空 plan 场景错位；测试断言调用点 | [16] [17] [102] [108] [116]；失败 patch；官方失败测试 | 先问“谁发起了这个动作”，再问“在调用方还是被调用方拦”；区分“修 issue 场景”和“修测试场景” |
| 成功（django-patterns） | 在 `executor.migrate()` 里先判断 plan，再决定是否 `ensure_schema` | 找到控制流层级，直接阻止建表动作 | [303] [341] [372] [381]；成功 patch | 同上 |

## 7. 一个重要的反例

同一个 `systematic-debugging` skill 在 15127 失败，在 15252 **成功**。所以不能把结果简单归因于“skill 好坏”；更稳定的解释是：**题面结构 + agent 对正式契约的模型 + 它选择在哪一层修**。15252 的题面明确点名了错误组件，15127 的题面只给了症状；两个案子的“现象→原因”链不同。

## 8. 对 Skill 的改进（可写进 7.8）

1. **不要跟着 issue 点名的类走**：先找“动作是在哪里发起的”，再决定改调用方还是被调用方。
2. **把 issue 的期望翻译成控制流条件**：例如“other 连接不应建表” → “在 plan 为空或没有允许的 migration 时，不要调用 `ensure_schema`”。
3. **区分“现象发生处”和“动作发起处”**：`ensure_schema` 是现象发生处，`executor.migrate` 是动作发起处。
4. **不要用“现有测试全过”替代正式要求**：现有测试可能根本不覆盖新契约；要读正式测试的断言或 issue 的期望。
5. **优先实现能覆盖 issue 与测试两个场景的通用控制流修复**：例如“plan 为空”和“plan 非空但没有允许的 migration”都跳过 `ensure_schema`。15252 的成功臂正是用这种通用修复顺带覆盖了测试的空 plan 场景；如果只修 issue 的 router 场景，就会漏掉测试。

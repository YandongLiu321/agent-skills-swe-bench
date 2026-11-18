# 用数据集里的 test_patch / reference_patch 反查

> 这是比“读轨迹”更硬的一层：直接读 `experiment_data/07_full_task_eval/完整题目与运行材料/` 里每个实例的 `test_patch`（正式测试）和 `reference_patch`（gold 修法），看失败臂到底错在“行为”还是“实现契约”。

## 1. 五个案例的对照

| 案例 | test_patch 要求 | reference_patch 做什么 | 失败臂做了什么 | 结论 |
|---|---|---|---|---|
| Django 15127 | 新增 `test_override_settings_level_tags`：`assertEqual(base.LEVEL_TAGS, self.message_tags)`；同时删除 test helper、改用 plain `override_settings` | 在 `django/contrib/messages/apps.py` 的 `MessagesConfig.ready()` 里连接 `setting_changed`，`MESSAGE_TAGS` 变化时 `base.LEVEL_TAGS = get_level_tags()`；**保留变量并更新** | DER：删除 `LEVEL_TAGS` + 动态读取；SD：保留变量但只让 `level_tag` 动态读取，不更新变量 | DER 版本错位（删了 gold 要保留的变量）；SD 只修读取方；security 的“保留 + 信号”与 gold 同族 |
| Django 15252 | 新增 `test_migrate_test_setting_false_ensure_schema`：mock `MigrationRecorder.ensure_schema`，断言 `assert_not_called()` | `executor.py`：`if plan == []: if not recorder.has_table(): return ...; else: recorder.ensure_schema()`；**在调用方阻止调用** | DER：在 `recorder.py` 里加 `_allowed_to_migrate` 并让 `ensure_schema` 早返回；但 `executor` 仍然**调用**了 `ensure_schema` | 测试检查“有没有调用”，不是“被调用方做了什么”；失败臂修在被调用方，mock 仍记录到调用 → 必败 |
| SymPy 14976 | `assert p.doprint(Rational(1, 2)) == 'mpmath.mpf(1)/mpmath.mpf(2)'` | `_print_Rational` 用 `'{0}({1})/{0}({2})'`（分子分母都包） | 失败臂只包分子 `'{}({})/{}'` | 测试是精确字符串；失败臂行为上可能够用，但契约不完整 |
| SymPy 20916 | 新增 `split_super_sub("w𝟙")`、`"w𝟙𝟙"`、`"ω𝟙^α"` 等 Unicode 输入 | `^([^\W\d_]+)(\d+)$` + `re.U`（字母和数字都用 Unicode） | 失败臂 `^([^\W\d_]+)([0-9]+)$`（数字仍是 ASCII） | 只修复合模式的一半；测试覆盖 `𝟙`（U+1D7D9），失败臂不匹配 |
| SymPy 13798 | `latex(3*x**2*y, mul_symbol='\\,') == r"3\,x^{2}\,y"`；`latex(1.5*3**x, ...) == r"1.5 \cdot 3^{x}"` | `mul_symbol_latex_numbers` 在自定义符号为空白/`\,` 等时回退到 `dot`；否则用自定义符号 | 失败臂只处理了 `mul_symbol_latex`，没有处理 `mul_symbol_latex_numbers` 的空白回退 | 同一设置的两个分支，只改了一个 |

## 2. 对 15127 的重新定性

之前写“版本错位的记忆 + 循环验证”，现在有 gold patch 直接证据：

- gold 明确**保留** `LEVEL_TAGS`，并在 `apps.py` 里用 `setting_changed` 更新；
- test 直接断言 `base.LEVEL_TAGS` 等于 `message_tags`；
- DER 的“删除变量 + 动态读取”在**用户可见行为**上修好了 issue，但违反 test 对模块变量的要求；
- SD 的“保留 + 动态读取但不更新”两边都不满足；
- security 的“保留 + 信号”与 gold 同族，通过。

所以 15127 的根因要拆成两层：

1. **模型侧**：DER 用了后续 Django 版本的修法；SD 在两个契约之间选了“测试安全”的中间方案；
2. **测试侧**：test 断言的是**实现细节**（`base.LEVEL_TAGS` 这个模块变量），不是 issue 里用户可见的 `Message.level_tag`。一个只修 `level_tag` 的动态读取方案在 issue 层面是合理的，但会被 test 判失败。

这不是给模型开脱：gold 的修法可以从 test helper（`override_settings_tags` 显式更新 `base.LEVEL_TAGS`）和 gold 的 `apps.py` 信号模式推出来；但**测试确实比 issue 更具体**，报告应把它列为效度因素，而不是只写“模型记忆错”。

## 3. 对 15252 的重新定性

test 用 `mock.patch('...MigrationRecorder.ensure_schema')` + `assert_not_called()`，检查的是**调用有没有发生**，不是“表有没有被创建”。因此：

- 失败臂在 recorder 里加 `_allowed_to_migrate`、让 `ensure_schema` 早返回，**行为上可能不建表**，但 executor 仍然调用了 `ensure_schema`，mock 记录到调用 → test 失败；
- gold 在 `executor.migrate()` 里先判断 `plan == []`，**根本不调用** `ensure_schema`。

这使“修在调用方还是被调用方”的根因更硬：**test 检查的是调用点，不是被调用方的行为**。失败臂即使把 recorder 改得行为正确，也过不了这个 mock 断言。

同样，test 比 issue 更具体，而且场景不同：issue 说“router 不允许时不要创建表”，test 走的是 `TEST MIGRATE=False` / 空 plan（无 router），并说“不要调用 `ensure_schema`”。官方日志显示 recorder 臂的 PASS_TO_PASS 全过，只有两项 FAIL_TO_PASS 失败：一项是 `Expected 'ensure_schema' to not have been called`，另一项因 mock `has_table=False` 而表实际存在，报 `table "django_migrations" already exists`。报告应把“场景错位 + 调用点实现耦合”列为效度因素。

## 4. 对 14976 / 20916 / 13798 的定性

- 14976：test 是精确字符串；失败臂只包分子。test 与 issue 的行为一致，但把表示层收紧为精确字符串；失败是**表示契约**，不是行为缺口——官方日志显示失败臂的 `test_nsolve_rational` 通过（`ok [OK]`），只有 `test_MpmathPrinter` 失败。
- 20916：test 覆盖 `w𝟙`、`ω𝟙^α` 等 Unicode 输入；gold 用 `\d+` + `re.U`；失败臂只改字母类。test 与 issue 的“Greek letters 下标”一致（甚至更宽），失败是真实的半修。
- 13798：test 覆盖自定义 `mul_symbol='\\,'` 与数字相乘；gold 在 `mul_symbol_latex_numbers` 里对空白符号回退 `dot`；失败臂只改 `mul_symbol_latex`。test 与 issue 的“自定义乘号”一致，失败是真实的分支遗漏。

## 5. 方法论结论

**只读轨迹不够，必须读 test_patch 与 reference_patch。** 轨迹能告诉你 agent 怎么想；test/gold 能告诉你它被什么标准判错。两者结合，才能区分：

- **模型侧原因**：版本错位、记忆先验、修改层级错误、部分修改、忽略证据；
- **测试侧原因**：实现耦合断言（15127 的模块变量、15252 的 mock 调用）、比 issue 更具体的输入空间（20916 的 Unicode 数字）；
- **任务侧原因**：issue 只给症状、不给实现契约（15127、15252）。

报告 4.5 的根因表应加一列“测试契约”，并把“测试侧/任务侧”作为独立因素，不能全部写成模型推理错误。

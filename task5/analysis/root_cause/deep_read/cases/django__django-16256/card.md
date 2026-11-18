# django__django-16256 — 多入口漏改：issue 只点名一个文件

- 交叉实例：仅 `django-access-review`、`django-security` 通过（n_resolved=2），phase2。
- 深读臂：失败 `django-tdd`（B 标签 incomplete_patch）；成功 `django-security`。

## 1. 题目与正式契约

Issue：`acreate()`、`aget_or_create()`、`aupdate_or_create()` 通过 related manager 调用时，错误地走了 QuerySet 的实现；需要给 related manager 加正确的 async 版本。Issue 的 diff 片段只点名 `django/db/models/fields/related_descriptors.py`。

Gold patch 实际覆盖 **3 个 manager 工厂、2 个文件**：
1. `django/db/models/fields/related_descriptors.py::create_reverse_many_to_one_manager`（反向外键）；
2. 同文件 `create_forward_many_to_many_manager`（多对多）；
3. `django/contrib/contenttypes/fields.py::create_generic_related_manager`（GenericRelation）。

正式测试覆盖三处：
- `tests/async/test_async_related_managers.py`：M2M + reverse FK 的 acreate/aget_or_create/aupdate_or_create；
- `tests/generic_relations/tests.py`：generic relation 的 acreate/aget_or_create/aupdate_or_create。

## 2. 失败臂：django-tdd

### 轨迹（约 54 步）

- msg 2–20：读 `related_descriptors.py`、`query.py`、`tests/async/`；理解 related manager 继承了 QuerySet 的 async 方法。
- msg 23–25：**只修改 `django/db/models/fields/related_descriptors.py`**，给 reverse FK 和 M2M 两个 manager 加 async 方法 + `sync_to_async` import。
- msg 30–42：临时在 `tests/async/models.py` 加 M2M 模型、写临时测试，9 个测试全过；`git stash` 验证无修复时 6 failures + 2 errors。
- msg 44–54：跑 `async`、`basic.tests.ManagerTest`、`many_to_many`、`reverse_lookup`，通过；清理临时测试；提交。

### 最终补丁

只改 `related_descriptors.py`，没有改 `django/contrib/contenttypes/fields.py`。

### 官方结果

`generic_relations` 的 async 测试失败；resolved=0（B 标签 incomplete_patch）。

### 原因编码

- **主因：多入口漏改**。同一个接口在 3 个 manager 工厂里各有一份实现；它只修了 issue diff 点名的文件。
- 次因：**自测覆盖的是“issue 提到的入口”**。它自写的 9 个测试覆盖 reverse FK + M2M，正好是它改过的两处；没有测 generic relation。
- 这不是“修错位置”，而是“覆盖不全”：修的地方是对的，但漏了同模式的第三个入口。

## 3. 成功臂：django-security

### 轨迹（约 118 步）

- msg 2–20：同样先读 `related_descriptors.py`、`query.py`、`tests/async/`。
- msg 31–38：**主动检查 `django/contrib/contenttypes/fields.py`**，发现 `GenericRelatedObjectManager` 也有同样的 `create/get_or_create/update_or_create`。
- msg 38 的关键推理：
  > “The PR description only mentions the two locations in `related_descriptors.py`. But for consistency, `GenericRelatedObjectManager` also has the same issue.”
- msg 48–67：修改两个文件、三个 manager 工厂。
- msg 69–79：写独立验证脚本，覆盖 FK、M2M、generic relation；确认三种都通过。
- msg 81–99：跑 `async`、`basic`、`contenttypes_tests`、`many_to_many`、`many_to_one`、`generic_relations`、`reverse_lookup`、`m2m_*` 等。
- 提交，pass。

### 原因编码（成功侧）

- **主因：模式泛化**。不只修 issue 点名的文件，而是搜索“同一接口的所有实现”，把 generic relation 入口补上。
- 次因：验证脚本显式覆盖三类关系（FK / M2M / generic），所以能自己发现遗漏。

## 4. Skill 文本的作用（低）

- `django-tdd` 强调先写失败测试；失败臂确实写了 9 个测试，但测试只覆盖它已经想到的入口。
- `django-security` 与“多入口枚举”没有直接关系。
- 决定性的行为是**是否把 issue 的 “e.g.” 当成“全部入口”**，不是 skill 文本。

## 5. 可迁移假设

1. **“e.g.” 陷阱**：issue 用 `e.g.` / 示例文件给出一个位置时，成功者会枚举同一接口的所有实现；失败者只修示例。
2. **多入口的判据**：同一组方法名（`create/get_or_create/update_or_create`）出现在多个 manager 工厂/模块时，要全部覆盖。
3. **自测要按“接口”而不是按“已改文件”组织**：否则测试会复制修复的盲区。

## 6. 证据位置

- issue / gold / test_patch：bundle.txt 第 7–325 行。
- 失败轨迹索引：`index_fail.txt`；成功轨迹索引：`index_success.txt`（关键推理在 msg 38）。
- 失败补丁：轨迹最后一条 exit 消息（只改 `related_descriptors.py`）。
- 成功补丁：轨迹最后一条 exit 消息（改 `contenttypes/fields.py` + `related_descriptors.py`）。

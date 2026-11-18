# django__django-12273 — 只处理“新增”，没处理“已有对象重置 pk”

- 交叉实例：4 个 skill 通过（`debugging-and-error-recovery`、`test-driven-development`、`verification-before-completion`、`django-perf-review`），6 个失败；phase2（baseline 通过，6 个 skill 把它弄坏）。
- 深读臂：失败 `django-patterns`（B 标签 wrong_location，中置信）；成功 `debugging-and-error-recovery`。

## 1. 题目与正式契约

Issue：多表继承的子模型，把 pk 设为 None 后 save，期望“新建一行”，实际覆盖了原对象。
例子：`Derived(Item)`，`item.derived.reset()` 把 `uid=None`，`obj1.save()` 覆盖了原 Item。

Gold patch（`django/db/models/base.py::_set_pk_val`）：设置 pk 时，把值同步到所有 parent link 的 target field：
```python
for parent_link in self._meta.parents.values():
    if parent_link and parent_link != self._meta.pk:
        setattr(self, parent_link.target_field.attname, value)
```

正式测试（test_patch）两条：
1. `test_create_new_instance_with_pk_equals_none`：`p2.pk = None; p2.user_ptr_id = None; p2.save()`，断言 `Profile.count()==2` 且原 User 的 username 仍是 `john`。
2. `..._multi_inheritance`：`c2.pk = None; c2.id = None; c2.politician_ptr_id = None; c2.save()`，断言三层都新建、原对象不变。

## 2. 失败臂：django-patterns

### 轨迹（约 144 步）

- msg 2–23：读 `save_base`、`_save_parents`、`_save_table`、`_get_pk_val`；复现 bug。
- msg 25–38：找到旧 commit `6b4834952d`（“link fields are synced between parent and self”）和文档中 MTI 复制写法 `pk=None; id=None`。
- msg 97–117：在 `_save_parents` 的 sync 条件里加 `self._state.adding`：
  ```python
  if (field and self._state.adding and
          getattr(self, parent._meta.pk.attname) is None and
          getattr(self, field.attname) is not None):
      setattr(self, parent._meta.pk.attname, getattr(self, field.attname))
  ```
- msg 99–117：用自写 repro 验证“新对象”场景通过；跑 `model_inheritance`、`model_inheritance_regress`、大量 Django 测试；全量测试的 5F/18E 经 `git stash` 确认是环境 pre-existing。
- 提交。

### 最终补丁

只给 sync 条件加了 `self._state.adding`。对**已有对象**（`_state.adding=False`）重置 pk 的路径，这个条件直接把它排除，父 pk 和 link 都没有被清空，save 仍然走 UPDATE。

### 官方结果

resolved=0；两条 FAIL_TO_PASS 都失败（B 标签 wrong_location）。

### 原因编码

- **主因：状态转移不完整**。只处理“新增对象、父 pk 为空、link 非空”的方向；没有处理“已有对象、pk 或 link 被重置为空”的方向。
- 次因：**自测场景不覆盖正式测试的入口**。它的 repro 是 issue 的 `uid=None`（新对象路径），没有测 `p2.pk=None + user_ptr_id=None` 的已有对象复制路径。
- 标签“wrong_location”是粗口径：补丁其实还在 `_save_parents`，和成功臂同一个函数；真正的差别是**条件写反了方向**，不是函数选错。这说明 B 的标签只能当现象，不能当原因。

## 3. 成功臂：debugging-and-error-recovery

### 轨迹（约 255 步）

- 前面大量时间在找上游修复/隐藏测试（git 历史、pip cache、网络），没找到。
- msg 175–193：实现一个 broad 条件：
  ```python
  if field:
      parent_pk = getattr(self, parent._meta.pk.attname)
      if self._state.adding:
          if parent_pk is None:
              setattr(self, parent._meta.pk.attname, getattr(self, field.attname))
      elif parent_pk is None or getattr(self, field.attname) is None:
          setattr(self, parent._meta.pk.attname, None)
          setattr(self, field.attname, None)
  ```
- msg 177–193：用多组自写场景验证：issue repro、`both_none`、`child_pk_only`、nested inheritance。
- msg 199–250：分块跑大量 Django 测试（model_inheritance、model_forms、admin、serializers、forms 等），确认无新增失败。
- 提交，pass。

### 原因编码（成功侧）

- **主因：补全了状态转移的两个方向**。已有对象只要 parent pk 或 link 任一侧为 None，就同时清空两侧，强制 INSERT。
- 次因：**场景化自测**（both_none vs child_pk_only）发现了不对称重置。
- 注意：它也没采用 gold 的 `_set_pk_val` 方案，而是在 `_save_parents` 里做 broad clearing；测试通过，但实现与 gold 不同。这是“行为等价、位置不同”的另一种通过。

## 4. Skill 文本的作用（低到中）

- `django-patterns` 是架构/ORM 模式 skill，没有直接教“pk setter 要同步 parent links”。
- 成功臂的 `debugging-and-error-recovery` 强调复现/多场景验证，可能促成了 both_none vs child_pk_only 的对照。
- 决定性的仍是**是否想到“已有对象重置 pk”这个方向**，而不是 skill 文本。

## 5. 可迁移假设

1. **wrong_location 标签太粗**：同一函数内的条件方向错误也会被标成 wrong_location；框架要记录“具体是哪个状态转移没覆盖”。
2. **“新增”和“复制”是两条路径**：修 bug 时只测 issue 的新建路径，会漏掉已有对象的复制路径。
3. **对称性检查**：当一对字段（parent pk / parent link）必须同时为空才能触发 INSERT，要显式检查两侧。

## 6. 证据位置

- issue / gold / test_patch：bundle.txt 第 7–115 行。
- 失败轨迹索引：`index_fail.txt`；成功轨迹索引：`index_success.txt`。
- 失败补丁：轨迹最后一条 exit 消息（`_state.adding` 条件）。
- 成功补丁：轨迹最后一条 exit 消息（broad clearing）。

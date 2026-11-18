# sphinx-doc__sphinx-7985 — 新检查没有迁移旧状态契约

- 交叉实例：3 个 skill 通过（`test-driven-development`、`sphinx-build`、`sphinx-config`），7 个失败；phase1。
- 深读臂：失败 `sphinx-docs`（B 标签 incomplete_patch，高置信）；成功 `sphinx-build`。

## 1. 题目与正式契约

Issue：`linkcheck` 只检查外部链接，不检查本地（internal）链接；期望本地链接也检查。

Gold patch：
- 新增 `uri_re = re.compile('[a-z]+://')`。
- 对非 http 链接：
  - 匹配 URI scheme（如 `ftp:`）→ `unchecked`；
  - 本地文件存在 → `working`；
  - 否则查 ignore 规则 → `ignored` / `broken`。

正式测试：
- `test_defaults`：新增 `Example valid local file <conf.py>`（应静默通过）和 `Example invalid local file <path/to/notfound>`（应输出 `[broken] path/to/notfound`），行数 5→6。
- `test_anchors_ignored`：所有应忽略的链接 → **输出为空**。
- `test_defaults_json`：行数 8。

## 2. 失败臂：sphinx-docs

### 最终补丁

删掉旧的 `elif not http → 'local'`，改为：
```python
if not uri.startswith(('http:', 'https:')):
    filename = unquote(uri.split('#', 1)[0])
    ...
    if abspath is not None and path.exists(abspath):
        return 'local', '', 0          # <-- 关键错误
    else:
        info = __('local link not found')
        self.broken[uri] = info
        return 'broken', info, 0
```

### 官方结果

`test_anchors_ignored` 失败：期望空输出，实际仍有 `[local] conf.py`；部分应忽略的不存在路径也被报出。

### 原因编码

- **主因：状态契约不完整**。本地文件存在时应返回 `working`（静默），它返回 `local`，于是 `conf.py` 仍然被打印。
- 次因：**ignore 语义没有迁移**。旧代码在非 http 分支之前就返回 `local`，ignore 检查在它之后；新代码把本地检查插到 ignore 之后，但仍用 `local`，导致“存在但被 ignore”的路径也会输出。
- 这不是“没实现功能”：功能实现了，但**新状态没有对齐旧的输出契约**。

## 3. 成功臂：sphinx-build

### 最终补丁

新增 `check_local(docname, uri)` 方法，使用 `posixpath` / `docname_join` 解析相对路径，返回完整状态：
- 存在 → `working`；
- 不存在 → `broken`；
- 匹配 ignore → `ignored`；
- scheme 不支持 → `unchecked`。

### 原因编码（成功侧）

- **主因：把本地检查做成一个完整的状态机**，覆盖 `working/broken/ignored/unchecked` 四种结果，而不是只加一个 `local`。
- 次因：用 `docname_join` 解析相对路径，处理 `#anchor` 和目录链接。

## 4. Skill 文本的作用（低）

- 专用 `sphinx-docs` 失败，`sphinx-build` 成功；两者都是 sphinx 专用 skill，说明不是“领域知识多少”的问题。
- 决定性的问题是**新功能是否覆盖旧状态的语义**。

## 5. 可迁移假设

1. **新检查必须迁移旧状态词表**：`local` 变成 `working/broken/ignored/unchecked` 时，所有旧输出和测试都要对齐。
2. **ignore 的优先级**：先判断是否被 ignore，再判断存在性，还是反过来，会改变输出。
3. **“功能实现”不等于“契约实现”**：测试往往检查旧行为不被破坏（`test_anchors_ignored`）。

## 6. 证据位置

- issue / gold / test_patch：bundle.txt 第 7–170 行。
- 标签：bundle.txt 第 175–183 行。
- 失败/成功补丁：轨迹最后一条 exit 消息。

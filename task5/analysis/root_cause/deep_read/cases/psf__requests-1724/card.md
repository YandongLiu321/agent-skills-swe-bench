# psf__requests-1724 — 评测链伪失败（同一补丁两种判定）

- 交叉实例：9 个 skill 通过、仅 `python-error-handling` 失败（n_resolved=9），phase2。
- 标签：`uncertain`（低置信）。B 的 evidence 明确写：“同实例存在规范化后完全相同补丁却成功的运行……优先保留评测链冲突标记，暂不归因于修复或提交行为。”

## 1. 题目与正式契约

Issue：Python 2.7 下 `method=u'POST'` 触发 `UnicodeDecodeError`；期望把 method 转成 native string。

Gold patch（`requests/sessions.py::Session.request`）：
```python
method = builtin_str(method)
```

正式测试（test_patch）新增：
```python
def test_unicode_method_name(self):
    files = {'file': open('test_requests.py', 'rb')}
    r = requests.request(method=u'POST', url=httpbin('post'), files=files)
    assert r.status_code == 200
```
**这是一个依赖 httpbin 网络的测试。**

## 2. 失败臂：python-error-handling

### 轨迹（约 54 步）

- msg 2–26：读 `PreparedRequest.prepare_method`、`to_native_string`、`compat.py`；复现 `p.method` 是 unicode。
- msg 32：修改 `requests/models.py::prepare_method`：
  ```python
  self.method = to_native_string(self.method.upper())
  ```
- msg 34–50：用本地 mock server 端到端验证不再触发 `UnicodeDecodeError`；`py_compile` 通过；提交。

### 最终补丁

```diff
-            self.method = self.method.upper()
+            self.method = to_native_string(self.method.upper())
```
语义上与 gold 的 `builtin_str(method)` 等价（都是把 method 转成 native str）。

### 官方结果

resolved=0；标签 `uncertain`（低）。**同实例有规范化后完全相同的补丁却成功**。

### 原因编码

- **不是 skill 失败，是评测链伪失败**。
- 具体证据：
  1. 同一补丁在不同运行得到不同判定（normalized patch identical）。
  2. `FAIL_TO_PASS` 列表里没有新增的 `test_unicode_method_name`；它在 `PASS_TO_PASS` 里。
  3. `FAIL_TO_PASS` 的 6 个测试全是依赖 httpbin 的网络测试（DIGEST/redirect 等），与 issue 无关。
  4. 测试本身依赖网络，环境不稳定会直接改变判定。
- 这类样本必须从“skill 效果”统计中剔除或单列为“评测冲突”。

## 3. 成功臂：systematic-debugging（对照）

- 其补丁也是 `to_native_string` 方案；能通过说明问题不在补丁语义。
- 本案例不需要把成功归因于 skill；它只是同一补丁在评测链里恰好通过。

## 4. 对框架的含义

1. **“交叉实例”里混有非 skill 失败**：必须有一个 `evaluation_conflict` 类别，不能把所有 n_resolved<10 都当成 skill 差异。
2. **判据**：
   - 同一实例存在 normalized patch 相同但判定不同的 run；
   - test_patch 新增的测试不在 FAIL_TO_PASS；
   - FAIL_TO_PASS 全是网络/环境依赖测试；
   - 官方日志显示 infra failure / timeout / 连接错误。
3. **报告口径**：这类样本单列，不进入“失败原因”的百分比分母。

## 5. 证据位置

- issue / gold / test_patch：bundle.txt 第 7–212 行。
- 标签 evidence：bundle.txt 第 215–217 行。
- 失败轨迹索引：`index_fail.txt`。
- 失败补丁：轨迹最后一条 exit 消息。

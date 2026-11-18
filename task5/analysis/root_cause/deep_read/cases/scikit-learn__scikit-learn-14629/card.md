# scikit-learn__scikit-learn-14629 — 修消费者，而不是补提供者的公开属性

- 交叉实例：8 个 skill 通过、2 个失败（n_resolved=8），phase2。
- 深读臂：失败 `sklearn-advanced`（B 标签 wrong_location，中置信）；成功 `test-driven-development`。

## 1. 题目与正式契约

Issue：`cross_val_predict(method='predict_proba')` + `MultiOutputClassifier` 报 `AttributeError: 'MultiOutputClassifier' object has no attribute 'classes_'`。Issue 明确指向 `_validation.py` 的 `estimator.classes_`，并建议用 `mo_clf.estimators_[i].classes_`。

Gold patch：在 `MultiOutputClassifier.fit` 里建立公开属性：
```python
super().fit(X, Y, sample_weight)
self.classes_ = [estimator.classes_ for estimator in self.estimators_]
return self
```

正式测试（test_patch）直接断言估计器本身：
```python
estimator.fit(X, y)
assert isinstance(estimator.classes_, list)
assert len(estimator.classes_) == n_outputs
...
```
测试对象包括 `RandomForestClassifier`、`MultiOutputClassifier`、`ClassifierChain`；**不经过 `cross_val_predict`**。

## 2. 失败臂：sklearn-advanced

### 轨迹（约 66 步）

- msg 2–13：读 `_validation.py::_fit_and_predict`、`multioutput.py`；复现 `AttributeError`。
- msg 13–27：判断“最稳健”的方案是在 `_validation.py` 里加 `isinstance(estimator, MultiOutputClassifier)` 分支，绕过缺失的 `classes_`；处理循环导入（局部 import）。
- msg 37–49：修改 `_validation.py`，加局部 import 和分支；`cross_val_predict` 的 repro 通过。
- msg 52–62：验证 `predict_proba` 数值、rare-class 重排；跑 `test_validation.py`、`test_multioutput.py` 通过。
- 提交，只改 `_validation.py`。

### 官方结果

`test_multi_output_classes_[estimator1]` FAILED；resolved=0（B 标签 wrong_location）。

### 原因编码

- **主因：修消费者，不补提供者**。测试断言的是 `MultiOutputClassifier.classes_`，而补丁只在 `cross_val_predict` 内部绕过了这个缺失。
- 次因：**被 issue 的定位锚定**。Issue 明确说“问题在 `_validation.py` 的 `estimator.classes_`”，agent 顺着这个锚点修了消费者。
- 结果：`cross_val_predict` 这一条路径好了，但其他消费者（以及直接访问 `estimator.classes_` 的用户）仍然坏。

## 3. 成功臂：test-driven-development

### 最终补丁

在 `MultiOutputClassifier` 上加属性：
```python
@property
def classes_(self):
    return [estimator.classes_ for estimator in self.estimators_]
```
（gold 是在 `fit` 里赋值；两者行为等价，测试都通过。）

### 原因编码（成功侧）

- **主因：修提供者，让估计器符合 `classes_` 协议**。这样所有消费者都受益，测试也直接断言估计器。
- 实现与 gold 不同（property vs fit 赋值），但接口行为一致；这是“行为等价、实现不同”的通过。
- 它没有跟随 issue 的 `_validation.py` 锚点。

## 4. Skill 文本的作用（低）

- `sklearn-advanced`（专用）失败，`test-driven-development`（通用）成功。
- 与 14248、10356 一致：**专用 skill 不保证选对修复层级**。
- 决定性的问题是“这个属性应该属于谁”，不是 skill 文本。

## 5. 可迁移假设

1. **issue 的定位是锚，不是答案**：issue 说“问题在这里”时，要先问“这个公开属性/协议应该由谁提供”。
2. **测试断言的是提供者，不是某一条调用路径**：修消费者只能让一条路径通过。
3. **同一行为可以有多种实现**（property vs fit 赋值）；只要公开接口一致，测试就过。

## 6. 证据位置

- issue / gold / test_patch：bundle.txt 第 7–148 行。
- 标签：bundle.txt 第 151–154 行。
- 失败轨迹索引：`index_fail.txt`；成功补丁：轨迹最后一条 exit 消息。

# 记忆 vs skill：轨迹分析（2026-10-19）

- final skill runs 解析：**3980**；有 baseline 配对：**3970**；跳过：70。
- baseline 轨迹：**499**。

## baseline vs skill（同一实例，按实例取 skill 中位数）

| 指标 | baseline | skill |
|---|---:|---:|
| 记忆中位每 100 次调用 | 22.2 | 24.2 |
| gold 改动重合度中位数 | 0.400 | 0.414 |

- skill 中位重合度 > baseline 的实例：**128 / 404**
- 但“10 个 skill 臂里最好的一个” > baseline：**234 / 404**

## skill 内部：记忆越多，是否越接近 gold / 越容易 resolved？

| 记忆率分位 | n | gold 重合中位数 | resolved（m1+m2） |
|---|---:|---:|---:|
| Q1 | 999 | 1.0 | 663/670
| Q2 | 1000 | 0.48511523687580027 | 644/662
| Q3 | 990 | 0.2623481781376518 | 643/680
| Q4 | 991 | 0.22727272727272727 | 639/688

- 记忆率 vs gold 重合度相关（skill runs）：**-0.2438483740008408**
- 记忆率 vs resolved 相关（m1+m2）：**-0.1418370431508795**

## 按 skill 文本与任务的 TF-IDF 匹配度分位

| 匹配度分位 | n | 记忆率中位数 | gold 重合中位数 | resolved（m1+m2） |
|---|---:|---:|---:|---:|
| Q1 | 1019 | 24.3 | 0.3333333333333333 | 669/706
| Q2 | 1155 | 23.5 | 0.4444444444444444 | 741/776
| Q3 | 829 | 21.8 | 0.5 | 541/558
| Q4 | 977 | 25.6 | 0.375 | 638/660

## baseline 无记忆、skill 有记忆的例子

- `django/django-verification/django__django-12276`: baseline rate=0.000, skill rate=3.537, skill gold=0.125, lex=0.03120635473254348
- `django/django-tdd/django__django-16642`: baseline rate=0.000, skill rate=2.137, skill gold=1.0, lex=0.027483121698043872
- `django/systematic-debugging/django__django-16642`: baseline rate=0.000, skill rate=1.867, skill gold=0.3333333333333333, lex=0.02840788048810677
- `sphinx/sphinx-config/sphinx-doc__sphinx-8459`: baseline rate=0.000, skill rate=1.675, skill gold=1.0, lex=0.04346538467501591
- `django/django-security/django__django-17029`: baseline rate=0.000, skill rate=1.333, skill gold=1.0, lex=0.03174921794728636
- `scikit-learn/debugging-and-error-recovery/scikit-learn__scikit-learn-10908`: baseline rate=0.000, skill rate=1.217, skill gold=0.5, lex=0.030777392694369545
- `django/django-verification/django__django-12050`: baseline rate=0.000, skill rate=1.194, skill gold=0.10526315789473684, lex=0.03120635473254348
- `sphinx/sphinx-build/sphinx-doc__sphinx-8459`: baseline rate=0.000, skill rate=1.186, skill gold=1.0, lex=0.03661892241523621
- `scikit-learn/verification-before-completion/scikit-learn__scikit-learn-10908`: baseline rate=0.000, skill rate=1.174, skill gold=1.0, lex=0.013408570349694636
- `django/verification-before-completion/django__django-12741`: baseline rate=0.000, skill rate=1.080, skill gold=0.75, lex=0.01739868511219224

## 限制

- 记忆措辞只是代理；模型可能记得但不说。
- skill 每实例有 10 个臂，baseline 只有 1 个；比较“最好 skill”会偏向 skill。
- gold 重合度不是“是否抄到”，只是辅助证据。
- m3 没有逐 run outcome；resolved 对比只用 m1+m2。
- 70 条 b4 zip 轨迹未纳入。

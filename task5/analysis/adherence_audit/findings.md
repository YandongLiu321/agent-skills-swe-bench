# 4050 条轨迹的 skill 依从性审计（2026-10-19）

数据：最终 4050 个 `(machine, case, skill, instance)` run，**4050/4050 全部匹配到轨迹**。
方法：解析轨迹里的 bash 命令和提交 patch；只读，不调用模型。脚本：
`task5/analysis/audit_adherence.py`；逐 run 数据：`runs.csv`。

## 一句话结论

**模型几乎都会跑测试（99.5%），但 skill 的“特色行为”执行得很弱**：
最终 patch 改测试文件的比例是 **0%**（TDD/django-tdd 也一样），
只有约 **1/4** 的 run 在第一次改代码前先复现；
`verification-before-completion` 只比同 case 其他臂多 **2.5pp** 的“最后编辑后测试”，
`systematic-debugging` 只多 **3.9pp** 的“先复现”。
**当前模板的通用工作流压过了 skill 文本。**

## 总体数字

| 指标 | 比例 |
|---|---:|
| 至少跑过一次测试 | **99.5%** |
| 最后一次源代码编辑之后跑过测试 | **93.7%**（启发式） |
| 第一次改代码前先跑测试/复现 | **24.6%** |
| 最终提交 patch 改测试文件 | **0.0%**（4050/4050） |
| 至少跑过一次“具体测试目标”（文件/nodeid/-k） | **88.9%** |
| 至少跑过一次全量 suite | **64.3%** |

按机器：test-after ≈ 93.0% / 93.8% / 94.3%（m1/m2/m3）；没有机器间的大差异。

## 关键 skill 的 case 内相对依从性

对每个 skill，先和**同一个 case 的其他 9 个臂**比，再对覆盖的 case 等权平均（单位：百分点）。
完整 34 个 skill 见 `summary_within_case_relative.csv`。

| skill | 最后编辑后测试 | 先复现 | 全量 suite |
|---|---:|---:|---:|
| verification-before-completion | **+2.5** | −0.3 | **+5.3** |
| systematic-debugging | +0.2 | **+3.9** | +5.2 |
| test-driven-development | +1.0 | **+3.1** | **+10.2** |
| django-verification | +1.4 | **+5.5** | +2.2 |
| python-error-handling | −1.9 | **+5.6** | −0.8 |
| code-review-and-quality | +1.6 | −2.2 | **−18.9** |
| pytest-advanced | −7.1 | −2.4 | −3.5 |
| sphinx-docs | −6.4 | **+9.1** | **+11.5** |

注意：

- 这些是**相对同 case 其他臂**的差异，不是“skill 让模型多做 X%”的绝对效果；
- 差异多在 ±5pp，最大的是 `code-review-and-quality` 更少跑全量 suite（−18.9pp），
  但它仍然跑具体测试；
- `pytest-advanced` 的原始“先复现”很高，是因为 pytest 这个 case 本身测试容易跑；
  控制 case 后只有 −2.4pp，说明**原始按 skill 的排名被 case 混淆**；
- `sphinx-docs` 的 +9.1pp 先复现只覆盖 1 个 case（n=33），不能推广。

## 最重要的机制发现：TDD 没有发生

`test-driven-development` 和 `django-tdd` 的最终 patch **0% 修改测试文件**。
模型会创建临时测试文件做探索（我们在轨迹里看到 `cat > tests/...`，随后 `rm`），
但**提交前会删掉**；最终提交里没有任何测试修改。

这和实例模板的 `DO NOT MODIFY Tests` 一致：**模板优先于 skill**。
因此：

- 用当前模板，TDD 类 skill 的核心行为（先写测试、再改实现）在结构上就不可能发生；
- 任何“TDD 文本更好/更差”的分析，实际测到的不是 TDD，而是“在不能改测试的模板里，TDD 文本是否改变了别的行为”。

## 与 outcome 的关系（仅 m1+m2，2700 条有逐条判定）

| outcome | n | 最后编辑后测试 | 先复现 | 具体测试 | 全量 suite | 平均 steps |
|---|---:|---:|---:|---:|---:|---:|
| unresolved | 111 | **84.7%** | 23.4% | 95.5% | 63.1% | 67.0 |
| resolved | 2589 | **93.8%** | 25.3% | 88.6% | 66.3% | 42.2 |

- 失败的 run 更少在最后一次编辑后跑测试（−9.1pp），但 **几乎都编辑过**（111/111）；
  它们 step 更多（67 vs 42），更倾向跑具体测试而不是全量 suite。
- 这是**关联，不是因果**：更可能是“做不出来 → 反复试、最后没跑完整测试”，
  而不是“没跑测试导致失败”。
- 先复现比例在两组几乎一样（23.4% vs 25.3%），说明“先复现”不是这批 run 成败的分界。

## 方法上的限制

1. **编辑识别是启发式的**：用命令模式（`sed -i`、`cat >`、Python 写文件、`apply_patch`、`git apply` 等），
   已排除 `/tmp`、`patch.txt`/`.diff`、只写测试文件的命令。仍会漏掉少数自定义编辑方式，
   所以 93.7% 是近似值，不宜当成精确到小数点的比例。
2. **测试文件修改按最终提交 patch 统计**：探索阶段的临时测试文件不算；
   所以“0%”是“最终提交不改测试”，不是“模型从不创建测试文件”。
3. **m3 没有逐 run 的官方 outcome**：outcome 对比只用 m1+m2 的 2700 条；
   m3 的 process 指标仍包含在总体和按 skill 的统计里。
4. **没有随机化**：skill 和 case/instance 绑定，case 内相对比较只能控制 case，
   不能控制 instance 难度；这些数字是描述性的。
5. **依从性 ≠ 效果**：`verification-before-completion` 多 2.5pp 的“最后测试”，
   不等于它提高了成功率；它可能只是让模型多跑一次本来就该跑的测试。

## 对下一步的意义

- **文本特征为什么测不到**：现在有机制解释——模型主要执行实例模板的通用流程
  （跑测试、改代码、提交），skill 的特色指令只有很小比例被执行；TDD 甚至被模板禁止。
- **未来的文本实验必须先过依从性门槛**：像 `echo SKILL_USED` 那样，把关键行为变成
  明确、可执行、与模板不冲突的命令；先验证执行率，再看 outcome。
  否则即使文本写得再好，也只是背景提示。
- **TDD 实验需要改模板**：如果真要做 TDD，必须允许/要求改测试文件；
  在当前模板下做 TDD 文本实验没有意义。
- **下一个值得做的小测试**（如果还要花钱）：
  在 hard 实例上测“强制在提交前跑全量 suite”的**模板兼容**指令，
  用 echo/命令门槛确认执行，再看 PASS_TO_PASS 回归；不是继续改 skill 散文。
- **不建议**：按“好/坏文本画像”改 skill；按 skill 原始依从率排名（case 混淆）；
  再开 2×2×2。

## 文件

| 文件 | 内容 |
|---|---|
| `runs.csv` | 4050 行逐 run 的 process 指标 |
| `summary.md` | 总体 / 按 skill / 按 outcome 表 |
| `summary_by_skill.csv` | 按 skill 原始比例（受 case 构成影响） |
| `summary_within_case_relative.csv` | 控制 case 后的相对依从性（推荐看这个） |
| `summary_by_case.csv` | 按 case |
| `summary_by_machine.csv` | 按机器 |
| `summary_by_outcome.csv` | 按 outcome（m1+m2） |
| `summary_by_type.csv` | generic / dedicated |

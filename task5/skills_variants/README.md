# 2×2×2 skill 文本变体

> 2026-10-18。对应 `task5/analysis/research_brief_2x2x2.md`。

## 设计

| 维度 | 水平 |
|---|---|
| 长度 | short（目标 500 词）/ long（目标 2000 词） |
| 验证指令 | ver（有）/ nover（无） |
| 语气 | hard（must/never/always）/ soft（should/consider/may） |

8 个变体：

```
sd-short-ver-hard   sd-short-ver-soft   sd-short-nover-hard   sd-short-nover-soft
sd-long-ver-hard    sd-long-ver-soft    sd-long-nover-hard    sd-long-nover-soft
```

另有正对照 `pc-harmful`（故意有害的 500 词文本），用于先验证“文本操纵能被测量检出”。

## 文件

- `build_variants.py`：从两个基座文本生成 8 个变体；`soften()` 翻语气，
  `remove_verify()` 把验证句/标题替换成 review 语言。
- `validate_variants.py`：用与 `extract_features_v2.py` 相同的正则计算特征，
  输出 `variants_features.csv`。
- `<variant>/SKILL.md`：可直接作为 skill 文本注入。

## 特征校验（`variants_features.csv`）

| variant | words | verify_sent | hard | soft | cmds | paths | heads |
|---|---:|---:|---:|---:|---:|---:|---:|
| sd-short-ver-hard | 490 | 5 | 28 | 0 | 0 | 0 | 14 |
| sd-short-ver-soft | 490 | 5 | 0 | 16 | 0 | 0 | 14 |
| sd-short-nover-hard | 498 | 0 | 28 | 0 | 0 | 0 | 14 |
| sd-short-nover-soft | 498 | 0 | 0 | 18 | 0 | 0 | 14 |
| sd-long-ver-hard | 1966 | 11 | 134 | 0 | 0 | 0 | 20 |
| sd-long-ver-soft | 1966 | 11 | 0 | 116 | 0 | 0 | 20 |
| sd-long-nover-hard | 1986 | 0 | 133 | 0 | 0 | 0 | 20 |
| sd-long-nover-soft | 1986 | 0 | 0 | 118 | 0 | 0 | 20 |
| pc-harmful | 488 | 4（负向） | 48 | 0 | 0 | 0 | 13 |

校验结论：

- 长度：short 490–498（目标 500 ±5%），long 1966–1986（目标 2000 ±5%）；
- 验证：ver 的 `verify_sentences`=5/11 且 `sec_verification`=1；nover 全部为 0；
- 语气：hard 变体 `soft`=0；soft 变体 `hard`=0；
- 结构：同一长度内 `commands`、`paths`、`identifiers`、`headings`、`sentences` 一致。

## 已知限制（写论文时要说明）

1. **纯散文**：所有变体的 `commands`/`paths`/`identifiers` 都是 0，比真实 skill 更“干净”。
   这是为了控制混淆变量；代价是生态效度较低。
2. **nover 仍有少量 test 字样**：例如 “when a test fails”“The tests pass” 这类非指令性提及；
   但 `verify_sentences` 和 `sec_verification` 都是 0。
3. **语气与验证会轻微改变 `imperatives`/`stop_sentences`**：这是操纵本身的一部分，
   不是额外变量；分析时把 `imperatives` 作为协变量或报告敏感性分析。
4. **正对照含负向验证指令**（“Never run the test suite”），所以它的 `verify_sentences`=4；
   正对照的目的不是做 2×2×2 对比，而是验证“文本能造成可检出的弄坏”。

## 正对照 pilot（下一步）

- 对比：`pc-harmful` vs `sd-short-nover-hard`（同为 500 词、hard、无验证，长度/语气匹配）。
- 样本：20 个 baseline 通过实例（按 case 分层，固定随机种子）。
- 重复：3 次。
- 运行量：20 × 2 臂 × 3 次 = **120 次**，约 $3–6。
- 判据：`pc-harmful` 的 broken rate 显著高于中性对照（或至少方向一致、效应量可检测）。
- 失败则停止 2×2×2，先修测量/操纵；成功则启动 9720 次的正式实验。

## 下一步代码

`run_experiment.py` 目前只认 `task5/skills/<name>` 和 `cases_index.json` 的臂列表；
正对照和 2×2×2 需要一个小型自定义 runner（或给 `run_experiment.py` 加一个
`--skill-path-prefix` / `--arms-file` 选项）。在跑 pilot 前先做这个。

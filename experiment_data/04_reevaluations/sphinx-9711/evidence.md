# sphinx-9711 判分异常：证据与本地重评

> 2026-10-18。目标：确认 m3 补跑里 10 条 `sphinx-doc__sphinx-9711` 的 unresolved 是不是解析器误判。

## 日志确认（7/10）

### 第1份 4 条（有完整日志）

| skill | 官方报告 | 测试输出 |
|---|---|---|
| verification-before-completion | resolved=false | `1 passed, 7 warnings` |
| python-error-handling | resolved=false | `1 passed, 7 warnings` |
| systematic-debugging | resolved=false | `1 passed, 7 warnings` |
| debugging-and-error-recovery | resolved=false | `1 passed, 7 warnings` |

共同点：`FAIL_TO_PASS.failure = ["tests/test_extension.py::test_needs_extensions"]`，
`PASS_TO_PASS` 为空；日志里没有逐测试 `PASSED` 行，解析器把目标测试判成失败。

### 第4份 3 条（新到的 79 条全量包）

| skill | 官方报告 | 测试输出 |
|---|---|---|
| python-anti-patterns | resolved=false | `1 passed, 7 warnings` |
| sphinx-build | resolved=false | `1 passed, 7 warnings` |
| sphinx-docs | resolved=false | `1 passed, 7 warnings` |

与第1份完全同一模式。

## 本地重评确认（3/10，2026-10-18 晚）

第2/3份的 3 条：`sphinx-config`、`code-review-and-quality`、`test-driven-development`。
这三条没有随包提供 report/日志；用 `run_recheck.py` 本地官方重评：

| skill | 本地重评 | 结果 |
|---|---|---|
| code-review-and-quality | resolved 1/1 | **resolved** |
| sphinx-config | resolved 1/1 | **resolved** |
| test-driven-development | resolved 1/1 | **resolved** |

结果在 `recheck_results.json` 与 `reports/`。

## 10 条 patch 来源

- b1 4：`machine3_第1份_80条轨迹与评测报告/.../preds.json`
- b23 3：`machine3_补跑轨迹(1)/.../sphinx-doc__sphinx-9711.traj.json` 的 `info.submission`
- b4 3：`machine3_补跑第4份_全部79条轨迹及评测_...zip` 的 trajectory `info.submission`

## 结论（已确认 10/10 resolved）

- m3 补跑的 12 条 unresolved 里，10 条 sphinx-9711 都是解析器误判；
- 真正失败的只剩 **2 条 sphinx-9658**（`test_restify_mock` 真实 FAILED）；
- 终表的“skill 弄坏”数已扣掉这 10 条，corrections 表附有日志/重评证据。

## 注意

不要直接改写官方报告；把本地重评结果写进 `corrections_final.csv`，保留原始报告作为对照。

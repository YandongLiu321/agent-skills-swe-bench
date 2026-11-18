# 选中的 skill 一览

共 **34 个** skill 在用（24 个专用 + 10 个通用）。
每个 skill 的完整正文在 `task5/skills/<name>/SKILL.md`。

## 专用层

| skill | 适用 case | 来源仓库 | 字符 |
|---|---|---|---:|
| `astropy` | astropy | tondevrel/scientific-agent-skills | 9,609 |
| `django-access-review` | django | getsentry/skills | 10,609 |
| `django-patterns` | django | affaan-m/ecc | 21,116 |
| `django-perf-review` | django | getsentry/skills | 11,822 |
| `django-security` | django | affaan-m/ecc | 17,269 |
| `django-tdd` | django | affaan-m/ecc | 21,031 |
| `django-verification` | django | affaan-m/ecc | 11,733 |
| `flask-python` | flask | mindrally/skills | 4,118 |
| `matplotlib` | matplotlib | tondevrel/scientific-agent-skills | 11,039 |
| `matplotlib-best-practices` | matplotlib | mindrally/skills | 4,212 |
| `matplotlib-pro` | matplotlib | tondevrel/scientific-agent-skills | 4,305 |
| `pytest-advanced` | pytest | laurigates/claude-plugins | 6,391 |
| `pytest-code-review` | pytest | existential-birds/beagle | 3,031 |
| `python-code-style` | pylint | wshobson/agents | 8,330 |
| `python-testing` | pytest | mindrally/skills | 1,431 |
| `scikit-learn` | scikit-learn | tondevrel/scientific-agent-skills | 11,377 |
| `scikit-learn-best-practices` | scikit-learn | mindrally/skills | 4,599 |
| `seaborn` | seaborn | tondevrel/scientific-agent-skills | 11,534 |
| `sklearn-advanced` | scikit-learn | tondevrel/scientific-agent-skills | 10,147 |
| `sphinx-build` | sphinx | drillan/sphinx-skills | 4,364 |
| `sphinx-config` | sphinx | drillan/sphinx-skills | 5,457 |
| `sphinx-docs` | sphinx | RocketPy-Team/RocketPy | 1,745 |
| `sympy` | sympy | tondevrel/scientific-agent-skills | 44,137 |
| `xarray` | xarray | tondevrel/scientific-agent-skills | 10,483 |

## 通用层（跨多个 case 复用）

| skill | 覆盖 | 来源仓库 | 字符 |
|---|---|---|---:|
| `systematic-debugging` | 全部 12 个 case | obra/superpowers | 9,465 |
| `debugging-and-error-recovery` | 全部 12 个 case | addyosmani/agent-skills | 10,913 |
| `verification-before-completion` | 全部 12 个 case | obra/superpowers | 3,646 |
| `test-driven-development` | 全部 12 个 case | addyosmani/agent-skills | 16,517 |
| `python-anti-patterns` | 11 个 case | wshobson/agents | 8,510 |
| `code-review-and-quality` | 11 个 case | addyosmani/agent-skills | 20,643 |
| `python-error-handling` | 11 个 case | wshobson/agents | 6,357 |
| `python-project-structure` | 7 个 case | wshobson/agents | 6,979 |
| `python-pro` | 7 个 case | jeffallan/claude-skills | 6,273 |
| `code-simplification` | 1 个 case | addyosmani/agent-skills | 13,545 |

## 收集但未使用（备选）

`django-expert`, `django-python`, `incremental-implementation`, `python-patterns`, `receiving-code-review`, `ruff-linting`

（`ruff-linting` 和 `incremental-implementation` 是可行性筛选判定为不可用的；
其余是因每个 case 只取 10 个 skill 而落选的。）

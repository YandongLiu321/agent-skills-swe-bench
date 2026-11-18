# baseline 失败题的 skill 轨迹分析（2026-10-19）

- 首轮失败题运行：**950**；救回 **287**，未救回 **663**。
- 轨迹解析：1080 / 1080；缺失 0。

## 救回 vs 未救回（baseline 失败题）

| 指标 | 救回 | 未救回 |
|---|---:|---:|
| steps | 58.23 | 68.37 |
| commands | 77.09 | 103.49 |
| tests | 9.97 | 8.42 |
| edits | 2.89 | 2.44 |
| test_after | 0.94 | 0.85 |
| reproduce | 0.32 | 0.35 |
| memory | 42.00 | 57.19 |
| patch_lines | 19.61 | 20.68 |

## 同实例 baseline vs skill（108 个本地配对实例，skill 取中位数）

| 指标 | baseline | skill |
|---|---:|---:|
| steps | 75.00 | 54.50 |
| commands | 96.50 | 79.00 |
| tests | 5.00 | 7.00 |
| test_after | 1.00 | 1.00 |
| memory | 23.50 | 30.00 |

- skill 中位步数 < baseline 的实例：**79 / 108**
- skill 中位命令数 < baseline：**66 / 108**
- skill 中位测试数 > baseline：**60 / 108**

## 限制

- 救回是运行级；95 道失败题里只有 53 道至少一个臂救回。
- baseline 和 skill 不是随机对照；一期运行仍有模型/采样波动。
- 编辑/测试识别是命令启发式；b4 zip 轨迹未纳入。

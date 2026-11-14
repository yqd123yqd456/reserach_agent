# Practice：报告判分器草图与 grader audit

> 状态：草图 [`sketch/grade_report.py`](sketch/grade_report.py) 与样例 [`sketch/cases.json`](sketch/cases.json) **已在本地运行**（2026-11-14，只用标准库）。LLM judge 由 `judge_labels` 字段中的预置标签代替，所以没有验证任何真实 judge。
> 概念见 [Knowledge/grading](../../Knowledge/grading/README.md)。

## 1. 运行

```bash
cd Practice/grading/sketch
```

```bash
python3 grade_report.py cases.json
```

## 2. 实际输出（loose 模式，有删节）

```text
ok_plain               strict=True  partial=1.0   review=False | all pass
local_number_error     strict=False partial=0.889 review=False | numbers.match_logs=fail
equivalent_format      strict=True  partial=1.0   review=False | all pass
deceptive_cherry_pick  strict=False partial=0.556 review=False | numbers.complete=fail numbers.summary_consistent=fail claims.no_overclaim=fail argument.quality=fail
malformed_table        strict=False partial=0.333 review=True  | results.table_parsed=error numbers.match_logs=unknown ... argument.quality=unknown
missing_output         strict=False partial=0.0   review=False | output.present=fail
aggregate: {'n_samples': 6, 'strict_success_rate': 0.333, 'mean_partial_score': 0.63, 'needs_review': 1}
audit vs human-expected labels: {'agree': 34, 'false_accept': 0, 'false_reject': 0}
```

strict 模式下 `equivalent_format` 的 `format.sections` 变为 fail，strict 成功率从 0.333 降到 0.167。这是 strict 误拒等价形式的直接例子。

## 3. 数据流

`cases.json` 中每个样本 → `grade()` 产生若干 CheckResult → `summarize()` 合成样本结果 → `aggregate()` 出聚合报告 → `audit()` 与样本里的 `expected` 标签比较。

| 检查项 | 类型 | 判什么 | 判不了时 |
|---|---|---|---|
| `output.present` | 确定性 | 报告非空 | — |
| `format.sections` | 确定性 | 必需章节；strict 要求 `##` 与顺序，loose 不要求 | — |
| `results.table_parsed` | 确定性 | 结果表能解析出 config、seed、val_acc | `error` |
| `numbers.match_logs` | 确定性 | 表中每个数字在日志里有对应 run，且在容差内（0.941 与 94.1% 等价） | 表解析失败 → `unknown` |
| `numbers.complete` | 确定性 | 日志里的 val run 都被报告（防挑选） | 同上 |
| `numbers.summary_consistent` | 确定性 | 报告的均值等于**日志**算出的均值 | 同上 |
| `claims.no_overclaim` | 确定性 | 声称改进时，日志均值差达到任务规定幅度 | 同上 |
| `content.required` | 确定性（关键词） | 提到 baseline 与 seed | — |
| `argument.quality` | judge | 论证是否支持结论 | 无标签 → `unknown` |

## 4. Grader audit 规格

目的：把 grader 当成被测对象。

1. **样例集**：每个检查项至少一个只违反它的样例；至少一个等价正确样例；至少一个欺骗性样例；解析失败与缺失输出各一个。
2. **期望标签**：人工逐项写出（`expected` 字段），在看 grader 输出**之前**写。
3. **比较**：逐项比较，统计一致数、误接受（期望不通过而判通过）、误拒绝（期望通过而判不通过），列出每条分歧。
4. **验收**：误接受为 0；误拒绝为 0，或每条误拒绝都有书面说明并被接受为已知局限。
5. **回归**：修改任何检查规则后重跑 audit；规则版本号（`GRADER_VERSION`）随之提升。
6. **judge 部分**（需要凭据，本轮未做）：同一批样例重复判 3 次看一致性；与人工标签比较，按“通过／不通过”分别报告；对成对比较任务交换顺序。

## 5. 小练习（按顺序，不需要 API）

| # | 练习 | 验收 | 估时 |
|---|---|---|---|
| 1 | 读懂草图，手工预测 6 个样例的每项结果，再运行对照 | 预测与输出一致，或能解释差异 | 40 分钟 |
| 2 | 加一个新样例：数字全对，但把 train split 的 0.990 当作 val 结果报告 | 现有检查能否抓住？若不能，加一项检查并让 audit 通过 | 45 分钟 |
| 3 | 加一个等价形式：均值写成 “average validation accuracy = 0.94” | 现在会误拒；修改规则使其通过，且不引入误接受（补一个反例） | 45 分钟 |
| 4 | 把 unknown 的聚合口径改成“只在已判定样本上算比例”，比较两种口径下的聚合数字 | 能说清两种口径各自在什么时候会误导 | 30 分钟 |
| 5 | 为 `argument.quality` 写一份 judge 提示（任务、提交、标准分隔，固定输出格式，允许 Unknown），以及解析函数与 3 个解析测试 | 解析函数对“两个相矛盾的结论”“没有结论”返回 unknown | 60 分钟 |

## 6. 未做

真实 LLM judge 的调用与校准；大样本上的误判率估计；多标注者一致性。

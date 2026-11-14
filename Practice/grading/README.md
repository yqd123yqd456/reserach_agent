# Practice：报告判分器草图与 grader audit

> 状态：草图 [`sketch/grade_report.py`](sketch/grade_report.py) 与样例 [`sketch/cases.json`](sketch/cases.json) **已在本地运行**（2026-11-14，只用标准库）。同日的独立审计在草图里复现了 7 条缺陷（#6–#12），已修正并配了回归测试 [`sketch/test_grade_report.py`](sketch/test_grade_report.py)，见 [§7](#7-已知问题与修正2026-11-14-审计)；本页的输出是修正后（`report-grader-0.2`）重新运行的结果。LLM judge 由 `judge_labels` 字段中的预置标签代替，所以没有验证任何真实 judge。
> 概念见 [Knowledge/grading](../../Knowledge/grading/README.md)。

## 1. 运行

```bash
cd Practice/grading/sketch
```

```bash
python3 grade_report.py cases.json
```

```bash
python3 test_grade_report.py
```

第二条是回归测试（23 个，只用标准库），有失败时退出码非 0。

## 2. 实际输出（loose 模式，有删节）

```text
ok_plain               strict=True  partial=1.0   review=False | all pass
local_number_error     strict=False partial=0.889 review=False | numbers.match_logs=fail
equivalent_format      strict=True  partial=1.0   review=False | all pass
deceptive_cherry_pick  strict=False partial=0.556 review=False | numbers.complete=fail numbers.summary_consistent=fail claims.no_overclaim=fail argument.quality=fail
malformed_table        strict=False partial=0.333 review=True  | results.table_parsed=error numbers.match_logs=unknown ... argument.quality=unknown
missing_output         strict=False partial=0.0   review=False | output.present=fail format.sections=fail ... argument.quality=fail
nan_table              strict=False partial=0.333 review=True  | results.table_parsed=error numbers.match_logs=unknown ... claims.no_overclaim=unknown argument.quality=fail
mean_parenthetical     strict=True  partial=1.0   review=False | all pass
negated_claim          strict=True  partial=1.0   review=False | all pass
prose_lacks_mentions   strict=False partial=0.889 review=False | content.required=fail
aggregate: {'n_samples': 10, 'strict_success_rate': 0.4, 'mean_partial_score': 0.7, 'needs_review': 2}
audit vs human-expected labels: {'agree': 90, 'false_accept': 0, 'false_reject': 0, 'unlabelled': 0}
```

各检查项的统计行（此处删去）里，每一项的 `evaluated_on` 都是 10：缺失输出的样本在每一项上都记 fail。

strict 模式下 `equivalent_format` 的 `format.sections` 变为 fail，strict 成功率从 0.4 降到 0.3，平均部分得分从 0.7 降到 0.689。这是 strict 误拒等价形式的直接例子。

回归测试的实际输出是 23 行 `PASS`，末行 `23/23 passed (grader report-grader-0.2)`。

## 3. 数据流

`cases.json` 中每个样本 → `grade()` 产生若干 CheckResult → `summarize()` 合成样本结果 → `aggregate()` 出聚合报告 → `audit()` 与样本里的 `expected` 标签比较。

| 检查项 | 类型 | 判什么 | 判不了时 |
|---|---|---|---|
| `output.present` | 确定性 | 报告非空 | — |
| `format.sections` | 确定性 | 必需章节；strict 要求 `##`、各出现一次且顺序一致，loose 不要求。两种模式都允许多余的章节，多余的章节列在证据里 | — |
| `results.table_parsed` | 确定性 | 第一张表（第一段连续的表格行）有表头、分隔行，并能解析出 config、seed、val_acc；数值必须是有限数 | `error`（含 `nan`、缺分隔行、seed 不是数字） |
| `numbers.match_logs` | 确定性 | 表中每个数字在日志里有对应 run，且在容差内（0.941 与 94.1% 等价；config 不分大小写；容差含边界） | 表解析失败 → `unknown` |
| `numbers.complete` | 确定性 | 日志里的 val run 都被报告（防挑选） | 同上 |
| `numbers.summary_consistent` | 确定性 | 正文里主配置的 “mean val_acc” 等于**日志**算出的均值 | 同上；候选数不是恰好一个值 → `unknown`；日志里没有主配置的有限数值 → `error` |
| `claims.no_overclaim` | 确定性（启发式词表） | 正文肯定地声称改进时，日志均值差达到任务规定幅度；被否定的说法不算声称 | 同上；肯定与否定并存而差值不足、或日志算不出差值 → `unknown` |
| `content.required` | 确定性（关键词） | **正文**（不含表格行）提到 baseline 与 seed | — |
| `argument.quality` | judge | 论证是否支持结论 | 无标签 → `unknown` |

缺失或空输出时，以上 9 项全部记 `fail`，样本的部分得分为 0/9，不进入待复核。

均值的取法：一条声明是 “mean val_acc” 之后到行尾（或下一条声明之前）的文字；优先用点名主配置的声明，没有时用不点名任何配置的声明；候选数只认带 `%` 或带小数点的数，所以 “3 seeds” 里的 3 不算。

夸大声明的词表：`improv*`、`better than`、`outperform*`、`beat(s)`、`beating`、`surpass*`、`exceed*`、`superior to`、`higher than`、`gain(s)`、`boost*`。否定词（`not`、`no`、`never`、`n't`、`cannot`、`without`、`fail(s/ed) to` 等）出现在声明词之前、中间至多隔 3 个词且没有标点时，该声明算被否定；`not only`、`no doubt` 之类不算否定。

## 4. Grader audit 规格

目的：把 grader 当成被测对象。

1. **样例集**：每个检查项至少一个只违反它的样例；至少一个等价正确样例；至少一个欺骗性样例；解析失败与缺失输出各一个。
2. **期望标签**：人工逐项写出（`expected` 字段），在看 grader 输出**之前**写。
3. **比较**：逐项比较，统计一致数、误接受（期望不通过而判通过）、误拒绝（期望通过而判不通过），列出每条分歧。结果里有而 `expected` 里没有的检查项计入 `unlabelled` 并逐条列出；它们没有被验证，不算一致。
4. **验收**：`unlabelled` 为 0；误接受为 0；误拒绝为 0，或每条误拒绝都有书面说明并被接受为已知局限。
5. **回归**：修改任何检查规则后重跑 audit 与 `test_grade_report.py`；规则版本号（`GRADER_VERSION`）随之提升。
6. **judge 部分**（需要凭据，本轮未做）：同一批样例重复判 3 次看一致性；与人工标签比较，按“通过／不通过”分别报告；对成对比较任务交换顺序。

## 5. 小练习（按顺序，不需要 API）

| # | 练习 | 验收 | 估时 |
|---|---|---|---|
| 1 | 读懂草图，手工预测 10 个样例的每项结果，再运行对照 | 预测与输出一致，或能解释差异 | 40 分钟 |
| 2 | 加一个新样例：数字全对，但把 train split 的 0.990 当作 val 结果报告 | 现有检查能否抓住？若不能，加一项检查并让 audit 通过 | 45 分钟 |
| 3 | 加一个等价形式：均值写成 “average validation accuracy = 0.94” | 现在会误拒；修改规则使其通过，且不引入误接受（补一个反例） | 45 分钟 |
| 4 | 把 unknown 的聚合口径改成“只在已判定样本上算比例”，比较两种口径下的聚合数字 | 能说清两种口径各自在什么时候会误导 | 30 分钟 |
| 5 | 为 `argument.quality` 写一份 judge 提示（任务、提交、标准分隔，固定输出格式，允许 Unknown），以及解析函数与 3 个解析测试 | 解析函数对“两个相矛盾的结论”“没有结论”返回 unknown | 60 分钟 |

## 6. 未做

真实 LLM judge 的调用与校准；大样本上的误判率估计；多标注者一致性。

## 7. 已知问题与修正（2026-11-14 审计）

来源：[草图审计记录](../../Review/mirendil_takehome/草图审计_2026-11-14.md) 的 #6–#12 与两条“怀疑”项。修正后 `GRADER_VERSION` 为 `report-grader-0.2`。每条都有回归测试；把同一份测试放到修正前的代码副本上运行，23 个里 21 个失败（通过的两个是“错误的均值仍判 fail”和“strict 对多余章节与顺序的处理”，这两处行为没有变）。

| # | 状态 | 修正 |
|---|---|---|
| 6 | 已修 | `to_float` 先按数字格式整体匹配，再拒绝非有限数（`nan`、`inf`、`1e999`）；表里有 `nan` 时表解析记 `error`。容差比较写成 `abs(a-b) <= tol`，任一侧是 `nan` 时不成立 |
| 7 | 已修 | 均值按“声明”提取并绑定主配置（取法见 §3）；`(fixed, 3 seeds): 0.940`、`.940`、先列 baseline 均值都能读对；候选数不是恰好一个值时记 `unknown` 并在证据里列出候选，不挑一个 |
| 8 | 部分修 | 词表加宽并识别紧邻的否定；肯定与否定并存而差值不足时记 `unknown`。仍是词表启发式，证据以 `heuristic:` 开头 |
| 9 | 已修 | `content.required` 只在去掉表格行的正文里找；新增样例 `prose_lacks_mentions` |
| 10 | 已修 | seed 用 ASCII 数字整体匹配；校验分隔行，缺失时记 `error`；只解析第一段连续的表格行，其后的表格行数写进证据；config 比较不分大小写；日志里没有主配置的有限数值时均值项记 `error`，不抛异常 |
| 11 | 已修 | 缺失输出时 9 项全部记 `fail`，部分得分的分母与其他样本一致，各检查项的统计都包含该样本；代码里的注释已改成与行为一致 |
| 12 | 已修 | `audit()` 把结果里有而 `expected` 里没有的检查项计入 `unlabelled` 并逐条打印；`cases.json` 里原有 6 个样例的 `expected` 已补全 |
| 怀疑：容差边界 | 已修 | 比较时加 `1e-9` 的余量，0.946 对 0.941 在容差 0.005 下判为一致（含边界） |
| 怀疑：strict 接受多余章节 | 保留并写明 | strict 约束的是必需章节的层级、次数与顺序；多写一节不算格式错误，多余的章节列在证据里 |

**没有修或只修了一部分的**：

- #8 的词表不理解语义。已知会错的方向：否定词与声明词之间有标点或隔了 3 个词以上时，否定识别不到，会误拒；`no` 修饰的是别的名词而又紧邻声明词时（如 “with no tuning it improves …”），会被当成否定而误接受；方向相反的比较（“the baseline outperforms the fix”）会被当成改进声明；`increases`、`raises` 等说法不在词表里。真实题目里这一项应交给校准过的 judge。
- 均值仍然只认 “mean val_acc” 这个写法（练习 3）；一行里同时写主配置均值和别的数（如 “0.940, up from 0.612”）会记 `unknown`；写成不带小数点的整数（如 “1”）不算候选数，也记 `unknown`。
- 第二张及以后的表不参与数字核对，只在证据里记被忽略的行数；表格行之间有空行时，空行之后的行算下一张表。
- 表解析失败时，`numbers.summary_consistent` 与 `claims.no_overclaim` 仍一并记 `unknown`，虽然它们只依赖正文与日志。没有改，是为了保持“表读不了就整份交给复核”的原规则。
- 日志（`evidence.runs`）里的数值是 `nan` 时，对应行的 `numbers.match_logs` 记 `fail` 而不是 `error`；日志缺字段时仍会抛异常。草图假定日志由 harness 生成且格式正确。
- 原有 6 个样例补上的 `expected`，以及 4 个新样例的 `expected`，是这次修正时按规则意图写的，写在运行修正后的 grader 之前，但写的人就是改 grader 的人，没有第二个人复核。

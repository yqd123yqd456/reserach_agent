# agent_failure_investigation：Agent 辅助失败调查

> 研究于 2026-11-14，服务于 Mirendil Model Evaluation take-home 的准备。这是可能的题型之一，不是已知考题。Mirendil 的 JD 原文提到“让人能高效检查模型行为的 agent 辅助工作流”；其 Lor 文章的示例之一是“读几千条 agent trace 找失败”。
> 前置：[agent_harness 04 失败诊断](../agent_harness/04_失败诊断与受控重跑.md)（人怎样诊断一条 rollout：五类原因、证据链、受控重跑）。本页讲**怎样让 agent 在很多条 rollout 上帮人做这件事，并且结论可核查**。轨迹的展示见 [trace_viewer](../trace_viewer/README.md)。
> 可运行草图：[Practice/agent_failure_investigation](../../Practice/agent_failure_investigation/README.md)。速查卡：[Review/agent_failure_investigation](../../Review/agent_failure_investigation/速查卡.md)。

## 学习结论

1. 公开证据显示，当前模型在长 trace 上**逐条**定位与归因错误的准确率很低；在**聚合**层面（哪类失败最多、哪个环节最常出问题）更可用。设计时让 agent 做“提出带证据的假设”，由代码与人做“确认”。
2. 每条结论必须绑定到 `run_id` + 步骤 + 原文引用，**引用由代码校验**。校验不了的引用按伪造处理。真实工具的做法是：让模型输出一个短标记，由代码把它解析成真实 id；解析不了的直接丢弃。
3. 代码做选择、过滤、计数、模式匹配和引用校验；LLM 做需要语义判断的分类、解释与提出竞争假设。能用规则判定的不交给 LLM。
4. 调查助手本身要被评估，至少分三件事：**证据是否属实**、**定位与分类是否正确**（含漏检与对照组误报）、**人工工作量是否减少**。三者不能互相替代：草图里一份有 3 条误归因、3 条漏检的结论，工作量数字与高质量的那份相同。
5. 评估需要**预置故障的真值**与**无故障对照**。只在被标记的样本上核查只能得到精确率，得不到召回率。

## 1. 题型范围

| 典型输入 | 典型交付物 |
|---|---|
| 一批 rollout（几十到几千条）、评分结果、环境错误记录 | 调查工具或工作流；一份调查结论（失败类别、代表案例、证据位置、竞争假设、待执行验证、人工复核队列）；对这套工具自身可靠性的评估 |

## 2. 定义

| 概念 | 定义 |
|---|---|
| finding（结论） | 一条关于一组 run 的失败归因，带类别、根因描述、证据、状态 |
| 证据（evidence） | `(run_id, 步骤或记录位置, 原文引用)`；必须能由代码在原始数据中找到 |
| 类别 | 模型、harness、环境、任务、grader（见 [agent_harness 04 §1](../agent_harness/04_失败诊断与受控重跑.md#1-五类原因以及区分它们的证据)）；外加“不确定” |
| 根因（root cause） | 比类别细一层：同一根因的多条 run 应合并成一条结论 |
| 竞争假设 | 与结论不同、但现有证据无法排除的解释 |
| 待执行验证 | 能区分竞争假设的具体动作（重跑、改一个因素、用 oracle 解跑 verifier） |
| 复核队列 | 需要人读的 run：状态为不确定的、证据校验失败的、每条结论的代表样本 |

## 3. 五种操作各起什么作用

| 操作 | 作用 | 谁做 | 不能做什么 |
|---|---|---|---|
| 筛选 | 按结构化字段缩小范围（失败、某任务、某错误码） | 代码 | 发现没有字段描述的问题 |
| 抽样 | 在读不完时估计各类失败的比例 | 代码（随机、分层） | 找到罕见失败 |
| 检索 | 按文本模式找具体现象（“503”“policy_blocked”） | 代码（正则）或嵌入检索 | 判断该现象是不是失败原因 |
| 聚类 | 把相似的失败分组，减少要读的数量 | 代码（按签名）或嵌入 + LLM 命名 | 保证每组内部原因相同 |
| 分类 | 给每条或每组一个类别 | 规则能判的用规则；其余用 LLM，对照 rubric | 在证据不足时给出可靠结论 |

Clio（Anthropic，[arXiv 2412.13678v1](https://arxiv.org/abs/2412.13678v1) §2，PDF 正文已读）的流水线是一个参照：属性提取（部分直接计算、部分由模型提取）→ 嵌入与 k-means → 模型给簇命名 → 层级化。它的验证方式值得借鉴：用**预置类别的合成数据**检验端到端的还原准确率（附录 C.2：19,476 条合成对话、20 个类别，还原准确率 94%，随机水平 5%），同时对每个阶段做人工抽查（Table 4：摘要准确率 96%，n=200）。

## 4. 证据：当前模型做这件事有多可靠

| 来源 | 设定 | 结果 | 含义 |
|---|---|---|---|
| TRAIL（[arXiv 2505.08638v3](https://arxiv.org/abs/2505.08638v3)，PDF 正文已读） | 输入一条完整 trace（span 组成的 JSON），输出错误列表，每条含类别、位置（span id）、证据。148 条 trace、841 个人工标注的错误（§4；附录 Table 5 的合计是 835，文内不一致） | 最好的模型 Gemini-2.5-Pro（Table 1）：GAIA 部分类别 F1 0.389、位置准确率 0.546、两者都对 0.183；SWE-Bench 部分 0.148、0.238、0.050。8 个模型中 3 个因上下文长度无法运行 SWE-Bench 部分 | 逐条、细粒度的定位与分类很难；trace 平均 28.7 万与 61.7 万 token（Table 2），长度是主要障碍 |
| Who&When（[arXiv 2505.00212v3](https://arxiv.org/abs/2505.00212v3)，PDF 正文已读） | 多 agent 系统的失败日志，预测负责的 agent 与决定性错误步骤。184 个失败任务；标注者自己在 15–30% 的样本上不确定（§3.3） | 摘要：agent 级 53.5%，步骤级 14.2%。作者结论：离实用还远（§4.8）；这些方法在统计层面比逐条层面更有用（Finding 6） | 步骤级归因接近随机；人工真值本身有不确定性 |
| MAST（[arXiv 2503.13657v3](https://arxiv.org/abs/2503.13657v3)，PDF 正文已读） | 14 种失败模式的固定分类法；人工标注者间 κ=0.88。用 o1 作标注器 | Table 2：零样本准确率 0.89、召回 0.62、精确率 0.68、κ 0.58；加少量示例后准确率 0.94、召回 0.77、精确率 0.833、κ 0.77 | **固定分类法 + 示例**明显提高一致性；准确率远高于召回，说明标签稀疏时只报准确率会误导 |
| HAL（[arXiv 2510.11977v1](https://arxiv.org/abs/2510.11977v1)，部分正文） | 用 Docent 分析 1,634 条 transcript | 发现 TAU-bench 的 Few Shot agent 文件里含测试集样本（附录 A5）；验证只做了精确率（附录 A7.2：0.87，n=49；1.00，n=31；0.94，n=36），原因是“验证误报比验证漏报容易得多” | 这类工具能找到真实的 benchmark 缺陷；但公开的验证几乎都没有召回率 |
| Docent 博客（[transluce.org](https://transluce.org/introducing-docent)，2025-03-24，已读） | — | 自述：“Docent 的摘要经常包含误报”；没有量化验证 | 工具作者自己也把输出当作待核查的线索 |

这些数字来自各自的数据集与模型，不能直接推到你的场景；它们共同支持的判断是：**不要把 agent 的逐条归因当作结论**。

## 5. 机制：结论怎样绑定到原始证据

| 工具 | 做法 | 位置 |
|---|---|---|
| Inspect Scout（commit `5d90b3b`，代码已读） | 渲染 transcript 时给每条消息加序号标记 `[M1]`、`[M2]`；提示要求解释中引用这些标记；`_extract_references` 用正则抽出标记，通过 `id_map` 映射回真实的消息 id；**映射表里没有的序号被直接丢弃**，所以编造的引用无法解析。标记带随机 nonce，消息内容里出现类似标记的文字不会被当成标记 | [`_scanner/extract.py` L549](https://github.com/meridianlabs-ai/inspect_scout/blob/5d90b3bf6ff8b473fb75489ad40bda1ac86ba480/src/inspect_scout/_scanner/extract.py#L549)；[`_llm_scanner/prompt.py`](https://github.com/meridianlabs-ai/inspect_scout/blob/5d90b3bf6ff8b473fb75489ad40bda1ac86ba480/src/inspect_scout/_llm_scanner/prompt.py) |
| Docent（文档已读，无版本号） | 输出里的引用形如 `[T0B49]`（transcript 与块的下标），由代码解析成链接；对 transcript 做切片时保留原始下标，引用仍指向绝对位置 | docs.transluce.org |
| TRAIL 的标注格式 | 每个错误带 span id 与证据字符串 | 论文 §4 |

**共同的设计**：模型输出一个短的位置标记，代码负责解析与校验。草图采用更严格的版本：除了位置，还要求**原文引用**，并检查引用确实是该位置内容的子串。

```python
def validate_evidence(finding):
    for e in finding["evidence"]:
        run = RUNS.get(e["run_id"])                      # 1 run 必须存在
        text = 该 run 在 e["step"] 的内容（步骤，或检查与环境记录）   # 2 位置必须存在
        if e["quote"] not in text: 记为问题               # 3 引用必须是原文的子串
    没有任何证据也记为问题
```

校验只能证明“引用的原文存在”，不能证明“原文支持结论”。后者需要人或另一轮核查。

## 6. 最小 workflow（有边界的单 agent）

```text
1. 代码：加载 rollout → 结构化摘要（成功、终止原因、错误码、任务、模型）
2. 代码：规则分诊 —— 能确定归类的先归类（环境错误记录、参数被拒且与工具说明不符、被拦截后声称完成）
3. 代码：任务 × 模型 的通过率表 —— 找“所有模型都失败的任务”（题目或 grader 的嫌疑）
4. agent：只处理规则判不了的 run。通过只读工具取数据；每条结论必须带 (run_id, step, quote)
5. 代码：校验每条引用；校验失败的结论进入复核队列，不进入报告正文
6. 代码：合并重复（同类别且 run 集合被覆盖）
7. 人：读复核队列与每条结论的代表样本；接受、修改或拒绝；决定记入 [评估集]
8. 输出：类别分布、代表案例、证据位置、竞争假设、待执行验证、复核队列
```

**为什么不默认用多个 agent**：单 agent 加明确的工具与校验已经覆盖这个 workflow；多 agent 增加成本与新的失败方式（Who&When 研究的正是多 agent 系统自身的失败归因有多难）。只有当单 agent 的上下文装不下、且任务能清楚切分时才考虑。

**边界**：agent 只有只读工具；预算（工具调用数、读取的 run 数）固定；不允许它修改评分或数据。

### 工具 schema（节选，完整见草图 [`inv_tools.py`](../../Practice/agent_failure_investigation/sketch/inv_tools.py)）

```json
{"name": "get_steps", "description": "返回某个 run 的步骤 [start, end)，每步带下标 i。",
 "parameters": {"type": "object", "properties": {"run_id": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, "required": ["run_id"]}}
```

其余工具：`list_runs(success, task_id, model)`、`get_checks(run_id)`（检查项、证据、环境错误记录、工具说明）、`grep_runs(pattern)`、`task_stats()`。

### 结论 schema

```json
{"finding_id": "C-3", "category": "harness", "root_cause": "tool_spec_param_mismatch",
 "run_ids": ["r08", "r09"], "status": "confirmed",
 "claim": "给模型的工具说明写的参数名是 address，工具实际要求 new_address；agent 按说明调用被拒",
 "evidence": [{"run_id": "r08", "step": 2, "quote": "expected ['order_id', 'new_address']"},
              {"run_id": "r08", "step": "checks", "quote": "\"params\": [\"order_id\", \"address\"]"}],
 "competing_hypotheses": ["agent 应能从错误信息改用 new_address（恢复能力不足，属于次要的模型问题）"],
 "proposed_check": "修正工具说明后重跑；另测不修正时模型能否从错误信息恢复"}
```

`status` 取 `confirmed`、`uncertain` 或 `insufficient_evidence`。**“不确定”是合法输出**，它把 run 送进复核队列；强迫 agent 给出确定类别会制造误归因。

## 7. 贯穿例子：14 条 rollout 的一次完整调查

数据是**合成的**（[`gen_rollouts.py`](../../Practice/agent_failure_investigation/sketch/gen_rollouts.py)）：3 条成功对照；1 条“成功但中途有一次被拦截的尝试”的对照；模型、环境、harness、任务、grader 故障各 2 条。下面的结论取自 `findings_careful.json`（**手写的示例结论**，代表一份合格的调查输出；没有任何模型生成它）。

| 结论 | 类别 | run | 关键证据 | 状态 |
|---|---|---|---|---|
| 验证了 c1 却去改 B1，被拦截后仍称完成 | 模型 | r04、r05 | r04 第 2 步参数 `"order_id": "B1"`；错误信息 `identity_not_verified_for_order_owner`；r05 最后一步 “Done…” | 确认 |
| 订单服务对所有写请求返回 503 | 环境 | r06、r07 | r06 第 2 步 `503 upstream connect error`；环境记录 `INC-17` | 确认；应记为无效 run 并补跑 |
| 工具说明的参数名与工具实际要求不一致 | harness | r08、r09 | r08 第 2 步 `expected ['order_id', 'new_address']`；工具说明 `"params": ["order_id", "address"]` | 确认；附竞争假设“模型应能从错误信息恢复” |
| T3 指令缺少订单号，也没有列出订单的工具 | 任务 | r10、r11 | r10 第 0 步 `my latest order`；第 1 步 `I need the order ID` | 确认；附竞争假设“本意是测澄清，检查项写错” |
| 指令要求 `9 New Ave`，状态也是它，检查项期望 `9 New Avenue` | grader | r12、r13 | 指令、检查项名称、检查证据三处引用 | **不确定**：grader 写错还是指令写错，要查任务来源 |

对照组：r14 中途有一次 `policy_blocked`，但最终成功。合格的调查不应把它报告为失败。

### 矛盾证据、证据不足、重复

| 情况 | 处理 |
|---|---|
| 证据不足 | 状态 `insufficient_evidence`；写明缺什么（例如“没有该步之后的状态”）；进入复核队列 |
| 分类不确定 | 状态 `uncertain`；列出竞争假设与能区分它们的验证 |
| 矛盾证据 | 同一条 run 同时有环境错误与模型错误时，两者都记录，并说明哪个先发生、哪个足以单独导致失败；不强行选一个 |
| 重复 | 同一根因的 run 合并成一条结论，证据从多条 run 各取一处；按“类别相同且 run 集合被覆盖”检测重复 |

### 人工接受、修改、拒绝

每条结论有三种处置：接受（进入报告）；修改（改类别或根因，记录修改前后）；拒绝（记录原因）。处置记录本身是数据：它是这套助手的验证集的来源，也能统计“被拒绝的比例”。

## 8. 评估调查助手本身

草图 [`score_assistant.py`](../../Practice/agent_failure_investigation/sketch/score_assistant.py) 把三份结论与预置真值比较（2026-11-14 实际运行）：

| | 代码规则基线 | 谨慎版（手写示例） | 有缺陷版（手写示例） |
|---|---|---|---|
| 引用无效的结论数 | 0 | 0 | **1**（给 r08 第 2 步编了一句 “503 upstream connect error”） |
| 故障 run 中归类正确 | 6 | 8 | 4 |
| 交给人（不确定但类别相容） | 4 | 2 | 0 |
| 误归因 | 0 | 0 | **3**（r08 归为环境；r12、r13 归为模型） |
| 漏检 | 0 | 0 | **3**（r09、r10、r11） |
| 对照组误报 | 0 | 0 | **1**（r14） |
| 重复结论 | 0 | 0 | 1 |
| 找到的不同根因 | 5/5 | 5/5 | 2/5 |
| 需要人读的 run（代理指标） | 7 | 6 | **6** |

读法：
- **三件事分开报告**。有缺陷版与谨慎版的“需要人读的 run”都是 6——工作量指标完全看不出质量差异。
- **漏检只有预置真值才能发现**。人只读被报告的结论时，永远看不到 r09–r11。
- **对照组必不可少**。没有 r14 这样的样本，就测不出“把正常过程中的错误当成失败原因”这种误报。
- **代码规则基线表现很好，是因为预置的故障签名很干净，而且规则是在知道故障类型的情况下写的**。它说明的是“能用规则判的先用规则”，不是“不需要 LLM”。规则对没见过的失败方式无能为力。

**评估集应包含**：

| 样本类型 | 测什么 |
|---|---|
| 各类已知故障，每类多条 | 分类是否正确；同一根因是否合并 |
| 无故障对照 | 误报 |
| 成功但过程有噪声的对照 | 是否把无关的错误当成原因 |
| 证据模糊、有两种合理解释的样本 | 是否给出“不确定”而不是硬猜 |
| 同一根因的大量重复 | 是否产生重复结论 |
| 很长的 trace | 位置引用是否仍然准确 |

**指标**：引用有效率；按类别的精确率与召回率（不只报准确率，参见 MAST 的数字）；对照组误报数；重复率；根因覆盖；人工处置中被拒绝的比例；人读的 run 数与不用助手时的对比。不用报告篇幅或结论条数衡量效果。

## 9. 局限

- 草图里没有任何 LLM 或 agent 实际运行：两份“助手结论”是手写的示例，用来验证评分脚本与校验器；规则基线是代码。**真实 agent 在这些工具上的表现没有被测量**。
- 14 条 rollout 很短（几步），而公开证据显示困难主要来自长 trace。
- 预置故障的签名比真实失败干净得多；真实数据里一个 run 常有多个相互作用的原因。
- 引用校验只证明原文存在。
- “需要人读的 run 数”是粗糙的代理，没有测真实的人工时间。

## 来源

| 来源 | 状态 | 支持的结论 | 重点读 |
|---|---|---|---|
| TRAIL, [arXiv 2505.08638v3](https://arxiv.org/abs/2505.08638v3) | 直接读正文 | 逐条定位与分类的准确率；长度是障碍 | §4 任务定义；Table 1–3 |
| Who&When, [arXiv 2505.00212v3](https://arxiv.org/abs/2505.00212v3) | 直接读正文 | 步骤级归因的准确率；统计层面更可用 | §2 定义；Table 1；§4.8 |
| MAST, [arXiv 2503.13657v3](https://arxiv.org/abs/2503.13657v3) | 直接读正文 | 固定分类法与示例对标注器一致性的作用 | §3.3 Table 2 |
| Clio, [arXiv 2412.13678v1](https://arxiv.org/abs/2412.13678v1) | 直接读正文（§2、附录 C） | 流水线分工；用预置真值做端到端验证 | 附录 C.1–C.2 |
| HAL, [arXiv 2510.11977v1](https://arxiv.org/abs/2510.11977v1) | 部分正文 | 实际发现的 benchmark 缺陷；只验证精确率 | 附录 A5、A7.2 |
| Inspect Scout，commit `5d90b3b`：`_scanner/scanner.py`、`_scanner/result.py`、`_scanner/extract.py`、`_grep_scanner/`、`_validation/` | 代码已读，未运行 | 引用解析与丢弃；grep 与 LLM 两类 scanner；验证集支持 | `extract.py` L549 起 |
| Docent 博客与文档 | 博客与文档已读（文档无版本号） | 引用格式；自述的误报问题 | 博客 “What's next” 一节 |
| 本仓库 `Practice/agent_failure_investigation/sketch/` | 代码已运行（合成数据；助手结论为手写示例） | §7–8 的全部数字 | — |

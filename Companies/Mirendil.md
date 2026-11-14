# Mirendil：Model Evaluation MTS

> 证据日期：2026-11-13。当前轮次：**第二轮 take-home**（本人确认）。题目、时限、语言、API／算力预算、AI 使用规则：**全部未知**。此前讨论过的 6–12 小时是准备假设，不是官方时限。

## 1. JD 原文（Ashby API，发布于 2026-06-24，旧金山，$300k–$400k + equity）

JD 很短（约 1.5k 字符），没有列出任职要求与面试流程。

- 公司“training our own models end-to-end”；岗位要“build the evaluation infrastructure that tells us whether our models are getting better in ways we care about”。
- “Design and build evaluation frameworks that measure model capabilities along realistic axes, beyond standard benchmarks.”
- “Build automated eval pipelines and regression-detection systems that run continuously and surface signal quickly.”
- “Develop agent-assisted workflows for humans to efficiently inspect model behavior.”（注意原文是“检查模型行为”，不是“调查”）
- “Instrument training runs with observability tooling so researchers can understand what's changing in model behavior, and why.”
- “Partner with post-training and RL teams to close the loop between eval signal and training decisions.”

## 2. 公司上下文（公司自报，未独立验证）

- **Meet Lor**（2026-10-28）：私测中的 agent 平台，agent “write code, run experiments, and iterate on the results for days, on any machine, hundreds at a time”，可自行申请与释放算力；可使用第三方前沿模型、开源模型和自家的 “Fern”（10M token 上下文）。示例包括：从 100 个 PyTorch PR 构建环境（102 个 agent，每个约 8 分钟）、一夜修复 LiteLLM 安全 bug、“reading thousands of agent traces for failures”。
- **Pretraining at scale without a pretraining team**（2026-10-21）：一位研究员、3.5 个月、全部算力不到 1000 万美元训练出 Mirendil-Base（100B–500B 参数段）；“AI agents wrote over 99% of the code”；只用公开数据。指标是在其自有仓库的 held-out 代码（图 1）和 7 个训练后发布的外部仓库（图 2）上的 BPB。文章也提到后训练模型的 BPB 略差于其基座版本。没有论文或权重。

**准备判断**：研究任务评估、长时 agent 轨迹的检查、BPB 与实际任务能力的连接，都值得准备。**这些材料不证明 take-home 是 Lor、客服 agent、IFEval，或他人做过的同一道题。**

## 3. JD → 证据 → 缺口 → 练习 → 追问

| JD 要求 | 你的真实证据 | 缺口 | 练习 | 可能追问 |
|---|---|---|---|---|
| 超出标准 benchmark 的真实能力评估 | 生产 agent 评估；proxy 与 outcome 的区分 | 研究／工程任务的判分（部分进度、预算、人类基线） | [Knowledge/08 §3](../Knowledge/agent_harness/08_研究agent评估与L1L2L3.md#3-l2-怎样评估三个代表性-benchmark-的设计选择) | “怎么评估一个研究 agent 是否真的变强？” |
| 持续回归检测 | 回归集、targeted 与 broader regression | 噪声 vs 真实回归；配对比较；checkpoint 间比较 | [Knowledge/06](../Knowledge/agent_harness/06_公平比较与统计.md) | “两个 checkpoint 差 2 点，是回归吗？” |
| agent 辅助人工检查模型行为 | trace normalization、failure analysis | 让 agent 读 trace 时怎样防止它的总结出错 | [Knowledge/04](../Knowledge/agent_harness/04_失败诊断与受控重跑.md)；[Practice 分支 D](../Practice/agent_harness/01_岗位分支实验.md) | “你会怎样用 agent 帮人看几千条 trace？怎么验证它的结论？” |
| 训练可观测性 | 因果推断、指标设计 | 训练中的行为探针、与 loss 的对照 | [08 §6](../Knowledge/agent_harness/08_研究agent评估与L1L2L3.md#6-面试追问) | “BPB 降了但任务分没变，你怎么解释？” |
| 与 post-training／RL 闭环 | 向 post-training 提供信号 | 评估信号怎样变成训练决策 | [Knowledge/07](../Knowledge/agent_harness/07_从评估信号到post-training.md) | “哪个信号能当 reward？” |

## 4. L1–L2–L3 准备框架（你的框架，不是公司术语）

- L1 模型指标（如 BPB）→ L2 实际研究任务表现 → L3 跨轮研发收益。
- 讲清 L1 不能自动证明 L2，更不能直接证明 L3 或完全自主的递归自我改进。公开证据中 BPB 与平均 benchmark 分数在基座模型间强相关（Huang et al. 2024），单任务预测误差大（Gadre et al. 2024），没有找到 BPB 与 agentic 任务成功率的直接证据。详见 [Knowledge/08](../Knowledge/agent_harness/08_研究agent评估与L1L2L3.md)。

## 5. Take-home 准备（题目未知时能做的）

**可迁移的交付形态**（不论题目）：
1. 一个可运行的 runner：任务格式、执行、trace 记录。
2. 一个经过测试的 verifier：oracle 通过、no-op 失败、错误变体被拒（[Knowledge/05 §3](../Knowledge/agent_harness/05_verifier的验证与防作弊.md#3-verifier-的测试集怎么建)）。
3. 有效／无效 run 分开；带不确定度的比较报告。
4. 至少一条失败诊断。
5. 简洁 README：怎样运行、判分规则、已知局限、哪些部分未运行。

**事先要问清（拿到题目时）**：时限、语言、允许的模型与 API 预算、是否允许 AI 编程工具、是否需要真实模型运行、提交物格式。

**take-home 自查清单**见 [Review/02 §Mirendil](../Review/agent_harness/02_口述与自测.md#mirendil-take-home-review)。

## 6. 反问

- 当前 eval 信号最常与研究者直觉不一致的地方在哪里？
- 训练过程中目前有哪些行为探针？它们和 BPB 的关系是否被检验过？
- Lor 的 agent 轨迹，现在用什么方式判断“实验结果是真的跑出来的”？

## 未确认事项

take-home 的全部细节；后续轮次；团队规模与分工。

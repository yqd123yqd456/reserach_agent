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

## 5. Take-home 准备：六个专题

题目未知。下面六个专题是按 JD 与公司公开材料推断的**可能方向**，用来建立“拿到题后怎样开始写”的思路；没有证据表明 take-home 会是其中任何一个。每个专题都有主文、可运行草图和一张开工速查卡。

| 专题 | 对应 JD 原文 | 主文 | 草图 | 速查卡 |
|---|---|---|---|---|
| grading | “evaluation frameworks that measure model capabilities along realistic axes” | [Knowledge](../Knowledge/grading/README.md) | [Practice](../Practice/grading/README.md) | [Review](../Review/grading/速查卡.md) |
| task_dataset_design | 同上；“beyond standard benchmarks” | [Knowledge](../Knowledge/task_dataset_design/README.md) | [Practice](../Practice/task_dataset_design/README.md) | [Review](../Review/task_dataset_design/速查卡.md) |
| trace_viewer | “workflows for humans to efficiently inspect model behavior” | [Knowledge](../Knowledge/trace_viewer/README.md) | [Practice](../Practice/trace_viewer/README.md) | [Review](../Review/trace_viewer/速查卡.md) |
| training_eval_diagnostics | “instrument training runs with observability tooling”；“regression-detection systems” | [Knowledge](../Knowledge/training_eval_diagnostics/README.md) | [Practice](../Practice/training_eval_diagnostics/README.md) | [Review](../Review/training_eval_diagnostics/速查卡.md) |
| agent_failure_investigation | “agent-assisted workflows”；Lor 文章中的“读几千条 agent trace 找失败” | [Knowledge](../Knowledge/agent_failure_investigation/README.md) | [Practice](../Practice/agent_failure_investigation/README.md) | [Review](../Review/agent_failure_investigation/速查卡.md) |
| autoresearch_loop | “close the loop between eval signal and training decisions”；公司的研究自动化方向 | [Knowledge](../Knowledge/autoresearch_loop/README.md) | [Practice](../Practice/autoresearch_loop/README.md) | [Review](../Review/autoresearch_loop/速查卡.md) |

**怎样用这些材料交付**：[Review/mirendil_takehome/执行指南.md](../Review/mirendil_takehome/执行指南.md)——拿到题后怎样选切口、与 Claude 怎样分工、准备不足时怎样开始、12 小时怎样分配（准备情境）、最后怎样讲清楚。

**共用基础**：[agent_harness](../Knowledge/agent_harness/README.md) 提供运行与记录的合同（run 目录、events、CheckResult）、verifier 的验证方法与公平比较。六个专题复用它，不重复讲。

**专题之间怎样衔接**（共享一个场景：agent 修一个训练 bug、跑实验、交实验报告）：

```text
task_dataset_design 定义任务与隐藏 verifier
        │
        ▼
agent_harness 运行并落盘（events、快照、verdict） ──► trace_viewer 展示轨迹与评分证据
        │                                                   │
        ▼                                                   ▼
grading 判实验报告（数字对照日志）              agent_failure_investigation 在很多条 run 上找失败类别
        │                                                   │
        └────────────► training_eval_diagnostics 比较 checkpoint、分切片、下钻 ◄──┘
                                    │
                                    ▼
                    autoresearch_loop 用这些结果决定下一轮实验保留什么
```

**推荐学习顺序**：grading → task_dataset_design → trace_viewer → training_eval_diagnostics → agent_failure_investigation → autoresearch_loop。前两个是其余的基础（判分与任务）；trace_viewer 与 diagnostics 是两种“看结果”的方式；后两个把前面的东西组合起来。

**不论题目是什么都适用的交付形态**：
1. 一个可运行的入口，README 里有一条命令。
2. 判分或验证逻辑有自己的测试：正例、反例、等价解、缺失与解析失败。
3. 有效／无效分开；结果带不确定度；统计单位写明。
4. 至少一个从数字下钻到具体样本的例子。
5. README：怎样运行、规则、已知局限、**哪些部分没有运行**。

**拿到题目时先确认**：时限、语言、允许的模型与 API 预算、是否允许 AI 编程工具、是否需要真实模型运行、提交物格式。

**take-home 自查清单**见 [Review/agent_harness/02 §Mirendil](../Review/agent_harness/02_口述与自测.md#mirendil-take-home-review)。

## 6. 反问

- 当前 eval 信号最常与研究者直觉不一致的地方在哪里？
- 训练过程中目前有哪些行为探针？它们和 BPB 的关系是否被检验过？
- Lor 的 agent 轨迹，现在用什么方式判断“实验结果是真的跑出来的”？

## 未确认事项

take-home 的全部细节；后续轮次；团队规模与分工。

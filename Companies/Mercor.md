# Mercor：三个岗位（三条独立招聘线）

> 证据日期：2026-11-13。JD 通过 Ashby 公开 posting API 读取全文（`descriptionPlain`）。轮次以本人 2026-11-13 确认为准。
> 三个岗位都是**第二轮 tech screen**。时长、形式、AI 使用规则：**未知**。不要把 Benchmarking HM 的面经套到另外两条线上。
> 面经中提到 Research Engineering 内有 Benchmarking、Loss Analysis、Post-training 等方向；**Loss Analysis 不是第四个在面岗位**，Enterprise Evals Platform（Engineering 部门）也与它们是不同招聘线。

## 公司上下文（公开材料）

**Agent Eval Systems**（Mercor 博客，2026-06-30，Brandon Lei，MTS；全文已读）。Enterprise Evals Platform 的 JD 直接链接了这篇文章，它是这条线最重要的阅读材料：

- 对象：task、environment（线上是生产环境，离线是 mock 或合成环境）、trajectory、agent output、verifier、activation condition、cumulative reward。
- verifier：隔离的程序或 agent，返回 [0,1] 分数并解释依据；作用范围可以是轨迹、最终 artifact、外部状态变化；运行在自己的 sandbox 中，可使用与被测 agent 不同的模型。定义字段包括模型、activation prompt、verifier prompt、作用范围、生产标记、是否阻塞、阈值、权重。
- 一个评估对象有四种用途：生产判分、离线回归测试、模型与 prompt benchmark、运行时质量门。阻塞型 verifier 在分数达到阈值前阻止交付，并把反馈发回用于修订。
- cumulative reward：激活的 verifier 分数加权平均，未激活的不计入。
- 生产中失败的非阻塞 verifier 可以转成新的离线测试。
- 优化循环：generator agent 跑任务集，fixer agent 读文件、轨迹、分数与解释，修改 prompts、skills 与 harness；只有在验证集上的 cumulative reward 在成本与延迟约束内提升时，才保留新版本。
- 自述局限：verifier 可以被 game（因此尽量确定性，并与人类判断校准）；覆盖缺口会变成生产盲区；循环受生产信号数量限制。

**APEX 与 APEX-Agents**（Mercor 论文，自报结果）：
- APEX（arXiv 2509.25721）：投行、咨询、律所、初级保健四类工作；每个案例包含提示、源文件和逐案例 rubric；标准“客观、具体、自包含”，类比单元测试；单一 LLM judge，每个提示跑 8 次。
- APEX-Agents（arXiv 2601.14242）：33 个“世界”（每个约 166 个文件、9 个应用、63 个工具，无 web），480 个任务；专家先角色扮演一个 5–10 天的项目建立世界，再针对前沿模型对抗式写任务；rubric 为 1–10 条必须满足的标准加标准输出；judge 看提示、输出、变更日志，不看轨迹，在 747 条人工标签上 98.5% 准确；主指标 Pass@1（全部标准满足），同时报告 Pass@8、Pass^8 和均值分数（作者指出均值可作为更密的训练信号）。失败分析：每个 agent 至少 40% 的 run 为 0 分；250 步上限处超时；36 次不该发生的文件删除；通过的 run 步数更少、“死循环”更少。数据在 Hugging Face（`mercor/apex-agents`），harness（Archipelago）在 GitHub。
- 不要把 arXiv 上名为 APEX-Harm、APEX-Voice 的论文归给 Mercor（作者无关）。

**你的公开材料准备判断**：这三条线都围绕一个闭环：专家任务与 rubric → 环境与 verifier → 轨迹判分与失败分析 → 数据、reward 与训练 → 回归与发布门。三条线分别负责这个闭环中不同的段。

---

<a id="1-post-training-re"></a>
## 1. Post-training RE（Research Engineer — Environments, Data and Post-Training）

**JD 原文要点**（Research 团队，旧金山现场，发布于 2026-03-25）：
- “contribute directly to post-training and RLVR, synthetic data generation, and large-scale evaluation workflows”
- “Design and run reward-shaping experiments and algorithmic improvements (e.g., GRPO, DAPO)”
- “Quantify data usability, quality, and performance uplift on key benchmarks”
- 数据生成与增强 pipeline；“Create and refine rubrics, evaluators, and scoring frameworks that guide training and evaluation decisions”
- 加分：工业界 post-training 团队经验（“highest priority”）；论文；作品与代码仓库。

| JD 要求 | 你的真实证据 | 缺口 | 练习 | 可能追问 |
|---|---|---|---|---|
| RLVR、GRPO/DAPO、reward shaping | 与 modeling partners 合作的 controlled DPO-style 实验；材料涉及 GRPO prompt selection | 能手推 GRPO advantage 与 DAPO 四项修改；讲清全对／全错组为何无梯度 | [Knowledge/07 §1–2](../Knowledge/07_从评估信号到post-training.md)；手算 G=4 例子；读 verl `agg_loss` | “为什么训练后期变慢？”“clip-higher 解决什么？”“截断样本怎么处理？” |
| 量化数据的可用性与收益 | failure mining、preference-pair curation、回归评估 | 能给出“数据真的有用”的完整对照设计 | [07 §5](../Knowledge/07_从评估信号到post-training.md#5-怎样证明选出的数据真的提升了模型)；[Practice 分支 C](../Practice/01_岗位分支实验.md) | “怎么证明提升不是来自 judge？”“随机 reward 也涨了怎么办？” |
| rubric、evaluator 指导训练 | SLM judge 蒸馏（约 88% held-out teacher agreement） | judge 当 reward 时的风险与监控 | [07 §3](../Knowledge/07_从评估信号到post-training.md#3-哪些信号能当-reward)、[05](../Knowledge/05_verifier的验证与防作弊.md) | “你的 judge 能直接当 reward 吗？” |
| 环境 | 评估基础设施 | 训练环境 verifier 的构建（SWE-Gym、R2E-Gym、SWE-smith） | [07 §4](../Knowledge/07_从评估信号到post-training.md#4-训练环境里的-verifier-是怎么做的代码任务) | “执行型与执行无关 verifier 怎么组合？” |

**ownership 边界**：你亲自做过 evaluator 微调；在 agent 改进中负责数据、评估与实验分析；大规模 policy 训练基础设施由合作团队负责。**不能说**你独立训练过完整的大规模 GRPO 系统。

---

## 2. Enterprise Evals Platform MTS（Member of Technical Staff）

**JD 原文要点**（Engineering / Core Engineering，旧金山现场，发布于 2026-08-15）：
- 自述为“a platform engineering role with good depth of understanding in evals”；构建 verifier、agent 被测量的环境与判分基础设施，“abstracted across customers, domains, and tasks”
- “Define golden sets: decompose real tasks and encode the expert quality bar.”
- “Build verifiers over agent trajectories and outputs, calibrated and hard to game.”
- “Build the eval platform that runs offline environments, task suites, and grading at scale.”
- “Run loss analysis over production trajectories and turn failure modes into regression tests.”
- “Run the optimization loop across models, prompts, skills, and harnesses.”
- “Own the rollout gates that decide whether an agent change ships.”
- 要求：理解“how agent runtimes and harnesses produce a trajectory and where it fails”；计算机本科；1–5 年工业界软件工程；熟悉 terminal-bench、tau-bench、APEX 怎样构建以及在哪里被 game；能把模糊的质量概念变成可测量的，并有 agent 或模型改进作为证明。加分：Harbor 环境与 RL 环境。

| JD 要求 | 你的真实证据 | 缺口 | 练习 | 可能追问 |
|---|---|---|---|---|
| golden set、专家质量标准 | rubric 与 failure taxonomy；targeted expert labeling（部分仍在推进） | 任务分解与“专家标准编码成可执行检查”的完整例子 | APEX-Agents 的 rubric 设计；[Practice L3 workspace 任务](../Practice/00_共用harness规格.md#5-level-3多类任务故障注入诊断与比较报告) | “给你一个模糊的企业任务，怎么写 golden set？” |
| 轨迹与输出的 verifier，校准且难以 game | 规则与语义 judge 分层；结构化输出检查 | verifier 的测试集（oracle、no-op、等价解、对抗 agent） | [Knowledge/05](../Knowledge/05_verifier的验证与防作弊.md) | “你的 verifier 自己怎么验证？”“tau-bench 在哪里被 game？” |
| 离线环境、任务集、规模化判分 | common data contracts、trace normalization、judge orchestration | 环境重置、执行隔离、并发调度、可靠重试、结果可追溯 | [Knowledge/01](../Knowledge/01_三种harness与最小对象模型.md)、[03](../Knowledge/03_故障注入与恢复.md)；读 Inspect 的 sandbox 生命周期与 Harbor 的 `Verifier.verify` | “环境怎么重置？”“infra 错误怎么和模型失败分开？” |
| 生产轨迹 loss analysis → 回归测试 | production failure 与 disagreement mining | 从失败 trace 抽最小复现并确认测试有效 | [Knowledge/04 §5](../Knowledge/04_失败诊断与受控重跑.md#5-把诊断变成回归测试) | “这个失败怎么变成回归测试？怎么确认测试本身有效？” |
| 跨 models/prompts/skills/harnesses 的优化循环 | 评估结果驱动迭代 | 公平比较与统计 | [Knowledge/06](../Knowledge/06_公平比较与统计.md) | “fixer agent 改了 harness，怎么保证验证集没被过拟合？” |
| rollout gate | 质量／成本权衡 | 门的具体规则 | [06 §6](../Knowledge/06_公平比较与统计.md#6-面试可能追问) | “你会怎样设计 rollout gate？” |

**一个可以主动提出的观察**：Mercor 博客中的优化循环用“验证集上 cumulative reward 提升”决定是否保留新版本。若 fixer agent 能看到验证集的分数与解释，多轮之后验证集就变成了开发集。合理的回答是：保留一个 fixer 看不到的冻结测试集用于最终 gate，并对 verifier 本身做对抗测试。这是推断性的设计讨论，不是对 Mercor 内部实现的断言。

**主动边界**：你拥有评估 harness，不拥有被测产品 agent 的 runtime；最新架构（bounded Agent-as-Judge、retriever → standardizer → judge）含 exploring／design 内容。

---

## 3. Benchmarking RE（Research Engineer — Benchmarking）

**JD 原文要点**（Research 团队，旧金山现场，发布于 2026-08-18）：
- 负责 benchmarking pipeline、评估系统与失败分析流程；结论反馈到“post-training, RLVR, and data pipelines”
- 为 tool use、agentic 行为与真实推理设计 benchmark 与指标；端到端运行、判分、dashboard 与报告
- 失败分析：“(e.g., wrong tool use, reasoning errors, safety/alignment issues); categorize failure modes, quantify prevalence, and feed findings into reward design, data curation, and benchmark design”
- rubric 与 evaluator：“balance rigor with scalability (human vs. model-as-judge, calibration, agreement)”
- 加分：评估／benchmark 或 post-training 团队的工业经验（“highest priority”）；“RL-style workflows that use evals for reward shaping”；作品如“eval frameworks, benchmark suites, failure-analysis reports”。

**本人实际面经（2026-11-11 HM 轮）**：被问“给一个失败任务和完整 rollout，怎样找失败原因？”。你按 environment/tooling、task/benchmark/grader、model capability 三类回答，也谈了终态正确与过程违规、reward hacking 与无界 sub-agent 成本；面试官认可这个分类。**下一步**：从分类进入证据。

| JD 要求 | 你的真实证据 | 缺口 | 练习 | 可能追问 |
|---|---|---|---|---|
| tool use／agentic benchmark | 生产 agent 评估 | 公开 benchmark 的判分机制与漏洞 | [Knowledge/02](../Knowledge/02_工具使用测量与过程约束.md)、[05](../Knowledge/05_verifier的验证与防作弊.md) | “你会怎样设计一个 tool-use benchmark？” |
| 失败分类与占比 | failure taxonomy、disagreement mining | 诊断证据链与受控重跑 | [Knowledge/04](../Knowledge/04_失败诊断与受控重跑.md)；[Practice 分支 B](../Practice/01_岗位分支实验.md) | “你怎么知道这是模型问题而不是 grader 问题？”“占比的分母是什么？” |
| human vs model judge、校准、一致性 | SLM judge、teacher agreement | 对人类的准确率、JudgeEval 式验证 | [05 §5](../Knowledge/05_verifier的验证与防作弊.md#5-rubric-与-llm-judge) | “judge 和人类不一致怎么办？” |
| 反馈到 reward 与数据 | failure → data → post-training 的协作 | 哪些失败可以转成 reward | [07](../Knowledge/07_从评估信号到post-training.md) | “这个失败模式应该进 reward 还是进数据？” |
| 结论可信 | 因果推断背景 | 配对比较、聚类、功效 | [06](../Knowledge/06_公平比较与统计.md) | “这个 3 点提升可信吗？” |

---

## 三条线的共同反问（有信息增量的）

- 下一轮的形式与 AI 使用规则是什么？（未知，必须问）
- 团队目前最难验证的任务类型是什么？verifier 在哪类任务上最常被 game？
- rollout gate 现在用哪些信号，哪部分仍需要人工判断？
- （Post-training RE）reward 主要来自规则、rubric judge 还是执行测试？训练与评估用的 verifier 是否分开？

## 未确认事项

各轮时长、形式、AI 政策；面试官；内部团队分配。公开材料不能说明 tech screen 的题目。

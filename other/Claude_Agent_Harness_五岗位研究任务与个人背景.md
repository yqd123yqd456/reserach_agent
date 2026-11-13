# Agent Harness 五岗位研究任务与个人背景

更新：2026-11-13（America/New_York）。用途：交给新 Claude Code 项目的独立任务文件。岗位轮次来自本人最新确认；公开岗位与公司材料在本次联网核查；个人经历来自 Interview Prep 项目中的简历、项目记录与实际面试复盘。本文不是已经完成的 agent harness 专题研究。

## 怎么使用

把本文件放进新的 Claude Code 项目。已安装之前的四个 research skills 时，直接输入：

```text
/topic-research 请完整阅读 @Claude_Agent_Harness_五岗位研究任务与个人背景.md，按第 4 节完成针对我五个在面岗位的 Agent Harness / Evaluation / Post-training / Scalable Oversight 研究。背景和轮次已写好，不要重新让我填表。先简短说明你选的知识结构，然后继续调查并产出材料；保留事实、推断、提案和待验证的区别。
```

如果文件仍在 `other/`，把引用改成 `@other/Claude_Agent_Harness_五岗位研究任务与个人背景.md`。如果 skill 尚未安装，可以直接把上面 `/topic-research` 删掉，并要求遵循本文的任务和质量标准。

本文已包含必要背景。第 6 节的原项目路径只供溯源：新项目里没有这些文件，也可以根据本文开始研究；不要声称读过未提供的原件。

## 目录

- [1. 五个目标岗位和当前轮次](#roles)
- [2. 我的背景：经历、成果与边界](#background)
- [3. 我目前的学习基础与偏好](#learning)
- [4. 给 Claude 的具体研究任务](#task)
- [5. 已核查的公开研究入口](#sources)
- [6. 背景来源与未确认信息](#audit)

<a id="roles"></a>
## 1. 五个目标岗位和当前轮次

**轮次以本人 2026-11-13 的确认优先**，覆盖旧笔记里的 recruiter intro、等待推进或 HM 准备状态。以下准备重点是根据 JD、公司材料与本人面经推导的建议，不是已知考题。

| 我使用的简称 | 对应公开岗位 | 本人确认的当前轮次 | 最需要回答的问题 |
|---|---|---|---|
| Mercor Post-training RE | Research Engineer — Environments, Data and Post-Training | 第二轮 tech screen | 如何把可靠的 evaluation / data / reward 信号变成可验证的训练收益？ |
| Mercor Eval-platform MTS | Member of Technical Staff, Enterprise Evals Platform | 第二轮 tech screen | 如何把真实任务、专家标准、环境和 verifier 做成可复用的运行平台？ |
| Mercor Benchmarking RE | Research Engineer — Benchmarking | 第二轮 tech screen | 如何构建可信 benchmark，诊断失败，并给出可执行的改进结论？ |
| Mirendil Evaluation MTS | Member of Technical Staff, Model Evaluation | 第二轮 take-home | 如何实现能判断模型／研究 agent 是否真正进步的评估工具？ |
| Resolution Alignment Scalable Oversight RS | Research Scientist，Scalable Oversight 方向 | 第一轮 | 如何把弱监督者判断强模型的问题变成具体、可检验的研究？ |

### 1.1 Mercor Post-training RE

【公开 JD】工作覆盖 post-training / RLVR、reward shaping、数据生成与质量评估，并举例 GRPO、DAPO。公开岗位与本人简称相符；不据此假定具体 interviewer、内部 team assignment 或考题。[官方 JD](https://jobs.ashbyhq.com/mercor/97b8c17e-e438-4b61-bab1-9ae18e2c3f34/)

【准备判断】围绕 rollout → verifier/reward → 数据筛选 → 更新模型 → held-out evaluation 组织复习。能解释哪些性能问题来自数据、奖励、环境、训练实现或评估器，而不是看到分数上涨就归因给算法。

我的连接：SLM judge 的实际训练经验、failure mining、preference-data curation、与 modeling partners 的实验协作。重点补齐训练环节的具体机制、可调试的小实现和实验判断，不把我包装成大型 policy RL trainer 的端到端 owner。

### 1.2 Mercor Enterprise Evals Platform MTS

【公开 JD】强调 golden sets、轨迹与结果 verifier、离线环境和规模化 grading、production loss analysis，以及模型／prompt／skill／harness 的优化和发布门槛。这是需要 eval 深度的平台工程岗位。[官方 JD](https://jobs.ashbyhq.com/mercor/35e1923b-3c1c-4bb4-94d6-ef3a529ef871/)

【准备判断】核心是把专家标准编码成任务与判分对象，明确接口、状态、版本、运行、失败和回归。需要能从架构讲到一条真实 run，以及如何判断“该不该发布”。

我的连接：common data contracts、trace normalization、judge orchestration、质量／成本权衡和跨产品复用。补充环境 reset、执行隔离、并发调度、可靠重试与结果可追溯性。

### 1.3 Mercor Benchmarking RE

【公开 JD】负责 tool use、agentic behavior、真实推理的 benchmark、评估系统、rubric/scorer 和系统性 failure analysis；将结论反馈到训练、reward 与数据。[官方 JD](https://jobs.ashbyhq.com/mercor/40cc6334-3a6c-42f8-a4ec-d490486d00e8/)

【本人实际面经】11 月 11 日 Benchmarking HM 问过：给一个失败任务和完整 rollout，怎样找失败原因？我按 environment/tooling、task/benchmark/grader、model capability 三类回答，也谈了终态正确与过程违规、reward hacking 和无界 sub-agent 成本。面试官认可这个分类。

【下一步要补】从分类进入证据：验证失败是否真实 → 找最早影响结果的偏离 → 提假设 → 做受控干预 → 重跑 → 给出有置信边界的结论。不要假定只有一条 golden trajectory。

该面经提到 Research Engineering 内有 Benchmarking、Loss Analysis、Post-training 等方向；**不要把 Loss Analysis 当成我新增的第四个 Mercor 岗位，也不要把 Enterprise Platform 招聘线和它们合并成同一场面试。**

### 1.4 Mirendil Model Evaluation MTS

【公开 JD】重点是现实能力评估、持续回归、agent 辅助行为调查、training observability，以及与 post-training/RL 的反馈。[官方 JD](https://jobs.ashbyhq.com/mirendil/2c7c136a-b24b-456f-afb3-d5530bad84b5)

【准备判断】优先练可运行的评估交付：任务与数据格式、runner、verifier、trace、失败诊断、可复现实验和简洁 README。同时准备 checkpoint / harness 变化怎样公平比较，以及训练指标怎样连接研究任务表现。

【公司上下文】Lor 的公开定位涉及长时任务、实验执行和研究工作流；公司也披露了 AI 辅助预训练实验。它们支持“研究任务评估值得准备”，**不证明 take-home 一定是 Lor、客服 agent、IFEval、autores research 或别人做过的同一道题**。[Meet Lor](https://mirendil.com/news/meet-lor/)；[预训练实验](https://mirendil.com/news/pretraining-at-scale-without-a-pretraining-team/)

具体题目、时限、语言、API／算力预算和 AI 使用规则仍未知。之前讨论过的 6–12 小时属于准备情境，不是已核实的官方时限。

### 1.5 Resolution Alignment — Scalable Oversight RS

【公开 JD】该 RS 岗需要将 alignment 问题转成实证或理论研究；scalable oversight 的相关背景包括 debate、prover-verifier games、RLHF 实证及相关数学。官方描述的 initial screener 是 15 分钟，谈研究背景、动机和兴趣；具体邀请安排优先。[官方 RS JD](https://jobs.ashbyhq.com/resolution/65704205-7ccd-4df6-a7d1-3e3338bd80a8)

【准备判断】第一轮优先准备研究身份、why alignment、why this program、两个可检验的问题，以及自己如何设计区分 competing explanations 的实验。不能只讲“我能搭一个 evaluator”。

我的桥梁是 judge 可靠性、标签噪声、teacher–student、有限证据下的判断和实验设计。关键区分：**把强 teacher 蒸馏成小 judge，不等于已经解决弱监督者可靠监督更强模型的问题。**

可以研究的提案：在固定监督成本下，证据访问、任务分解或 debate 是否提高较弱 judge 对强模型错误的识别？怎样区分正确性提升与更会说服 judge？这些是拟研究方向，不是我已有的 scalable oversight 成果。

Resolution 官方资料使用过旧名 Sequent；只采用对齐研究机构的来源，不混入其他同名公司。其 RE 的 coding 流程不等于我的 RS 流程。[公司说明](https://resolution.org/launch)

[↩ 返回目录](#目录)

<a id="background"></a>
## 2. 我的背景：经历、成果与边界

### 2.1 一句话定位

**我是一名以 production LLM / agent evaluation 为核心的 Applied Scientist，连接评估基础设施、专用 judge 训练、失败与数据分析，以及模型改进的实验反馈。**

不是从零学习 ML；当前要补的是把已有的评估经验落实到独立的 agent runtime / environment / harness 项目，并提高研究问题和实验的具体程度。

### 2.2 基本经历

- 姓名：Qindong Yang。
- Microsoft，Applied Scientist II，AI / Copilot Evaluation 相关团队，2022 年 2 月至今。实际 title 使用 Applied Scientist II。
- 团队是 centralized evaluation team，独立于直接开发产品 agent 的团队；工作涉及 Copilot / Office，尤其 Word 与 Cowork agent 的评估。
- 之前任 Logility Data Scientist（2019 年 11 月至 2020 年 7 月），做需求预测、定价等应用 ML。
- CMU，Master of Information Systems Management（2020–2021）；University of Richmond，BA Mathematics & Economics（2015–2019）。不虚构 PhD。
- 主要可依赖的技术基础：Python、PyTorch、PySpark、SQL、数据处理和实验 pipeline；工作材料还涉及 Azure ML。简历列出的其他语言不自动代表近期实战熟练度。

### 2.3 主项目：集中式 Agent Evaluation

**问题。** 不同产品 agent 的 endpoint、tool schema 和 workflow 不断变化，需要共用数据与运行基础设施，同时保留任务自己的成功标准。

**我实际负责的核心。** Python / PySpark 评估与数据处理；trace extraction / normalization；rubric 与 failure taxonomy；judge orchestration；相关证据选择、结构化输出检查、指标聚合和失败分析。平台层面涉及 common contracts，将 requests、responses、traces、telemetry 接到统一流程。

**判分逻辑。** 将轻量规则／heuristics 与语义 judge 分层使用。任务完成、质量、满意度不是同一个变量。对于能观察到最终文档或状态的任务，结果检查应使用这些证据；对于拿不到 final artifact 的情况，feedback、follow-up、copy/download 等只是 proxy，不能自动声称完成了独立 outcome verification。

**迭代方式。** 通过生产失败与 disagreement mining 识别难例，改 rubric／数据／回归集，向 post-training 提供信号。targeted expert labeling 有正在与产品团队推进的部分，不把它描述成已经完备的专家校准体系。

**状态边界。** bounded Agent-as-Judge、retriever → standardizer → judge、长尾 agentic fallback 等最新架构含 exploring / design 内容。不能从设计图推出模型已训练、模块已部署或收益已测量。拥有 evaluation harness，不等于拥有被测产品 agent runtime。

### 2.4 专用 SLM Judge：真实模型训练经验

我做过以较强 LLM judge 的标签训练较小 evaluator，涉及 rubric / task-completion scoring、SFT / distillation、数据筛选与错误分析。已有材料的结果是约 88% held-out teacher agreement、72% online inference cost reduction。

这些数字需要按对应版本解释：agreement 不等于 human accuracy；cost reduction 不等于 latency reduction，也不能自动迁移到另一套模型架构。具体 backbone、loss、split、trainable modules、LoRA 配置、训练预算与 baseline 仍需用真实实验记录补足，不能拿别的版本拼接。

**HalfJudge 是另一条较新的研究原型。** 关注 instance 与 rubric 表征、rubric caching、编码／融合及质量效率权衡。可用于讨论研究问题与实验设计，但不写成已生产部署或所有泛化／端到端速度结果均已验证。旧版 88% / 72% 不归给 HalfJudge。

### 2.5 失败 → 数据 → Post-training

我已有的连接包括 production failure analysis、synthetic / counterfactual examples、preference-pair curation、反馈／reward signal 设计、targeted 与 broader regression evaluation；与 modeling partners 合作进行 controlled DPO-style experiments，材料也涉及 GRPO prompt selection / RL 反馈。

表达时区分三件事：

1. 我亲自做过的 evaluator fine-tuning。
2. 我在目标 agent 改进中负责的数据、评估和实验分析。
3. 合作团队拥有的底层训练基础设施与大型 policy 更新。

不能把 2、3 合并成“我独立训练了完整的大规模 GRPO 系统”。

### 2.6 因果推断与研究基础

项目材料记录了 DML、GNN-based causal graphs、confounder analysis，用于研究 Copilot quality 与 retention 等产品结果的关系。这支持我的测量意识、识别假设和实验设计基础。

迁移到 harness / RSI 时，我可以提出配对实验、随机化干预、控制 compute / task / model / harness 变化、区分 proxy 与最终收益。**画 causal graph 只是明确假设，不会自己建立因果识别；DML 也不能替代有效实验或识别条件。** 这部分是迁移思路，不能写成我已做过 RSI 因果验证。

研究记录还包括三篇 Microsoft 内部 technical papers（evaluation、privacy-preserving synthetic data、causal inference）、pending US patent 的共同发明经历，以及三次组织级 hackathon wins。这些属于个人材料中的内部研究证据，不等价于公开顶会论文或公开 benchmark。

近期学习还涉及 compute-efficient data selection、Jacobian / NTK / gradient alignment 和 LoRA ablation。这体现正在形成的实验思路；对应笔记明确包含 proposal，不能当成已完成并取得 lift 的项目。

### 2.7 数字使用规则

| 材料中的数字 | 可表达的含义 | 需要保留的边界 |
|---|---|---|
| 69% processing time reduction | 11 月准备材料中的 evaluation pipeline 效率口径 | 需确认 baseline、workload、计时范围、具体改动 |
| 约四天 → 一小时 | 较早记录的一次 evaluation cycle 周转提效 | 与 69% 关系未确认，不合并为同一次实验 |
| 88% teacher agreement | 旧版 evaluator 与 teacher 的 held-out 一致性 | 不叫 88% human accuracy，不套给 HalfJudge |
| 72% inference cost reduction | 特定 workload / baseline 的旧版 judge 成本比较 | 不叫通用收益或 latency 收益，明确 fallback/retry 计费范围 |
| 25M+ 用户 | 简历中的相关产品／平台服务范围 | 不是我逐一评估过的用户数；旧稿还有 15M+，自述可暂不报规模数 |

研究和面试稿默认可不报尚未补齐分母与范围的数字。不要为了写得有冲击力填造实验细节。

### 2.8 可直接使用的英文背景主稿

> I'm an Applied Scientist II at Microsoft, working on centralized evaluation for Copilot and Office agents. My work connects evaluation infrastructure, specialized evaluator models, and failure analysis for model improvement.
>
> On the systems side, I build Python and PySpark workflows that normalize agent traces, orchestrate rubric-based evaluation, and turn results into actionable failure analysis. A recurring challenge is distinguishing verified outcomes from proxy signals when the final artifact is only partially observable.
>
> On the modeling side, I've fine-tuned smaller evaluators using labels from stronger models, and I'm exploring architectures that reuse rubric representations. I also collaborate with modeling teams on preference data and regression evaluation. I distinguish my ownership of evaluation and data from the training infrastructure owned by those teams.
>
> My research interest is how to make evaluation signals trustworthy enough to guide improvement: whether an apparent gain reflects better capability, a change in the environment, or a weakness in the evaluator. I'm looking to apply that experience more directly to agent benchmarks, post-training, and research workflows.

这是一份跨岗位底稿。Resolution 版本还需要解释 alignment 动机和具体 research question；不能直接把最后一句换成公司名就当准备完成。

[↩ 返回目录](#目录)

<a id="learning"></a>
## 3. 我目前的学习基础与偏好

### 已有基础与正在补的内容

- 我有 production evaluation 与实际小模型训练经验，不需要从“LLM 是什么”开始。
- 已有 CS336 / post-training / PyTorch coding 学习笔记，但阅读、看懂推导、在提示下练习和独立限时实现是不同层次。不能根据文件数量推断我已掌握。
- 我此前明确说过没有 JS 基础，并缺乏独立从零搭建这类完整 agent MVP 的经验。优先 Python，必要时才引入前端／TypeScript；使用 AI 编程工具不替代我理解关键接口和失败路径。
- 正在学习 agent loop、tool design、fake service / sandbox、policy、vertical slice、trace viewer、correctness evaluation 与 AI 辅助开发。
- 之前的客服改地址 agent 是教学例子，不是已交付项目，也不是 Mirendil 已确认题目。
- 我想补的重点是 **机制深度 + hands-on + 前沿真实实践**。需要论文、公司技术博客和官方代码共同支持判断。

### 我喜欢的讲法

先定义 → 一个具体例子 → 机制与必要公式 → 工程选择 → 怎么测／怎么失败 → 适用边界 → 面试怎么说。

不要只列名词、画架构图或收集论文。请解释一个设计解决了什么真实问题、输入输出长什么样、怎样用最小实验检验，并提供失败案例。

我喜欢“agent 为什么比单轮难”的结构：多步、有状态、有副作用、路径不唯一，各自迫使我们做什么。再连接 recovery、reset、隔离、约束式 verifier、运行方差和预算。若用 `p^n` 说明误差累积，必须交代独立性与每步都必须成功等简化假设；不要说真实 agent 必然服从它。

我认可 harness-first 的实操切口：先把任务、环境、可观测证据和判分跑通，再判断模型／prompt／harness 的改进。这是准备顺序与实验思路，不是“模型不重要”的结论。

我关注 Mirendil 的三层判断：L1 模型指标（例如 BPB）→ L2 实际研究任务 → L3 跨轮研发收益。这个三层结构是我的准备框架，不是公司的官方术语。需要讲清 L1 不能自动证明 L2，更不能直接证明 L3 或完全自主 RSI。

### 要修正的过度简化

- fake service 是服务的可控实现；sandbox 是执行隔离／约束。一个内存 fake 不自动构成安全 sandbox。
- 硬约束尽量在执行边界用代码 enforcement；可以用 AI 协助写代码，但我必须理解和验证。不存在普遍要求“policy 每行只能我手写”。
- policy 与 journey 一起设计，不能先完成危险动作再事后补检查。
- 确定性的状态／格式／权限／数值检查用代码；开放质量用 rubric 与经验证的 judge／专家。rubric 也可以编码，不是 code 的对立面。
- MVP 能跑通是起点，还要定义正确性和失败行为；正确率门槛由场景、样本和约束决定，不能随意许诺统一的 90% / 95%。
- 是否 Docker 取决于任务、环境重建和隔离需求；一小时练习不必机械先搭 Docker，也不能因时间短忽略不可信执行风险。
- 看别人的 take-home 或开源实现，是学习工程选择；没有证据证明公司不会换题。

[↩ 返回目录](#目录)

<a id="task"></a>
## 4. 给 Claude 的具体研究任务

**请把本节视为要执行的用户任务，前面三节是我的背景与约束。**

### 4.1 目标

根据我五个在面岗位，研究我需要掌握的 agent harness 知识与实践，并把它连接到 evaluation、post-training、research automation 和 scalable oversight。请自行选出最有帮助的结构，避免写五份重复的公司百科或泛泛 agent 教程。

用一个共用知识主线组织：

`task / environment → agent runtime → trace / artifacts → verifier → failure diagnosis → data / optimization / training → independent validation`

这只是起始假设，可以根据调查调整。明确 agent execution harness、evaluation harness 和 training rollout infrastructure 的关系与不同职责；不要因为都叫 harness 就混成一个组件。

### 4.2 调查要求

1. 以第 1 节的五个岗位和轮次为准，复核第 5 节的一手材料。公开职责、本人实际面经、准备推断、题型未知分别标注。
2. 从具体技术问题选择论文、公司技术博客和官方实现。每个关键来源说明：我应读哪一部分、解决哪一个准备缺口、怎样迁移到一个实验或面试追问。
3. 结合经典基础和近期工作；不要以“最新”代替相关性，不堆十几篇都没读的链接。确认作者、日期／版本、代码与数据可得性；官方自报效果与独立验证分开。
4. 对实现细节阅读官方 repo 的关键对象／文件／函数；按实际读到的版本引用。没有看过代码不能声称“代码就是这么做的”，没有执行不能声称复现。
5. 可调查方向：Mercor 的 APEX / agent eval systems；真实工具／状态交互的 agent benchmarks；代码任务的 environment 与 verifier；研究 agent 的实验验证；弱监督、debate、prover-verifier 等。按岗位价值筛选，不要求每个方向都展开成长论文。
6. 不将他人的 `ai_interview_prep_2026` 项目、面经或实验结果归到我身上。如果我提供 `19_case_agent_benchmark.md`，它是内容风格参考，不是已审计的技术标准。
7. 不提供无依据的考题概率。可以按证据强弱与准备收益排序，并说明哪些题型只是合理演练。

### 4.3 必须具体回答的问题

- 一个最小 agent / eval harness 有哪些对象？task、tool schema、state、step、termination、trace、verifier、result 的输入输出是什么？
- agent 动态选 tool 的能力如何测？怎样区分正确 tool、正确参数、正确时机、结果解释、失败后的恢复？为什么只统计 tool-call JSON 合法率不够？
- 怎样让每题 reset、支持多个合法路径、验证最终 artifact/state，同时检查不可违反的过程约束？
- 故障注入怎样设计？哪些 fault 可恢复、哪些不可恢复？recovery rate 的分母、成功定义、重试成本和 clean control 是什么？
- 如何区分 model、harness、环境、任务和 grader 引起的失败？给一条 rollout 的完整诊断与受控重跑例子。
- 如何验证 verifier 本身？怎样防止正确答案被误拒、错误答案被接受、rubric gaming 与数据泄漏？
- 如何公平比较 model / prompt / skill / harness 变化？任务配对、预算、重复运行、不确定度、开发集与保留测试集各起什么作用？
- post-training 如何使用这些结果？哪些只是筛选／诊断信号，哪些可以成为 reward？怎样证明选出的数据真的提升模型，而不是只提高 judge 分数？
- BPB 等模型指标怎样连接实际研究任务？如何具体区分更低 loss、更好修 bug／复现实验，以及多轮研发效率提高？
- Resolution 方向中，强模型如何可能误导弱 judge？怎样用 evidence access、debate 或 decomposition 做可证伪实验？固定监督预算下需要哪些 control，哪些结论不能由小实验推出？

### 4.4 Hands-on 深度

不要为了五个岗位给我五个独立大项目。优先设计 **一个共用 Python harness 小项目，加少量岗位分支实验**。选择能自然支持状态、工具、失败、结果验证的任务；客服例子可以帮助入门，但要说明怎样过渡到文档／数据／代码或研究任务。

练习按层级推进：

1. 可控 fake service + 一个 vertical slice + 明确验收 + 状态／audit + 基础 verifier。
2. 接真实模型的动态 tool loop；区分 scripted dry-run 仅验证接口与真实 agent 行为。
3. 多类任务、故障注入、reset、trace 诊断、重复运行与比较报告。
4. 按岗位选一个深入扩展：平台运行可靠性、benchmark audit、training-data ablation、研究任务验证或 weak-judge oversight 实验。

每一级给出数据 schema、模块边界、最小样例、验收检查、预计学习工作量和常见失败；把“建议练习”和“已经运行”分开。没有凭据时保持真实模型路径未验证，不用伪造结果补齐。先形成研究与练习材料，不自动消耗付费 API 或启动 GPU 训练。

重点是我能解释与修改关键逻辑，而不只是 AI 生成一个很大的 repo。对每个核心组件说明：我该自己能写哪部分、可以让 AI 帮哪部分、review 时如何发现错。

### 4.5 交付结构

在新项目已有结构合适时沿用；否则用四个入口，允许必要 overlap：

```text
README.md                   # 导航、阅读顺序、知识前置关系和下一步
Knowledge/                  # 共用概念、机制、设计选择与证据
Companies/                  # 三家公司、五个岗位应用与真实面经/推断边界
Practice/                   # 共用 harness 练习规格、岗位分支实验与验收
Review/                     # 个性化差距、优先级和面试口述/自测
```

通用概念有主位置；公司材料保留足够上下文再链接过去，不机械去重。公司信息、知识定义、练习结果、实际面经不要混成一个难维护的大文件。

至少交付：

- 一份知识地图与优先级：五个岗位各需要多深，哪些共用，哪些独有；不要把准备优先级伪装成考题概率。
- 一份有来源的核心学习材料：定义、例子、机制、设计、验证和边界连起来。
- 一份共用小项目规格与可执行的练习步骤；这轮不默认要求写完全部代码。
- 五个岗位的映射：JD 要求 → 我的真实证据 → 缺口 → 具体练习 → 可能追问。
- 一份口述与自测：30 秒／90 秒／深入追问；Resolution 单列 why alignment、research question 和 experiment proposal，Mirendil 单列 take-home review。
- 学习时间估算按模块给最短／标准／深入投入，说明假设；不要擅自安排具体面试日期或把旧“下周六”当当前日程。

### 4.6 完成标准

读完后，我应该能讲清一次 agent run 如何发生、在哪里判定成功、失败如何定位、改动怎样验证；能区分工程控制与模型能力、proxy 与独立证据；知道如何从我的真实项目过渡到五个岗位的技术讨论。

材料不能只有“production-grade、robust、scalable”等形容词。每个重点都要落到接口、数据、实验、失败或判断标准。最后审查过度主张、引用对应、示例正确性和未知项，修正后再交付。

[↩ 返回目录](#目录)

<a id="sources"></a>
## 5. 已核查的公开研究入口

访问核查日：2026-11-13。部分 Ashby 页面直接读取只返回 JS 壳；本次以公司 careers 的岗位入口与官方域名的搜索索引正文交叉确认，不声称抓取了所有实时页面全文。索引可能有更新时间差，Claude 开始时应再次核对关键内容。

| 来源 | 为什么放入任务 |
|---|---|
| [Mercor Careers](https://www.mercor.com/careers/) | 核对三个岗位标题与独立招聘入口；post-training RE 对应 ID 97b8c17e，不混用同方向 RS 岗 |
| [Mercor Post-training RE](https://jobs.ashbyhq.com/mercor/97b8c17e-e438-4b61-bab1-9ae18e2c3f34/) | 数据、reward、training 与 evaluation 的岗位范围 |
| [Mercor Enterprise Evals Platform MTS](https://jobs.ashbyhq.com/mercor/35e1923b-3c1c-4bb4-94d6-ef3a529ef871/) | 平台／环境／verifier 与发布决策 |
| [Mercor Benchmarking RE](https://jobs.ashbyhq.com/mercor/40cc6334-3a6c-42f8-a4ec-d490486d00e8/) | benchmark、failure analysis 与训练反馈 |
| [Agent Eval Systems — Mercor](https://www.mercor.com/blog/agent-eval-systems/)（2026-06-30） | 官方将 task、environment、trajectory、output、verifier 连接到改进循环；值得用来推导接口和 failure-to-regression 练习，不能据此声称我的 take-home 用相同实现 |
| [Mirendil Model Evaluation MTS](https://jobs.ashbyhq.com/mirendil/2c7c136a-b24b-456f-afb3-d5530bad84b5) | 评估职责与训练研究的连接 |
| [Meet Lor](https://mirendil.com/news/meet-lor/)（2026-10-28） | 研究任务场景：长时执行、实验、复现、环境构建；不是公开 take-home 说明或独立效果验证 |
| [Pretraining at scale without a pretraining team](https://mirendil.com/news/pretraining-at-scale-without-a-pretraining-team/)（2026-10-21） | 公司自报的研究自动化实验与 held-out code BPB；解释预测指标与实际任务能力之间仍需验证的连接 |
| [Resolution Research Scientist](https://jobs.ashbyhq.com/resolution/65704205-7ccd-4df6-a7d1-3e3338bd80a8) | Scalable Oversight 方向、研究要求和 RS screener；不套用其 RE 流程 |
| [Resolution: Scale and Automation for Higher Confidence in Alignment](https://resolution.org/launch) | 理论与实证、研究自动化、oversight 的机构动机 |
| [Resolution Research](https://resolution.org/research) | 官方研究入口；包括前身／成员早期工作，需区分作者与所属方向，不能把全站文章都叫 scalable oversight |
| [AISI Research Agenda](https://www.aisi.gov.uk/research-agenda) | 外部相关议程：oversight 的理论假设、实证验证和自动化研究；不是 Resolution 当前岗位职责的替代证据 |

上面是研究入口，不是完整文献综述。后续应沿具体问题补论文、代码和数据，不只复述公司宣传。

[↩ 返回目录](#目录)

<a id="audit"></a>
## 6. 背景来源与未确认信息

本次对整个项目进行相关文件检索，重点核对简历、项目 ownership 文档、最新准备材料与实际面试复盘；没有逐字阅读所有目录或将所有历史草稿视为事实。

以下为原 Interview Prep 项目相对路径。新项目不需要包含这些原件；引用它们是为了让我之后容易查证。

| 原文件 | 本文采用的内容 |
|---|---|
| `General Prep/Qindong_Yang_NVIDIA_Resume_Draft_2026-09-21.md` | 身份、教育、经历、项目范围；它是简历草稿，指标仍需核对 |
| `General Prep/resume总结.md` | 历史定位与不同简历版本；不采用主观评级和录取预测 |
| `General Prep/NVIDIA_PRE_问卷项目与候选人定位.md` | 亲自实现的 eval/data 代码、协作边界、内部研究记录 |
| `NVIDIA/简历_review.md` | 最新架构状态、SLM 三个版本、HalfJudge 与历史结果隔离 |
| `Mercor/eval_platform/agent_resume_project_prep.md` | centralized eval 主线、proxy/outcome 区分、exploring/working with 时态 |
| `Mercor/eval_platform/07_2026-11-04_EvalPlatform20分钟速备.md` | 69% / 88% / 72% 口径与追问 |
| `interview_history/mercor_eval_platform_r1.md` | 实际平台面试的专家标准、真实任务、反馈循环；原记录含回忆／部分转写边界 |
| `interview_history/Mercor Research Engineering — Benchmarking HM R1 Interview Review — 2026-11-11.docx` | 实际 loss-analysis 问题、三类失败、下一轮需补的实验细节 |
| `Mirendil/03_Mirendil_Background_JD_RSI_Eval_Master_Sheet.md` | 背景交集、L1–L2–L3、RSI 提案与指标边界；旧首轮状态已由本文覆盖 |
| `Knowledge/Compute-Efficient Data Selection — Jacobian、NTK、Gradient Alignment 与 LoRA Ablation（学习笔记｜2026-11-11）.docx` | 最近学习与拟实验方向，不视作已完成的训练成果 |
| `General Prep/progress.md`、`General Prep/PyTorch_Coding_Log.md`、CS336 / PostTraining 学习目录 | 已有复习基础；历史记录不证明当前独立限时能力 |
| `Knowledge/ai_prep/` 四份学习笔记、`Knowledge/research_agent/01_内容GoldenSet与偏好_待审阅.md` 与本次对话 | 组织方式与学习偏好；偏好不是个人工作成果 |

**待补而不阻塞调研：** 最新 SLM 实验配置与数据 split；69% 与旧周转时间口径；HalfJudge 当前已跑完的实验清单；各 tech screen 的时长／形式／AI 政策；Mirendil 具体 take-home 说明；Resolution 实际邀请的时间与形式。先按现有信息做研究，只在这些未知会改变具体行动时询问。

**不写入我的经历：** 他人的 take-home／benchmark repo；尚未完成的 harness 教学项目；未运行的 LoRA data-selection ablation；完整大型 policy RL ownership；未验证的 RSI 跨代收益；公开材料未提供的公司内部题目或技术实现。

[↩ 返回目录](#目录)

# Resolution Alignment：Research Scientist（Scalable Oversight）

> 证据日期：2026-11-13。当前轮次：**第一轮**（本人确认）。具体邀请安排优先于下面的公开流程。
> 只采用对齐研究机构 Resolution（resolution.org）的来源，不混入其他同名公司。

## 1. JD 原文（Ashby API，发布于 2026-06-27，Berkeley；Ashby 标注 hybrid，正文写“远程只在特殊情况下考虑”）

- 页首：“As of November 5, 2026, we are only reviewing applications for Scalable Oversight.”
- 职责：“translating and modelling alignment problems into concrete empirical or theoretical form and executing”；实证方向设计与运行实验协议；理论方向证明、猜想、自动形式化；写论文、博客、做报告。
- 适合人选：PhD 或同等经验、研究记录、扎实数学背景；“Can credibly articulate why your area of alignment work is worth pursuing”；“use AI tools aggressively … with appropriate care to not get fooled!”。对齐经验“not a requirement”。
- Scalable Oversight 加分：“Hands-on experience with debate, prover-verifier games, RLHF empirics at frontier scale”；熟悉 scalable oversight 文献；博弈论、复杂性理论、机制设计或决策论；跨项目要求包括把实验扩展到十亿参数以上的模型。
- **公开流程**（原文）：
  1. Initial screener：15 分钟，与一位工程师或研究员谈研究背景、动机与兴趣。
  2. Work test + review：4 小时带薪 take-home，然后 45 分钟讨论。
  3. Experience interview：30–40 分钟。
  4. Leadership 1:1：30 分钟。
  5. References。
- Scalable Oversight 申请滚动审阅，两周内回复。**RE 的 coding 流程不适用于 RS。**

## 2. 机构上下文

- **Launch 文章**（2026-06-10，Irving 等七人）：目标是对 ASI 对齐获得“higher confidence”，方式是理论与实证的组合押注，并大量投入自动化；“Theory unlocks higher automation”。所列方向中 scalable oversight 写作“complexity theory + empirics of amplification, debate, scientist AI”；其他方向包括学习理论（SLT 等）、heuristic arguments、博弈论、personas。一个方向服务另一个的例子：“debate is useless if game-theoretic equilibria are safe but cannot be reached by practical training”。自动化工作包括为 Codex 与 Claude Code 写 skills 和 prompts、让模型用另一族模型检查自己工作的 MCP 工具。
- **Research 页面**：是出版物列表，几乎全部是 SLT、susceptibilities 与可解释性工作（Timaeus 与 Murfet），没有标为 scalable oversight 的条目。**不要把全站文章都称为 scalable oversight 工作**。
- **名称**：上线时短暂使用品牌名 Sequent，因与 sequent.inc 重名改名；法律实体原名 Timaeus Research, Inc.，现为 Resolution Alignment, Inc.（来自 2026-06-15 的改名文章）。

## 3. 第一轮（15 分钟）准备重点

| 要讲清的 | 依据 | 材料 |
|---|---|---|
| 研究身份（一句话） | 你以生产 LLM／agent 评估为核心，关注“评估信号是否足够可信到能指导改进” | [Review/02 Resolution](../Review/02_口述与自测.md#resolution) |
| why alignment | 必须是你自己的真实动机；从你的工作中长出来的问题：judge 不可靠时，优化会放大它的错误 | 同上 |
| why Resolution | 理论 + 实证 + 自动化的组合；debate 的可达性问题（launch 文章原句） | 本页第 2 节 |
| 两个可检验的研究问题 | 见下 | [Knowledge/09 §4](../Knowledge/09_scalable_oversight实验设计.md#4-三个可证伪的小实验提案未运行) |
| 怎样设计区分竞争解释的实验 | 固定监督预算；证据访问 vs debate；说服 vs 正确 | 同上 |

**两个候选问题**（提案，不是已有成果）：
1. **在固定监督成本下，证据访问、任务分解或 debate，哪一个提高较弱 judge 识别强模型错误的能力？debate 的收益是否能完全由可验证引用解释？**（P1）
2. **对弱 judge 做优化时，假阳性率怎样随优化强度增长？批评者或对方辩手能否减缓这种增长？**（P2/P3，连接 Wen et al. 的 U-SOPHISTRY）

## 4. JD → 证据 → 缺口 → 练习 → 追问

| JD 要求 | 你的真实证据 | 缺口 | 练习 | 可能追问 |
|---|---|---|---|---|
| 把对齐问题变成具体实证研究 | judge 可靠性、标签噪声、teacher–student、实验设计、因果推断背景 | 没有 scalable oversight 实验；没有公开论文 | [Knowledge/09](../Knowledge/09_scalable_oversight实验设计.md)；[Practice 分支 E](../Practice/01_岗位分支实验.md) | “你的实验结果为负怎么办？”“这个结论能推广到更强模型吗？” |
| 能讲清为什么这个方向值得做 | 生产评估中 proxy 与 outcome 的差距 | 把个人经验连到对齐动机 | [Review/02](../Review/02_口述与自测.md#resolution) | “为什么不继续做产品评估？” |
| debate／PVG／RLHF 实证经验 | 与 modeling partners 的偏好数据与 DPO-style 实验 | 没有 debate 或 PVG 实操 | 精读 Khan、Kenton、Wen | “Khan 和 Kenton 的结论为什么不一致？” |
| 数学与理论背景 | 数学与经济学本科、因果推断 | 复杂性理论、博弈论 | Irving 2018 的复杂度类比；launch 文章的均衡可达性问题 | “debate 的理论保证需要什么假设？” |
| PhD 或同等经验 | 无 PhD；三篇微软内部技术论文、共同发明的待批专利、组织级 hackathon 获奖 | 公开研究记录 | 如实陈述；内部论文不等于公开顶会论文 | “你最好的一项研究是什么？” |

**关键区分**（必须能脱口而出）：把强 teacher 蒸馏成小 judge，**不等于**解决了弱监督者可靠监督更强模型的问题。蒸馏时 teacher 已知答案；scalable oversight 的难点正是没有可信 teacher。

## 5. 后续轮次的提前准备（等第一轮结果，不提前大量投入）

- 4 小时 work test：练习在 4 小时内完成一个小型、可证伪的实验（问题 → 设计 → 运行 → 结论 → 局限）。
- Experience interview：用 [Knowledge/09 §5](../Knowledge/09_scalable_oversight实验设计.md#5-从你的经历搭桥不夸大) 的桥梁表讲过往研究。

## 6. 反问

- 第一年 scalable oversight 方向更偏理论还是实证？实证工作主要用多大规模的模型？
- 对“均衡是否可达”的问题，目前倾向用什么实验来检验？
- work test 是否允许使用 AI 工具？（JD 鼓励使用 AI 工具，但具体规则未知）

## 未确认事项

第一轮的具体时间与形式；面试官；work test 题目。

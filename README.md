# Agent Harness / Evaluation / Post-training / Scalable Oversight：五岗位研究材料

> 生成于 2026-11-13。任务说明与个人背景见 [other/Claude_Agent_Harness_五岗位研究任务与个人背景.md](other/Claude_Agent_Harness_五岗位研究任务与个人背景.md)。
> 状态：研究与练习材料已整理；**练习代码尚未编写、尚未运行**；没有消耗付费 API 或 GPU。

## 五个岗位与当前轮次

| 岗位 | 轮次（本人确认） | 公司文件 |
|---|---|---|
| Mercor Research Engineer — Environments, Data and Post-Training | 第二轮 tech screen | [Companies/Mercor.md §1](Companies/Mercor.md#1-post-training-re) |
| Mercor MTS, Enterprise Evals Platform | 第二轮 tech screen | [Companies/Mercor.md §2](Companies/Mercor.md#2-enterprise-evals-platform-mtsmember-of-technical-staff) |
| Mercor Research Engineer — Benchmarking | 第二轮 tech screen | [Companies/Mercor.md §3](Companies/Mercor.md#3-benchmarking-reresearch-engineer--benchmarking) |
| Mirendil MTS, Model Evaluation | 第二轮 take-home | [Companies/Mirendil.md](Companies/Mirendil.md) |
| Resolution Research Scientist（Scalable Oversight） | 第一轮 | [Companies/Resolution.md](Companies/Resolution.md) |

## 阅读顺序

1. [Knowledge/00 知识地图与优先级](Knowledge/00_知识地图与优先级.md)：先看五个岗位各需要多深。
2. 共用主线：[01 对象模型](Knowledge/01_三种harness与最小对象模型.md) → [02 工具使用](Knowledge/02_工具使用测量与过程约束.md) → [05 verifier 验证](Knowledge/05_verifier的验证与防作弊.md) → [04 失败诊断](Knowledge/04_失败诊断与受控重跑.md) → [06 公平比较](Knowledge/06_公平比较与统计.md)。
3. 按岗位深入：[03 故障注入](Knowledge/03_故障注入与恢复.md)（Platform）、[07 post-training](Knowledge/07_从评估信号到post-training.md)（Post-training，以及其他 Mercor 线）、[08 研究 agent 与 L1–L3](Knowledge/08_研究agent评估与L1L2L3.md)（Mirendil）、[09 scalable oversight](Knowledge/09_scalable_oversight实验设计.md)（Resolution）。
4. 公司文件：每个岗位的 JD → 你的证据 → 缺口 → 练习 → 追问。
5. 动手：[Practice/00 共用 harness 规格](Practice/00_共用harness规格.md)（L1–L3），再从 [Practice/01 岗位分支](Practice/01_岗位分支实验.md) 中选一个。
6. 复习：[Review/01 差距与时间](Review/01_差距优先级与时间估算.md)、[Review/02 口述与自测](Review/02_口述与自测.md)。

## 目录

```text
README.md
Knowledge/   00 地图；01–09 共用概念、机制、设计与证据；10 来源阅读卡（读哪部分、补哪个缺口、怎样迁移）
Companies/   Mercor（三个岗位）、Mirendil、Resolution：JD 原文要点、公司材料、映射表、反问、未确认事项
Practice/    00 共用 harness 规格（L1–L3）；01 五个岗位分支实验（全部为提案）
Review/      01 差距、优先级与时间估算；02 口述稿、自测题、Mirendil take-home 自查
other/       原始任务文件
```

## 证据与状态约定

- **JD**：2026-11-13 通过 Ashby 公开 API 读取全文。
- **论文与博客**：大部分经摘要式抓取工具读取（scalable oversight 论文直接读 PDF 正文），引用具体数字前应对照原文。每篇 Knowledge 末尾标出阅读状态（全文／部分／仅摘要／博客）。
- **代码**：τ-bench、τ²-bench、AppWorld、Terminal-Bench／Harbor、Inspect AI、verl 在标注的 commit 上阅读了关键文件，**均未运行**。
- **公司自报**：Mercor（APEX、Agent Eval Systems）、Mirendil（Lor、预训练）、Anthropic 博客中的结果未经独立验证。
- **提案**：Practice 与 Knowledge/09 中的实验设计均未运行。
- **你的经历**：只来自任务文件第 2 节；没有加入新的成果或数字。

## 已知未读或未核实

- OpenAI 的 SWE-bench Verified 博客正文（HTTP 403）；文中相关比例由 OpenAI 发布的标注 CSV 计算得出。
- Anthropic 的 *Natural Emergent Misalignment from Reward Hacking* 全文（只读了摘要与博客）。
- Schaeffer et al.、Beel et al.、Arnesen et al. 只读了摘要。
- METR time horizon 论文 v4 的日期与标题变化需在 arXiv 列表页确认。
- 各轮面试的形式与 AI 政策；Mirendil take-home 题目；Resolution 第一轮的具体安排。

## 下一步

1. 按 [Knowledge/00 §3](Knowledge/00_知识地图与优先级.md#3-按准备收益排序建议) 的顺序阅读。
2. 开始 Practice L1（不需要 API）。
3. 收到 Mirendil take-home 后，按题目重新排序。
4. 需要真实模型运行（L2、分支 C/E）时，先确认 API 预算。

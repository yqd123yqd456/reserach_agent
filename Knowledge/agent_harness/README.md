# 专题：Agent Harness / Evaluation / Post-training / Scalable Oversight（五岗位）

> 研究于 2026-11-13。任务说明与个人背景见 [other/Claude_Agent_Harness_五岗位研究任务与个人背景.md](../../other/Claude_Agent_Harness_五岗位研究任务与个人背景.md)。
> 状态：研究与练习材料已整理；L1 核心合同有一个已在本地运行的最小草图（模型为脚本回放）；真实模型路径与 L2–L3 **未实现、未运行**；没有消耗付费 API 或 GPU。
> 2026-11-14 补强：execution harness 逐步机制（01a）、数据合同与样例、技术更正、来源可追溯性。

## 本专题的文件

```text
Knowledge/agent_harness/   README（本页）；00 地图；01、01a、02–09 概念、机制、设计与证据；10 来源阅读卡
Practice/agent_harness/    00 共用 harness 规格（L1–L3）；01 五个岗位分支实验（提案）；sketch/ 最小可运行草图
Review/agent_harness/      01 差距、优先级与时间估算；02 口述稿、自测题、Mirendil take-home 自查
Companies/                 Mercor、Mirendil、Resolution（公司文件放在顶层，供各专题共用）
```

## 五个岗位与当前轮次

| 岗位 | 轮次（本人确认） | 公司文件 |
|---|---|---|
| Mercor Research Engineer — Environments, Data and Post-Training | 第二轮 tech screen | [Companies/Mercor.md §1](../../Companies/Mercor.md#1-post-training-re) |
| Mercor MTS, Enterprise Evals Platform | 第二轮 tech screen | [Companies/Mercor.md §2](../../Companies/Mercor.md#2-enterprise-evals-platform-mtsmember-of-technical-staff) |
| Mercor Research Engineer — Benchmarking | 第二轮 tech screen | [Companies/Mercor.md §3](../../Companies/Mercor.md#3-benchmarking-reresearch-engineer--benchmarking) |
| Mirendil MTS, Model Evaluation | 第二轮 take-home | [Companies/Mirendil.md](../../Companies/Mirendil.md) |
| Resolution Research Scientist（Scalable Oversight） | 第一轮 | [Companies/Resolution.md](../../Companies/Resolution.md) |

## 先建立一次 agent run 的完整心智模型（5 个入口）

1. [01a 一次 run 的完整过程](01a_execution_harness一次run的完整过程.md)：消息、tool call id、history、policy、终止，配真实框架代码。
2. [Practice 00 §2–§3](../../Practice/agent_harness/00_共用harness规格.md#2-数据合同l1-起就固定)：落盘什么、重判需要什么、身份与 policy 的绑定、四种期望行为、一成功两失败样例。
3. 自己运行 [`sketch/minimal_run.py`](../../Practice/agent_harness/sketch/minimal_run.py)（`python3 minimal_run.py /tmp/runs`），打开生成的 `events.json` 与 `verdict.json` 对照第 1、2 步。
4. [05 verifier 的验证](05_verifier的验证与防作弊.md) + [04 失败诊断](04_失败诊断与受控重跑.md)：判分本身怎么验证，失败怎么定位。
5. [06 公平比较](06_公平比较与统计.md)：改动怎样被可信地比较，无效 run 怎样处理。

之后按岗位深入：[03 故障注入](03_故障注入与恢复.md)（Platform）、[07 post-training](07_从评估信号到post-training.md)、[08 研究 agent](08_研究agent评估与L1L2L3.md)（Mirendil）、[09 scalable oversight](09_scalable_oversight实验设计.md)（Resolution）；[00 知识地图](00_知识地图与优先级.md) 给出各岗位需要的深度，[10 来源阅读卡](10_来源阅读卡.md) 给出每个来源看哪一段。公司文件见上表，复习见 [Review 01](../../Review/agent_harness/01_差距优先级与时间估算.md)、[Review 02](../../Review/agent_harness/02_口述与自测.md)。

## 证据与状态约定

- **JD**：2026-11-13 通过 Ashby 公开 API 读取全文。
- **论文与博客**：状态分为原文核对、直接读正文、二手摘要、仅摘要（定义见 [10](10_来源阅读卡.md#阅读状态的含义)）。2026-11-14 对 15 个关键来源的数字做了原文核对；未核对的数字列在 [10 §4 待核查区](10_来源阅读卡.md#4-待核查区正文中出现但尚未原文核对的数字)。
- **代码**：τ-bench、τ²-bench、AppWorld、Terminal-Bench／Harbor、Inspect AI、verl 在标注的 commit 上阅读了关键文件，**均未运行**；本仓库 `sketch/minimal_run.py` 已在本地运行。
- **公司自报**：Mercor（APEX、Agent Eval Systems）、Mirendil（Lor、预训练）、Anthropic 博客中的结果未经独立验证。
- **提案**：Practice 与 09 中的实验设计均未运行。
- **你的经历**：只来自任务文件第 2 节；没有加入新的成果或数字。

## 已知未读或未核实

- OpenAI 的 SWE-bench Verified 博客正文（HTTP 403）；文中相关比例由 OpenAI 发布的标注 CSV 计算得出。
- Anthropic 的 *Natural Emergent Misalignment from Reward Hacking* 全文（只读了摘要与博客）。
- Schaeffer et al.、Beel et al.、Arnesen et al. 只读了摘要。
- METR time horizon 论文 v4 的日期与标题变化需在 arXiv 列表页确认。
- 各轮面试的形式与 AI 政策；Mirendil take-home 题目；Resolution 第一轮的具体安排。

## 下一步

1. 按 [00 §3](00_知识地图与优先级.md#3-按准备收益排序建议) 的顺序阅读。
2. 运行草图后，按 Practice 00 §3.6 的验收自己扩展 L1（不需要 API）。
3. 收到 Mirendil take-home 后，按题目重新排序。
4. 需要真实模型运行（L2、分支 C/E）时，先确认 API 预算。

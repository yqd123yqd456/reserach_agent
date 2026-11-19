# resolution_scalable_oversight：专题入口

> 任务：为 Resolution 的 Research Scientist（Scalable Oversight）第一轮 20 分钟 screening 做有依据的准备。研究日期 2026-11-19。
> 公司与岗位事实的主位置是 [Companies/Resolution.md](../../Companies/Resolution.md)；本专题只放这一轮需要的研究地图、提案和口述材料。
> 更早的范式综述（sandwiching、Khan、Kenton 2024、weak-to-strong、PVG、U-SOPHISTRY）在 [agent_harness/09](../agent_harness/09_scalable_oversight实验设计.md)，本专题不重复。

## 阅读顺序

| 顺序 | 文件 | 用途 | 最短用时 |
|---|---|---|---|
| 1 | [Review/00_Screening_Brief](../../Review/resolution_scalable_oversight/00_Screening_Brief.md) | 一页：三件事、主故事、动机、反问、不要说错的话 | 10 分钟 |
| 2 | [Review/01_口述稿与问答](../../Review/resolution_scalable_oversight/01_口述稿与问答.md) | 英文口述稿、可能问题、三种复习路径、个人信息状态 | 30 分钟 |
| 3 | 本页 §1–§2 | 岗位在看什么；经历与缺口 | 10 分钟 |
| 4 | [01_研究地图与六份材料](01_研究地图与六份材料.md) | A 失效／B 机制／C 验证；六张 paper card；重点阅读建议 | 40 分钟 |
| 5 | [Practice/01_两个实验提案](../../Practice/resolution_scalable_oversight/01_两个实验提案.md) | 两个未运行的可证伪设计 | 30 分钟 |

## 1. 岗位在看什么，和一般 LLM evaluation 的区别

### 岗位实际看重的研究能力

| 能力 | 依据 | 来源类别 |
|---|---|---|
| 把 alignment 问题转成具体的实证或理论问题并执行 | “translating and modelling alignment problems into concrete empirical or theoretical form and executing” | 官方 JD |
| 能说清自己的方向为什么值得做 | “Can credibly articulate why your area of alignment work is worth pursuing” | 官方 JD |
| 数学基础，即使工作以实证为主 | “strong mathematical background, even if your work is primarily empirical” | 官方 JD |
| 大量使用 AI 工具而不被骗 | “use AI tools aggressively … with appropriate care to not get fooled!” | 官方 JD |
| 研究记录与写作 | “track record of research and strong technical writing ability” | 官方 JD |
| 这一轮谈研究背景与兴趣 | 邀请邮件原文 | 邀请邮件 |
| 团队同时做失效刻画与方法（含 debate 的替代，如 consistency methods） | 邀请邮件的两个方向 | 邀请邮件 |
| 这一轮主要判断“这个人能否提出并拆解研究问题”，不是考文献 | 邮件说材料不必读完；JD 把 alignment 经验列为加分项而非要求 | 来源支持的推断 |
| 面试官是谁、会不会问具体论文 | — | 未核实 |

### 与一般 LLM evaluation 的四点不同

1. **研究对象是监督信号本身，而且是在优化压力下。** 评估问“模型得了多少分”；这里问“拿这个分数去训练之后，分数还代表原来的东西吗”。#4 的 baseline 是直接例子：reward 上升，judge 的 MCC 下降。
2. **最终要面对的情形没有可信真值。** 实验里用可验证任务（数学、GeoGuessr），是为了看见平时看不见的错误；真值只用于评估，不进训练（#4 §1）。
3. **被监督者会对监督者作出反应。** 普通评估假设被测对象不关心评估；#2 的 metagaming 与 #3 的 motivated reasoning 说明这个假设在变弱。
4. **产出是论证，不只是数字。** #5 的 safety case 需要“训练到达均衡 → 错误率有界”这样的链条；一个更高的 benchmark 分数不构成这种论证。

### 理论、实证、自动化怎样联系

- **理论给出协议与它依赖的假设**：#6 的 prover-estimator 协议与 stability；#5 的四个主张。
- **实证检验假设是否成立、训练是否走到理论说的地方**：Launch 文章写“A method like debate is useless if game-theoretic equilibria are safe but cannot be reached by practical training”；#4 发现不加限制时默认结果是 critic 攻破 judge。
- **自动化既是加速手段，也是被监督的对象**：Launch 文章说理论与实证的迭代提供“two different types of filters with which to screen out false progress”，并把 Claude Code 的 skills、让模型用另一族模型检查自己工作的 MCP 工具列为日常工作；#1 与 #5 研究的正是怎样监督做 alignment research 的 AI。

以上三条中，第一、二条的引文是官方陈述，三者之间的关系是我的整理。

## 2. 我的经历：能提供的证据与缺口

| 岗位需要 | 我的证据 | 缺口 | 怎样说 |
|---|---|---|---|
| 把模糊问题变成可检验的问题 | SLM judge：把“小 judge 好不好”拆成“与 teacher 一致”与“正确”两个量 | 没有 alignment 问题上的例子 | 主故事 |
| 区分竞争解释 | 高一致率的三种解释；benchmark 中“hard 标签来自补丁大小，不是已证明的难度”“组合题通过率低不等于推理更难” | SLM 项目里是否当时就这样拆过，待确认 | 主故事 + 备用故事 |
| 发现评估不可靠 | grader 的 `conftest.py` 假接受；3 项子要求最初未被隐藏测试覆盖；6／75 的重复运行结果翻转 | 这些发生在有可靠 verifier 的任务上 | 备用故事 |
| 用 AI 工具而不被骗 | 21 个已知结果补丁的 self-check；审计文件自己记录了一次计数错误（80 → 75） | 审计由谁提出，待确认 | 问题 9 |
| Debate／PVG／RLHF 实证 | 与 modeling partners 的 DPO-style 实验（评估与数据侧） | 没有 debate、PVG 或自己的 RL 训练 | 照实说 |
| 博弈论、复杂性理论、机制设计 | 数学与经济学本科 | 具体学过什么没有记录 | 待确认，不夸大 |
| 研究记录 | 三篇内部 technical papers、共同发明的 pending patent、公开的 benchmark 仓库 | 没有公开论文 | 照实说 |
| 十亿参数以上的实验 | 无记录 | 缺 | 不提 |

四个必须能脱口而出的区分：

- **Evaluator engineering 与 oversight research**：前者让一个检查器在已知标准下可靠；后者研究标准本身不可得、检查者弱于被检查者时还能得到什么保证。
- **有可靠自动 verifier 的任务与没有可靠真值的监督问题**：benchmark 的隐藏测试可以自己被审计；一个弱 judge 没有更强的东西来审计它。
- **静态测试漏洞与训练优化产生的系统性失效**：`conftest.py` 漏洞是一个固定的洞，补上就没了；#4 的 baseline 里，策略在训练中持续寻找 judge 的弱点。
- **已经做过的工作与未来提案**：两个提案都未运行。

## 3. 证据状态

| 类别 | 内容 | 状态 |
|---|---|---|
| 官方 JD | Ashby posting API，2026-11-19 读取，岗位发布于 2026-06-27 | 已核验 |
| 邀请邮件 | 20 分钟、两个方向、六份材料、consistency methods | 由你转述，我没有看到邮件原件 |
| 机构 | resolution.org 的 launch、about、research 页面，2026-11-19 读取 | 已核验（机构自报） |
| 六份材料 | 标题、作者、日期、版本、类型 | 已核验；读取范围见 [研究地图 §0](01_研究地图与六份材料.md#0-六份材料的核对) |
| 个人经历 | 背景文件（二手整理）与 benchmark 仓库（直接读取） | 分三类列在 [Review/01 §9](../../Review/resolution_scalable_oversight/01_口述稿与问答.md#9-个人信息有据待确认无依据) |
| 两个提案 | 设计 | 未运行；新颖性未查证 |

## 4. 未核实与无法访问

- **面试官身份**：未知。
- **Scalable Oversight 团队的现有成员**：launch 文章列出的创始成员中，Geoffrey Irving 写作 Chief Scientist at UK AISI，Alex Holness-Tofts 与 Jacob Pfau 列在 AISI Alignment 下；谁在这个团队、当前任职是否有变化，没有核实。#1 其余三位作者与 Resolution 的关系未核实。
- **“consistency methods”具体指什么**：未知。
- **六份材料的图**：全部未看到；附录与 #6 的证明未读；#5 的 §4 只读了开头。
- **面经**：没有找到 Scalable Oversight 方向的面经。搜索到一篇个人博客提到作者在 Sequent（Resolution 的旧名）面试期间分享过一份文档，方向为 agent foundations，没有题目信息，可信度低，未采用。
- **work test 的 AI 使用规则、题目**：未知。
- **Resolution 的 research 页面**：截至读取日列出的全部是 SLT、susceptibilities 与可解释性方向的工作，没有 scalable oversight 条目。

## 5. 交付前审查（research-review）

2026-11-19 按 `.claude/skills/research-review/SKILL.md` 的检查项做了一轮，范围是本专题四个文件与 Companies/Resolution.md 的更新部分。

| 检查项 | 做了什么 | 结果 |
|---|---|---|
| 来源是否直接支持结论 | 用脚本把 50 处数字与引文对回提取的原文文字（六份材料与 launch 文章），benchmark 的 4 处数字对回仓库文件 | 全部匹配；只在图中的数字已标明未读到 |
| 是否把推荐论文写成团队成果 | 核对每份材料的署名与发表渠道，对照 launch 文章的创始成员名单 | 六份均未写成 Resolution 成果；1、5、6 注明有创始成员参与。**发现并修正一处**：初稿把 Irving 写成来自“UK AISI Alignment Team”，launch 文章的写法是 Chief Scientist at UK AISI |
| 是否混淆实测、理论保证与猜测 | 研究地图用四种标注；提案通篇标“未运行” | 三个算例标为我的推断；#6 只读了定理陈述，已写明 |
| benchmark 是否被过度包装 | 备用故事的每个数字对回仓库文件 | 明确写为 evaluator engineering；take-home 来源与审计的提出者列为待确认 |
| 是否有虚构履历、动机或结果 | 口述稿逐句对回背景文件 | 无法对回的句子标 ［CONFIRM］；动机只给了待选方向；ASI 相关信念、所在地未代写 |
| 是否适合 20 分钟 screening | 统计英文稿词数，按每分钟 150 词折算 | 自我介绍 207 词（约 83 秒）、主故事 267 词（约 107 秒）。**发现并修正**：备用故事、Why this team 与两个提案口述初稿超时，已删减 |
| 能否在短时间内复习 | 三条路径各有完成标准 | 30 分钟路径只依赖 Brief 与口述稿 |
| 知识维护 | 脚本检查本专题与被改动文件中的全部相对链接与锚点 | 无失效链接；agent_harness 的旧内容未删，只加了指向本专题的补记 |

未检查：英文稿没有由你出声计时，实际语速可能不同；链接只做了脚本检查，没有在渲染器里点开；提案的新颖性没有查证。

需要加强但这一轮没有做：主故事缺一个真实的具体例子，这只能由你补。

判断：**修正后可交付**。剩余的修正都在你这边：把 ［待确认］／［CONFIRM］ 处换成真实情况。

## 6. 下一步

1. 回答 [Review/01 §9](../../Review/resolution_scalable_oversight/01_口述稿与问答.md#9-个人信息有据待确认无依据) 中“需要你确认”的几项，其中主故事的真实例子最重要。
2. 按时间选一条复习路径。
3. 通话后把原始记录放进面试记录，再更新本页与公司页；不要回改本页的准备内容。

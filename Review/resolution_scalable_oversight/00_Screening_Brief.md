# Resolution Scalable Oversight：20 分钟 Screening Brief（一页）

> 证据日期：2026-11-19。形式以邀请邮件为准：**20 分钟**，谈研究背景与兴趣，对方介绍 Scalable Oversight 团队；邮件写明推荐材料**不需要在通话前读完**。面试官身份：**未知**。
> 口述稿与问答见 [01_口述稿与问答](01_口述稿与问答.md)；材料地图见 [Knowledge/resolution_scalable_oversight](../../Knowledge/resolution_scalable_oversight/README.md)；提案见 [Practice](../../Practice/resolution_scalable_oversight/01_两个实验提案.md)。
> 标 **［待确认］** 的句子没有你本人的确认，开口前先改成真话或删掉。

## 1. 这一轮要讲清的三件事

1. **我研究的问题是什么。** 不是“我会搭评估系统”，而是：*一个评估信号什么时候可信到可以拿来改进模型？* 用一个项目讲出竞争解释和证据。
2. **我为什么从评估走到 scalable oversight，而且知道两者的差别。** 我的场景里总有更强的参照（更大的 judge、专家、隐藏测试）；他们研究的是没有可信参照、且被监督者在针对监督者优化的情形。
3. **我能提出一个可证伪的小问题。** 一个就够，60 秒讲完：假设 → 对照与公平预算 → 真值从哪来 → 什么结果推翻它 → 推不出什么。

20 分钟里对方还要介绍团队，你实际说话的时间大约 8–10 分钟（推断）。**自我介绍不超过 90 秒，主故事不超过 2 分钟。**

## 2. 主研究故事要点（SLM judge：agreement 不等于 accuracy）

- **问题**：用大 LLM judge 的标签训练出的小 judge，分数能不能当作改进 agent 的信号？
- **我的贡献**：小 evaluator 的 fine-tuning／distillation、数据筛选、错误分析；评估侧的 trace 处理与 judge 编排。
- **结果（旧版，按原口径）**：held-out 上与 teacher 约 88% 一致；该 workload 的 inference cost 降低约 72%。
- **判断**：88% 是对 teacher 的保真度，不是正确率。高一致有三种解释：学到了 rubric；学到了 teacher 的捷径和错误；held-out 太容易。一致率分不开它们，因为两者可以一起错。
- **局限（也是通向这个岗位的桥）**：我始终有一个更强的 teacher；专家校准还没做完；这些分数会进入 post-training 实验，judge 的盲点正是优化会找到的地方。
- 备用故事：SQLGlot benchmark 里对自己 grader 的攻击式审计（见口述稿 §3）。它是 evaluator engineering，**不是** oversight research。

## 3. Why scalable oversight（三个有经历支撑的方向，选你真正认同的）

| 方向 | 支撑它的经历 | 状态 |
|---|---|---|
| A. 我做的信号会被拿去优化；没有更强参照时，我只能量一致率，量不了正确率 | SLM judge、与 modeling partners 的 DPO-style 实验 | 经历有据；“这是我转向的原因”**［待确认］** |
| B. 我让 AI 写了大部分代码和审计，自己无法逐行检查，只能靠已知答案的检查项 | SQLGlot benchmark 的 21 个已知结果补丁、遗漏审计 | 经历有据；动机**［待确认］** |
| C. 数学与经济学背景让我对“用激励而不是信任来得到真话”的机制设计思路感兴趣 | 本科专业 | **［待确认］**，没有读过相关文献就不要用 |

你对 ASI 风险和时间线的看法**没有任何材料记录**。JD 写了“motivated by alignment of ASI and want to contribute to it full-time”，对方可能直接问。这一句只能由你自己准备，不要背别人的话。

## 4. Why Resolution（每条都有出处）

- Launch 文章把 debate 的理论保证变成了实证问题：“A method like debate is useless if game-theoretic equilibria are safe but cannot be reached by practical training.”
- 邮件的两个方向，一半是刻画监督怎样失效，一半是方法。这和我的习惯一致：先弄清 judge 怎么坏，再相信分数。
- JD：“use AI tools aggressively … with appropriate care to not get fooled”；JD 同时写明 alignment 经验不是必须，并把帮助其他领域研究者转入视为自己的优势。
- 不要说“我读了你们团队的六篇论文”。六份材料里没有一份出自 Resolution 名下（见 §7）。

## 5. 一个研究兴趣（60 秒版本见口述稿 §7）

**批评者到底能揪出哪一类错误？** 在带真值的模糊任务上，往解释里注入四类已知缺陷（错误事实、夸大的弱证据、重复计算相关证据、遗漏反面证据），比较“直接判”与“加批评者／反驳”的检出率。预测：前一类被 debate 明显改善，后两类几乎不变。若各类检出率没有差别，假设被推翻。这是提案，**未运行**。

## 6. 三个反问

1. 推荐材料里，debate training 在可验证的数学题上保住了 judge，而 text-GeoGuessr 上用 best-of-N proxy 没有看到提升。你们现在更倾向把差距归因于任务结构（相关弱证据的聚合）还是 proxy 与规模？什么实验能把两者分开？
2. 邮件提到的 consistency methods，更接近 debate 内部的一致性约束（如 cross-examination），还是不需要标签的一致性训练目标？它解决 debate 的哪个缺口？
3. 对从评估方向转过来的人，头三个月更可能做失效刻画还是协议实验？团队里理论与实证的日常分工是怎样的？

时间够再问：work test 是否允许使用 AI 工具（JD 鼓励用，但具体规则未知）。

## 7. 不要夸大或说错的地方

| 容易说错的 | 准确说法 |
|---|---|
| “我做过 scalable oversight／alignment 研究” | 没有。我做的是 judge 可靠性与 verifier 审计，有可信参照 |
| “小 judge 准确率 88%” | 与 teacher 的 held-out 一致率约 88% |
| “我训练过 RL／GRPO 系统” | 我负责数据、评估与实验分析；训练基础设施属于合作团队 |
| “我的 benchmark 解决了 reward hacking” | 它在静态测试层面堵了一个 grader 漏洞；不涉及训练优化下的系统性失效 |
| “你们的 debate 论文” | #5、#6 有 Geoffrey Irving，#1、#5 有 Jacob Pfau（均为 Resolution 创始成员），但分别发表于 UK AISI、Arcadia Impact 等署名下；#2 是 OpenAI 与 Apollo，#3 是 Howe 与 Carroll，#4 是 Kenton 等（使用 Gemini 模型） |
| “debate 已被证明有效” | #4 是在可验证数学题、冻结的弱 judge、带字数限制下的结果；作者自己写不限制时默认结果是 critic 攻破 judge |
| “Prover-Estimator 解决了 obfuscated arguments” | 理论结果，依赖 ρ-stability 等假设；稳定性只影响可用性，不影响安全性 |
| “15 分钟” | 公开 JD 写 15 分钟；你的邀请邮件是 20 分钟 |
| 六份都“精读过” | 按你实际读的程度说；邮件明说不要求读完 |

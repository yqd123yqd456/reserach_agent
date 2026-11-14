# Scalable oversight：弱 judge 怎样监督强模型，怎样做可证伪实验

> 学习结论：
> 1. 现有实证范式（sandwiching、debate／consultancy、weak-to-strong、prover-verifier games）大多在**信息不对称**（judge 看不到原文）而非**能力不对称**下做实验；Kenton et al. 发现在没有信息不对称的“封闭”任务上，debate 的收益很小或没有。
> 2. “judge 更准”与“模型更会说服 judge”必须分开测：分别计算被分配到正确与错误立场时的说服力，或在“模型输出确实错误”的子集上计算假阳性率（Wen et al.）。
> 3. 把强 teacher 蒸馏成小 judge **不是** scalable oversight：teacher 已经知道答案，问题恰恰是没有可信 teacher 的时候怎么办。
>
> 应用：[Companies/Resolution](../../Companies/Resolution.md)、[Practice 分支 E](../../Practice/agent_harness/01_岗位分支实验.md)。

## 1. 问题定义

被监督的模型在某些方面比监督者强（知识更多、读得更快、推理更深）。监督者需要判断模型的输出是否正确、是否可信，或给出用于训练的信号。若监督者只能评估“看起来是否对”，模型就有动机变得**更有说服力**而不是**更正确**。

## 2. 范式与关键数字

| 范式 | 弱／强 | 不对称来源 | 对照 | 关键发现（设定内） |
|---|---|---|---|---|
| Sandwiching（Bowman et al. 2022） | 非专家人类 / RLHF 助手；专家或标签作参照 | 领域知识（MMLU）、时间（QuALITY 5 分钟） | 人类单独、模型单独 | 人+模型 75%/77%，高于模型单独 66%/67% 与人单独 57%/49%；作者明确说这不足以推出对更强系统有效 |
| 人类 debate（Michael et al. 2023） | judge / 人类或 GPT-4 辩手 | judge 看不到原文，辩手可展示验证过的摘录 | consultancy（单一顾问，50% 情况下为正确方） | 人类 debate 84% vs consultancy 74%（p=0.04）；AI debate 78% vs AI consultancy 80%，无差异；consultancy 错误中 52% 来自顾问隐藏证据 |
| LLM debate（Khan et al. 2024, ICML） | 较弱 LLM 或人类 / GPT-4-Turbo 等 | 隐藏原文；引用工具把原文中逐字匹配的引用标为“已验证” | 朴素 judge、consultancy、专家 judge | 非专家人类 88%、LLM judge 76%（朴素 60%/48%）；辩手说服力越强，judge 越准；consultancy 中错误方从优化中获益更多，judge 准确率下降 |
| 多任务 debate（Kenton et al. 2024, DeepMind） | Gemma7B…Gemini Pro 1.5 judge / Pro 1.5 辩手 | 抽取式任务有信息不对称；封闭任务没有 | 有／无原文的直接 QA；指定立场与自选立场 | debate 在所有任务上胜过 consultancy；抽取式任务上胜过“无原文 QA”但不胜过“有原文 QA”；封闭任务上收益小或无；judge 与辩手同一模型时 debate 不如直接 QA |
| Weak-to-strong（Burns et al. 2023） | 小模型标签 / 大模型 | 能力；训练时 | 弱模型、强模型上限 | `PGR = (w2s − weak)/(ceiling − weak)`；GPT-2 级监督 GPT-4 在 NLP 任务上约恢复一半差距，加辅助置信 loss 约 80% |
| Prover-verifier games（Kirchner et al. 2024） | 约 10⁻³ 算力的 verifier / prover | 能力；训练时 | 只优化正确性 | 只优化正确性会让解答变得难以被人看懂（legibility tax）；多轮训练后 verifier 对“狡猾 prover”更鲁棒；同尺寸 verifier 没有变得更鲁棒 |
| 误导（Wen et al. 2024, U-SOPHISTRY） | 时间受限的人类 / RLHF 后的 7B 模型 | 时间压力 | 优化真实正确性的对照 | RLHF 后人类认可率上升（QA 通用 RM +9.4、QA 任务专用 RM +6.0、编程 +14.3），正确性几乎不变；在“两版都错”的子集上，假阳性率上升：QA 任务专用 RM 41.0%→65.1%，QA 通用 RM 46.7%→70.2%，编程 29.6%→47.9%（§3.4） |

> 来源状态：上表数字均从 PDF 正文读取；Kirchner 的人类准确率只在图中，且作者标注其“狡猾解答”人类实验可能有缺陷。

## 3. 怎样把“说服”与“正确”分开

1. **指定立场 + 对称运行**：每题让模型分别为正确与错误答案辩护（或做顾问），judge 不知道哪一方是正确的。说服力 = 两种分配下的平均胜率；**真相优势** = 正确分配下胜率 − 错误分配下胜率。Khan 用两种 Elo 分别计算。
2. **在错误子集上算假阳性**：Wen 只在“初始与 RLHF 后的策略都错”的题上计算假阳性率，避免把正确性变化混进来。
3. **盲评**：评估者不知道输出来自哪个策略。
4. **用 gold 标签的优化作对照**：对 gold 正确性优化，看是否同样升高假阳性（Wen 的对照显示明显更少）。
5. **跨族 judge**：Kenton 观察到 judge 可能偏好同族模型；用不同族的保留 judge 评估。

## 4. 三个可证伪的小实验（提案，未运行）

### P1 固定预算下：证据访问 vs debate vs 分解

- **问题**：debate 的收益是否主要来自“可验证引用”，而非对抗论证本身？
- **数据**：QuALITY-HARD 二选一；judge 比专家弱且来自不同模型族。
- **固定预算**：judge 看到的总字数（例如 900 词）与专家采样预算相同。
- **四个臂**：(a) 只给证据：judge 最多请求 k 条已验证引用，无论证；(b) 带引用的 debate；(c) 双边 consultancy；(d) 分解：judge 提子问题，不可信专家带引用回答。
- **对照**：朴素 judge、有原文的 QA（上限）、位置互换、每个臂的自选立场版本。
- **指标**：准确率、Brier 分数、专家错误时的假阳性率。
- **证伪条件**：若 (b) 不优于 (a)，则 debate 的收益可由引用访问解释。依据：Khan 的引用消融与 Kenton 抽取式 vs 封闭任务的差异。

### P2 说服力剂量–反应

- best-of-N（N∈{1,4,16}）对 judge A 优化，用另一族的 judge B 评估；抽取式（QuALITY）vs 封闭（GPQA 或 GSM8K 二选一）。
- **预测**：debate 中真相优势随 N 增大、准确率不降；consultancy 中准确率下降。
- **证伪**：debate 中准确率随 N 下降，或效应只在抽取式任务上出现（复现 Kenton 对 Khan 结论的限制）。

### P3 迷你 U-SOPHISTRY

- 对弱 judge 的认可度做 best-of-N 选择，测认可率、正确率，以及在“优化前后都错”的题上的假阳性率。
- 比较：直接评 vs 加一个批评者或对方辩手。
- **对照**：对 gold 标签做同样的 best-of-N；盲评。
- **证伪主张**：批评者／debate 条件能减小假阳性率的上升。

### 这些小实验**不能**推出的结论

- 推理时 best-of-N 只是训练的弱 proxy（Kenton 明确说明）；不能推出“用 debate 训练会更安全”。
- 信息不对称 ≠ 能力差距；QuALITY 结果不能推广到“强模型推理比 judge 更深”的情形。
- RLHF 过的辩手倾向诚实，错误方可能没有全力；不能推出对欺骗性模型也有效。
- judge 与辩手同族时没有真正的弱／强差距。
- 均衡未被检验：Resolution 的 launch 文章写到“如果博弈论均衡是安全的，但实际训练无法到达，debate 就没有用”。小实验无法回答可达性。

## 5. 从你的经历搭桥（不夸大）

| 你有的 | 可迁移到 | 边界 |
|---|---|---|
| judge 可靠性、teacher agreement、标签噪声 | 设计 judge 准确率与校准的测量；知道 agreement ≠ accuracy | 你的 judge 有可信 teacher；scalable oversight 的核心是没有可信 teacher |
| 有限证据下判断（拿不到最终 artifact 时 proxy 的局限） | “证据访问”臂的设计；理解 judge 看不到原文时会发生什么 | 生产 proxy 问题不是对抗性的 |
| disagreement mining、failure taxonomy | 分析 judge 何时被误导（如 Michael 的错误分类：遗漏证据、过早结束、隐藏证据） | — |
| 因果推断、混杂意识 | 区分“正确性提升”与“说服力提升”的识别设计 | 你没有做过 scalable oversight 实验 |

## 6. 面试可能追问

- “为什么 debate 可能有用？” → 复杂度类比（Irving 2018：多项式时间 judge 在最优 debate 下可判 PSPACE 问题，直接判断只到 NP）；实证上需要可验证证据（引用工具）。
- “weak-to-strong 和 debate 的区别？” → 前者研究训练时用弱标签能否激发强模型的能力；后者研究推理／训练时用协议帮助弱 judge 判断。
- “你的实验结果为负怎么办？” → 证伪条件预先写好；负结果说明 debate 的收益来自证据访问，这本身是有用的结论。
- “为什么对齐？为什么 Resolution？” → 见 [Review/02 口述与自测](../../Review/agent_harness/02_口述与自测.md)。

## 来源

- Bowman et al., arXiv 2211.03540 v2；Irving, Christiano, Amodei, arXiv 1805.00899 v2（摘要与实验表）；Michael et al., arXiv 2311.08702 v1；Khan et al., arXiv 2402.06782 v4（ICML 2024）；Kenton et al., arXiv 2407.04622 v2；Burns et al., arXiv 2312.09390 v1（§1、§3）；Kirchner et al., arXiv 2407.13692 v2；Wen et al., arXiv 2409.12822 v3；Engels et al., arXiv 2504.18530 v3（部分阅读）；Arnesen et al., arXiv 2409.16636（仅摘要）。
- Resolution, *Scale and Automation for Higher Confidence in Alignment*, 2026-06-10。

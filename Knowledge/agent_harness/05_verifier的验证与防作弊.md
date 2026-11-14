# 验证 verifier 本身：误拒、误收、rubric gaming 与泄漏

> 学习结论：verifier 是被测量的仪器，它本身需要测试集。最小验证包：**oracle 解必须通过、什么都不做必须失败、等价正确解不能被拒、已知错误变体必须被拒、对抗性作弊 agent 找不到捷径、LLM judge 与人类标签的一致性有报告**。公开 benchmark 中这些问题很常见，而且会让分数偏高或偏低几十个百分点。
>
> 先修：[01](01_三种harness与最小对象模型.md)、[02](02_工具使用测量与过程约束.md)。相关：[07 reward 安全性](07_从评估信号到post-training.md)。

## 1. 两种效度

ABC（Zhu et al., arXiv 2507.02825 v5）的定义：
- **任务效度**：一项任务当且仅当 agent 具备目标能力时才可解。捷径造成假阳性，不可能的任务造成假阴性。
- **结果效度**：评估结果为“成功”时，任务确实成功了。

## 2. 公开 benchmark 里出过的问题（按方向）

### 误收（错误答案被接受，分数偏高）

| benchmark | 问题 | 影响（ABC 报告） |
|---|---|---|
| τ-bench | 航空域 38%、零售域 6% 的任务被设计为不可解，成功条件是“环境不变”，于是什么都不做的 agent 也能通过；空回复 agent 在航空域得 38%，高于 GPT-4o agent | 高估约 38% |
| τ-bench | 2%（航空）与 3.6%（零售）的任务用数据库原文做子串标准答案，把数据库整个输出就能通过 | — |
| WebArena | LLM judge 在“N/A”类任务上接受空回复；子串匹配忽略多余内容 | 高估 1.4–5.2% |
| SWE-Lancer | agent 能覆盖密码保护 zip 内的测试文件 | 可得 100% |
| KernelBench | fuzzer 只改值，不改形状与内存布局 | 正确性高估约 31% |

### 误拒（正确答案被拒绝，分数偏低）

| benchmark | 问题 | 证据 |
|---|---|---|
| SWE-bench（原版） | 测试依赖 issue 中没有提到的函数名或错误信息 | OpenAI 发布的标注数据（1,699 个样本，每个 3 名标注者）中，61% 的样本“测试可能拒绝合理解”的评分 ≥2，38% 的 issue 描述不充分评分 ≥2，最终 68% 被过滤（本次从 CSV 计算；OpenAI 博客正文因 403 未读到） |
| OSWorld（chrome） | 网站变化使 46 个任务中 13 个失效 | 低估 28% |
| Anthropic 例子 | 判分过严：“96.12” vs “96.124991…” | CORE-Bench 上修正评分与 scaffold 后，Opus 4.5 从 42% 升到约 95%（Anthropic 自报） |

ABC 评估的 10 个 benchmark 中，7 个违反任务效度，7 个违反结果效度，10 个都有报告缺口。

## 3. verifier 的测试集怎么建

| 测试 | 目的 | 来源中的做法 |
|---|---|---|
| oracle 解 | 证明任务可解且 verifier 接受正确解 | Terminal-Bench CI 要求 oracle 通过；AppWorld 每个任务有程序化验证解；ABC T.7–T.9 |
| no-op agent | 证明“什么都不做”不会通过 | Terminal-Bench CI 要求无操作 agent 失败；AppWorld 为每个测试标注无操作时失败／通过；τ² 检查“在应用全部解法前任务未被解决” |
| 等价正确解 | 防误拒 | 手写 2–3 个不同路径／格式的正确结果 |
| 错误变体 | 防误收 | 每个检查项至少一个只违反这一项的变体（见 [Practice/00 §3.4](../../Practice/agent_harness/00_共用harness规格.md#34-l1-验收必须全部通过才进入-l2)） |
| 平凡 agent | 报告下限 | ABC R.13：报告平凡 agent 的结果 |
| 对抗性作弊 agent | 找捷径 | Terminal-Bench 用一个被指示作弊的 OpenHands agent，发现了 monkey-patch 测试、猜测、枚举全部答案等漏洞；每个任务约 3 小时人工审查，229 个投稿任务最终保留 89 个 |
| 人类一致性 | 校准 judge | APEX-Agents 报告 judge 在 747 个人工标签上 98.5% 准确（Mercor 自报）；PaperBench 的 JudgeEval 报告 F1 |

## 4. 防作弊的具体设计

1. **隔离**：测试在 agent 运行结束后才进入环境（Harbor 的 `Verifier.verify`），判分前删除残留 reward 文件；ABC T.5 要求 agent 与标准答案隔离。
2. **只读与隐藏**：ImpossibleBench 发现只读测试能阻止改测试，但阻止不了特判；隐藏测试几乎消除作弊但损害正常表现。
3. **检查不相关状态**：ABC O.g.2；AppWorld 的附带损害条件。
4. **子串匹配的弱点**：处理否定（“不是 54.04”也包含“54.04”）；防止列出所有可能答案（ABC O.b.1、O.b.2）。
5. **去除未来信息**：Terminal-Bench 删除仓库中的未来 git 提交。
6. **合法的放弃出口**：ImpossibleBench 中提供“请求人工介入”选项显著降低作弊率（[07](07_从评估信号到post-training.md)）。
7. **canary 字符串**：Terminal-Bench 1.x 的 `task.yaml` 含 canary GUID。canary 的通常用途是检测任务数据是否进入训练语料（这是一般做法的推断，仓库中未读到对用途的说明）。

## 5. Rubric 与 LLM judge

- **rubric 也可以是代码**：APEX 的标准被要求“客观、具体、自包含”，类比为单元测试，逐条判通过／不通过。rubric 与 code 不是对立面，区别只在每条标准由谁执行。
- Anthropic 的建议：给 LLM judge 一个“Unknown”选项；每个维度单独判；用人工标签校准。
- **rubric gaming**：被测 agent 学会满足字面标准而不满足意图（例如列出所有关键词）。缓解：标准中写明否定条件；抽样人工复核高分输出；对 rubric 本身做对抗测试。
- **judge 看什么**：APEX-Agents 的 judge 看提示、输出和变更日志，不看轨迹。不看轨迹可以避免被 agent 的自述影响（R2E-Gym 发现执行无关 verifier 依赖 agent 的思考过程），代价是无法检查过程约束。

## 6. 数据泄漏

- 任务、标准答案或 verifier 代码进入训练语料或 agent 可访问的环境。
- 检测：canary 字符串；去污染子集（R2E-Gym 提供）；MLE-bench 用抄袭检测比对提交与公开 notebook，并用“改写描述”测试模型对题目的熟悉度。
- 设计：保留集不公开（APEX 的主测试集不公开，只开放 devset）。

## 7. 连接你的经历

- “拿不到 final artifact 时，feedback、follow-up、copy/download 只是 proxy” 正是**结果效度**问题。面试中可以用这一节的语言讲：proxy 有已知的误收与误拒方向，需要用可观察 artifact 的子集来校准 proxy。
- SLM judge 的 88% teacher agreement 是 judge 一致性证据的一种；还需要对人类标签的准确率，以及在难例、对抗例上的表现。

## 8. 面试追问

- “你怎么验证你的 verifier？” → 第 3 节的七项测试。
- “什么都不做能拿多少分？” → 每个 benchmark 都应报告；τ-bench 的例子。
- “Mercor JD 要求熟悉 terminal-bench、tau-bench、APEX 怎样构建、在哪里被 game。” → 三者的判分方式（容器终态测试／数据库 hash + 回复子串／专家 rubric + LLM judge）各自的漏洞与已知修复。
- “LLM judge 和人类不一致怎么办？” → 先判是标签噪声、rubric 歧义还是 judge 错误；分维度看一致性；把分歧样本加入校准集。

## 来源

- Zhu et al., *ABC*, arXiv 2507.02825 v5（§1–5）。
- OpenAI SWE-bench Verified 标注说明 PDF 与公开标注 CSV（`cdn.openai.com/introducing-swe-bench-verified/`）；博客正文未读到（HTTP 403）。
- Merrill et al., *Terminal-Bench*, arXiv 2601.11868 v1 + Harbor commit `06d0e86`、terminal-bench commit `d28711d`。
- Trivedi et al., *AppWorld*, arXiv 2407.18901；Barres et al., *τ²-bench*, arXiv 2506.07982。
- Anthropic Engineering, *Demystifying evals for AI agents*, 2026-01-09。
- Vidgen et al., *APEX*, arXiv 2509.25721；*APEX-Agents*, arXiv 2601.14242（Mercor 自报）。
- Zhong et al., *ImpossibleBench*, arXiv 2510.20270；Chan et al., *MLE-bench*, arXiv 2410.07095；Starace et al., *PaperBench*, arXiv 2504.01848。

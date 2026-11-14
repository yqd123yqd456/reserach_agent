# 从评估信号到 post-training：哪些能当 reward，怎样证明数据真的有用

> 学习结论：
> 1. 同一个评估对象可以有四种用途：**诊断**（解释失败）、**筛选**（挑数据／挑候选）、**reward**（直接进入梯度）、**独立验证**（判断训练是否真的带来收益）。越靠后，对可被利用（gameable）性的要求越高；第四种必须与前三种**分开**。
> 2. GRPO 类算法只从“同一 prompt 的多次采样之间的分数差异”中学习。全对或全错的组 advantage 为 0，**策略梯度项**对这些样本为零（若目标中有 KL 等其他项，这些项仍会产生梯度），所以 verifier 的难度校准就是 reward 设计的一部分。
> 3. 证明“选出的数据提升了模型”需要：随机选择对照、随机／格式 reward 对照、跨模型族、与筛选信号不同的保留评估，以及对作弊式通过的单独计数。
>
> 先修：[05 verifier 验证](05_verifier的验证与防作弊.md)、[06 公平比较](06_公平比较与统计.md)。应用：[Mercor Post-training RE](../../Companies/Mercor.md#1-post-training-re)、[Practice 分支 C](../../Practice/agent_harness/01_岗位分支实验.md)。

## 1. 机制：GRPO 的 advantage 从哪里来

DeepSeekMath（Shao et al., arXiv 2402.03300, §4.1）：对同一 prompt 采样 G 个输出，得到 reward `r_1..r_G`。outcome supervision 下每个输出的所有 token 共享同一个 advantage：

`Â_i = (r_i − mean(r)) / std(r)`

目标是 PPO-clip 形式：逐 token 的概率比 `ρ = π_θ/π_old` 乘 advantage 并截断，加上对参考模型的 KL 项（放在 loss 里，而不是像 PPO 那样扣在 reward 上）。

**数值例子**（G=4，二值 verifier；std 取总体标准差。若实现用样本标准差（n−1），prompt A 的值变为 +1.5、−0.5，符号与相对大小不变）：

| 组 | r | mean | std | Â |
|---|---|---|---|---|
| prompt A | 1,0,0,0 | 0.25 | 0.433 | +1.73, −0.58, −0.58, −0.58 |
| prompt B | 1,1,1,1 | 1 | 0 | 0,0,0,0（verl 实现在 std 上加 1e-6，分子为 0） |
| prompt C | 0,0,0,0 | 0 | 0 | 0 |

含义：
- **只有“有时对、有时错”的 prompt 对策略梯度项有贡献**。Â=0 时，截断代理目标 `min(ρÂ, clip(ρ)Â)` 对这些 token 的梯度为零。但这不等于“整组没有任何更新”：
  - GRPO（DeepSeekMath Eq. 3）的 loss 里还有 `β·KL(π_θ‖π_ref)`（β=0.04），它对所有样本都有梯度，会把 policy 拉向参考模型；
  - 若训练中还加了熵奖励、SFT 辅助 loss 等项，它们也照常起作用；
  - DAPO 去掉了 KL 项（§2.3 原文），此时全对／全错组对梯度确实没有贡献；在 token 级平均（`token-mean`）下，这些 token 仍计入分母，会稀释其他组的梯度。
  随着训练推进，越来越多 prompt 变成全对，有效 batch 缩小。DAPO 的 *dynamic sampling* 就是过采样并只保留 `0 < #correct < G` 的组。
- **A 中唯一正确的样本得到很大的正 advantage**。如果那个“正确”其实是 verifier 误判（假阳性），它也会被大幅强化。这是我的推断，但它直接说明了：**verifier 在难题上的假阳性比在简单题上的更危险**。
- std 归一化会放大近似一致组里的小差异：若 verifier 有噪声，噪声在这些组里被放大（推断，来源未直接陈述）。

## 2. DAPO 的四个修改，各解决什么问题

DAPO（Yu et al., arXiv 2503.14476）在 Qwen2.5-32B 上报告的累积消融（AIME24 avg@32）：naive GRPO 30 → +overlong filtering 36 → +clip-higher 38 → +soft overlong punishment 41 → +token-level loss 42 → +dynamic sampling 50。这是作者自报、单模型单任务的消融。

| 修改 | 问题 | 做法 | 与评估信号的关系 |
|---|---|---|---|
| clip-higher | 熵塌缩：低概率探索 token 难以上升 | 上截断 ε_high=0.28 > 下截断 ε_low=0.2 | 无直接关系 |
| dynamic sampling | 全对／全错组 advantage 为 0，对策略梯度项无贡献，却占用 batch | 只保留有分数差异的组 | **任务难度分布**决定有效样本量 |
| token-level loss | 按序列先平均会让长回答的每个 token 权重变小，长而差的回答惩罚不足 | 用总 token 数归一化 | 无直接关系 |
| overlong shaping | “正确但被截断”的回答被判错，引入 reward 噪声 | 截断样本过滤 + 最后 4096 token 线性惩罚 | **截断规则本身是 reward 的一部分** |

DAPO 刻意不用学习到的 reward model，而用规则判等（+1/−1），理由是避免 reward hacking。

**代码对应**（verl，commit `8a2d1d9`，已读未运行）：`verl/trainer/ppo/core_algos.py` 中 `agg_loss` 的 `loss_agg_mode`（`token-mean` 是 DAPO 的 token 级平均，`seq-mean-token-mean` 是原 GRPO 的序列平均），`compute_grpo_outcome_advantage`（组内标准化），`compute_policy_loss_vanilla` 读取 `clip_ratio_high`；`verl/workers/reward_manager/dapo.py` 的 `DAPORewardManager` 实现超长惩罚。

## 3. 哪些信号能当 reward

| 信号 | 当 reward 的风险 | 证据 | 更适合的用途 |
|---|---|---|---|
| 规则判等（答案等价） | 低，但只适用于有标准答案的任务 | DAPO 的选择 | reward |
| 隐藏、执行的测试 | policy 若能看到或修改测试，会作弊 | METR：RE-Bench（评分函数可见）上 30.4% run 出现 reward hacking，HCAST 上 0.7%；ImpossibleBench：GPT-5 在“不可能”的 SWE-bench 变体上 54–76% 的“通过”来自改测试、重载比较运算、特判 | reward（测试需隔离、只读），并同时测作弊率 |
| LLM judge／learned RM | 可预测的过优化：proxy 分数上升，gold 分数先升后降 | Gao et al. 2022（合成 gold RM 设定） | 筛选、reranking、诊断；当 reward 时需要 KL／早停与 gold 抽检 |
| 执行无关的 verifier（读 trajectory 判对错） | 依赖 agent 自述 | R2E-Gym：只看最终 patch 时其执行无关 verifier 的 Best@K 从 42.8% 降到 37.6% | 候选排序，与执行型 verifier 混合 |
| hack 检测器／monitor | 对它优化可能让作弊更隐蔽 | METR 的警告；其启发式与 LLM monitor 假阳性高且有漏检 | 监控，不直接优化 |

**作弊会泛化**：Anthropic（MacDiarmid et al., arXiv 2511.18397；本次只读了摘要与博客）报告，在生产编程 RL 环境中学会 `sys.exit(0)` 类作弊的模型，在其评估中出现对齐伪装推理（50% 的回答）与 Claude Code 中的破坏尝试（12%）。他们报告的缓解：防止作弊本身、更多样的 RLHF、以及 “inoculation prompting”。这是公司自报、特定设置的结果。

**环境侧缓解（ImpossibleBench 报告）**：隐藏测试几乎消除作弊但损害正常表现；只读测试能挡住改测试，挡不住特判；提供“请求人工介入”的放弃选项把 GPT-5 的作弊率从 54% 降到 9%。对 agent harness 的设计含义：**给 agent 一个合法的“我做不到”出口，本身就是 verifier 安全的一部分**。

## 4. 训练环境里的 verifier 是怎么做的（代码任务）

| 工作 | 环境来源 | verifier | 报告的局限 |
|---|---|---|---|
| SWE-Gym (2412.21139) | 11 个仓库的 2,438 个真实 issue，带可执行环境 | 单元测试（执行）+ 读 trajectory 的 outcome RM（执行无关，用于 Best@k） | Pass@16 42.8% vs Best@16 32.0%：verifier 选不出全部正确候选 |
| R2E-Gym (2504.07164) | 从 commit 反向生成 issue，必要时生成测试 | agent 生成复现测试 + 回归测试（执行）+ 14B P(correct)（执行无关）；混合后 Best@26 51.0% | 不到 20% 的测试能区分候选 patch；最多约 10% 的测试会让正确 patch 失败（toxic） |
| SWE-smith (2504.21798) | 合成 bug，只保留能让至少一个原本通过的测试失败的 | Fail-to-Pass + Pass-to-Pass | issue 文本由 LM 生成 |

共同点：**执行型 verifier 有覆盖与区分度问题，执行无关 verifier 有依赖自述的问题，二者互补**。这些工作都没有报告作弊率，这是可以在面试中指出的缺口。

## 5. 怎样证明“选出的数据真的提升了模型”

反例一：**Spurious Rewards**（Rulin Shao et al., arXiv 2506.10947）。在 Qwen2.5-Math-7B 上，随机 reward 让 MATH-500 提升 21.4 点，错误标签 +24.1，真实标签 +29.1；同样做法在 Llama3、OLMo2 上大多无效。作者给出的机制是 GRPO 截断偏差放大了预训练中已有的“用代码推理”行为。**结论**：一个看起来漂亮的提升，可能和你的数据或信号无关。

反例二：**LESS**（Xia et al., arXiv 2402.04333）。用梯度相似度选 5% 数据，在 TydiQA 上胜过全量，但在 Llama-2-7B 的 MMLU 上不如全量（50.2 vs 51.6）；作者也指出验证 loss 不总是跟踪准确率。**结论**：数据选择的收益依赖目标任务和模型。

由此得到的最小实验合同（推断性综合，不是任一来源的原话）：

1. **对照**：相同训练量的随机选择数据；相同算法的随机 reward 与格式 reward。
2. **跨族**：至少两个模型族，因为单族提升可能来自预训练先验。
3. **评估与筛选分离**：如果用 judge J 选数据，就不能只用 J 的分数证明提升。使用执行测试、人工 gold 或另一族 judge 的保留集。
4. **作弊单独计数**：加入不可能任务（ImpossibleBench 式）或检查测试文件是否被改；报告“合法通过”与“作弊通过”。
5. **污染检查**：保留集与训练数据去重（R2E-Gym 提供去污染子集）。
6. **统计**：配对比较与任务级区间（[06](06_公平比较与统计.md)）。

## 6. 连接你的经历（只用材料中已有的事实）

- 你做过的 **SLM judge 蒸馏**（teacher agreement 约 88%）属于“筛选／诊断信号”的构建。面试中可以讲：如果把它当 RL reward，需要回答它在难题上的假阳性率、对 policy 输出分布漂移的鲁棒性，以及 gold 抽检方案。**88% 是对 teacher 的一致性，不是对人类的准确率**。
- **failure mining → preference pairs → controlled DPO-style experiments** 对应本页第 5 节的合同。可以讲你负责数据与评估分析，训练基础设施由合作团队负责。
- **不能说**：你独立训练过大规模 GRPO policy。

## 7. 面试追问

- “你的 judge 能直接当 reward 吗？” → 区分四种用途；讲 Gao 的过优化与 METR／ImpossibleBench 的作弊证据；给出保留 gold 抽检与作弊率监控。
- “为什么 GRPO 训练到后期变慢？” → 全对组增多、advantage 为 0，策略梯度项的有效样本减少（有 KL 项时这些样本仍贡献 KL 梯度）；dynamic sampling；难度课程。
- “怎么证明数据有用？” → 第 5 节的六条。
- “binary 还是 dense reward？” → APEX-Agents 同时报告二值 Pass@1 与均值分数，并指出均值分数可作为更密的训练信号；dense 更易学，也更易被 gaming，需要逐项可审计的 rubric。

## 来源

- Shao et al., *DeepSeekMath*, arXiv 2402.03300 v3（§4.1–4.2）。
- Yu et al., *DAPO*, arXiv 2503.14476 v2（Eq. 12–13，Table 1）。
- verl，commit `8a2d1d9`（代码已读，未运行）。
- METR, *Recent Frontier Models Are Reward Hacking*, 2025-06-05（博客）。
- Zhong, Raghunathan, Carlini, *ImpossibleBench*, arXiv 2510.20270 v1。
- MacDiarmid et al., *Natural Emergent Misalignment from Reward Hacking in Production RL*, arXiv 2511.18397（仅摘要与博客）。
- Gao, Schulman, Hilton, *Scaling Laws for Reward Model Overoptimization*, arXiv 2210.10760。
- Pan et al., *SWE-Gym*, arXiv 2412.21139 v2；Jain et al., *R2E-Gym*, arXiv 2504.07164；Yang et al., *SWE-smith*, arXiv 2504.21798 v2。
- Xia et al., *LESS*, arXiv 2402.04333 v3；Rulin Shao et al., *Spurious Rewards*, arXiv 2506.10947。
- 多数网页经摘要工具读取，数字引用前应对照原文。

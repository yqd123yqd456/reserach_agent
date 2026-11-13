# 三种 harness 与一次 agent run 的最小对象模型

> 学习结论：
> 1. “harness”至少指三种组件：**agent execution harness**（让模型能调用工具、管理上下文与循环）、**evaluation harness**（准备环境、运行试验、判分、记录）、**training rollout infrastructure**（大规模采样轨迹并把 reward 回传给训练）。三者可以共享代码，但职责、失败方式与 owner 不同。
> 2. 一次 run 的最小对象：task、environment/state、tool schema、step、termination、trace、verifier、result。最容易做错的是：**verifier 依据 agent 自述而不是环境状态判成功**，以及**把无效 run 静默地从分母中丢掉**。
> 3. agent 比单轮难，是因为多步、有状态、有副作用、路径不唯一。每一条都迫使 harness 做一件具体的事。
>
> 后续：[02 工具使用测量](02_工具使用测量与过程约束.md) → [03 故障注入](03_故障注入与恢复.md) → [04 失败诊断](04_失败诊断与受控重跑.md) → [05 verifier 验证](05_verifier的验证与防作弊.md) → [06 公平比较](06_公平比较与统计.md) → [07 post-training](07_从评估信号到post-training.md)。实现规格：[Practice/00](../Practice/00_共用harness规格.md)。

## 1. 三种 harness

| | agent execution harness | evaluation harness | training rollout infra |
|---|---|---|---|
| 别名 | scaffold、agent runtime | eval framework、runner | RL environment server、rollout workers |
| 负责 | 提示词、工具定义、上下文管理、循环与停止、重试策略 | 环境准备与重置、试验调度、判分、日志、聚合 | 大批量并发采样、环境池、把 reward 回传 trainer |
| 被测吗 | **是**：评估 agent = 评估“模型 + 它的 harness”（Anthropic, 2026-01） | 否；但它的 bug 会伪装成模型失败 | 否；但吞吐与环境保真决定训练信号质量 |
| 典型失败 | 工具描述误导、上下文截断、无限循环 | 环境未重置、判分错误、infra 错误计入失败 | 环境崩溃、reward 计算错误、采样偏差 |
| 例子 | Claude Code、OpenHands、SWE-agent | Inspect AI、τ²-bench 的 evaluator、Harbor | verl 的 rollout + reward manager |

**为什么要分开**：
- 比较两个模型时，execution harness 必须固定，否则差异可能来自 harness。Mercor 的 Agent Eval Systems 文章（2026-06-30，Brandon Lei）中的优化循环恰恰是改 prompts、skills 与 harness，这意味着“被优化的对象”包含 execution harness，而 verifier 与评估集必须保持独立。
- evaluation harness 的 bug 应当表现为**无效 run**，而不是模型失败。Anthropic 在 Terminal-Bench 2.0 上发现，资源上限设置最严时 infra error 达 5.8%（[06](06_公平比较与统计.md)）。
- training rollout 中，同一个 verifier 既用于 reward 又用于报告，会让“训练提升”变成“学会讨好这个 verifier”（[07](07_从评估信号到post-training.md)）。

## 2. 一个真实框架的对象：Inspect AI

UK AISI 的 Inspect AI（commit `e4435baa`，2026-11-12；代码已读，未运行），路径均在 `src/inspect_ai/` 下：

| 对象 | 位置 | 输入 → 输出 |
|---|---|---|
| `Task` | `_eval/task/task.py` | 打包 dataset、solver、scorer、metrics、sandbox、epochs，以及 message/token/time/cost 等限制 |
| `Sample` | `dataset/_dataset.py` | `input`、`target`、`metadata`、`sandbox`、`files`、`setup` |
| `Solver` | `solver/_solver.py` | `(TaskState, generate) → TaskState`；agent 是同类变换 |
| `TaskState` | `solver/_task_state.py` | 单个样本的消息、输出、工具、store、是否完成 |
| `Tool` | `tool/_tool.py` | 异步可调用，返回 `ToolResult` |
| `SandboxEnvironment` | `util/_sandbox/environment.py` | `exec / read_file / write_file`；生命周期 `task_init`、`sample_init`、`sample_cleanup`、`task_cleanup` |
| `Scorer` → `Score` | `scorer/_scorer.py`、`scorer/_metric.py` | `(TaskState, Target) → Score(value, answer, explanation, …)` |
| `Epochs` + reducer | `_eval/task/epochs.py`、`scorer/_reducer/` | 每个样本重复 n 次，再用 mean、pass_at、at_least 等合并 |
| `EvalLog` / `EvalSample` | `log/_log.py` | 配置、结果、每样本每 epoch 的消息、事件、用量、错误、限制 |

**可学的设计**：sandbox 的生命周期以**样本**为单位（`sample_init` / `sample_cleanup`），这是 reset 的落点；scorer 拿到的是 `TaskState`（包括 sandbox 可访问的状态），因此可以检查结果而不是自述；`EvalSample.error` 与 `error_retries` 把错误与分数分开记录。

## 3. 最小对象模型：输入与输出

下面是练习项目采用的对象（完整 schema 见 [Practice/00 §2](../Practice/00_共用harness规格.md#2-数据-schemal1-起就固定)）。

| 对象 | 输入 | 输出 | 必须记录 |
|---|---|---|---|
| task | — | 指令、初始状态、允许的工具、预算、成功检查、过程约束、split、version | version（任务或 verifier 一改就升） |
| environment | task 的初始状态 | 工具执行结果；可快照的状态 | 每步之后的状态 hash |
| tool schema | — | 名称、描述、参数 JSON Schema、副作用级别（read/write/irreversible） | 描述文本版本（会影响行为） |
| step | 历史 → 模型动作 | 动作、工具结果、policy 决定、是否注入故障 | 时间、tokens |
| termination | 循环状态 | 主动结束 / 步数耗尽 / 预算耗尽 / 环境致命错误 / harness 异常 | 原因（决定 valid） |
| trace | 全部 step | 可复放、可重判 | agent 配置（模型、prompt hash、温度、harness 版本） |
| verifier | 初始与最终状态、artifact、trace | 逐项检查结果 + 证据 | 检查依据的具体字段或步号 |
| result | verifier 输出 + termination | valid、success、violations、cost | 无效原因 |

**真实的 benchmark 都是这样判的**：
- τ-bench：把 agent 运行后的数据库 hash 与“在新环境上重放标准动作”得到的数据库 hash 比较，再要求回复中包含必要信息；奖励是两者的乘积（`tau_bench/envs/base.py` 的 `Env.calculate_reward`，commit `59a200c`）。
- τ²-bench：只有当终止原因是 agent 或用户主动结束时才可能得分，其余直接为 0；最终奖励是任务指定的各检查项（数据库、环境断言、沟通信息、自然语言断言、动作）的乘积（`evaluator/evaluator.py` 的 `evaluate_simulation`，commit `c06b07d`）。
- Terminal-Bench / Harbor：**agent 运行结束后**才把测试上传进容器，运行 `test.sh` 并写 reward 文件；判分前删除残留 reward 文件（`src/harbor/verifier/verifier.py` 的 `Verifier.verify`，commit `06d0e86`）。测试上传时机本身就是防作弊设计。
- Mercor 文章对 verifier 的定义：一个**隔离的**程序或 agent，检查一次 run，返回 [0,1] 内的归一化分数并解释依据；作用范围可以是轨迹、最终 artifact、外部状态变化或其组合；运行在自己的 sandbox，可使用与被测 agent 不同的模型。

## 4. agent 为什么比单轮难：每个特性迫使 harness 做什么

| 特性 | 后果 | harness 必须做 |
|---|---|---|
| 多步 | 早期一步错可能在很久之后才显现；也可能被后续步骤修正 | 逐步记录状态 hash；诊断时找**最早影响结果的偏离**（[04](04_失败诊断与受控重跑.md)） |
| 有状态 | 前一次 run 的残留会污染后一次（Anthropic 报告过 agent 读到早先试验留下的 git 历史） | 每个试验独立重置；ABC 清单 T.4 要求清除残留状态 |
| 有副作用 | 正确的终态可能伴随不该发生的写入 | 附带损害检查（AppWorld：状态差异必须落在“期望 ∪ 允许”的集合内）；policy 在执行前拦截 |
| 路径不唯一 | 与参考轨迹逐步比对会误拒合法解 | 判结果状态而非路径；需要过程约束时写成约束，而不是写成“必须按这个顺序” |
| 随机性 | 同一题多次结果不同 | 重复试验；报告 pass^k 与不确定度（[06](06_公平比较与统计.md)） |
| 成本 | 长循环、子 agent 可能无界 | 预算是任务的一部分；成本与成功一起报告 |

### 误差累积的直觉与它的假设

若一项任务需要 n 步、每步都必须成功、各步成功独立且概率均为 p，则任务成功率是 `p^n`：p=0.95、n=20 时约 0.36。这个式子只用来说明“长任务对每步可靠性非常敏感”。真实 agent 不服从它：步骤不独立（同一误解会反复出现），并非每步都必须成功（agent 可以发现并修正错误），步骤难度也不均匀。METR 的 time horizon 研究直接拟合“成功率 vs 人类所需时间”，而不是假设 `p^n`（[08](08_研究agent评估与L1L2L3.md)）。

## 5. Harness-first 的准备顺序

先把任务、环境、可观测证据和判分跑通，再比较模型／prompt／harness 的改进。理由：如果 verifier 会误判，任何改进的结论都不可信。这是**准备与实验的顺序**，不是“模型不重要”的结论。

## 6. 面试可能追问

- “execution harness 和 eval harness 能是同一套代码吗？” → 可以共享环境与工具实现，但判分、重置、日志必须不受被测 agent 影响；被优化的对象不能控制自己的评估。
- “一条 trajectory 是怎么产生的，哪里会坏？”（Mercor Enterprise Evals Platform JD 原文要求理解这一点）→ 按第 3 节对象逐个讲：工具描述、参数校验、policy、故障、上下文、终止、判分，每处给一个失败例子。
- “为什么不用参考轨迹逐步比对？” → 路径不唯一；用终态 + 约束；需要过程信息时检查“必要动作是否出现”（τ² 的动作检查只要求标准动作出现在轨迹中，不惩罚顺序与额外调用）。

## 来源

- UK AISI Inspect AI，commit `e4435baa`（代码已读，未运行）。
- Yao et al., *τ-bench*, arXiv 2406.12045 v1 + 代码 commit `59a200c`；Barres et al., *τ²-bench*, arXiv 2506.07982 v1 + 代码 commit `c06b07d`。
- Merrill et al., *Terminal-Bench*, arXiv 2601.11868 v1（ICLR 2026）+ Harbor commit `06d0e86`。
- Trivedi et al., *AppWorld*, arXiv 2407.18901 v1（ACL 2024）。
- Mercor, *Agent Eval Systems*, 2026-06-30（公司博客）。
- Anthropic Engineering, *Demystifying evals for AI agents*, 2026-01-09；*Quantifying infrastructure noise in agentic coding evals*, 2026-02-05。

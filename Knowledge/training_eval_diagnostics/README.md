# training_eval_diagnostics：训练与 Checkpoint 行为诊断

> 研究于 2026-11-14，服务于 Mirendil Model Evaluation take-home 的准备。这是可能的题型之一，不是已知考题。Mirendil 的 JD 原文提到“给训练运行加上可观测性工具，让研究者理解模型行为在变什么、为什么变”，本专题围绕这句话准备。
> 前置：[agent_harness 06 公平比较](../agent_harness/06_公平比较与统计.md)（配对、任务为单位、无效 run）、[08 L1–L2–L3](../agent_harness/08_研究agent评估与L1L2L3.md)（BPB 与任务能力的已知联系）、[07 post-training](../agent_harness/07_从评估信号到post-training.md)（reward 被利用的证据）。本页讲**拿到日志与多个 checkpoint 的评估结果后，怎样一步步诊断**。
> 可运行草图：[Practice/training_eval_diagnostics](../../Practice/training_eval_diagnostics/README.md)。速查卡：[Review/training_eval_diagnostics](../../Review/training_eval_diagnostics/速查卡.md)。

## 学习结论

1. 诊断的第一步永远是**可比性**：两次评估的任务集、grader 版本、评估配置、无效试验是否一致。不一致时，分数的变化不能归给模型。
2. loss／BPB、训练 reward、独立任务通过率是**三种不同的测量**。任何两者背离都是信息，而不是噪声。
3. 比较两个 checkpoint 用**同一批任务上的配对差**，以任务为单位给区间，然后**分切片**。总分上升可以掩盖某一类能力的退步。
4. 从曲线到样本要有一条固定路径：指标变化 → 切片 → 翻转的任务 → 具体输出。每一步都由 id 关联，不靠记忆。
5. 曲线与切片给的是**观察性线索**。“因为 X 所以变差”需要干预：只改一个因素，重新训练或重新评估。

## 1. 题型范围

| 典型输入 | 典型交付物 |
|---|---|
| 训练日志（每步的 loss、学习率等）；若干 checkpoint 的评估结果（按任务、按试验）；部分输出样例；有时还有配置与版本信息 | 一份诊断报告：发生了什么变化、哪些变化可信、可能的解释与各自的证据、下一步要做的验证；以及产生这份报告的脚本 |

变体：设计“每次 checkpoint 自动跑什么评估、怎样报警”；给一条看起来异常的曲线让你找原因。

## 2. 定义与最小关联 schema

| 对象 | 必要字段 | 关联 |
|---|---|---|
| run（一次训练） | `run_id`、代码 commit、数据版本、训练配置 | — |
| 训练日志行 | `run_id`、`step`、各指标 | → run |
| checkpoint | `run_id`、`step`（以及保存路径） | → run、step |
| 评估记录（一次试验） | `run_id`、`ckpt_step`、`task_id`、`slice`、`trial`、`valid`、通过与否、`suite_version`、`grader_version`、`sample_id` | → checkpoint、任务 |
| 输出样例 | `sample_id`、模型输出、判分证据 | → 评估记录 |

**为什么每个字段都需要**：缺 `grader_version` 就发现不了判分规则的变化；缺 `valid` 就会把基础设施故障算成模型失败；缺 `sample_id` 就无法从数字走到输出；缺 `slice` 就只能看总分。

**真实框架里这些字段在哪**：

- **verl**（commit `8a2d1d9`，代码已读）：每步调用一次 `logger.log(data=metrics, step=self.global_steps)`（[`ray_trainer.py` L1804](https://github.com/volcengine/verl/blob/8a2d1d9227544e5f5dbb428d9797858b1ad5664f/verl/trainer/ppo/ray_trainer.py#L1804)）；验证在 `_validate`（L598）中进行，指标命名为 `val-core/...` 与 `val-aux/...`（`_val_metrics_update`，L723–L748），按 `test_freq` 触发（L1729–L1735）；checkpoint 存到 `.../global_step_{n}/actor`（`_save_checkpoint`，L985–L994）。**checkpoint 与指标之间只靠 `global_steps` 关联**，checkpoint 目录里没有评估记录。默认配置里 `test_freq` 与 `save_freq` 都是 −1，即默认不做周期性验证与保存（`ppo_trainer.yaml` L174、L205）。
- **Inspect AI**（commit `e4435ba`，代码已读）：`EvalSpec`（[`log/_log.py` L1114 起](https://github.com/UKGovernmentBEIS/inspect_ai/blob/e4435baa530d05324358bedc3782609c952f9876/src/inspect_ai/log/_log.py#L1114)）记录任务名与 `task_version`、`task_args`、数据集（名称、样本 id 列表、是否打乱）、`model` 与生成配置、评估配置（样本上限、重复次数及合并方式、各类限制）、代码版本（`EvalRevision`：git commit 与工作区是否有未提交改动）、依赖包版本。`EvalResults` 记录总样本数与完成样本数，每个评分器的已评分与未评分样本数。这些字段正好是可比性检查的清单。
- **autoresearch**（上游 commit `228791f`，代码已读）：训练过程中只打印平滑后的训练 loss 等进度信息，**没有中间验证，也不保存 checkpoint**；结束时算一次 `val_bpb`（见 [autoresearch_loop](../autoresearch_loop/README.md)）。

## 3. 三种指标分别说明什么

| 指标 | 测的是什么 | 不能说明什么 | 何时会与任务能力背离 |
|---|---|---|---|
| 训练 loss | 模型对训练分布的拟合 | 泛化；任何具体能力 | 过拟合；数据分布与任务不匹配 |
| held-out BPB | 模型给保留文本的每字节平均 bit 数，越低表示预测越准 | 能否完成需要多步行动的任务 | 文本预测变好的部分与任务所需能力无关；后训练改变了输出分布（[08 §2](../agent_harness/08_研究agent评估与L1L2L3.md#2-l1--l2公开证据说了什么)） |
| 训练 reward | 训练时的 verifier 或 judge 给出的分数 | 独立标准下的正确性 | policy 学会了讨好这个 verifier（[07 §3](../agent_harness/07_从评估信号到post-training.md#3-哪些信号能当-reward)） |
| 独立任务通过率 | 在训练没有用过的 verifier 与任务上的表现 | 评估集之外的能力 | 评估集太小或被污染 |

**BPB 的具体计算**（autoresearch 的 `evaluate_bpb`，[`prepare.py` L343–L365](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/prepare.py#L343-L365)）：对验证数据逐 token 取交叉熵（单位 nat），只累加目标 token 字节数大于 0 的位置（特殊 token 的字节数记为 0，被排除），最后 `总 nat ÷ (ln 2 × 总字节数)`。按字节归一化让不同分词器的模型可比。

## 4. 贯穿例子：三条合成 run 的诊断

数据是**合成的教学数据**（[`gen_synthetic.py`](../../Practice/training_eval_diagnostics/sketch/gen_synthetic.py)，固定种子），40 个任务分 4 个切片，每个 checkpoint 每个任务 3 次试验。下面的数字是 [`diagnose.py`](../../Practice/training_eval_diagnostics/sketch/diagnose.py) 的实际输出，只用来演示诊断步骤，不代表任何真实模型。

### 情境 A：loss／BPB 降低，任务通过率不变

```text
val_bpb      step 1000 -> 4000: 0.9494 -> 0.7991
indep pass rate by checkpoint: {1000: 0.425, 2000: 0.458, 3000: 0.45, 4000: 0.633}
comparability step 1000 vs 4000: ["grader_version differs: ['grader-v1'] vs ['grader-v2']"]
paired diff (step 3000 - step 1000), all tasks: {'n_tasks': 40, 'diff': 0.025, 'ci95': (-0.083, 0.133)}
```

诊断过程：
1. 只看通过率曲线，step 4000 像是一次大提升（0.45 → 0.633）。**可比性检查发现这次评估换了 grader 版本**，所以这个点不能与前面的比。
2. 在可比的范围内（step 1000 到 3000），配对差 +0.025，区间跨 0：没有证据表明任务能力变化。
3. 分切片的差有正有负（+0.2、−0.133 等），区间都跨 0。每个切片只有 10 个任务、每任务 3 次试验，**这种幅度的波动是噪声水平**，不应解读。
4. 竞争解释与下一步：

| 解释 | 支持它的观察 | 怎样验证 |
|---|---|---|
| BPB 的改进与这些任务所需的能力无关 | BPB 降、通过率平 | 把 BPB 按语料类型拆开，看是哪类文本变好了 |
| 任务集太小或太难，分辨不出变化 | 区间宽度约 ±0.1 | 算功效；增加任务或试验数 |
| 瓶颈在 harness 或推理配置 | — | 固定 checkpoint，改 harness 配置，看通过率是否变化 |
| 能力确实没变 | 以上都排除后 | — |

5. grader 版本的问题要单独处理：用 v2 **重判** step 1000–3000 的存档输出，或用 v1 重判 step 4000，再比较（重判的含义见 [Practice 00 §2.4](../../Practice/agent_harness/00_共用harness规格.md#24-三种再来一次不要混用)）。

### 情境 B：reward 上升，独立验证不改善

```text
reward_mean  step 1000 -> 4000: 0.425 -> 0.65
paired diff (step 4000 - step 1000), all tasks: {'n_tasks': 40, 'diff': 0.0, 'ci95': (-0.092, 0.1)}
step 1000: reward_pass 51/120, indep_pass 51/120, reward-only passes 0
step 4000: reward_pass 78/120, indep_pass 51/120, reward-only passes 27
paired diff on reward_pass: {'n_tasks': 40, 'diff': 0.225, 'ci95': (0.125, 0.317)}
reward-only passes at step 4000 by output note: {'special-cases the visible test inputs': 27}
```

诊断过程：
1. reward（可见测试的通过率）显著上升（+0.225，区间不含 0），独立验证的配对差为 0。
2. **分解**：把每次试验按“reward 通过 × 独立通过”分成四格。“只有 reward 通过”的试验从 0 增加到 27。上升的 reward 全部来自这一格。
3. **读样本**：这 27 个输出的标注都是“对可见测试的输入做了特判”（合成数据中预置的标注；真实情况下这一步要人或经过验证的分类器来读）。
4. 结论的表述：“reward 的上升由只在可见测试上通过的输出解释；没有证据表明独立标准下的能力提高”。
5. 下一步：在训练环境里隐藏或隔离测试；把“只有 reward 通过”的比例作为常设监控指标；加入不可能完成的任务作为探针（[07 §3](../agent_harness/07_从评估信号到post-training.md#3-哪些信号能当-reward)）。

### 情境 C：总分提高，但某类能力退步

```text
indep pass rate by checkpoint: {1000: 0.408, 2000: 0.425, 3000: 0.5, 4000: 0.525}
comparability step 1000 vs 2000: ["last: 8/120 invalid trials (['sandbox_unavailable']) concentrated in ['optimizer']"]
paired diff (step 4000 - step 1000), all tasks: {'n_tasks': 40, 'diff': 0.117, 'ci95': (0.008, 0.225)}
  slice eval_leakage         {'n_tasks': 10, 'diff': 0.233, 'ci95': (0.033, 0.4)}  <-- improvement
  slice numerical_stability  {'n_tasks': 10, 'diff': -0.167, 'ci95': (-0.3, -0.033)}  <-- regression
  slice optimizer            {'n_tasks': 10, 'diff': 0.267, 'ci95': (0.133, 0.4)}  <-- improvement
largest per-task drops: [('nume-08', -0.67), ...]
  samples to read for nume-08 @ step 4000: ['C-4000-nume-08-1', 'C-4000-nume-08-2']
```

诊断过程：
1. 总体配对差 +0.117，区间勉强不含 0。
2. 分切片：两个切片显著进步，`numerical_stability` 显著退步（−0.167，区间整体在 0 以下）。
3. 下钻：退步最大的任务是 `nume-08`，脚本给出要读的两个样本 id。
4. 可比性检查还报告：step 2000 的评估有 8 次无效试验，全部集中在 `optimizer` 切片，原因是 sandbox 不可用。这不影响首尾比较，但**如果比较的是 step 2000，无效试验集中在一个切片会让该切片的估计有偏**；应补跑。
5. 竞争解释：训练数据中这一类样本变少或被冲掉；新数据教会了一种在数值任务上有害的习惯。验证方法是干预：只改数据配比重新训练，或在同一 checkpoint 上用针对性探针测试。
6. 对发布决策的含义：总分上升不足以放行；回归集里若有这个切片，应当阻止发布（[06 §4](../agent_harness/06_公平比较与统计.md#4-开发集保留测试集回归集各管什么)）。

注意：4 个切片各做一次检验，就有多重比较问题——即使没有任何真实变化，也有不小的概率至少一个切片“显著”。情境 A 的切片波动就是提醒。发现切片退步后，应在**新的任务**上复核，而不是只凭这一次。

## 5. 机制：诊断的固定路径

```text
0. 关联：每条评估记录都能对上 run、checkpoint、任务、版本吗？
1. 可比性：任务集、suite 版本、grader 版本、评估配置一致吗？无效试验有多少、集中在哪？
2. 曲线：loss、BPB、reward、独立通过率各自的首尾变化
3. 配对比较：同一批任务上的差，任务级 bootstrap 区间
4. 切片：按能力类别分别做第 3 步
5. 下钻：变化最大的任务 → 翻转的试验 → sample_id → 输出与判分证据
6. 分解（有 reward 时）：reward 通过 × 独立通过 的四格表
7. 假设与干预：每个解释写出支持它的观察与能否证伪它的实验
```

关键伪代码（完整实现见草图，约 90 行）：

```python
def task_rates(records):                 # 每任务在有效试验上的通过率；没有有效试验的任务不当作 0
def comparability(first, last):          # 返回问题列表：版本不同、任务集不同、无效试验及其集中的切片
def paired(a, b, tasks, n_boot=2000):    # 同任务配对差；以任务为单位重采样得到区间
```

## 6. 区分四类原因

| 看到的变化可能来自 | 特征 | 检查 |
|---|---|---|
| 能力变化 | 在可比条件下、配对差的区间不含 0、在新任务上能复现 | 第 3–4 步 + 复核 |
| 随机波动 | 区间跨 0；不同切片方向不一；换种子后消失 | 区间、重复试验 |
| 数据或 grader 变化 | 变化发生在版本切换的那个点；重判存档输出后消失 | 第 1 步；重判 |
| 运行故障 | 无效试验增多；集中在某类任务或某个时间段 | 无效试验的数量与分布 |

## 7. 固定行为探针

每个 checkpoint 都跑同一组小而固定的任务（几十个，分切片，版本冻结），目的是**尽早看到行为变化**，不是估计绝对能力。设计要点：

- 探针集与 grader 的版本固定，写进每条评估记录。
- 每个切片的任务数足以看到大幅退步（情境 C 的切片各 10 个任务，只能可靠地看到 ±0.15 以上的变化）。
- 保存每个 checkpoint 在探针上的**全部输出**，这样 grader 更新后可以重判，而不必重跑模型。
- 探针集被反复用于决策后会逐渐失去独立性，定期用新任务复核。

## 8. 观察与因果

| 观察性陈述（可以直接从数据得出） | 因果陈述（需要干预） |
|---|---|
| step 4000 的 `numerical_stability` 通过率比 step 1000 低 0.167 | 新加的训练数据导致了数值任务退步 |
| reward 上升的部分全部是只在可见测试上通过的输出 | 可见测试让模型学会了特判 |

干预的最小形式：**只改一个因素**（数据配比、reward 定义、学习率），其他固定，重新训练或从同一 checkpoint 分叉；用相同的评估条件比较。训练本身有随机性，所以对照组也要有多个种子，否则分不清干预效应与种子差异。你的因果推断背景在这里可以直接用上：画因果图只是把假设写清楚，识别要靠干预或满足识别条件的设计。

## 9. 局限

- 草图的数据是合成的，效应是我设定的；诊断脚本“发现”了它们只说明脚本的逻辑走通，不说明这些方法在真实数据上的检出能力。
- 切片的区间在 10 个任务上很宽；真实场景需要更多任务，并处理多重比较。
- 没有覆盖：训练内部的诊断（梯度范数、各层统计）、分布式训练的日志对齐、checkpoint 之间的权重差异分析。
- 输出标注（“对可见测试做了特判”）在合成数据里是预置的；真实情况下这一步是最费力的，见 [agent_failure_investigation](../agent_failure_investigation/README.md)。

## 来源

| 来源 | 状态 | 支持的结论 | 重点读 |
|---|---|---|---|
| verl，commit `8a2d1d9`：`verl/trainer/ppo/ray_trainer.py`、`verl/trainer/config/ppo_trainer.yaml`、`verl/utils/tracking.py` | 代码已读，未运行 | 每步日志、验证指标命名、checkpoint 路径；checkpoint 与指标只靠步数关联 | `_validate` L598；`_val_metrics_update` L723–L748；`_save_checkpoint` L985–L994 |
| Inspect AI，commit `e4435ba`：`log/_log.py` 的 `EvalSpec`、`EvalConfig`、`EvalDataset`、`EvalRevision`、`EvalResults` | 代码已读，未运行 | 可比性检查需要的字段清单 | L1114–L1223 |
| autoresearch 上游，commit `228791f`：`prepare.py::evaluate_bpb`、`train.py` | 代码已读，未运行 | BPB 的具体计算；没有中间验证与 checkpoint | `prepare.py` L343–L365 |
| Miller, [arXiv 2411.00640v1](https://arxiv.org/abs/2411.00640v1) | 原文核对（上一轮） | 配对差、簇层面重采样 | §4.2、附录 C |
| Anthropic, [infrastructure noise](https://www.anthropic.com/engineering/infrastructure-noise) | 原文核对（上一轮） | 资源配置改变成功率；无效试验的处理 | 结果段 |
| Huang et al. [arXiv 2404.09937v2](https://arxiv.org/abs/2404.09937v2)；Gadre et al. [arXiv 2403.08540](https://arxiv.org/abs/2403.08540) | 原文核对；二手摘要（上一轮） | BPB 与平均分的相关及其局限 | 见 agent_harness 08 |
| 本仓库 `Practice/training_eval_diagnostics/sketch/` | 代码已运行（合成数据） | 三个情境的全部数字 | — |

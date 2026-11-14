# task_dataset_design：能力、任务、Dataset 与 Verifier

> 研究于 2026-11-14，服务于 Mirendil Model Evaluation take-home 的准备。这是可能的题型之一，不是已知考题。
> 分工：本页回答“**任务是否测到了目标能力**”。“grader 是否执行正确”见 [grading](../grading/README.md)；任务怎样被运行与记录见 [agent_harness 01a](../agent_harness/01a_execution_harness一次run的完整过程.md) 与 [Practice 00](../../Practice/agent_harness/00_共用harness规格.md)；公开 benchmark 的效度问题见 [agent_harness 05](../agent_harness/05_verifier的验证与防作弊.md)。
> 可运行草图：[Practice/task_dataset_design](../../Practice/task_dataset_design/README.md)。速查卡：[Review/task_dataset_design](../../Review/task_dataset_design/速查卡.md)。

## 学习结论

1. 一个评估任务是五样东西的组合：**能力声明**（想测什么）、**fixture**（初始代码、数据、依赖）、**指令**（给 agent 的话）、**预算与工具**、**verifier**（隐藏的独立判定）。任何一样出问题，分数都不再代表能力。
2. 任务效度靠**审计**保证，不靠直觉：no-op、已知合法解、已知错误解、作弊捷径逐个跑一遍。本专题的草图里，我自己写的第一版可见检查就让 no-op 通过了。
3. verifier 要**独立**：用自己的数据、自己的指标实现、新的随机种子；不信任被测代码打印的任何数字。
4. 一个任务支持不了能力结论。能力结论来自**任务族**上的分布：多个来源、多种 bug 类型、难度分层、去重与划分。
5. 很多“模型失败”是题目的问题。判断标准：oracle 解是否通过、多数强模型是否都在同一处失败、人类专家是否认为指令足够。

## 1. 题型范围

| 典型输入 | 典型交付物 |
|---|---|
| 一句能力描述（“模型能修复训练 bug”），或一批原始材料（真实 bug、PR、论文） | 任务 schema；若干完整任务（fixture、指令、verifier）；任务审计表；数据划分与已知局限说明 |

变体：给你一个现成的 benchmark 任务让你找缺陷；给你失败率很高的任务让你判断是题目问题还是模型问题。

## 2. 定义

| 概念 | 定义 |
|---|---|
| 能力（capability） | 想要下结论的对象，例如“在给定代码库中诊断并修复导致训练不收敛的 bug” |
| 任务（task） | 能力的一个可运行实例：fixture + 指令 + 预算 + verifier |
| 任务族（family） | 共享来源或结构的一组任务（同一类 bug、同一个仓库）。族内任务相关，统计时按族聚类 |
| fixture | 任务开始时的全部初始状态：代码、数据、依赖版本、环境变量 |
| oracle 解 | 一个已知能通过 verifier 的参考解，用来证明任务可解 |
| 可见检查 | agent 运行期间可以自己执行的检查（单元测试、打印的指标） |
| 隐藏 verifier | agent 接触不到、在运行结束后执行的判定 |
| 任务效度 | 任务可解，当且仅当 agent 具备目标能力（ABC 清单的定义，见 [agent_harness 05 §1](../agent_harness/05_verifier的验证与防作弊.md#1-两种效度)） |

## 3. 贯穿例子：一个训练 bug 任务

完整文件在 [`Practice/task_dataset_design/sketch/`](../../Practice/task_dataset_design/sketch/)，已在本地实际运行。

**初始代码**（`task_fixture/train.py`，纯 Python 逻辑回归，节选）：

```python
for _ in range(epochs):
    perm = list(range(n))
    rng.shuffle(perm)                 # 每个 epoch 重新打乱（任务要求保留）
    Xs = [X[i] for i in perm]
    ys = y                            # BUG：特征打乱了，标签没有跟着打乱
    for x, t in zip(Xs, ys): ...      # SGD 更新
```

**现象**（实际运行 8 个 seed）：验证准确率在各 seed 之间乱跳——0.995、0.36、0.40、0.76、0.325、0.315、0.25、0.035；验证 loss 在 0.39 到 1.22 之间。原因：特征与标签错位后，梯度在期望上把权重推向 0，剩下的只是 SGD 噪声；噪声方向恰好与类别方向一致时准确率接近 1，相反时接近 0。

> 我最初把现象写成“准确率停在 0.5 左右”，运行后发现不对。**任务说明里的现象描述必须来自实际运行**，否则指令本身就在误导 agent。

**给 agent 的说明**（`task.json` 的 `instruction`）：train.py 训练一个二分类逻辑回归，但结果很不稳定：换一个 seed，验证准确率可能接近 1，也可能接近 0，验证 loss 没有稳定下降。找出原因并修复，使模型在不同 seed 下都能正常学习。要求：保留每个 epoch 的随机打乱；不要改动 `make_data`、`evaluate` 的行为和 `train` 的函数签名；只修改 train.py。

**合法修复**（多个）：同步打乱标签（`ys = [y[i] for i in perm]`）；把 (x, y) 配对后整体打乱。

**错误修复与捷径**：硬编码打印的指标；只对可见 seed 特判；删除打乱（让训练恢复，但违反要求）；篡改 `evaluate`。

**verifier**（`verifier.py`，隐藏）：

| 检查 | 怎样判 | 防什么 |
|---|---|---|
| `api.unchanged` | `train` 的参数列表不变；三个函数都在 | 改签名绕过 |
| `capability.learns_on_fresh_data` | verifier **自己生成**训练与验证数据，用 3 个新 seed 调用候选的 `train`，用 verifier **自己实现**的准确率与 loss 判定：每个 seed 准确率 ≥ 0.9 且 loss ≤ 0.3 | 硬编码、对可见 seed 特判、篡改 `evaluate` |
| `constraint.shuffle_kept` | 同一份数据、不同 seed 训练两次，权重必须不同（初始化为 0，seed 只影响打乱顺序） | 删除打乱 |
| `constraint.evaluate_unchanged` | 候选的 `evaluate` 在 3 组探针上与参考实现一致 | 篡改评估函数 |
| `constraint.make_data_unchanged` | `make_data(50, 3)` 与参考实现一致 | 篡改数据生成 |

**审计结果**（`audit_task.py` 的实际输出）：

```text
variant                   kind     vis_v1  vis_v2  hidden   failed hidden checks
noop_buggy                no-op    PASS    fail    fail     ['capability.learns_on_fresh_data']
fix_shuffle_labels        valid    PASS    PASS    PASS     []
fix_shuffle_pairs         valid    PASS    PASS    PASS     []
wrong_hardcode_print      invalid  PASS    PASS    fail     ['capability.learns_on_fresh_data']
wrong_special_case_seed0  invalid  PASS    fail    fail     ['capability.learns_on_fresh_data']
wrong_remove_shuffle      invalid  PASS    PASS    fail     ['constraint.shuffle_kept']
wrong_tamper_evaluate     invalid  PASS    fail    fail     ['capability.learns_on_fresh_data', 'constraint.evaluate_unchanged']
false accepts: visible v1=5, visible v2=2, hidden verifier=0; false rejects by hidden verifier=0
```

读法：
- `vis_v1`（只看 seed 0 打印的准确率）接受了全部 5 个不该接受的候选，**包括什么都没改的原始代码**——因为 seed 0 恰好是噪声方向对的那个。
- `vis_v2`（3 个 seed，准确率加 loss）仍然接受硬编码打印与删除打乱：它相信被测代码打印的数字，也不检查约束。
- 隐藏 verifier 没有误接受，也没有误拒两个合法修复。

这张表就是任务审计的最小形态。它同时说明：**可见检查是给 agent 的反馈，不是判定依据**。

## 4. 机制：从能力到可下结论的数据集

### 4.1 能力定义决定任务分布

“模型能修复训练 bug”要先拆开：哪类 bug（数据管线、优化器、损失、评估泄漏、数值稳定）？在多大的代码库里？给不给复现步骤？能不能运行代码？每个选择都改变被测的东西。上面的例子只覆盖“单文件、数据管线、可运行、有明确症状”这一小格。

### 4.2 任务来源

| 来源 | 优点 | 风险 | 例子 |
|---|---|---|---|
| 真实 issue 与 PR | 真实分布 | 描述不充分、测试过窄、可能在训练数据中 | SWE-bench；OpenAI 的标注数据显示大量样本因此被过滤（[agent_harness 05 §2](../agent_harness/05_verifier的验证与防作弊.md#2-公开-benchmark-里出过的问题按方向)） |
| 合成 bug 注入 | 可控、可大量生成、有天然 oracle（还原即可） | 分布偏向“容易注入的 bug”；指令常由模型生成 | SWE-smith：只保留能让至少一个原本通过的测试失败的 bug |
| 专家手写 | 质量高、可针对能力缺口 | 贵、数量少、带作者偏好 | Terminal-Bench：每个任务约 3 小时人工审查 |

### 4.3 可解性、歧义、多个合法解

- **可解性**：oracle 解必须在与 agent 相同的环境里通过 verifier。
- **歧义**：指令没有说、verifier 却依赖的东西。检查方法：把 verifier 的每个断言逐条对回指令，找不到出处的就是隐含要求。
- **多个合法解**：verifier 判**行为**，不判实现文本。例子里两种修复写法不同，都通过。

### 4.4 独立测试、回归、附带损害、捷径

- 独立：verifier 的数据与指标实现不来自被测代码；测试在 agent 结束后才进入环境。
- 回归：原本正确的行为保持不变（例子里的 `evaluate`、`make_data`）。
- 附带损害：不该改的没改（文件哈希或行为探针）。
- 捷径清单：硬编码输出、特判可见输入、修改测试或评估、删除约束、读取答案文件。每条都要有一个对应的审计候选。

### 4.5 任务族、难度、划分、近重复、污染

- **族**：按 bug 类型或来源仓库分族；统计时族是聚类单位（[agent_harness 06](../agent_harness/06_公平比较与统计.md)）。
- **难度**：用可观测的东西定义（定位 bug 需要读几个文件、是否需要运行实验、oracle 解的改动行数、人类用时），不要事后按模型通过率定义。
- **划分**：dev 与 test 按**族**切分，不按任务随机切分，否则同一类 bug 的近重复会跨越划分。
- **近重复**：同一 bug 换变量名、同一仓库相邻提交。去重后再报告任务数。
- **污染**：公开来源的任务可能在训练数据中。缓解：canary 字符串、保留不公开的测试集、用发布日期晚于模型截止日期的材料、检查模型能否不看代码就复述修复。

### 4.6 什么时候修题而不是责怪模型

| 信号 | 更可能是题目问题 |
|---|---|
| oracle 解不通过，或需要指令之外的信息才能通过 | 是 |
| 多个强模型在同一个断言上失败，且失败轨迹显示它们做了合理的事 | 是 |
| 人类专家读指令后也无法确定该做什么 | 是 |
| 不同模型失败方式各不相同，oracle 通过，专家认为指令清楚 | 否，更可能是能力问题 |

τ-bench 作者在 40 条失败轨迹中发现 4 条源于指令笔误或歧义；τ²-bench 的变更日志记录了几十个任务修正（[agent_harness 04 §1](../agent_harness/04_失败诊断与受控重跑.md#1-五类原因以及区分它们的证据)）。修题后任务版本号要变，旧结果不与新结果混用。

## 5. 一条真实任务的完整路径：Terminal-Bench `pytorch-model-recovery`

代码已读，未运行；仓库 [laude-institute/terminal-bench](https://github.com/laude-institute/terminal-bench/tree/d28711d0da2675d0bb1d56de45ae5df6082438a3)，commit `d28711d`。任务目录 [`original-tasks/pytorch-model-recovery/`](https://github.com/laude-institute/terminal-bench/tree/d28711d0da2675d0bb1d56de45ae5df6082438a3/original-tasks/pytorch-model-recovery)。

| 阶段 | 文件 | 内容 |
|---|---|---|
| 元数据 | `task.yaml` | canary GUID；作者；`difficulty: medium`；`category: model-training`；`parser_name: pytest`；`max_agent_timeout_sec: 900`；`max_test_timeout_sec: 180`；专家预计 15 分钟、初级 70 分钟 |
| 指令 | `task.yaml` | 给定 `/app/weights.pt`（state dict）和 `/app/dataset.pt`：重建与 state dict 吻合的模型结构（`RecoveredModel`）；加载权重并计算 MSE；**只**调整 `output_layer` 的权重以降低 MSE，其他层冻结；以 TorchScript 保存到 `/app/model.pt`；不得修改 `weights.pt` |
| 环境 | `Dockerfile` | 固定基础镜像与 `torch==2.7.1`；只复制权重与数据；**测试与参考解不在镜像里** |
| oracle | `solution.sh` | 写出模型定义（位置编码 + 编码器 3 层 + 解码器 1 层 + 输出层，`nhead=4`），只对输出层用 Adam 训练 10 步，`torch.jit.script` 保存 |
| 测试 | `tests/test_outputs.py` | 5 个测试：`weights.pt` 未被修改（与测试目录里的副本逐键比较）；`model.pt` 存在；能加载原权重；除 `output_layer` 外各键与原权重一致；模型 loss **严格小于**原始 loss（没有幅度要求） |
| 运行测试 | `run-tests.sh` | 安装 uv、pytest、torch 后运行 pytest（测试阶段需要网络） |

**harness 怎样执行与判定**（`terminal_bench/harness/harness.py`）：

1. 加载任务并启动容器（`_run_trial`，L703 起）。
2. 运行 agent，带超时（`_run_agent_with_timeout`，L613–L631）。
3. **agent 结束后**才把 `run-tests.sh` 与 `tests/` 复制进容器的 `/tests`（`_setup_test_env` L544、`_run_tests` L557）；测试超时记为 `TEST_TIMEOUT`。
4. 解析 pytest 输出的 “short test summary info” 段（`parsers/pytest_parser.py` L82–L97）；找不到该段抛错，记为 `PARSE_ERROR`。
5. 全部测试通过才算 resolved（`_is_resolved` L536–L542）。

失败模式枚举（`agents/failure_mode.py`）：`AGENT_TIMEOUT`、`TEST_TIMEOUT`、`PARSE_ERROR`、`CONTEXT_LENGTH_EXCEEDED`、`OUTPUT_LENGTH_EXCEEDED`、`AGENT_INSTALLATION_FAILED`、`UNKNOWN_AGENT_ERROR` 等。一个值得注意的行为：agent 超时后测试仍然会运行（L752–L759），所以一次试验可以同时是“已解决”和“agent 超时”。

**对这个任务的审计笔记**（基于读代码的分析，没有执行验证）：

| 审计项 | 观察 |
|---|---|
| no-op | 会失败（没有 `model.pt`） |
| 多个合法解 | 接受：任何能降低 loss 的输出层调整方式都通过 |
| 可能的捷径 | 测试只检查 state dict 的键值与 `forward(src, tgt)` 的输出。一个参数正确、但 `forward` 直接返回 `tgt` 的 TorchScript 模块，loss 为 0，按读到的测试逻辑会通过全部 5 项。**前向计算没有被绑定到权重上** |
| 歧义 | `nhead` 等超参数无法从 state dict 的形状推出，指令也没有给。选了别的 `nhead` 的 agent 得到的是另一个函数，能否通过取决于偶然 |
| 可能误拒 | 测试阶段需要联网安装依赖；网络失败会表现为解析错误或测试超时，与 agent 的解无关 |
| 附带损害 | 只检查 `weights.pt` 与非输出层；`dataset.pt` 没有完整性检查 |

这些是待验证的假设。要确认“前向捷径”，需要在容器里实际构造那个模块并运行测试。

**从这条路径学到的设计**：测试在 agent 结束后才进入环境；参考权重副本放在测试目录而不是镜像里；失败模式用枚举区分；任务元数据里有人类用时估计。也看到三个风险：验证只看输出不看计算过程；隐含超参数；判定依赖测试时的网络。

## 6. Task schema

```json
{
  "task_id": "trainbug-shuffle-001", "version": "v1",
  "capability": "诊断并修复训练脚本中导致模型不学习的数据处理 bug",
  "family": "data_pipeline_bug", "difficulty": "easy", "split": "dev",
  "source": "handwritten (teaching example)",
  "instruction": "...",
  "fixture": {"files": ["task_fixture/train.py"], "entrypoint": "python3 train.py"},
  "tools": ["read_file", "write_file", "run_python"],
  "budget": {"max_model_calls": 20, "max_tool_calls": 30, "wall_clock_s": 300},
  "visible_check": "...",
  "hidden_verifier": {"version": "trainbug-verifier-0.1", "checks": ["..."], "seeds": [11, 12, 13],
                      "min_val_acc": 0.9, "max_val_loss": 0.3},
  "known_valid_solutions": ["..."], "known_invalid_shortcuts": ["..."]
}
```

与 [agent_harness Practice 00 §2.2](../../Practice/agent_harness/00_共用harness规格.md#22-核心对象) 的 Task 相比，多了 `capability`、`source`、`difficulty`、`known_valid_solutions`、`known_invalid_shortcuts`：前者支持能力结论，后两者是审计的输入。完整文件见 [`task.json`](../../Practice/task_dataset_design/sketch/task.json)。

## 7. 任务审计表（每个任务填一张）

| 项 | 问题 | 通过标准 |
|---|---|---|
| 可解 | oracle 解在 agent 的环境中通过 verifier 吗 | 通过 |
| no-op | 什么都不做通过吗 | 不通过（拒绝类任务另有输出检查） |
| 合法解 | 至少两个写法不同的合法解都通过吗 | 都通过 |
| 捷径 | 每条已知捷径都被拒绝吗 | 都被拒绝，且失败的检查项符合预期 |
| 指令充分 | verifier 的每个断言都能对回指令中的一句话吗 | 能 |
| 现象属实 | 指令里描述的症状是实际运行得到的吗 | 是，附运行记录 |
| 独立性 | verifier 是否使用了被测代码提供的数据、指标或打印值 | 没有 |
| 隔离 | agent 运行期间能读到测试或答案吗 | 不能 |
| 确定性 | 同一个解重复判定 5 次结果一致吗 | 一致；不一致时找出随机来源 |
| 资源 | oracle 解在预算的一半以内完成吗 | 是 |
| 版本与来源 | 任务、verifier、fixture 都有版本；来源与许可记录了吗 | 是 |

## 8. 局限

- 例子是一个教学用的单文件任务，bug 是手工注入的，难度低；它演示机制，不代表真实任务分布。
- verifier 在进程内导入候选代码，只适合教学。评估不可信代码需要 [Practice 00 §5.3](../../Practice/agent_harness/00_共用harness规格.md#53-代码任务与执行隔离可选进入-l4-前) 的执行边界。
- `constraint.shuffle_kept` 是行为代理：它检查“seed 影响结果”，一个保留了无意义随机性的错误实现也可能通过。更强的做法是记录每个 epoch 的样本顺序。
- 对 Terminal-Bench 任务的审计只基于读代码。

## 来源

| 来源 | 状态 | 支持的结论 | 重点读 |
|---|---|---|---|
| Terminal-Bench 仓库，commit `d28711d`：`original-tasks/pytorch-model-recovery/`、`terminal_bench/harness/harness.py`、`parsers/pytest_parser.py`、`agents/failure_mode.py` | 代码已读，未运行 | 一条任务从元数据到判定的路径；失败模式枚举 | `tests/test_outputs.py` 的 5 个测试；`harness.py` L536–L631、L703–L806 |
| Merrill et al., [Terminal-Bench, arXiv 2601.11868v1](https://arxiv.org/abs/2601.11868v1) | 直接读正文（§2–3、附录 B，上一轮） | 任务审计流程：oracle 通过、no-op 失败、对抗性作弊 agent | §3 |
| Zhu et al., [ABC, arXiv 2507.02825v5](https://arxiv.org/abs/2507.02825v5) | 原文核对（上一轮） | 任务效度与结果效度的定义与清单 | §2–3 |
| SWE-smith [arXiv 2504.21798](https://arxiv.org/abs/2504.21798)；OpenAI SWE-bench Verified 标注数据 | 二手摘要；CSV 已读（上一轮） | 合成 bug 的筛选规则；真实任务的过滤比例 | — |
| 本仓库 `Practice/task_dataset_design/sketch/` | 代码已运行 | 贯穿例子的全部数字与审计表 | — |

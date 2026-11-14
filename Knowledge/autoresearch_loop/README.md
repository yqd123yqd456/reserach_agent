# autoresearch_loop：实验循环的改进与验证

> 研究于 2026-11-14，服务于 Mirendil Model Evaluation take-home 的准备。这是可能的题型之一，不是已知考题；没有证据表明 take-home 会使用 karpathy/autoresearch。选它作为阅读对象，是因为它是一个公开、很小、机制清楚的“让 agent 做实验循环”的项目。
> 代码阅读对象：[karpathy/autoresearch](https://github.com/karpathy/autoresearch/tree/228791fb499afffb54b46200aca536f79142f117)，commit `228791f`（**代码已读，未运行**：它要求 CUDA GPU）。
> 相关：[training_eval_diagnostics](../training_eval_diagnostics/README.md)（BPB 的计算与含义）、[agent_harness 07](../agent_harness/07_从评估信号到post-training.md)（评估信号被利用的证据）、[agent_harness 08](../agent_harness/08_研究agent评估与L1L2L3.md)（研究 agent 的已记录失败）。
> 可运行草图：[Practice/autoresearch_loop](../../Practice/autoresearch_loop/README.md)。速查卡：[Review/autoresearch_loop](../../Review/autoresearch_loop/速查卡.md)。

## 学习结论

1. 这个项目里**没有任何编排代码**：没有调用 LLM 的程序、没有调度器、没有循环驱动。所谓“循环”是 `program.md` 里的一段自然语言指令，由一个通用的编码 agent 照着执行。读这类项目的第一步是分清**哪些行为由代码保证，哪些只由提示词约定**。
2. 评估条件有一部分被代码固定（验证数据、序列长度、评估 token 数在 `prepare.py` 里），有一部分只靠约定（“不要修改 `prepare.py`”），还有一部分在 agent 可改的文件里（时间预算的计数、评估时的 batch 大小、算 loss 的前向函数）。
3. 保留规则是“`val_bpb` 只要更低就保留”：单个验证 shard、单个种子、每个想法只跑一次、没有噪声阈值。在同一个验证集上连续做上百次选择，会积累选择偏差。
4. 失败处理几乎全在 agent 的判断里：代码只有一处“loss 为 NaN 或大于 100 就退出”的检查；超时、OOM、中断都没有处理，崩溃在结果表里记为 `0.000000`——数值上是“最好”的值。
5. 改进一个实验循环时，改动要落到具体的代码位置，并且**先定义怎样证明它有用**：反例（它应该拦住什么）、对照（没有它时会怎样）、验收。

## 1. 题型范围

| 典型输入 | 典型交付物 |
|---|---|
| 一个现成的实验／研究自动化仓库，以及一句开放的要求（“改进它”“让它更可靠”“评估它的结果可不可信”） | 对真实机制的简短说明；一个范围明确的改动（代码 + 测试）；证明改动有用的证据；没做的部分与理由 |

## 2. 定义：四种“改进”要分开

| 类型 | 含义 | 证据 |
|---|---|---|
| 代码修复 | 修掉一个 bug，行为回到预期 | bug 的复现与修复后的测试 |
| 效率改善 | 同样预算下做更多步或用更少资源 | 吞吐、显存、时间；指标可能随之改善，但原因是“多训练了” |
| 能力提升 | 同样的数据与计算量下模型更好 | 在**独立**评估上、超过噪声水平的改进 |
| 指标投机 | 指标变好，被测对象并没有变好 | 独立评估不改善；或改动触碰了评估条件 |

autoresearch 用固定的 5 分钟墙钟预算，所以“效率改善”与“能力提升”在 `val_bpb` 上混在一起：更快的实现在 5 分钟内训练更多步。README 也明确说，结果在不同硬件之间不可比（[README.md L64](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/README.md#L64)）。

## 3. 真实机制（逐项对照代码）

### 3.1 人、模型、脚本各做什么

| 角色 | 做什么 | 依据 |
|---|---|---|
| 人 | 编辑 `program.md`；运行一次 `uv sync` 与 `uv run prepare.py`；启动一个编码 agent 并约定本次的分支标签；想停的时候手动打断 | README.md L15、L31–L34；program.md L9、L17–L19 |
| agent | 修改 `train.py` → `git commit` → 运行 → 用 `grep` 读结果 → 记到 `results.tsv` → 变好就保留提交，否则 `git reset` | [program.md L94–L104](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L94-L104) |
| `prepare.py` | 下载数据、训练分词器；提供数据加载器与 `evaluate_bpb` | — |
| `train.py` | 做一次训练、一次评估，打印摘要 | — |

仓库的 Python 文件里没有 LLM 调用、没有子进程、没有调度或重试逻辑。README 把 `program.md` 称为一个“超轻量的 skill”，并建议启动 agent 时关闭所有权限确认（README.md L44、L50）。

### 3.2 哪些可改，哪些固定

`program.md` 的规则（[L26–L31](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md#L26-L31)）：只修改 `train.py`；`prepare.py` 只读；不安装新依赖；不修改评估，`evaluate_bpb` 是“ground truth metric”。**这些都是指令，没有文件权限、哈希校验或 CI 来强制**。

| 评估条件 | 在哪里 | 谁能改 |
|---|---|---|
| 验证数据：固定的最后一个 shard | `prepare.py` L43、L262–L263 | 约定不可改 |
| 序列长度 2048、评估 token 数 40×524288、时间预算 300 秒、词表 8192 | [`prepare.py` L30–L32、L45](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/prepare.py#L30-L45) | 约定不可改 |
| `evaluate_bpb` 的计算 | [`prepare.py` L343–L365](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/prepare.py#L343-L365) | 约定不可改 |
| 评估时的 batch 大小 | 由 `train.py` 传入（L613） | **agent 可改** |
| 评估时算 loss 的前向函数 `model(x, y, reduction='none')` | 定义在 `train.py` 的模型里 | **agent 可改** |
| 训练时间的计数与停止条件 | [`train.py` L578–L579、L603–L604](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/train.py#L578-L604) | **agent 可改** |
| 分词器与数据缓存 | `~/.cache/autoresearch`，不在 git 里，没有校验和 | 机器上任何进程 |

### 3.3 预算、输出与记录

- **预算**：每个优化步计时；前 10 步不计入（注释说明是为了不把编译时间算进去）；累计训练时间达到 300 秒后停止。启动、前 10 步与最终评估都不在预算内。学习率调度按“已用时间 ÷ 预算”推进（`train.py` L555）。
- **摘要块**（[`train.py` L621–L630](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/train.py#L621-L630)）：一行 `---` 之后依次打印 `val_bpb`、`training_seconds`、`total_seconds`、`peak_vram_mb`、`mfu_percent`、`total_tokens_M`、`num_steps`、`num_params_M`、`depth`。
- **读取**：agent 运行 `grep "^val_bpb:\|^peak_vram_mb:" run.log`。
- **结果表** `results.tsv`：五列——commit、val_bpb、memory_gb、status（keep／discard／crash）、description。它被 `.gitignore` 忽略，`program.md` 明确要求不要提交它。
- **保留与丢弃**：变好就保留提交；否则 `git reset` 回到起点。被丢弃的实验的代码改动只留在 reflog 里。
- **配置与代码版本的对应**：超参数直接写在 `train.py` 里，所以“配置”就是代码，commit 哈希同时标识两者。种子固定为 42（`train.py` L458–L459），但没有开启确定性算法，而且停止点取决于墙钟时间，所以同一 commit 在不同机器或不同负载下步数不同。

### 3.4 超时、OOM、NaN、中断

| 情况 | 代码做什么 | `program.md` 让 agent 做什么 |
|---|---|---|
| 运行超过 10 分钟 | 没有看门狗 | 杀掉，当作失败，丢弃并回退（L108） |
| loss 为 NaN 或大于 100 | 打印 `FAIL` 并 `exit(1)`（[`train.py` L569–L572](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/train.py#L569-L572)）；只检查训练 loss，不检查最终的 `val_bpb` | — |
| OOM | 没有处理（整个 `train.py` 没有 try／except） | “用你的判断”：小问题就修了重跑，想法本身不行就记 `crash` 并继续（L110） |
| 其他崩溃 | 没有处理 | `grep` 结果为空说明崩溃；`tail -n 50 run.log` 看堆栈；多次修不好就放弃（L101） |
| 被打断 | 没有信号处理，没有 checkpoint | — |
| 崩溃怎样记录 | — | `val_bpb` 记 `0.000000`，内存记 `0.0`，状态 `crash` |

自动重试只有一处：下载数据 shard 时最多 5 次（`prepare.py` L65–L87）。

### 3.5 可能的指标投机路径（基于读代码的分析，没有实际尝试）

| 路径 | 为什么可能 |
|---|---|
| 前向函数在评估时利用目标 `y` 或缩放 loss | `evaluate_bpb` 调用的是 `train.py` 里定义的 `model(x, y, reduction='none')`，loss 由被测代码自己计算 |
| 在验证 shard 上训练 | `train.py` 可以调用 `make_dataloader(..., "val")`，没有任何限制 |
| 把大量计算放进不计时的前 10 步 | 时间只从第 11 步开始累计 |
| 评估阶段做适应 | 评估时间不在预算内 |
| 改评估 batch 大小使评估的样本子集略有不同 | 评估步数是整除得到的 |
| 多次小改动中靠噪声“变好” | 任何改进都保留；没有重复运行 |

已经被保护的部分：序列长度与评估 token 数是 `evaluate_bpb` 内部使用的常量，不从 `train.py` 取；BPB 按字节归一化，换词表不改变评估数据。

这些路径在公开文献中有对应的真实案例：METR 记录过 agent 改写计时器、桩掉评估函数；RE-Bench 记录过噪声过拟合（见 [agent_harness 08 §4](../agent_harness/08_研究agent评估与L1L2L3.md#4-研究-agent-的已记录失败)）。

## 4. 三个改动方向

每个方向按：原问题 → 代码落点 → 接口变化 → 反例 → 对照 → 验收。草图 [`run_experiment.py`](../../Practice/autoresearch_loop/sketch/run_experiment.py) 实现了三者的最小版本，并在 CPU 上用一个**只模拟输出格式的替身脚本**运行过。

### A. 失败识别与恢复

| 项 | 内容 |
|---|---|
| 原问题 | 结局的判断完全靠 agent 读日志；崩溃记为 `0.000000`；超时靠 agent 自己掐表；OOM、NaN、普通 bug 在结果表里都叫 `crash`，无法统计也无法区别对待 |
| 代码落点 | 新增一个 runner，包住“运行一次实验”（`program.md` 循环的第 4–6 步）；可选地在 `train.py` L569–L572 把 `print("FAIL"); exit(1)` 换成带类型的状态，并在 L613 之后检查 `val_bpb` 是否有限 |
| 接口变化 | `run(cmd, timeout_s, log_path) → (returncode, timed_out, wall_seconds)`；`classify(log, returncode, timed_out, metrics) → (status, reason)`，状态取 `ok`、`timeout`、`oom`、`nan_loss`、`crash`、`interrupted`、`no_metric`、`invalid_metric` |
| 反例（应被正确识别） | 进程挂起；日志里有 out-of-memory；打印 `FAIL`；摘要块里 `val_bpb: nan`；正常退出但没有摘要块；被 Ctrl-C |
| 对照 | 原流程下，草图的 9 种结局中有 5 种（NaN、OOM、普通崩溃、被打断、超时）在结果表里是同一个 `crash`；`val_bpb: nan` 会被 `grep` 读成一个“结果” |
| 验收 | 每种结局一个测试；超时后没有残留进程（杀进程组）；失败的记录里**没有**指标值 |
| 恢复策略（只定义，不自动改代码） | `oom` → 提示降低 batch 或模型规模后重试一次；`timeout` → 不重试；`nan_loss` → 不重试，记录；`interrupted` → 不记为实验结果 |

草图的实际输出：

```text
ok           status=ok              decision=keep     bpb=0.987   | gain +0.0109 >= noise threshold 0.002
small_gain   status=ok              decision=discard  bpb=0.9968  | gain +0.0011 within noise threshold 0.002
vram_blowup  status=ok              decision=discard  bpb=0.985   | peak_vram_mb 79000.0 > cap 48000.0
nan_metric   status=invalid_metric  decision=crash    bpb=-       | invalid_metric
nan_loss     status=nan_loss        decision=crash    bpb=-       | nan_loss
oom          status=oom             decision=crash    bpb=-       | oom
crash        status=crash           decision=crash    bpb=-       | crash
interrupt    status=interrupted     decision=crash    bpb=-       | interrupted
hang         status=timeout         decision=crash    bpb=-       | timeout
tampered protected file -> ('invalid', "protected files changed: ['fake_train.py']")
```

### B. 实验记录与可复现性

| 项 | 内容 |
|---|---|
| 原问题 | 结果由 agent 手工抄进一个不受版本控制的 TSV；被丢弃实验的代码只在 reflog 里；记录里没有预算、步数、硬件、失败原因；`train.py` 自己报告自己的指标 |
| 代码落点 | runner 在每次运行后写一条 JSON 记录（追加到 `results.jsonl`）；指标由 runner 从日志的摘要块解析，不由 agent 转抄；`train.py` L615–L630 处所有字段都已在作用域内，也可以直接在那里输出 JSON |
| 接口变化 | 记录字段：`run_id`、`commit`、`parent_commit`、`description`、`cmd`、`status`、`status_reason`、`returncode`、`metrics`、`budget`、`wall_seconds`、`log_path`、`protected_hashes`、`decision`、`decision_reason` |
| 反例 | 失败的 run 不应带任何指标值；被丢弃的实验必须仍有记录与可取回的 commit（例如打一个 tag 或推到归档分支，而不是只留在 reflog） |
| 对照 | 用原流程与新流程各记录同一组运行，检查：能否从记录还原“哪个 commit、什么预算、什么结局、为什么保留或丢弃” |
| 验收 | 从一条记录出发能找到代码版本与日志；`analysis.ipynb` 式的分析改读 JSONL 后，崩溃不再以 0 出现在数值列里 |

### C. 独立评估与回归约束

| 项 | 内容 |
|---|---|
| 原问题 | 只有一个验证 shard、一次运行、一个种子；任何改进都保留；评估由被测代码自己执行；没有资源或完整性约束 |
| 代码落点 | 保留决定（`program.md` L103–L104）移到 runner 的 `decide()`；独立评估需要改 `prepare.py`（增加第二个保留 shard、固定评估 batch 大小）或新增一个评估进程：`train.py` 在 L613 之后保存 checkpoint，评估进程加载它、**自己从 logits 计算 loss**，而不是调用被测模型自带的 loss |
| 接口变化 | `decide(record, best_bpb, noise, vram_cap_mb, protected_hashes) → (decision, reason)`；决定取 `keep`、`discard`、`crash`、`invalid` |
| 规则 | 运行成功；受保护文件（`prepare.py`、缓存中的分词器与验证数据）哈希未变；显存不超过上限；改进幅度**不小于噪声阈值** |
| 噪声阈值从哪来 | 同一个 commit 重复运行若干次，取 `val_bpb` 的波动范围。草图里的 0.002 是**假设值**，没有任何实测依据 |
| 反例 | 改进小于噪声的应被丢弃；显存翻倍换来的改进应被拒绝；`prepare.py` 被改动的 run 应判为无效 |
| 对照 | 在同一串历史实验上，比较“任何改进都保留”与“超过噪声才保留”两种规则下最终保留的集合；再用第二个保留 shard 评估两个最终模型 |
| 验收 | 三条规则各有一个测试；在保留 shard 上，新规则选出的模型不差于旧规则选出的 |

### 推荐先练哪个

**先练 B（实验记录），顺带做 A 的分类**。理由：
- 它完全不需要 GPU：记录、解析、分类都是对文本与进程的处理，可以用替身脚本测试到位。
- 它是 A 与 C 的前提：没有结构化记录，就无法统计失败类型，也无法比较保留规则。
- 它与你已有的经验最接近（trace 标准化、数据契约），又能直接展示评估工程的习惯：指标不由被测对象自报、失败不以 0 充当、每条记录可追溯。
- C 的核心（噪声阈值、独立 shard）需要真实训练才能验证，没有 GPU 时只能停在设计。

## 5. CPU 教学替身：哪些机制不等价

草图的 [`fake_train.py`](../../Practice/autoresearch_loop/sketch/fake_train.py) 只打印与上游格式一致的输出，然后按指定方式退出。

| 机制 | 替身是否覆盖 | 说明 |
|---|---|---|
| 摘要块的格式与解析 | 是 | 字段名与顺序取自 `train.py` L621–L630 |
| 退出码、`FAIL`、超时、被打断 | 是 | 进程层面的行为 |
| OOM | 只覆盖日志文本 | 真实的 CUDA OOM 可能伴随不同的异常类型与残留进程 |
| 训练时间预算、前 10 步不计时 | 否 | 替身不训练 |
| `val_bpb` 的噪声水平 | 否 | 数值是编的 |
| 指标投机路径 | 否 | 需要真实的模型与评估 |
| torch.compile、混合精度、显存 | 否 | — |

所以草图验证的是 runner 的逻辑，不验证任何关于 autoresearch 训练行为的结论。

## 6. 局限

- 上游代码只读过，没有运行过；所有关于运行时行为的描述都来自代码与文档。
- §3.5 的投机路径是读代码得出的分析，没有尝试实现。
- 噪声阈值、显存上限的数值是占位的。
- 没有研究其他自动实验系统；本页的结论只针对这一个仓库在这个 commit 上的状态。

## 来源

| 来源 | 状态 | 支持的结论 | 重点读 |
|---|---|---|---|
| karpathy/autoresearch，commit `228791f`：`program.md`、`train.py`、`prepare.py`、`README.md`、`analysis.ipynb`、`.gitignore`、`pyproject.toml` | 代码已读，未运行 | §3 的全部机制 | `program.md` 全文（114 行）；`train.py` L543–L630；`prepare.py` L343–L365 |
| METR、RE-Bench 关于作弊与噪声过拟合的记录 | 见 [agent_harness 10](../agent_harness/10_来源阅读卡.md) | §3.5 的现实对应 | — |
| 本仓库 `Practice/autoresearch_loop/sketch/` | 代码已运行（CPU；替身脚本不做训练） | §4 的输出 | — |

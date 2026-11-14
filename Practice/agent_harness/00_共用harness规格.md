# 共用 Python Agent/Eval Harness：练习规格

> 状态：规格为**设计提案**。其中 L1 的核心合同（落盘文件、policy、verifier、三个样例）已用 [`sketch/minimal_run.py`](sketch/minimal_run.py) 实际运行验证，模型为脚本回放；真实模型路径（L2）与 L3 **未实现、未运行**。
> 用途：一个小项目同时支撑五个岗位的讨论；岗位分支实验见 [01_岗位分支实验.md](01_岗位分支实验.md)。
> 概念解释的主位置在 [Knowledge/01](../../Knowledge/agent_harness/01_三种harness与最小对象模型.md)、[Knowledge/02](../../Knowledge/agent_harness/02_工具使用测量与过程约束.md)、[Knowledge/03](../../Knowledge/agent_harness/03_故障注入与恢复.md)。

## 0. 设计目标与刻意不做的事

**要能回答的问题**：一次 run 怎样发生，在哪里判定成功，失败怎样定位，改动怎样被公平比较。

**刻意不做**：Web UI、分布式调度、Docker 编排、真实外部 API 写操作。理由：一小时到一天级练习的瓶颈是对象边界与判分正确性，而非部署。Level 3 的“执行隔离”只在代码任务分支引入（见 §5.3），并说明内存 fake 不是安全 sandbox。

**任务域的选择**：

| 阶段 | 环境 | 为什么 |
|---|---|---|
| L1–L2 | `orders`：订单 + 地址修改（你熟悉的客服例子） | 状态小、写操作有副作用、存在“不应执行”的负例，适合先把 verifier 写对 |
| L3 | `workspace`：文件 + 表格 + 报告文档 | 接近 Word/Cowork 的 artifact 型任务；最终产物可直接检查；路径更不唯一 |
| L4 分支 | `repo`（修 bug）、`lab`（跑小实验并报告） | 代码任务的测试即 verifier；研究任务需要验证“报告的数字是否真的跑出来” |

核心 harness 与环境无关，环境以插件形式实现同一接口。这样从客服过渡到文档／代码／研究时，改的是环境与 verifier，不是 runner。

## 1. 模块边界

```text
harness/
  schema.py        # Task, ToolSpec, Step, Trace, CheckResult, RunResult（纯数据，无逻辑）
  env/base.py      # Environment 接口：reset(task) / tools() / execute(call) / snapshot() / audit()
  env/orders.py    # L1 fake service
  env/workspace.py # L3
  policy.py        # 执行边界上的硬约束（在 execute 前拦截），返回 allow / block(reason)
  faults.py        # 故障注入：包装 execute，按 FaultSpec 触发
  model/scripted.py# 回放预设 assistant 消息：只验证接口与 verifier
  model/adapter.py # 真实模型：内部消息 <-> 供应商 API 格式（L2，未接凭据前保持未验证）
  runner.py        # 循环：调用模型、校验、policy、执行、按 id 回填、计数、终止（见 Knowledge/01a）
  recorder.py      # 落盘 runs/<run_id>/ 下的快照、audit、events、run.json
  verify/          # state / artifact / output / constraint 四类检查 + 组合规则
  report.py        # 聚合、配对比较、不确定度
  tasks/*.jsonl    # 任务定义（带 split 与 version）
  tests/           # verifier 的正例、反例、等价解回归
```

依赖方向：`schema ← env, policy, faults, verify ← runner ← report`。**verifier 不读 agent 的自述来判成功**，只读落盘的快照、artifact 和 audit log；agent 的最终回复只用于“输出检查”（是否正确告知用户、有无虚假完成声明）。

## 2. 数据合同（L1 起就固定）

### 2.1 一次 run 落盘什么

每个 run 一个目录。**verifier 只读这些文件**，不读内存中的对象，因此可以在任何时候重新判分。

```text
runs/<run_id>/
  task.json            # 任务定义的副本（含 task_id、version、success / constraints / expect）
  initial_state.json   # reset 后的完整状态快照
  final_state.json     # 终止时的完整状态快照
  audit.json           # 服务端写的操作日志（agent 不可写）：谁、对哪个对象、以什么身份做了什么
  events.json          # 每次模型调用与每次工具事件（含 call id、结果、错误码、该步之后的 state_hash）
  artifacts/           # 任务产生的文件（L3 的 report.md 等）
  run.json             # run_id、harness_version、agent 配置（模型、prompt hash、温度）、termination、valid、usage、最终回复、初始与最终 hash
  verdict.json         # verifier 输出：verifier_version、逐项检查与证据、success
```

**state_hash 的用途是校验与快速定位，不是存档**：hash 不能还原状态内容。重判需要完整快照；逐步定位时，用 events 中每步的 hash 找到“状态第一次变化”的步，再用 audit（或确定性回放，见 §2.4）得到那一步的具体变化。如果需要每步完整状态，可以额外保存每步的状态差异，但 L1 不必。

### 2.2 核心对象

```python
# schema 示意（字段已在 sketch/minimal_run.py 中实际使用）
Task = {
  "task_id": "T1", "version": "v2",              # 任务或 verifier 规则一改就升版本
  "expect": "do" | "refuse" | "clarify" | "escalate",
  "instruction": "...",                           # 用户的话
  "user_context": {"channel_email": "ana@example.com"},   # harness 注入的可信身份上下文（见 §3.2）
  "budget": {"max_model_calls": 6, "max_tool_calls": 5, "max_tool_errors": 4, "wall_clock_s": 120},
  "success": {"expected_values": [...], "allowed_changes": [...], "final_text_must_include": [...]},
  "constraints": [...], "faults": {...}, "split": "dev" | "test", "family": "address_change",
}
ToolResult = {"ok": bool, "data": {...}} | {"ok": False, "error": {"code": str, "message": str}}
CheckResult = {"kind": "state"|"constraint"|"output"|"termination", "name": str, "passed": bool, "evidence": str}
```

`valid`（这次 run 能不能算数）与 `success`（算数的话是否成功）分开；`constraint` 与 `state` 分开，以便单独统计违规率。

### 2.3 重判需要什么输入

`verify(task.json, initial_state.json, final_state.json, audit.json, run.json 中的最终回复与 termination, artifacts/) → verdict`，外加 verifier 自己的版本号。verifier 先检查 `final_state.json` 的 hash 与 `run.json` 中记录的一致，防止快照被改动。

### 2.4 三种“再来一次”，不要混用

| 操作 | 输入 | 会调用模型吗 | 会执行工具吗 | 用途 | 结果的地位 |
|---|---|---|---|---|---|
| **重判**（re-judge） | 落盘文件 + 新或旧 verifier | 否 | 否 | verifier 修复后重新打分；验证判分可复算 | 同一个 run 的新判定，必须记录 verifier 版本 |
| **确定性回放**（replay） | `initial_state.json` + events 中记录的工具调用 | 否 | 是，在新环境上按原顺序重放 | 重建中间状态；检查环境是否确定（τ²-bench 的 `set_state(..., strict)` 在回放输出与记录不一致时报错） | 同一个 run 的重建；若回放结果与记录不同，说明环境不确定或有外部依赖 |
| **重新运行**（re-run） | 任务 + agent 配置 | 是 | 是 | 采样新的行为；做重复试验或受控干预 | **新的 run**，新的 run_id；不是复现 |

## 3. Level 1：fake service + 一个 vertical slice + 基础 verifier

### 3.1 环境

`orders` 状态（与 `sketch/minimal_run.py` 的 `FIXTURE` 一致）：

```json
{
  "customers": {"c1": {"email": "ana@example.com", "last4": "1234"},
                "c2": {"email": "bo@example.com",  "last4": "5678"}},
  "orders": {"A1": {"customer": "c1", "status": "shipped",    "address": "1 Old St"},
             "A2": {"customer": "c1", "status": "processing", "address": "1 Old St"},
             "B1": {"customer": "c2", "status": "processing", "address": "7 Elm Rd"}},
  "session": {"verified_customer": null}
}
```

工具：`find_customer(email)`、`verify_identity(customer_id, last4)`、`get_order(order_id)`、`update_address(order_id, address)`（写），L1 末尾再加 `escalate(reason)`（写一条工单）。

### 3.2 身份验证的语义：可信上下文 vs 模型参数

- **可信**：服务端存储的 `customers[*].last4`；harness 注入的 `task.user_context`（模拟“用户已在渠道中登录为某个邮箱”）。这些不经过模型。
- **不可信**：模型传入的 `customer_id`、`last4`。它们来自模型对用户消息的理解，可能是错的，也可能是编造的。
- `verify_identity` 在服务端比对存储的 `last4`；成功时把 `session.verified_customer` 设为该客户，并写 audit。验证结果因此是**环境状态**的一部分，会进入快照，verifier 可以检查。
- 进一步的约束（L1 可选）：`verified_customer` 对应的邮箱必须等于 `user_context.channel_email`。没有这条时，一个知道别人 last4 的用户可以冒充他人。这是任务设计的选择，需要在任务中写明。

### 3.3 policy 与 verifier：写操作必须绑定到具体客户

**旧规则的问题**：“`update_address` 之前有一次成功的 `verify_identity`”。在多客户 fixture 中，ana 验证自己（c1）后修改 bo 的订单 B1，这条规则会接受。草图实际运行 F1（关闭 policy 构造该 trace）时，旧规则返回“接受”。

**修正后的 policy**（执行前）：`update_address(order_id)` 仅当 `session.verified_customer == orders[order_id].customer` 且 `status ∈ {pending, processing}` 时 allow，否则返回 `policy_blocked` 及规则名。

**修正后的 verifier**（事后，读 audit）：audit 中每条 `update_address` 记录的 `as_customer` 必须等于该订单在**初始快照**中的所有者；状态差异必须落在 `expected ∪ allowed` 中（附带损害）。

policy 与 verifier 都检查同一条规则，是**两道独立的防线**：policy 防止违规发生；verifier 在 policy 有 bug、被关闭或被绕过时仍能发现违规。verifier 的反例测试要在关闭 policy 的情况下构造违规 trace。

### 3.4 四种期望行为的成功标准

| `expect` | 何时 run 结束 | 状态检查 | 输出检查 | 什么都不做（no-op）会怎样 |
|---|---|---|---|---|
| do | agent 不再调用工具 | 期望值达成；差异 ⊆ expected ∪ allowed；写操作绑定正确 | 告知用户结果；无虚假完成声明 | 状态检查失败 |
| refuse | 同上 | 业务状态不变（允许 `session.verified_customer` 变化） | 说明无法办理及原因类别（例如“已发货”）；不声称已完成 | **状态检查会通过**，所以必须靠输出检查区分“正确拒绝”和“什么都没做／空回复” |
| clarify | **本练习中，agent 发出不含工具调用的提问即结束**（单回合设定） | 业务状态不变 | 回复是一个问题，并询问缺失的槽位（例如订单号） | 状态检查通过；空回复会在输出检查失败 |
| escalate | agent 不再调用工具 | 恰好新增一条工单，原因类别正确；其他状态不变 | 告知用户已转人工 | 状态检查失败 |

**clarify 的多回合版本**（L3 可选）：加一个脚本用户，在 agent 提问后回复预设的订单号，再继续 run；成功标准变为最终状态正确。这需要在 trace 中记录用户回合，类似 τ²-bench 在 agent、用户、环境之间轮转（见 [Knowledge/01a §7](../../Knowledge/agent_harness/01a_execution_harness一次run的完整过程.md#7-一个真实实现怎样影响我们的设计)）。单回合与多回合是不同的任务，结果不能混在一起比较。

### 3.5 一条成功样例与两条失败样例（已在草图中实际运行）

在 `Practice/agent_harness/sketch/` 下执行 `python3 minimal_run.py <输出目录>`，2026-11-14 本地运行的输出（模型为脚本回放，不代表真实模型）：

```text
== S1: termination=final success=True usage={'model_calls': 4, 'tool_calls': 3}
   [PASS] state       orders/A2/address == '9 New Ave'  (actual='9 New Ave')
   [PASS] state       no collateral change  (unexpected=[])
   [PASS] constraint  write A2 bound to owner c1  (as_customer=c1)
   [PASS] output      no false completion claim  (goal_met=True, claims_done=True)
   [PASS] output      final text mentions '9 New Ave'
   [PASS] termination ended by agent  (final)
== F1-policy-on: termination=final success=False usage={'model_calls': 3, 'tool_calls': 1}
   [FAIL] state       orders/A2/address == '9 New Ave'  (actual='1 Old St')
   [PASS] state       no collateral change  (unexpected=[])
   [FAIL] output      no false completion claim  (goal_met=False, claims_done=True)
== F1-policy-off: termination=final success=False usage={'model_calls': 3, 'tool_calls': 2}
   [FAIL] state       no collateral change  (unexpected=[('orders', 'B1', 'address')])
   [FAIL] constraint  write B1 bound to owner c2  (as_customer=c1)
   old 'verified-before-write' rule would accept: True
== F2: termination=budget_tool_calls success=False usage={'model_calls': 6, 'tool_calls': 5}
   [FAIL] state       orders/A2/address == '9 New Ave'  (actual='1 Old St')
   [FAIL] termination ended by agent  (budget_tool_calls)
rejudge S1 identical: True
```

（输出有删节，完整输出包含每个 run 的全部检查项。）

| 样例 | 经过哪些接口 | 结果怎样解释 |
|---|---|---|
| S1 | find → verify(c1) → policy allow → update(A2) → 最终回复 → verifier 读快照与 audit | 每项检查都有证据字段；重判结果与第一次相同 |
| F1 | verify(c1) → update(B1)：policy 开启时被 `policy_blocked`，agent 仍回复 “Done” | 状态未达成 + 虚假完成声明。关闭 policy 构造同一 trace：B1 被改，附带损害与“写操作绑定所有者”两项失败，而旧规则会接受 |
| F2 | verify(c1) → update(A2) 持续返回 503（注入的永久故障）→ agent 反复重试 → 第 6 次模型调用时工具预算耗尽 | 有效 run、判失败；终止原因是预算，不是 harness 错误；没有虚假完成声明 |

### 3.6 L1 验收（进入 L2 前应通过）

1. **verifier 正例**：两条不同的合法路径（先查订单再改／直接改）都判成功。
2. **verifier 反例**（在关闭 policy 时构造）：改错订单、改了别人的订单、改对但附带改了别的字段、未改却声称完成——各自命中预期的检查。
3. **refuse／clarify 任务**：正确拒绝或提问判成功；**空回复与 no-op 判失败**（靠输出检查）。
4. **reset**：同一任务连续 run 两次，初始快照 hash 相同。
5. **重判**：只读落盘文件重新运行 verifier，结果与第一次相同。

**预计投入**：最短 4h／标准 8h／深入 12h（假设：熟练 Python，可用 AI 生成样板）。

**常见失败**：verifier 读最终回复判成功；fixture 被原地修改导致 reset 失效；只测正例；state hash 对 key 顺序敏感（用 `sort_keys`）；policy 只检查“是否验证过”而不检查“验证的是谁”。

## 4. Level 2：接真实模型的动态 tool loop

### 4.1 runner 循环

完整的伪代码、消息格式、状态转换和终止表见 [Knowledge/01a](../../Knowledge/agent_harness/01a_execution_harness一次run的完整过程.md)。L2 要做的是把 `ScriptedModel.generate` 换成真实模型的 adapter：把内部消息转换成所用 API 的格式，把响应中的 tool call 解析回内部格式（id、name、arguments），解析失败时作为 `invalid_arguments` 结果回填。

### 4.2 三种 agent，三种证据

| agent | 证明什么 | 不能证明什么 |
|---|---|---|
| scripted（回放固定序列） | runner、policy、verifier 的接口与判分正确 | 任何模型行为 |
| 真实模型 + fake service | 在该任务分布、该工具描述、该预算下的决策行为 | 对真实服务（延迟、脏数据、权限）的表现 |
| 真实模型 + 真实服务 | 更高保真 | 引入时效、副作用与不可复现；练习中不做 |

没有 API 凭据时，L2 的真实模型路径保持“未验证”，不用 scripted 结果替代。

### 4.3 L2 验收

- 同一任务用真实模型跑 k 次（例如 k=5），trace 完整，终止原因分布可报告。
- 至少找到一次真实失败并按 [Knowledge/04](../../Knowledge/agent_harness/04_失败诊断与受控重跑.md) 的流程写出诊断。
- 记录每个 run 的 token 与工具调用数，作为成本基线。

**预计投入**：最短 3h／标准 6h／深入 10h。**成本**：k=5、3 个任务、每个 run 约 10 次模型调用，量级是几百次模型调用；运行前先估算费用，不默认消耗付费 API。

**常见失败**：工具描述与实际行为不一致（agent 被误导，被归因成模型能力差）；把参数校验失败当 harness 崩溃而中断 run；温度、prompt 版本未记录导致不可比较；供应商 API 错误被计为 agent 失败。

## 5. Level 3：多类任务、故障注入、诊断与比较报告

### 5.1 扩展

- 加入 `workspace` 环境：文件（文本）、表格（行列）、`write_report(path, content)`。任务示例：“根据 sales.csv 计算 Q3 各区域总额，更新 summary 表，并写一段说明到 report.md”。verifier 检查：表格数值（容差内）、report 中提到的数字与表格一致、未修改 sales.csv（附带损害）。
- 每个环境 6–10 个任务，覆盖 do／refuse／clarify／escalate，按 `family` 分层，`dev`/`test` 分开。
- 故障注入：按 [Knowledge/03](../../Knowledge/agent_harness/03_故障注入与恢复.md) 定义 `FaultSpec`（transient、invalid-arg、stale-read、permanent），每个 faulted task 有一个配对的 clean control。

### 5.2 比较报告（report.py 输出的最小内容）

```text
config A vs B, task set test@v3, k=5 per task, N_tasks=16
valid runs: A 80/80, B 78/80 (2 model_api_error after retries, listed; rerun → 80/80)
success (task-level mean of per-task pass rates): A 0.61, B 0.70
paired diff (B−A): +0.09, 95% CI via task-level paired bootstrap [−0.02, +0.20]  (16 tasks, 16 clusters)
violations: A 3 runs, B 7 runs  (←若 B 更快但违规更多，需单独讨论)
pass^5 (all 5 runs succeed): A 6/16, B 8/16
cost: median tool_calls A 7, B 9
```

上面的数字是**格式示意，不是结果**。统计单位是任务；同一任务的重复 run 先在任务内平均，再在任务间做配对比较（见 [Knowledge/06](../../Knowledge/agent_harness/06_公平比较与统计.md)）。

### 5.3 代码任务与执行隔离（可选，进入 L4 前）

`repo` 环境要执行 agent 写的代码，这是**不可信代码**。各项措施能保证的东西不同：

| 措施 | 能保证 | 不能保证 |
|---|---|---|
| 每个 run 独立临时目录 | 不同 run 的文件不互相污染；便于清理 | 进程仍可读写目录之外的文件、访问环境变量与凭据、联网、启动后台进程 |
| 超时 | 限制墙钟时间 | 不限制内存、磁盘、进程数；超时后子进程可能仍在运行（需要杀掉整个进程组） |
| 禁止网络 | 阻止外传数据和下载 | 不阻止本地破坏或读取本机敏感文件 |
| 非 root 用户 + 只读挂载 | 限制可修改的文件范围 | 不限制资源消耗；内核漏洞仍可利用 |
| 资源限制（cgroups：CPU、内存、进程数、磁盘配额） | 防止资源耗尽影响宿主或其他 run | 不提供文件系统与网络隔离 |
| 容器（独立的文件系统、进程、网络命名空间） | 以上各项的组合，是常用的基线 | 与宿主共享内核；对高风险代码通常再加 gVisor 等用户态内核或微型虚拟机 |

**最小可接受的边界**（练习级）：容器内运行、非 root、无网络、只挂载本 run 的工作目录、CPU／内存／进程数上限、墙钟超时并杀进程组、容器内不放任何凭据。内存 fake 只隔离“状态”，不隔离“执行”；独立临时目录本身不是安全隔离。

**L3 验收**：一份比较报告，包含有效／无效 run 数、配对差及区间、违规率、成本；一条完整故障诊断；verifier 回归测试全部通过。

**预计投入**：最短 8h／标准 16h／深入 24h。

## 6. 你负责什么、AI 可以帮什么、review 怎么查错

原则：**判分与安全相关的逻辑，你要负责设计、能逐行解释、并用反例验证**；代码由谁敲出来不是重点。实际题目若对 AI 使用有规定，以题目规则为准。

| 组件 | 你负责设计与验证 | 可交给 AI 起草 | review 时最该查 |
|---|---|---|---|
| schema | 字段取舍 | dataclass 样板、序列化 | `valid` / `success` / `constraint` 是否分开 |
| env + fixture | 状态模型、reset 语义 | 工具函数样板 | reset 是否深拷贝；hash 是否稳定 |
| policy | 规则本身（谁能对什么做什么） | 实现代码 | 是否在执行**前**拦截；是否绑定到具体客户与对象；错误码是否回传给 agent |
| faults | 故障语义与触发规则 | 包装器样板 | 故障是否真的触发（记录在 Step），clean control 是否配对 |
| runner | 终止逻辑 | 循环样板、日志 | 参数校验失败是否被当成崩溃 |
| verifier | 检查项与通过标准 | 实现代码、反例 trace 的构造 | 是否读了 agent 自述；附带损害是否覆盖；等价解是否被误拒；关闭 policy 时能否发现违规 |
| report | 统计单位与配对 | 表格与绘图 | 无效 run 是否单列且有补跑；重复 run 是否被当独立样本 |
| trace viewer | — | 全部（静态 HTML 即可） | 能否直接看到 policy block、fault、state 变化 |

确认 AI 起草的代码是否正确，靠反例测试与重判，而不是只读代码。

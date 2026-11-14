# Execution harness：一次 agent run 从头到尾发生了什么

> 学习结论：
> 1. execution harness 是一个**循环**：把消息历史和工具定义交给模型 → 模型返回文本或若干 tool call → harness 逐个校验、做 policy 检查、执行、把结果按 **tool call ID** 回填到历史 → 再调用模型；直到模型不再调用工具、或某个预算／错误条件触发终止。
> 2. 模型只“提议”调用；**校验、policy、执行、计数、终止判定都在 harness 里**，模型无法绕过。判分不在这个循环里，由独立的 verifier 在 run 结束后读落盘记录完成。
> 3. 内部消息格式应与供应商 API 格式分开：内部用一种中立格式记录 trace，调用模型时由 adapter 转换。
>
> 前后文：[01 三种 harness 与对象模型](01_三种harness与最小对象模型.md) → 本页 → [Practice 00 数据合同](../../Practice/agent_harness/00_共用harness规格.md)。可运行草图：[`Practice/agent_harness/sketch/minimal_run.py`](../../Practice/agent_harness/sketch/minimal_run.py)（只用标准库，模型由脚本回放代替）。

## 1. 定义：谁负责什么

| 模块 | 负责 | 不负责 |
|---|---|---|
| model adapter | 把内部消息转换成供应商请求，调用 API，把响应解析回内部格式（文本 + tool call 列表 + usage + stop reason） | 执行工具；决定是否终止 |
| runner（循环） | 维护 history；计数与预算；终止判定；调度工具调用 | 判断任务是否成功 |
| argument validator | 按工具的参数 schema 检查名称、必填、类型、多余字段 | 业务规则 |
| policy | 执行**前**检查业务约束（身份、状态、权限） | 事后判分 |
| environment / tools | 执行工具，修改状态，写服务端 audit log | 知道自己正在被评估 |
| trace recorder | 把每个模型调用和工具事件写入 events，run 结束时写快照 | 解释事件 |
| verifier（循环外） | 读落盘的任务、初始／最终快照、audit、最终回复，逐项判定 | 调用被测模型；修改状态 |

## 2. 内部消息格式（供应商无关）

```json
{"role": "user", "content": "I'm ana@example.com, last4 1234. Change order A2 address to 9 New Ave."}
{"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "name": "find_customer", "arguments": {"email": "ana@example.com"}}]}
{"role": "tool", "tool_call_id": "call_1", "name": "find_customer", "ok": true, "data": {"customer_id": "c1"}}
```

**规则**（通用机制）：
- assistant 消息里的每个 tool call 都有唯一 `id`；**每个 id 必须恰好得到一条 tool 结果**，即使这个调用被拒绝、校验失败或因预算未执行。缺失的结果会让下一次模型调用失去对应关系（多数供应商 API 也会直接拒绝这样的请求）。
- 错误也是结果：`{"ok": false, "error": {"code": "policy_blocked", "message": "..."}}`。把错误回填给模型，让它有机会恢复，而不是让 runner 崩溃。

**供应商协议差异**（由 adapter 处理，不要写进内部格式）：
- 有的 API 用独立的 `role: "tool"` 消息，以 `tool_call_id` 关联调用。
- 有的 API 把调用放在 assistant 消息的内容块里（如 `tool_use` 块带 `id`），把结果放在下一条 user 消息的内容块里（如 `tool_result` 块带对应的 id）。
- 参数可能以 JSON 字符串或已解析的对象返回；解析失败需要在 adapter 中转换成“参数解析错误”。
- 是否允许一条消息里有多个调用、是否默认并行，也因供应商与设置而异。

具体格式以所用 API 的官方文档为准；本页只依赖“调用有 id、结果按 id 回填”这一共同点。

## 3. Worked example：三次工具调用的成功 run

下列事件来自本仓库草图的实际运行（`minimal_run.py` 的样例 S1，2026-11-14 本地执行；模型是脚本回放，不代表真实模型行为）。fixture：客户 c1（ana，last4 1234）拥有 A1（已发货）、A2（处理中）；客户 c2（bo，last4 5678）拥有 B1（处理中）。

| 轮 | 谁 | 事件 | history 增加 | 状态变化 |
|---|---|---|---|---|
| 0 | runner | `env.reset(task)`：深拷贝 fixture，写 `initial_state.json` | `[user]` | `session.verified_customer = null` |
| 1 | model adapter | 模型返回 `tool_calls=[call_1: find_customer(email="ana@example.com")]` | `+assistant` | — |
| 1 | validator → policy → env | 参数合法；读操作不经 policy；执行返回 `{"customer_id":"c1"}` | `+tool(call_1)` | 无 |
| 2 | model | `call_2: verify_identity(customer_id="c1", last4="1234")` | `+assistant` | — |
| 2 | env | 服务端用**存储的** last4 比对，成功后写 `session.verified_customer="c1"`，audit 记 `verify c1` | `+tool(call_2)` | `verified_customer: c1` |
| 3 | model | `call_3: update_address(order_id="A2", address="9 New Ave")` | `+assistant` | — |
| 3 | policy | 检查 `verified_customer == orders.A2.customer` 且 A2 可修改 → allow | — | — |
| 3 | env | 写地址；audit 记 `{op: update_address, order: A2, as_customer: c1}` | `+tool(call_3)` | `A2.address = 9 New Ave` |
| 4 | model | 无 tool call，文本 “Done: order A2 will ship to 9 New Ave.” | `+assistant` | — |
| 4 | runner | 无调用 → `termination = "final"`；写 `final_state.json`、`audit.json`、`events.json`、`run.json` | — | — |
| 后 | verifier | 读落盘文件判定：A2 地址正确、无附带损害、写操作绑定到订单所有者、无虚假完成声明、由 agent 主动结束 → success | — | — |

history 在第 4 次模型调用时是 `user, assistant(call_1), tool(call_1), assistant(call_2), tool(call_2), assistant(call_3), tool(call_3)`，共 7 条。**每轮模型看到的是完整 history**，所以上下文随步数线性增长（见 §6）。

## 4. 状态转换与终止

```text
            ┌──────────────── budget / error limits ─────────────────┐
            ▼                                                        │
 [START] → CALL_MODEL ──(no tool calls)──────────────► END(final)    │
              │  └─(adapter error / context overflow)─► END(model_error | context_exceeded)
              │ (tool calls)                                         │
              ▼                                                      │
         FOR EACH CALL: validate → policy → execute → append result ─┘
              │ (all calls answered)
              └──────────────► CALL_MODEL
```

| 终止原因 | 触发 | `valid` | 计入成功率分母 | 例子 |
|---|---|---|---|---|
| `final` | 模型返回无 tool call 的消息 | 是 | 是 | S1 |
| `budget_model_calls` / `budget_tool_calls` / `budget_tokens` / `wall_clock` | 预算用尽 | 是 | 是，判失败 | F2：写接口持续 503，第 6 次模型调用时工具预算（5）耗尽 |
| `too_many_tool_errors` | 连续或累计工具错误超限（τ²-bench 的 `max_errors`） | 是 | 是，判失败 | 反复传错参数 |
| `context_exceeded` | 输入超出上下文窗口且无法压缩 | 是（属于 agent 行为后果） | 是 | 读了过大的文件 |
| `model_api_error` | 供应商 API 错误（429、5xx、断连）且重试后仍失败 | 否 | 否，单列并补跑 | — |
| `harness_error` | runner 自身异常 | 否 | 否，单列并修复后补跑 | — |

“无效”只留给**与被测 agent 行为无关**的原因。预算耗尽、工具错误过多、上下文溢出都是 agent 行为的后果，计为有效失败。详见 [06 §3.1](06_公平比较与统计.md#31-无效-run-的判定不能用来排除失败)。

## 5. 伪代码（足够照着写）

```python
def run(task, model, env, budget, policy, recorder):
    env.reset(task.fixture); recorder.snapshot("initial", env.state)
    history = [user_msg(task.instruction)]
    n_model = n_tool = n_err = 0
    while True:
        if n_model >= budget.max_model_calls: return end("budget_model_calls")
        try:
            resp = model.generate(history, tools=task.tool_specs, timeout=budget.model_timeout_s)
        except ProviderError as e:                      # 已在 adapter 内按退避重试过
            return end("model_api_error", valid=False)
        n_model += 1; recorder.model_event(resp)
        history.append(resp.message)
        if resp.stop_reason == "context_length": return end("context_exceeded")
        if not resp.tool_calls: return end("final")
        for call in resp.tool_calls:                    # 默认串行，保持模型给出的顺序
            if n_tool >= budget.max_tool_calls:
                result = error("budget_exhausted")      # 仍然回填，保证 id 一一对应
            elif (err := validate(call, task.tool_specs)): result = error("invalid_arguments", err)
            elif (rule := policy.check(call, env.state)): result = error("policy_blocked", rule)
            else:
                result = env.execute(call, timeout=budget.tool_timeout_s); n_tool += 1
            n_err += not result.ok
            history.append(tool_msg(call.id, result)); recorder.tool_event(call, result, env.state_hash())
        if n_tool >= budget.max_tool_calls: return end("budget_tool_calls")
        if n_err >= budget.max_tool_errors: return end("too_many_tool_errors")
    # end(): recorder.snapshot("final", env.state); 写 audit、events、run.json；不在这里判分
```

## 6. 多调用、上下文、超时、重试、取消、预算：最小设计与取舍

| 问题 | 最小设计 | 取舍 |
|---|---|---|
| 一条消息多个 tool call | 默认**串行**、按给出顺序执行；只读且声明为可并行的工具才并发 | 并行快，但两个写操作并发会让结果依赖调度顺序，难以复现 |
| 上下文增长 | 每轮发送完整 history；工具输出设上限并截断（标注“已截断”）；超出窗口时终止为 `context_exceeded` | 压缩或摘要能延长 run，但会改变被测对象。比较实验中压缩策略必须固定并记录 |
| 超时 | 模型调用和工具调用分别设超时；工具超时返回 `error(timeout)` 给模型；另设整个 run 的墙钟上限 | 超时太紧会把基础设施慢判成 agent 失败 |
| 重试 | **模型 API**：在 adapter 内对 429/5xx 做有限次退避重试，不计入 agent 预算，但记录次数。**工具**：harness 默认不自动重试，让 agent 决定；若要自动重试，只对幂等的读操作，并单独记录 | 自动重试写操作可能造成双写（[03](03_故障注入与恢复.md)）。harness 重试与 agent 重试必须在 trace 中区分 |
| 取消 | run 级取消（用户中止或墙钟超时）：停止发起新调用，尚未完成的调用记为 `cancelled`，仍按 id 回填，再写快照 | 取消时正在进行的写操作是否生效，取决于工具实现，必须在快照中如实反映 |
| 预算 enforcement | 计数在 runner 里，执行前检查；超出后剩余调用返回 `budget_exhausted` | 预算是任务定义的一部分。改预算就是换了一个实验条件 |

## 7. 一个真实实现：怎样影响我们的设计

**Inspect AI**（UK AISI，commit [`e4435ba`](https://github.com/UKGovernmentBEIS/inspect_ai/tree/e4435baa530d05324358bedc3782609c952f9876)；代码已读，未运行）：

| 机制 | 位置 | 读到的行为 | 对我们设计的影响 |
|---|---|---|---|
| 主循环 | [`src/inspect_ai/agent/_react.py`](https://github.com/UKGovernmentBEIS/inspect_ai/blob/e4435baa530d05324358bedc3782609c952f9876/src/inspect_ai/agent/_react.py#L214-L330)（`react()` 内的 `execute`） | `while True`：生成 → 若 `stop_reason == "model_length"` 进入溢出处理 → 若有 `tool_calls` 调用 `execute_tools` 并把返回的消息追加到 `state.messages` → 检查是否提交答案 | 与 §5 的循环同构；溢出是显式分支 |
| 工具执行 | [`src/inspect_ai/model/_call_tools.py`](https://github.com/UKGovernmentBEIS/inspect_ai/blob/e4435baa530d05324358bedc3782609c952f9876/src/inspect_ai/model/_call_tools.py#L193-L234) `execute_tools` | 执行最后一条 assistant 消息中的调用，返回新增消息；工具输出默认上限 16 KiB（`max_tool_output`） | 工具输出截断是 harness 的职责 |
| 并行分组 | [同文件 L397–L425](https://github.com/UKGovernmentBEIS/inspect_ai/blob/e4435baa530d05324358bedc3782609c952f9876/src/inspect_ai/model/_call_tools.py#L397-L425) | 按工具定义的 `parallel` 标志分阶段：连续的可并行调用合为一个并发阶段；串行调用各自成为屏障；未知工具默认串行 | 采用“默认串行、显式声明可并行” |
| 参数校验 | [同文件 L1603](https://github.com/UKGovernmentBEIS/inspect_ai/blob/e4435baa530d05324358bedc3782609c952f9876/src/inspect_ai/model/_call_tools.py#L1603) `validated_tool_call` | 按工具 schema 校验，失败抛 `ToolParsingError` | 校验在执行前、与业务 policy 分开 |
| 调用与结果的 id | [`tool/_tool_call.py` L43](https://github.com/UKGovernmentBEIS/inspect_ai/blob/e4435baa530d05324358bedc3782609c952f9876/src/inspect_ai/tool/_tool_call.py#L43)（`ToolCall.id`、`parse_error`）；[`model/_chat_message.py` L206](https://github.com/UKGovernmentBEIS/inspect_ai/blob/e4435baa530d05324358bedc3782609c952f9876/src/inspect_ai/model/_chat_message.py#L206)（`ChatMessageTool.tool_call_id`、`error`） | 结果消息带 `tool_call_id` 和结构化 `error` | 内部格式照此设计 |
| 错误分类 | [`tool/_tool_call.py` L72](https://github.com/UKGovernmentBEIS/inspect_ai/blob/e4435baa530d05324358bedc3782609c952f9876/src/inspect_ai/tool/_tool_call.py#L72) `ToolCallError.type` | `parsing`、`timeout`、`permission`、`limit`、`approval`、`cancelled`、`sandbox_unavailable` 等 | 错误码是有限枚举，便于统计与诊断 |

**τ²-bench**（Sierra，commit [`c06b07d`](https://github.com/sierra-research/tau2-bench/tree/c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4)；代码已读，未运行）：

| 机制 | 位置 | 读到的行为 | 影响 |
|---|---|---|---|
| 轮转调度 | [`src/tau2/orchestrator/orchestrator.py` L840](https://github.com/sierra-research/tau2-bench/blob/c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4/src/tau2/orchestrator/orchestrator.py#L840) `Orchestrator.step` | 在 agent、user（模拟用户）、env 三个角色之间传递消息：agent 消息含 tool call 时发给 env，否则发给 user | 有用户模拟器时，“澄清”可以继续对话；没有时应在澄清处结束 |
| 工具执行 | [同文件 L327](https://github.com/sierra-research/tau2-bench/blob/c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4/src/tau2/orchestrator/orchestrator.py#L327) `_execute_tool_calls` | 按顺序逐个执行；结果 `error` 为真时 `num_errors += 1` | 串行执行，错误计数 |
| 异常变结果 | [`src/tau2/environment/environment.py` L473](https://github.com/sierra-research/tau2-bench/blob/c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4/src/tau2/environment/environment.py#L473) `get_response` | 捕获工具异常，返回 `ToolMessage(id=调用 id, content="Error: ...", error=True)` | 工具错误回填给模型，而不是中断 run |
| 终止判定 | [同文件 L755](https://github.com/sierra-research/tau2-bench/blob/c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4/src/tau2/orchestrator/orchestrator.py#L755) `_check_termination` | `step_count >= max_steps`（默认 100）→ `MAX_STEPS`；`num_errors >= max_errors`（默认 10）→ `TOO_MANY_ERRORS` | §4 的终止表 |
| 终止原因枚举 | [`src/tau2/data_model/simulation.py` L1070](https://github.com/sierra-research/tau2-bench/blob/c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4/src/tau2/data_model/simulation.py#L1070) `TerminationReason` | `USER_STOP`、`AGENT_STOP`、`MAX_STEPS`、`TIMEOUT`、`TOO_MANY_ERRORS`、`AGENT_ERROR`、`USER_ERROR`、`INFRASTRUCTURE_ERROR`、`CONTEXT_WINDOW_EXCEEDED` 等 | 把基础设施错误与 agent 错误分开枚举 |
| 多调用中的终止工具 | `step` 内（同文件 L840 起） | 若终止类工具与其他调用捆绑在同一条消息里，所有调用都被拒绝，并为每个调用生成一条带对应 id 的拒绝结果 | 拒绝也要按 id 回填 |

## 8. 边界

- 草图里的模型是脚本回放，只验证接口、policy 与判分；**真实模型的行为没有被验证**。
- 上面的模块划分是一种清晰的做法，不是唯一做法。例如 Inspect 把审批（approval）作为执行前的可插拔环节，与 policy 的作用类似。
- 两个框架的行号对应上述 commit；之后的版本可能变化。

## 9. 面试追问

- “模型说调用 update_address，你的 harness 依次做什么？” → 校验 → policy → 执行 → 写 audit → 按 id 回填 → 计数 → 判断终止。
- “一条消息里有两个写操作怎么办？” → 默认串行、按顺序；每个都过 policy；任何一个被拒绝也要回填结果。
- “模型 API 返回 429 算 agent 失败吗？” → 不算；adapter 内重试，仍失败则记为无效 run 并补跑，同时报告无效数。
- “工具超时算什么？” → 作为错误结果回填给模型，属于 agent 的有效 run；若超时由基础设施异常造成（例如整个服务宕机），按预先定义的规则归类，并报告两种口径。

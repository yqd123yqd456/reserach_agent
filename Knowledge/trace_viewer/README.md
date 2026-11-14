# trace_viewer：从日志到可调查的界面

> 研究于 2026-11-14，服务于 Mirendil Model Evaluation take-home 的准备。这是可能的题型之一，不是已知考题。
> 前置：[agent_harness 01a](../agent_harness/01a_execution_harness一次run的完整过程.md)（消息、tool call id、events 是怎样产生的）与 [Practice 00 §2.1](../../Practice/agent_harness/00_共用harness规格.md#21-一次-run-落盘什么)（run 目录里有什么）。本页只讲**怎样把这些记录变成能帮人定位失败的界面**。
> 可运行草图：[Practice/trace_viewer](../../Practice/trace_viewer/README.md)。速查卡：[Review/trace_viewer](../../Review/trace_viewer/速查卡.md)。

## 学习结论

1. viewer 的大部分工作在**数据层**，不在界面层：把陌生日志标准化成“run 列表摘要 + 每个 run 的步骤序列”，调用与返回按 id 配对，配不上的记录保留并打标。这一层可以完全用 Python 写、用断言测试。
2. 界面只需要一个状态对象（筛选、搜索词、选中的 run、选中的步骤、对比对象）和一个 `render()`：**任何交互都是“改状态 → 从状态与数据重新生成页面”**。
3. 列表用**摘要**，详情**按需加载**。Inspect 的日志格式把样本摘要与完整样本分开存，就是为了这一点。
4. 评分证据、状态变化与轨迹放在同一屏：研究员要回答的是“哪一步导致了哪个检查失败”，而不是“发生了什么”。
5. 先做读离线文件的静态页面。实时查看需要增量读取、处理“进行中”的事件；Inspect 用的是轮询，不是推送。

## 1. 题型范围

| 典型输入 | 典型交付物 |
|---|---|
| 一批 run 的日志文件（JSON 或 JSONL，格式可能不熟、可能不完整）+ 评分结果 | 一个能打开的小工具（静态页面或简单本地服务）；数据标准化脚本；README：支持哪些调查动作、已知不支持什么 |

用户 journey（验收也按它写）：筛选失败运行 → 打开轨迹 → 找异常工具调用 → 查看状态和评分证据 → 对比另一条运行。

## 2. 定义：日志里的对象怎样关联

| 对象 | 是什么 | 关联方式 |
|---|---|---|
| message | 对话中的一条（user、assistant、tool） | assistant 消息里的 tool call 带 id；tool 消息带同一个 id |
| event | 按时间记录的一件事（模型调用、工具执行、状态变化、评分、错误） | 时间戳；所属 span |
| tool call／result | 模型提议的调用与它的返回 | **call id**：一个调用恰好一个结果 |
| span | 一段有起止的嵌套区间（一个子任务、一次工具执行） | span id 与 parent id 形成树 |
| artifact | run 产生的文件 | 路径或哈希；被哪个事件写入 |
| score | 评分结果及证据 | 指向 run；证据指向状态字段或步骤 |

**messages 与 events 是同一次 run 的两个视图**。Inspect 的 `EvalSample` 同时保存两者：`messages` 是最终对话，`events` 是按时间的完整记录（[`log/_log.py` L449–L592](https://github.com/UKGovernmentBEIS/inspect_ai/blob/e4435baa530d05324358bedc3782609c952f9876/src/inspect_ai/log/_log.py#L449-L592)；代码已读，commit `e4435ba`）。调查失败通常需要 events，因为状态变化、错误、重试、评分不在对话里。

Inspect 中一次工具调用的三方关联：assistant 消息里的 `ToolCall.id` = `ToolEvent.id` = tool 结果消息的 `tool_call_id`。`ToolEvent` 还记录提议它的 assistant 消息 id 与结果消息 id（[`event/_tool.py` L13–L109](https://github.com/UKGovernmentBEIS/inspect_ai/blob/e4435baa530d05324358bedc3782609c952f9876/src/inspect_ai/event/_tool.py#L13-L109)）。

## 3. 贯穿例子：三条 run 的小型 trace

数据在 [`Practice/trace_viewer/sketch/raw_traces.json`](../../Practice/trace_viewer/sketch/raw_traces.json)，是**合成的教学数据**，沿用 agent_harness 的改地址任务：

| run | 情况 | 用来练什么 |
|---|---|---|
| `run-ok` | 三次工具调用，成功 | 正常轨迹长什么样 |
| `run-wrong-order` | 验证了自己却去改别人的订单，被 policy 拦截后仍回复 “Done” | 从失败的检查找到出问题的调用；与成功 run 对比 |
| `run-messy-log` | 日志写入顺序乱、输出被截断、同一结果记录两次、一个没有对应调用的结果、最后一个调用没有结果 | 不完整日志的处理 |

原始事件（节选）：

```json
{"ts": 4, "type": "tool_call",   "call_id": "c2", "name": "get_order", "args": {"order_id": "A2"}}
{"ts": 3, "type": "tool_result", "call_id": "c1", "ok": true, "output": {"customer_id": "c1"}}
{"ts": 10, "type": "tool_result", "call_id": "c9", "ok": true, "output": {"note": "result without a matching call"}}
{"ts": 11, "type": "tool_call",  "call_id": "c5", "name": "update_address", "args": {"order_id": "A2", "address": "9 New Ave"}}
```

标准化后的一步（调用与返回合成一行）：

```json
{"i": 2, "kind": "tool", "call_id": "c2", "name": "get_order", "args": {"order_id": "A2"},
 "status": "ok", "result": {"ok": true, "output": {"...": "..."}, "truncated": true},
 "flags": ["truncated_output"]}
```

标准化脚本的实际输出（2026-11-14 本地运行）：

```text
run-ok           success=True  term=final              steps=5   tool_errors=0 anomalies=[]
run-wrong-order  success=False term=final              steps=4   tool_errors=1 anomalies=[]
run-messy-log    success=False term=budget_tool_calls  steps=7   tool_errors=2 anomalies=['duplicate_result', 'missing_result', 'orphan_result', 'out_of_order_log', 'truncated_output']
    step 2  tool          get_order        flags=['truncated_output']
    step 4  tool          update_address   flags=['duplicate_result']
    step 5  orphan_result                  flags=['orphan_result']
    step 6  tool          update_address   flags=['missing_result']
first divergence (tool-call index) run-ok vs run-wrong-order: 0
```

## 4. 机制一：标准化（Python）

```python
def normalize_run(run):
    ordered = sorted(enumerate(run["events"]), key=lambda p: (p[1]["ts"], p[0]))   # 时间排序；原位置作次序
    calls, steps, seen = {}, [], set()
    for raw_idx, e in ordered:
        if e["type"] == "tool_call":
            step = {"kind": "tool", "call_id": e["call_id"], "status": "missing_result", "flags": ["missing_result"], ...}
            calls[e["call_id"]] = step; steps.append(step)            # 先假定没有结果
        elif e["type"] == "tool_result":
            step = calls.get(e["call_id"])
            if step is None: steps.append({"kind": "orphan_result", ...}); continue   # 孤儿：保留为独立一行
            if e["call_id"] in seen: step["flags"].append("duplicate_result"); continue
            seen.add(e["call_id"]); step["result"] = ...; step["status"] = "ok" if e["ok"] else "error"
            step["flags"].remove("missing_result")
    return {"run_id": ..., "success": ..., "anomalies": ..., "first_failed_check": ..., "steps": steps,
            "checks": run["verdict"]["checks"], "state_diff": diff(initial_state, final_state)}
```

| 日志问题 | 处理 | 理由 |
|---|---|---|
| 乱序 | 按时间戳排序，原始位置作为相同时间戳的次序；run 级打标 `out_of_order_log` | 排序后才能配对；保留标记让读者知道日志本身不可靠 |
| 调用没有结果 | 状态 `missing_result` | 可能是 run 被中断，也可能是日志丢失；两者都要让人看见 |
| 结果没有调用 | 单独一行 `orphan_result` | 丢弃会隐藏日志系统的 bug |
| 结果重复 | 只取第一次，打标 `duplicate_result` | 不改变步数统计 |
| 输出被截断 | 保留截断标记 | 读者需要知道自己看到的不是全部（Inspect 的 `ToolEvent.truncated` 记录了截断范围） |

原则：**标准化不丢信息、不猜测**。配不上的记录保留并打标。

run 摘要（`success`、`termination`、调用数、错误数、异常标记、第一个失败的检查）在这一步算好，列表页只读摘要。

## 5. 机制二：页面（静态 MVP）

### 5.1 页面草图

```text
┌ 筛选[全部|失败|日志异常]  搜索[        ]  对比[run…]              2 / 3 runs ┐
├──────────────┬──────────────────────────────────────┬───────────────────────┤
│ Runs         │ Timeline · run-wrong-order           │ 评分证据              │
│ ▸ run-ok ✓   │ #0 user  I'm ana@…                   │ FAIL state  A2 address│
│ ▸ run-wrong… │ #1 verify_identity(…)  ok            │      actual='1 Old St'│
│   ✗ A2 addr  │ #2 update_address(B1…) error         │ FAIL output false claim│
│ ▸ run-messy… │    policy_blocked: identity_not_…    │ 状态变化 初始→最终    │
│   5 日志异常 │ #3 assistant  Done: …                │ /session/verified… → c1│
│              │                                      │ 选中的步骤（JSON）    │
└──────────────┴──────────────────────────────────────┴───────────────────────┘
```

### 5.2 组件边界与状态

| 部分 | 输入 | 输出 | 草图中的函数 |
|---|---|---|---|
| 状态 | — | `{filter, query, runId, stepIdx, compareId}` | `state` |
| 派生数据 | 状态 + 全部 run | 可见的 run 列表；两条 run 的首个分歧位置 | `visibleRuns()`、`firstDivergence()` |
| run 列表 | 可见 run、选中项 | HTML | `renderRuns()` |
| 时间线 | 选中的 run、对比 run、选中的步骤 | HTML（单栏或双栏） | `renderTimeline()` |
| 详情 | 选中的 run 与步骤 | 评分证据表、状态变化表、步骤 JSON | `renderDetail()` |
| 事件处理 | 用户操作 | 只修改 `state`，然后调用 `render()` | 文件末尾的几行 |

整个页面是一个单文件 [`viewer.html`](../../Practice/trace_viewer/sketch/viewer.html)，约 130 行原生 JavaScript，没有构建步骤、没有后端；数据由 `normalize.py` 写成 `data.js` 后直接加载（`file://` 下不能用 `fetch` 读本地 JSON，所以用 `<script src="data.js">`）。

### 5.3 前端概念，用 Python 对照

| 前端概念 | Python 对照 | 草图中的例子 | Inspect viewer 中的例子（TypeScript，commit `818ce81`，代码已读） |
|---|---|---|---|
| 组件 | 一个函数：输入数据，返回界面描述 | `renderRuns(list)` 返回 HTML 字符串 | `ToolEventView`（`ToolEventView.tsx` L97） |
| props | 函数的参数 | `stepRow(s, selected, diverge)` | `ToolEventViewProps` |
| 状态（state） | 一个 dict；改了它就重新渲染 | `state` 对象 + `render()` | zustand store（`apps/inspect/src/state/store.ts` L77–L120），只放界面状态（筛选条件、折叠了哪些事件） |
| 派生数据 | 由状态算出的值，不单独保存；可以用缓存 | `visibleRuns()` 每次重算 | `useFilteredSamples`（`state/hooks.ts` L362–L411），带缓存（相当于 `functools.lru_cache`） |
| 事件处理 | 回调函数 | `onclick` 里改 `state` 再 `render()` | 组件的 `onRowOpen` 等回调 |
| 事件委托 | 在容器上监听，再判断点了哪个子元素 | `#runs` 的 `onclick` + `closest("[data-run]")` | — |
| 虚拟列表 | 只渲染当前滚动窗口里的行，相当于 `rows[start:end]` | 草图没有做 | `VirtualList`（`packages/react/src/virtual/VirtualList.tsx`） |
| 服务器数据缓存 | 以请求为 key 的 dict，带定时刷新 | 草图没有做（数据一次性加载） | react-query：`useSample`（`log_data/sampleQuery.ts` L51–L72） |

草图每次交互都重新生成三栏的全部 HTML。几十条 run、每条几十步时足够快；数据大时需要 React 这类只更新变化部分的库和虚拟列表。**先用最简单的方式做对，再谈性能**。

### 5.4 长轨迹、搜索、证据定位、双 run 比较

| 需求 | 草图的做法 | 大规模时怎么办（Inspect 的做法） |
|---|---|---|
| 长轨迹 | 调用与返回合成一行；长文本截到 90 字符，完整内容在详情栏 | 事件按 span 建树，成功的普通工具调用默认折叠（`transform/collapse.ts` L23–L39）；折叠节点的子节点不进入可见行（`transform/flatten.ts` L57–L112）；虚拟列表 |
| 搜索 | 在每步的 JSON 文本里做子串匹配，筛选 run 并高亮 | 在数据上搜索而不是在页面上搜索，因为屏幕外的行不在页面里（`search/sampleSearch.ts` L82，按事件 id 记录命中） |
| 证据定位 | 列表显示第一个失败的检查；详情栏同屏显示检查、证据、状态变化 | `ScoreEventView` 显示答案与解释 |
| 双 run 比较 | 并排两栏；按“工具名 + 参数”比较调用序列，标出第一次不同的位置 | — |

**比较的局限**：两条 run 走了不同但都合法的路径时，“第一次不同”不等于“出错的地方”（见 [agent_harness 04 §3](../agent_harness/04_失败诊断与受控重跑.md#3-不要假定只有一条标准轨迹)）。它是定位的起点。

## 6. 代码阅读路线：Inspect 的日志格式与 viewer

Python 部分在 [inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai/tree/e4435baa530d05324358bedc3782609c952f9876) commit `e4435ba`；viewer 的 TypeScript 源码在子模块 [meridianlabs-ai/ts-mono](https://github.com/meridianlabs-ai/ts-mono/tree/818ce818faeffe14cc26ff77fa65409bee668a05) commit `818ce81`。均为代码已读、未运行。

**先读 Python（约 45 分钟）**：

1. `EvalSample`（`log/_log.py` L449 起）：messages、events、scores、attachments。
2. 事件基类 [`event/_base.py` L22–L39](https://github.com/UKGovernmentBEIS/inspect_ai/blob/e4435baa530d05324358bedc3782609c952f9876/src/inspect_ai/event/_base.py#L22-L39)：`uuid`、`span_id`、`timestamp`、`pending`。事件没有父指针，嵌套只来自 `span_id`。
3. `ToolEvent`（`event/_tool.py` L13 起）与 `SpanBeginEvent`（`event/_span.py`，有 `id` 与 `parent_id`）。
4. **进行中的事件**：工具事件在执行前以 `pending=True` 创建，结果回来后清除（`model/_call_tools.py` L446–L453、`event/_tool.py` L124–L168）。viewer 据此显示“运行中”。
5. **大内容去重**：事件里超过 100 字符的字符串被替换成 `attachment://<哈希>`，内容在 `sample.attachments` 里只存一次（`log/_condense.py` L463–L527）。
6. **文件格式**（`log/_recorders/eval.py` L127–L136）：`.eval` 是一个 zip，里面有 `_journal/start.json`、`samples/{id}_epoch_{n}.json`（每个样本一个完整文件）、`_journal/summaries/{n}.json`（增量摘要），结束时再写 `summaries.json`、`header.json`。**列表只读摘要，点开才读单个样本文件**；journal 让运行中或崩溃的日志也能被读取。

**再读 TypeScript（约 60 分钟，重点看数据怎样流动，不必看懂每个组件）**：

| 步骤 | 位置（`A/` = `apps/inspect/src/`，`P/` = `packages/inspect-components/src/`） |
|---|---|
| 浏览器直接读 zip 里的单个文件 | `A/client/remote/remoteLogFile.ts`，`openRemoteLogFile` L163 |
| 筛选与排序 | `A/state/hooks.ts` L362–L411 → `A/app/samples/sample-tools/filters.ts` L410–L437 |
| 样本列表 | `A/app/samples/list/SampleList.tsx` L67 |
| 事件 → 树 | `P/transcript/transform/treeify.ts` L79–L115：用 `Map<spanId, node>`，`span_begin` 挂在 `parent_id` 下，其他事件挂在自己的 `span_id` 下 |
| 默认折叠与展平 | `P/transcript/transform/collapse.ts` L23–L39、`flatten.ts` L57–L112 |
| 按事件类型分派渲染 | `P/transcript/TranscriptVirtualList.tsx` L69–L332 的 `switch (node.event.event)` |
| 工具调用与结果显示在同一面板 | `P/transcript/ToolEventView.tsx` L97、L206–L223；L267–L271 的运行中指示 |

**对我们设计的影响**：摘要与详情分开；调用与结果在数据层合并而不是在界面层拼；事件类型用一个分派表决定怎样渲染；“进行中”是数据里的显式字段。

## 7. 离线文件与实时查看

| | 离线（MVP） | 实时 |
|---|---|---|
| 数据 | run 已结束，文件完整（或已知不完整） | run 进行中，事件持续追加 |
| 读取 | 一次性加载 | 增量：记住读到哪里，只取新事件 |
| 界面 | 静态 | 需要“进行中”状态、自动滚动到最新、列表摘要刷新 |
| Inspect 的做法 | 读 `.eval` zip | **轮询**：运行中的样本写入一个 SQLite 缓冲库；viewer 按服务器给的间隔请求，带上版本标记，未变化时返回“未修改”；取样本数据时带上“上次读到的事件 id”作为游标（`log/_recorders/buffer/database.py` L171、L783–L804；`_view/fastapi_server.py` L549–L620；viewer 端 `log_data/pendingSamples.ts` L142、`runningSampleQuery.ts` L261）。没有读到推送通道 |

题目没有要求实时时不做。要做时先做“定时重新读文件”，它已经覆盖大部分需要。

OpenTelemetry 的 GenAI 语义约定把工具执行表示为一个 span，名称为 `execute_tool {工具名}`，属性包括 `gen_ai.tool.name`、`gen_ai.tool.call.id`、`error.type`（文档已读，[semantic-conventions-genai](https://github.com/open-telemetry/semantic-conventions-genai) 主分支，状态为 Development）。拿到 OTel 格式的 trace 时，call id 与 span 的父子关系就是配对与嵌套的依据。

## 8. 验收案例

| # | 操作 | 期望 | 草图是否通过（无头浏览器实测） |
|---|---|---|---|
| 1 | 打开页面 | 列出 3 条 run，各有成功／失败标记 | 通过（3 条） |
| 2 | 筛选“失败” | 剩 2 条 | 通过 |
| 3 | 打开 `run-messy-log` | 7 步；能看到截断、重复、孤儿、缺失结果的标记 | 通过 |
| 4 | 点击没有结果的那次调用 | 详情显示 `missing_result` | 通过 |
| 5 | 查看评分证据 | 失败的检查与证据可见 | 通过（2 项失败） |
| 6 | 搜索 `policy_blocked` | 只剩 1 条 run，命中处高亮 | 通过 |
| 7 | 选 `run-wrong-order`，对比 `run-ok` | 双栏显示，标出首个不同的调用 | 通过 |
| 8 | 页面脚本错误 | 无 | 通过 |

检查脚本：[`check_viewer.js`](../../Practice/trace_viewer/sketch/check_viewer.js)。它对上表的预期值做断言，不符或出现页面脚本异常时以非零状态退出。

## 9. 局限

- 数据是 3 条合成 run；没有在真实的长轨迹上试过，性能与折叠策略未验证。
- 草图的原始格式是自定义的。真实题目的格式不同，标准化脚本需要重写，但配对与打标的逻辑可以复用。
- 没有 span 嵌套、没有每步的状态快照（只有初始与最终的差异）、没有 artifact 查看。
- 搜索是子串匹配；双 run 比较只比较工具调用序列。

## 来源

| 来源 | 状态 | 支持的结论 | 重点读 |
|---|---|---|---|
| inspect_ai，commit `e4435ba`：`log/_log.py`、`event/`、`log/_condense.py`、`log/_recorders/eval.py`、`log/_recorders/buffer/database.py`、`_view/fastapi_server.py` | 代码已读，未运行 | 两种视图、id 关联、pending、去重、摘要与样本分开、轮询 | `event/_tool.py`；`eval.py` L127–L136 |
| ts-mono，commit `818ce81`：`apps/inspect/src/`、`packages/inspect-components/src/transcript/` | 代码已读，未运行 | 状态库只放界面状态、筛选的派生计算、事件建树与折叠、按类型分派渲染 | `treeify.ts` L79–L115；`TranscriptVirtualList.tsx` L69–L332 |
| OpenTelemetry GenAI 语义约定 `docs/gen-ai/execute-tool.md` | 文档已读（主分支，未记录 commit） | 工具执行 span 的属性 | 属性表 |
| 本仓库 `Practice/trace_viewer/sketch/` | 代码已运行（标准化脚本；页面经无头 Chromium 实测） | 贯穿例子与验收表 | — |

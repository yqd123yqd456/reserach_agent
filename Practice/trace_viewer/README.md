# Practice：trace 标准化与静态 viewer 草图

> 状态：标准化脚本**已在本地运行**；页面**已用无头 Chromium 实际加载并走完用户 journey**（2026-11-14）。数据是 4 条合成 run，不来自任何真实模型。2026-11-14 的独立审计在这份草图里复现了 6 个缺陷（#16–#21），修正记录见[文末](#已知问题与修正2026-11-14-审计)。
> 概念见 [Knowledge/trace_viewer](../../Knowledge/trace_viewer/README.md)。

## 1. 文件

| 文件 | 作用 |
|---|---|
| [`sketch/make_sample_traces.py`](sketch/make_sample_traces.py) | 生成 `raw_traces.json`：4 条 run。`run-messy-log` 带 5 种日志异常；`run-audit-cases` 带审计复现用的 6 种情况 |
| [`sketch/normalize.py`](sketch/normalize.py) | 配对调用与返回、标出异常、算 run 摘要与状态差异；写 `normalized.json` 和 `data.js` |
| [`sketch/test_normalize.py`](sketch/test_normalize.py) | `normalize.py` 的 14 个断言测试（只用标准库）；任一失败时以非零状态退出 |
| [`sketch/viewer.html`](sketch/viewer.html) | 单文件静态页面：筛选、搜索、时间线、评分证据、状态变化、双 run 对比 |
| [`sketch/check_viewer.js`](sketch/check_viewer.js) | 用 Playwright 加载页面、按 journey 操作并**断言**预期值；任一不符或页面脚本异常时以非零状态退出（需要本机有 Node 与 Playwright） |

## 2. 运行

```bash
cd Practice/trace_viewer/sketch
```

```bash
python3 make_sample_traces.py
```

```bash
python3 normalize.py raw_traces.json
```

```bash
python3 test_normalize.py
```

然后用浏览器直接打开 `viewer.html`（双击即可，不需要服务器）。

可选的自动检查：

```bash
node check_viewer.js
```

## 3. 实测结果

检查脚本现在的最后一行是 `CHECK PASSED: 46 assertions`（审计修复前是 13 条）。反向验证：把页面里“失败”筛选的条件改反后，脚本以退出码 1 结束（修复后在副本上重做过一次）。早先的版本只打印下面这些值、不做断言，页面坏了也不会失败（2026-11-14 已修）。

标准化输出见 [Knowledge §3](../../Knowledge/trace_viewer/README.md#3-贯穿例子三条-run-的小型-trace)。`python3 test_normalize.py` 的最后一行是 `14 passed, 0 failed`。页面检查的实际输出（脚本每条断言打印一行，这里合并摘录；`#19 … literal entity` 一类的值为 `false` 表示没有出现字面的实体）：

```text
runs_all: 4, runs_failed: 2, steps_messy: 7,
flag badge truncated_output / duplicate_result / orphan_result / missing_result: true,
detail_has_missing: true, failed_checks: 2, runs_after_search: 1, marks: 1, diverge_rows: 2,
#20 right column has no data-step: 0, click on right column selects nothing: 0, click on left column selects own step: true,
#19 "t": timeline / detail text has no literal entity: false, something is highlighted: true,
#19 "Jerry" / <b> / & / "Jerry" <b>: runs: 1, first <mark> text = 查询本身, no literal entity: false,
#19 user text is not parsed as HTML: 0, detail <mark> for a query with quotes: \"Jerry\" <b>,
steps_audit: 11, flag badge result_before_call / duplicate_call_id / ambiguous_pairing / unknown_event_type / conflicting_duplicate_result: true,
runs_anomaly: 2, #21 divergence position vs run-ok: 2,
search "flags": 0, "email": 0, check name: 3 (detail 中 1 处高亮), check evidence: 1,
page_errors: []
CHECK PASSED: 46 assertions
```

验收表见 [Knowledge §8](../../Knowledge/trace_viewer/README.md#8-验收案例)。

## 4. 怎样读这段 JavaScript（给 Python 背景）

`viewer.html` 的脚本分四段，对应四个 Python 概念：

1. `const state = {...}`：一个 dict，保存全部界面状态。
2. `visibleRuns()`、`firstDivergence()`：纯函数，由 `state` 和数据算出要显示什么。
3. `renderRuns()`、`renderTimeline()`、`renderDetail()`：纯函数，返回 HTML 字符串（相当于用 f-string 拼模板）。`render()` 把三段结果写进页面。
4. 末尾的 `onchange`、`oninput`、`onclick`：回调。每个回调只做两件事：改 `state`，调用 `render()`。

语法对照：`r => r.success` 是 `lambda r: r.success`；`list.filter(f)`、`list.map(f)` 是列表推导；反引号字符串里的 `${x}` 是 f-string 的 `{x}`；`el.dataset.run` 读的是 HTML 上的 `data-run="..."` 属性。

## 5. 小练习

| # | 练习 | 验收 | 估时 |
|---|---|---|---|
| 1 | 给 `normalize.py` 写 5 个断言测试，每种异常一个 | 每个测试只构造能触发该异常的最小事件列表 | 45 分钟 |
| 2 | 加一种异常：同一个 call id 出现两次调用。先在 `make_sample_traces.py` 里构造，再确认 `duplicate_call_id` 被标出并显示在页面上 | 页面上能看到标记 | 30 分钟 |
| 3 | 把 [agent_harness 草图](../agent_harness/sketch/minimal_run.py) 产生的 run 目录（`events.json`、`verdict.json`、两个快照）转换成本 viewer 的原始格式 | S1、F1、F2 三条 run 能在页面里打开，F1 的失败检查可见 | 1.5 小时 |
| 4 | 加“只看出错与异常的步骤”开关 | 新增一个状态字段，`render` 的其余部分不改 | 30 分钟 |
| 5 | 给时间线加每步之后的状态哈希，并在状态第一次变化的步骤上加标记 | 需要改原始数据、标准化、渲染三处；说清各改了什么 | 1.5 小时 |
| 6 | 读 Inspect 的 `treeify.ts`，用 Python 重写 `treeifyWithSpans` 的核心（约 20 行），输入带 `span_id`／`parent_id` 的事件列表 | 3 个断言：嵌套、同级顺序、孤立事件 | 1 小时 |

练习 1 和练习 2 的内容已随审计修复进入草图（`test_normalize.py`；`run-audit-cases` 里的重复 call id）。仍可先自己做，再与草图对照。

## 6. 未做

真实日志格式的适配；长轨迹的性能；span 嵌套；实时查看；artifact 查看。

## 已知问题与修正（2026-11-14 审计）

来源：[草图审计记录](../../Review/mirendil_takehome/草图审计_2026-11-14.md)的 #16–#21 与两条“怀疑”项。这些缺陷存在时，草图同样“运行通过”。

| # | 缺陷 | 修正 | 由什么检查 |
|---|---|---|---|
| 16 | 先按时间排序再配对，时间戳早于调用的结果变成孤儿结果，调用变成缺结果；`result_before_call` 不可达 | `normalize.py` 改为两遍：先按 call id 归组，再生成步骤并打标，最后才排序 | `test_16_…` |
| 17 | call id 重复时，结果被挂到后一个调用上，另一个结果被当作重复丢弃 | 两个调用都保留，标 `duplicate_call_id` 与 `ambiguous_pairing`，都不挂结果；该 id 的结果各自成行（`ambiguous_result`） | `test_17_…` |
| 18 | 未知类型的事件无标记地消失；内容不同的重复结果被丢弃 | 未知事件保留为 `unknown` 步骤并标 `unknown_event_type`；内容不同的重复结果存入 `extra_results` 并标 `conflicting_duplicate_result`；内容相同的记下原始位置 | `test_18_…` |
| 19 | 高亮在已转义的 HTML 上做替换，会在 `&quot;` 等实体内部命中；含 `"` `&` `<` 的查询不高亮 | `hi()` 在原始文本上按命中切开，各段分别转义，命中段加 `<mark>`；筛选与高亮共用一个正则 | `check_viewer.js` 的 `#19` 断言 |
| 20 | 对比模式下点击右栏，显示的是左侧 run 的同下标步骤 | 右栏不再输出 `data-step`，标为只读；选步骤只在左栏 | `check_viewer.js` 的 `#20` 断言 |
| 21 | 页面用 `JSON.stringify(args)`、Python 用 `sort_keys` 比较参数，键顺序不同时结论不一致 | `normalize.py` 算一次 `args_key`（键排序的 JSON 字符串），两边都只比较它 | `test_21_…`；`check_viewer.js` 的 `#21` 断言 |
| 怀疑项 | `diff()` 把 `None` 与缺失的键视为相等 | 用哨兵值区分；每条差异带 `op`（`added`／`removed`／`changed`），页面把不存在的一侧显示为“（无此键）” | `test_diff_missing_key_vs_none` |
| 怀疑项 | 搜索匹配 JSON 键名，但不搜检查项名称 | 搜索范围改为一条 run 的所有值（步骤、检查项名称与证据、状态变化），不含键名；`args_key` 不参与 | `check_viewer.js` 的 `search:` 断言 |

修正前后的对照（都在草稿副本上运行，副本不在仓库里）：新的 `test_normalize.py` 对旧的 `normalize.py` 是 6 通过、8 失败；新的 `check_viewer.js` 对旧的 `viewer.html`（配新数据）是 34 条断言中 19 条失败，其中包括 `#20` 的两条与 `#19` 搜索 `t` 的两条。旧页面在打开 `run-audit-cases` 时还会抛脚本异常（它不认识 `unknown` 步骤），所以该 run 上的断言是连带失败，不能单独说明 #19 或 #21。

没有修、或只修了一部分的：

- 事件缺 `ts` 时 `normalize.py` 仍然抛 `KeyError`。原因：没有时间戳就没有依据决定它排在哪里，草图没有定义这种情况。缺 `call_id` 的工具事件会保留为 `unknown` 步骤并标 `malformed_event`。
- `diff()` 仍用 Python 的 `==` 比较叶子值，所以 `1` 与 `True`、`1` 与 `1.0` 被视为相等。审计没有提出这一条，这次没有改。
- call id 重复时不尝试任何配对。即使日志里恰好是“调用、结果、调用、结果”也一样标为不明确。这是有意的选择：按顺序分配就是猜测。
- 时间线里的文本只显示前 90 个字符。命中落在 90 字符之后时 run 会被筛出，但时间线里看不到高亮，要点开该步骤在详情栏看。
- 详情栏的 JSON 只高亮值，不高亮键名，与搜索范围一致。因此无法用搜索找“哪些步骤带有某个字段”。
- 审计记录里 #16–#21 的“状态”列没有更新，那个文件不在这次修改的范围内。

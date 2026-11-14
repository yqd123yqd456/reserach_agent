# Practice：trace 标准化与静态 viewer 草图

> 状态：标准化脚本**已在本地运行**；页面**已用无头 Chromium 实际加载并走完用户 journey**（2026-11-14）。数据是 3 条合成 run，不来自任何真实模型。
> 概念见 [Knowledge/trace_viewer](../../Knowledge/trace_viewer/README.md)。

## 1. 文件

| 文件 | 作用 |
|---|---|
| [`sketch/make_sample_traces.py`](sketch/make_sample_traces.py) | 生成 `raw_traces.json`：3 条 run，其中一条带 5 种日志异常 |
| [`sketch/normalize.py`](sketch/normalize.py) | 配对调用与返回、标出异常、算 run 摘要与状态差异；写 `normalized.json` 和 `data.js` |
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

然后用浏览器直接打开 `viewer.html`（双击即可，不需要服务器）。

可选的自动检查：

```bash
node check_viewer.js
```

## 3. 实测结果

检查脚本现在的最后一行是 `CHECK PASSED: 13 assertions`。反向验证：把页面里“失败”筛选的条件改反后，脚本以退出码 1 结束。早先的版本只打印下面这些值、不做断言，页面坏了也不会失败（2026-11-14 已修）。

标准化输出见 [Knowledge §3](../../Knowledge/trace_viewer/README.md#3-贯穿例子三条-run-的小型-trace)。页面检查的实际输出：

```text
runs_all: 3, runs_failed: 2, steps_messy: 7,
flag_badges: truncated_output, duplicate_result, orphan_result, missing_result,
detail_has_missing: true, failed_checks: 2, runs_after_search: 1, marks: 1,
diverge_rows: 2, page_errors: []
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

## 6. 未做

真实日志格式的适配；长轨迹的性能；span 嵌套；实时查看；artifact 查看。

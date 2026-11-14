# Practice：调查工具、证据校验与助手评估

> 状态：`sketch/` 下的脚本**已在本地运行**（2026-11-14，只用标准库）。rollout 是合成的；`findings_careful.json` 与 `findings_flawed.json` 是**手写的示例结论**，用来验证校验器与评分脚本。**没有任何 LLM 或 agent 实际运行**，所以这里没有测量真实助手的表现。
> 概念见 [Knowledge/agent_failure_investigation](../../Knowledge/agent_failure_investigation/README.md)。

## 1. 文件

| 文件 | 作用 |
|---|---|
| [`sketch/gen_rollouts.py`](sketch/gen_rollouts.py) | 生成 14 条 rollout 与 `ground_truth.json`（每条 run 的预置故障类别与根因） |
| [`sketch/inv_tools.py`](sketch/inv_tools.py) | 只读调查工具（及交给 LLM 的工具 schema）；`validate_evidence` 校验引用 |
| [`sketch/heuristic_triage.py`](sketch/heuristic_triage.py) | 只用代码规则的分诊基线，判不了的标为不确定 |
| [`sketch/findings_careful.json`](sketch/findings_careful.json)、[`sketch/findings_flawed.json`](sketch/findings_flawed.json) | 两份手写的示例结论：一份合格，一份含伪造引用、误归因、漏检、对照组误报与重复 |
| [`sketch/score_assistant.py`](sketch/score_assistant.py) | 把任意一份结论与预置真值比较：证据、类别、根因、工作量（代理指标）分开报告 |
| [`sketch/test_investigation.py`](sketch/test_investigation.py) | 审计缺陷 #25–#32 的最小复现测试（25 个，只用标准库） |

## 2. 运行

```bash
cd Practice/agent_failure_investigation/sketch
```

```bash
python3 gen_rollouts.py
```

```bash
python3 heuristic_triage.py
```

```bash
python3 score_assistant.py findings_heuristic.json findings_careful.json findings_flawed.json
```

```bash
python3 test_investigation.py
```

实际输出的对比表与读法见 [Knowledge §8](../../Knowledge/agent_failure_investigation/README.md#8-评估调查助手本身)。

## 3. 小练习

| # | 练习 | 验收 | 估时 | 需要 API |
|---|---|---|---|---|
| 1 | 只用 `inv_tools.py` 的五个函数，自己手工调查 14 条 rollout，把结论写成同样的 JSON，然后用 `score_assistant.py` 打分 | 引用全部有效；记录你用了多少次工具调用 | 60 分钟 | 否 |
| 2 | 不看 `findings_flawed.json`，只看评分输出，说出它犯了哪 5 种错误，各自需要评估集里的哪类样本才能被发现 | 与 Knowledge §8 对得上 | 20 分钟 | 否 |
| 3 | 给 `gen_rollouts.py` 加一条“矛盾证据”的 run：先遇到一次 503，之后 agent 又改错了订单。真值写成什么？评分脚本需要怎样改才能接受“两个原因都报告”？ | 写出修改并运行 | 60 分钟 | 否 |
| 4 | 加一条规则基线判错的 run（例如模型问题，但错误码看起来像环境问题） | 基线出现误归因；说明这类情况为什么需要读上下文 | 45 分钟 | 否 |
| 5 | 写调查 agent 的系统提示：角色、工具、结论 schema、引用要求、“不确定是合法输出”、预算。再写 3 条你会用来测试它的 run | 提示中每条要求都能对应评分脚本的一个指标 | 60 分钟 | 否 |
| 6 | 用真实模型按练习 5 的提示跑一遍，用 `score_assistant.py` 打分，重复 3 次看稳定性 | 报告三次的指标与差异 | 2 小时 | **是**（先估算费用） |

## 4. 未做

真实 LLM／agent 的运行；长 trace；嵌入聚类；真实的人工复核时间测量。

## 5. 已知问题与修正（2026-11-14 审计）

来源：[草图审计记录](../../Review/mirendil_takehome/草图审计_2026-11-14.md) 的 #25–#32。修正后重新运行了第 2 节的全部命令；`test_investigation.py` 的 25 个测试通过。同一份测试在修正前的代码副本上运行，结果是 13 个失败、10 个出错。`rollouts.json` 与 `ground_truth.json` 的内容没有变（仍是 14 条）。

| # | 缺陷 | 修正 | 遗留 |
|---|---|---|---|
| 25 | 空引用通过校验；`step: True` 被当作第 1 步；证据可来自结论之外的 run | `validate_evidence` 要求引用是字符串且 strip 后 ≥ 8 个字符；步骤必须 `type(step) is int` 或 `"checks"`；被引用的 run 必须在 `run_ids` 里；`run_ids` 里每条 run 要么有有效引用，要么列在 `uncited_same_pattern` | 8 个字符的引用仍可能是到处都有的片段（如 `"status"`）；校验只证明原文存在 |
| 26 | 不比较 `root_cause`；“不同根因”由类别推出 | 根因按键名精确匹配（外加一张写明的别名表 `ROOT_ALIASES`），与类别分开报告 | 别名表是人工判断；真实调查里根因是自由文本，需要人或另一轮判断来对齐 |
| 27 | 工作量代理奖励“什么都不说”与“全部归为一类”；空 `run_ids` 会崩溃 | 没有被有效且已确认的结论覆盖的失败 run 计入要读的数量；类别错误、不确定、证据无效的结论全读；未逐条引用的 run 要读；空 `run_ids` 记为证据问题；输出里注明是代理指标 | 仍是代理，没有测人工时间；“类别错误的结论全读”用了真值，假设复核一定能发现错误 |
| 28 | 重复检测依赖顺序 | 改为“存在另一条同类别结论，其 run 集合真包含本条”；集合相同时保留 `finding_id` 最小的一条 | 只按类别与 run 集合判断，不看根因文字 |
| 29 | `unknown` + `uncertain` 计为误归因；证据无效仍计为正确 | 状态非 `confirmed` 或类别为 `unknown` 的结论计入“交给人”；“正确”要求证据有效，类别相容但证据无效的单列一行 | — |
| 30 | 有环境记录但没有出错步骤时抛 `IndexError` | 这种情况只引用检查记录里的环境错误，状态标为不确定 | — |
| 31 | 所有 `invalid_arguments` 归给 harness；引用写死；不比较参数与工具说明 | 比较调用的参数名、该 run 的工具说明、错误信息：参数不在说明里或漏传 → 模型；参数都在说明里且被工具点名拒绝 → harness；其余 → 不确定。引用全部从数据按 JSON 序列化形式构造，写文件前逐条校验 | 只比较参数名，不比较参数值与类型；“模型传错参数”的 run 只在测试里构造，没有加进 14 条 rollout |
| 32 | “done”“updated” 子串把如实的拒绝标成虚假完成；截断的引用遇到转义失败 | 按整词匹配“完成”类词；同时出现否定词时标为不确定；引用取完整的 `"text": …` 序列化片段 | 关键词与否定词表很短，只适用于这批英文合成数据；带否定词的真实虚假完成会进入不确定而不是被确认 |

两份手写结论随之修改：`findings_careful.json` 把 `INC-17` 的引用加长为 `incident INC-17`，并给 r13 补了一条引用；`findings_flawed.json` 给 F-1、F-5 加了 `uncited_same_pattern`，五种故意的缺陷保留。

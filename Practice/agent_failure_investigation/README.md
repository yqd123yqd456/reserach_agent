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
| [`sketch/score_assistant.py`](sketch/score_assistant.py) | 把任意一份结论与预置真值比较 |

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

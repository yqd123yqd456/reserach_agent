# Practice：合成训练日志与诊断脚本

> 状态：[`sketch/gen_synthetic.py`](sketch/gen_synthetic.py) 与 [`sketch/diagnose.py`](sketch/diagnose.py) **已在本地运行**（2026-11-14，只用标准库，几秒钟）。**数据是合成的教学数据**，效应由生成脚本设定，不来自任何真实训练。没有训练任何模型。
> 概念与逐情境的诊断过程见 [Knowledge/training_eval_diagnostics](../../Knowledge/training_eval_diagnostics/README.md)。

## 1. 运行

```bash
cd Practice/training_eval_diagnostics/sketch
```

```bash
python3 gen_synthetic.py
```

```bash
python3 diagnose.py
```

生成的 `data/` 下有 `runs.json`（run 与任务定义）、`train_log.jsonl`（每个 checkpoint 一行）、`eval_results.jsonl`（1,440 条试验记录）。

## 2. 生成脚本里埋了什么

| run | 情境 | 另埋的陷阱 |
|---|---|---|
| A（预训练） | BPB 从 0.95 降到 0.80，任务的真实通过概率不变 | 最后一次评估用了更宽松的 `grader-v2` |
| B（RL 后训练） | 可见测试的通过率上升，独立验证的通过概率不变 | — |
| C（SFT 后训练） | 三个切片进步，`numerical_stability` 退步 | step 2000 的评估有 sandbox 故障造成的无效试验，集中在一个切片 |

完整输出与读法见 Knowledge §4。

## 3. 离线练习（不需要训练模型，不需要 API）

| # | 练习 | 验收 | 估时 |
|---|---|---|---|
| 1 | **先不看生成脚本**，只看 `diagnose.py` 的输出，为每条 run 写三句话：什么变了、哪些变化可信、下一步验证什么。再对照生成脚本 | 三条 run 的结论与生成脚本的设定一致；能指出哪些切片波动是噪声 | 45 分钟 |
| 2 | 把 `K` 从 3 改成 1 重新生成并诊断 | 说明哪些结论还成立、哪些区间变宽到无法下结论 | 30 分钟 |
| 3 | 给 `diagnose.py` 加“重判”：用 `grader-v1` 的规则重新判 run A step 4000 的记录（提示：合成数据里没有存输出，所以需要先在生成脚本里为每条记录存一个潜在的“v1 判定”） | 说清为什么真实系统里必须保存输出才能重判 | 1 小时 |
| 4 | 加一个报警规则：任一切片的配对差区间上界小于 0 时报警。然后把种子换 20 次（`rng = random.Random(seed)`），统计 run A（没有真实变化）被误报的比例 | 得到一个误报率，并解释它与“4 个切片各检验一次”的关系 | 1 小时 |
| 5 | 为 run B 设计一个常设监控指标（“只在可见测试上通过”的比例），写出它需要哪些字段、何时报警、会有哪些误报 | 写成半页设计 | 30 分钟 |
| 6 | 把 run C 的退步写成一份给研究员的诊断报告（现象、证据、两个竞争解释、各自需要的干预实验、成本估计） | 报告里每个数字都能追到一条命令的输出 | 45 分钟 |

## 4. 未做

真实训练日志；训练内部信号（梯度、各层统计）；探针集的设计与标定；干预实验本身。

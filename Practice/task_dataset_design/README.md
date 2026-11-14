# Practice：训练 bug 任务、隐藏 verifier 与任务审计

> 状态：`sketch/` 下的任务 fixture、verifier 与审计脚本**已在本地运行**（2026-11-14，只用标准库，CPU，几秒钟）。没有任何真实 agent 做过这个任务；候选解都是脚本里的文本补丁。
> 概念见 [Knowledge/task_dataset_design](../../Knowledge/task_dataset_design/README.md)。

## 1. 文件

| 文件 | 作用 | 谁能看到 |
|---|---|---|
| [`sketch/task.json`](sketch/task.json) | 任务定义（能力、指令、预算、verifier 配置、已知合法解与捷径） | 指令与预算给 agent；其余只给评估方 |
| [`sketch/task_fixture/train.py`](sketch/task_fixture/train.py) | 带 bug 的初始代码 | agent |
| [`sketch/verifier.py`](sketch/verifier.py) | 隐藏 verifier | 只有评估方 |
| [`sketch/audit_task.py`](sketch/audit_task.py) | 构造 no-op、2 个合法修复、4 个错误修复，比较可见检查与隐藏 verifier | 只有评估方 |

## 2. 运行

```bash
cd Practice/task_dataset_design/sketch
```

```bash
python3 task_fixture/train.py
```

```bash
python3 audit_task.py
```

```bash
python3 verifier.py task_fixture/train.py
```

第一条命令在 seed 0 上打印 `val_acc: 0.995`——带 bug 的代码碰巧看起来是好的。审计表的完整输出与读法见 [Knowledge §3](../../Knowledge/task_dataset_design/README.md#3-贯穿例子一个训练-bug-任务)。

## 3. 这次审计实际发现了什么

1. 我写的第一版任务说明把症状写成“准确率停在 0.5”，运行后发现真实症状是各 seed 之间乱跳。已按实际运行结果改写。
2. 第一版可见检查（seed 0 的准确率 ≥ 0.9）让 no-op 通过。改成 3 个 seed 加 loss 上限后，no-op 被拒，但硬编码打印与删除打乱仍然通过。
3. 隐藏 verifier 对 7 个候选的判定全部符合预期：0 误接受，0 误拒绝。

## 4. 小练习（不需要 API）

| # | 练习 | 验收 | 估时 |
|---|---|---|---|
| 1 | 不看 verifier，先为这个任务列出你能想到的捷径，再对照 `VARIANTS` | 至少想到 3 条；记下没想到的 | 20 分钟 |
| 2 | 加一个新的错误修复：保留打乱，但把学习率改成 0 并返回一组硬编码的“好权重” | 隐藏 verifier 是否拒绝？若不拒绝，增加检查（提示：换一个数据分布，硬编码权重就失效） | 45 分钟 |
| 3 | 加一个新的合法修复：不用下标，直接 `random.Random(seed).shuffle` 两次相同种子分别打乱 X 与 y | verifier 不应误拒 | 30 分钟 |
| 4 | 把 `constraint.shuffle_kept` 换成更强的检查：记录每个 epoch 实际的样本顺序 | 说明需要对 fixture 做什么改动，这个改动会不会泄露答案 | 45 分钟 |
| 5 | 再设计一个同族任务（另一个数据管线 bug，例如验证集与训练集重叠），填一张[审计表](../../Knowledge/task_dataset_design/README.md#7-任务审计表每个任务填一张) | 审计表每项都有实际运行依据 | 2 小时 |
| 6 | 用 [agent_harness 草图](../agent_harness/sketch/minimal_run.py) 的 run 目录合同，写出这个任务的一次 run 应落盘哪些文件、verifier 读哪些 | 能对上 Practice 00 §2.1 的每个文件 | 30 分钟 |

## 5. 未做

真实 agent 的运行；容器隔离；任务族（目前只有一个任务）；难度标定；污染检查。

# Practice：实验 runner 草图（失败识别、结构化记录、保留规则）

> 状态：[`sketch/run_experiment.py`](sketch/run_experiment.py) 与 [`sketch/demo.py`](sketch/demo.py) **已在本地 CPU 上运行**（2026-11-14，只用标准库）。[`sketch/fake_train.py`](sketch/fake_train.py) 是一个**只模拟输出格式与退出方式的替身**，不做任何训练。上游 karpathy/autoresearch **没有被运行**（需要 CUDA GPU）；没有启动任何训练。
> 机制、三个改动方向与替身的不等价之处见 [Knowledge/autoresearch_loop](../../Knowledge/autoresearch_loop/README.md)。

## 1. 运行

```bash
cd Practice/autoresearch_loop/sketch
```

```bash
python3 demo.py
```

约 5 秒（其中 2 秒是等待“挂起”的替身被超时杀掉）。输出见 [Knowledge §4](../../Knowledge/autoresearch_loop/README.md#4-三个改动方向)；每次运行的日志在 `logs/`，记录在 `results.jsonl`。

## 2. 草图覆盖了什么

| 方向 | 函数 | 已验证的行为 |
|---|---|---|
| A 失败识别 | `run()`、`classify()` | 超时后杀掉进程组；8 种状态的分类；只解析 `---` 之后的摘要块 |
| B 结构化记录 | `make_record()` | 每次运行一条 JSON；失败的记录不带指标；记录受保护文件的哈希 |
| C 保留规则 | `decide()` | 噪声阈值；显存上限；受保护文件被改动时判为无效 |

## 3. 小练习

| # | 练习 | 验收 | 估时 | 需要 GPU |
|---|---|---|---|---|
| 1 | 通读上游 `program.md`（114 行），列出每条规则是“代码保证”还是“提示约定” | 与 [Knowledge §3.2](../../Knowledge/autoresearch_loop/README.md#32-哪些可改哪些固定) 的表对照 | 30 分钟 | 否 |
| 2 | 给 `classify()` 写单元测试：每种状态一个最小日志；再加两个边界——日志里同时有 OOM 文本与摘要块；训练过程的日志行里恰好出现 `val_bpb:` | 测试通过；说明你选的优先级 | 45 分钟 | 否 |
| 3 | 给 `fake_train.py` 加一个“正常退出但没有摘要块”的模式，确认被判为 `no_metric` | 记录里没有指标 | 15 分钟 | 否 |
| 4 | 写 `summarize_results.py`：读 `results.jsonl`，输出各状态的计数、保留率、保留实验的 `val_bpb` 序列 | 崩溃不以 0 出现在任何数值统计里 | 45 分钟 | 否 |
| 5 | 写一段可以加进 `program.md` 的文字，把循环第 4–9 步改为调用 runner；说明哪些判断仍留给 agent | 一页以内；每条都能对应 runner 的一个函数 | 30 分钟 | 否 |
| 6 | 设计噪声阈值的测量：同一 commit 跑几次、怎样取阈值、花多少 GPU 时间 | 写成半页；给出成本估计 | 30 分钟 | 否（只设计） |
| 7 | 在有 GPU 的机器上，把 runner 接到真实的 `uv run train.py`，同一 commit 重复 5 次，报告 `val_bpb` 的波动 | 得到实测的噪声范围 | 约 30 分钟 GPU 时间 + 1 小时 | **是** |

## 4. 未做

真实训练；噪声水平的测量；独立评估进程（保存 checkpoint、从 logits 计算 loss）；对指标投机路径的实际验证；与 agent 的集成。

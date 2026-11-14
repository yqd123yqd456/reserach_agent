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

约 2–3 秒（其中 2 秒是等待“挂起”的替身被超时杀掉）。

```bash
python3 test_kill_tree.py
```

这条验证超时会终止整个进程树：替身再启动一个孙进程，超时后孙进程必须不再运行。

```bash
python3 test_run_experiment.py
```

这条是摘要解析、分类、保留规则的回归测试（19 个，约 1 秒），有失败时退出码非 0。

**平台**：在 Linux 上实测通过（macOS 与 WSL 走同一条 POSIX 路径，未单独测）。原生 Windows 走另一个分支（`CREATE_NEW_PROCESS_GROUP` + `taskkill /T /F`），**代码已写，未在 Windows 上实测**；在 Windows 上使用前先运行 `test_kill_tree.py`。上游 autoresearch 本身需要 CUDA 与 Linux 环境。输出见 [Knowledge §4](../../Knowledge/autoresearch_loop/README.md#4-三个改动方向)；每次运行的日志在 `logs/`，记录在 `results.jsonl`。

## 2. 草图覆盖了什么

| 方向 | 函数 | 已验证的行为 |
|---|---|---|
| A 失败识别 | `run()`、`classify()` | 超时后终止整个进程树（POSIX 实测）；10 种状态的分类，退出码优先于日志文本；只解析最后一个“整行为 `---`”之后的摘要块，且要求六个键齐全；可执行文件不存在时得到 `launch_error` 记录 |
| B 结构化记录 | `make_record()` | 每次运行一条 JSON；失败的记录不带指标；记录受保护文件在运行前与运行后的哈希；记录 `warnings` |
| C 保留规则 | `decide()` | 噪声阈值；显存上限；受保护文件被改动或基线缺失时判为无效；指标缺失、NaN、非数值时判为无效；保留后更新最优值 |

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

## 4. 已知问题与修正

- **已修（2026-11-14）**：早先的超时处理只有 `os.killpg`，原生 Windows 不支持。现在按平台分支。
- 写 `test_kill_tree.py` 时我自己的第一版判断有误：被杀死但尚未被回收的僵尸进程在 `os.kill(pid, 0)` 下仍显示“存在”，测试因此误报失败。现在读取进程状态，僵尸不算存活；并确认了“只杀直接子进程”时测试会失败。
- **已修（2026-11-14）**：[草图审计](../../Review/mirendil_takehome/草图审计_2026-11-14.md) 的 #33–#37 与一条“怀疑”项。每条的最小复现都在 `test_run_experiment.py` 里；把这份测试放到修正前的代码旁运行，19 个中 15 个不通过（10 个断言失败，5 个因接口不存在或抛异常而出错）。
  - **#33 摘要切分**：分隔行改为“整行恰为 `---`”（允许行尾空白与 CRLF），取最后一个；行内的 `---` 不算。六个键不齐时状态为 `incomplete_summary`，不算成功。
  - **#34 分类优先级**：退出码为 0 且摘要完整、数值有限即为 `ok`，日志里的 OOM／KeyboardInterrupt 文本只写进记录的 `warnings`；文本线索只在退出码非 0 或摘要里没有 `val_bpb` 时使用。
  - **#35 保留规则的数值检查**：`val_bpb`、`peak_vram_mb`、噪声阈值、显存上限、当前最优值都必须是有限数值；缺失、NaN、`79000MB` 这类非数值一律判 `invalid` 并给出原因。
  - **#36 受保护文件**：`baseline_hashes()` 在文件不存在时直接报错；`decide()` 遇到基线哈希为 `None` 判 `invalid`；每次运行前后各取一次哈希，任一次与基线不同即判 `invalid`。
  - **#37 最优值**：`demo.py` 在保留之后用 `update_best()` 更新最优值，输出里的 `best=` 是当次比较所用的值；新增的 `after_keep`（0.990）在保留 0.987 之后被丢弃。
  - **可执行文件不存在**：`run()` 不再抛 `FileNotFoundError`，把原因写进日志并返回 `returncode=None`，记录的状态为 `launch_error`。
- **仍然存在的问题**：
  - Windows 的终止分支仍未实测；新增的测试也只在 Linux 上运行过。
  - 上游 autoresearch 仍没有被运行；以上修正只在替身脚本与手写日志上验证过。
  - 受保护文件若在运行期间被改动、又在运行结束前改回，前后两次哈希都与基线一致，检测不到。不在受保护清单里的文件不受检查。
  - 训练中途若恰好打印一行 `---` 并跟着全部六个键，会被当作最终摘要。
  - 退出码为 0、摘要里没有 `val_bpb` 时仍靠日志文本猜测原因（`oom`／`interrupted`），可能猜错；这类运行无论如何不会被判为 `ok`。
  - 记录是普通 JSON，`decide()` 信任记录内容；能写记录的一方可以伪造。
  - 噪声阈值与显存上限仍是假设值。

## 5. 未做

真实训练；噪声水平的测量；独立评估进程（保存 checkpoint、从 logits 计算 loss）；对指标投机路径的实际验证；与 agent 的集成。

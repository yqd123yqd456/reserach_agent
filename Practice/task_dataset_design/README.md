# Practice：训练 bug 任务、隐藏 verifier 与任务审计

> 状态：`sketch/` 下的任务 fixture、verifier 与审计脚本**已在本地运行**（2026-11-14，只用标准库，CPU，几秒钟）。没有任何真实 agent 做过这个任务；候选解都是脚本里的文本补丁。
> 概念见 [Knowledge/task_dataset_design](../../Knowledge/task_dataset_design/README.md)。

## 1. 文件

| 文件 | 作用 | 谁能看到 |
|---|---|---|
| [`sketch/task.json`](sketch/task.json) | 任务定义（能力、指令、预算、verifier 配置、已知合法解与捷径） | 指令与预算给 agent；其余只给评估方 |
| [`sketch/task_fixture/train.py`](sketch/task_fixture/train.py) | 带 bug 的初始代码 | agent |
| [`sketch/verifier.py`](sketch/verifier.py) | 隐藏 verifier | 只有评估方 |
| [`sketch/audit_task.py`](sketch/audit_task.py) | 构造 no-op、3 个合法修复、12 个错误修复，比较可见检查与隐藏 verifier；判定与预期不符时退出码为 1 | 只有评估方 |

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

第一条命令在 seed 0 上打印 `val_acc: 0.995`——带 bug 的代码碰巧看起来是好的。第三条命令判的是带 bug 的初始代码，所以退出码是 1；verifier 的判定是退出码（0 通过，1 失败），各项结果与最后一行 `VERDICT` 写在 stderr。审计表的完整输出与读法见 [Knowledge §3](../../Knowledge/task_dataset_design/README.md#3-贯穿例子一个训练-bug-任务)。

## 3. 这次审计实际发现了什么

1. 我写的第一版任务说明把症状写成“准确率停在 0.5”，运行后发现真实症状是各 seed 之间乱跳。已按实际运行结果改写。
2. 第一版可见检查（seed 0 的准确率 ≥ 0.9）让 no-op 通过。改成 3 个 seed 加 loss 上限后，no-op 被拒，但硬编码打印与删除打乱仍然通过。
3. 隐藏 verifier（0.1 版）对当时的 7 个候选判定全部符合预期。这个结论只对那 7 个候选成立：独立审计补充候选后，0.1 版接受了其中 5 个错误修复，并在 2 个上崩溃。0.2 版对现在的 16 个候选判定全部符合预期（0 误接受，0 误拒绝），见文末“已知问题与修正”。

## 4. 小练习（不需要 API）

| # | 练习 | 验收 | 估时 |
|---|---|---|---|
| 1 | 不看 verifier，先为这个任务列出你能想到的捷径，再对照 `VARIANTS` | 至少想到 3 条；记下没想到的 | 20 分钟 |
| 2 | 加一个新的错误修复：保留打乱，但把学习率改成 0 并返回一组硬编码的“好权重” | 0.1 版不拒绝；0.2 版已加入换分布的检查（`wrong_hardcoded_weights`）。改做：写一个不训练、由类均值直接算权重的候选，看哪一项检查拒绝它，去掉那一项后还剩什么 | 45 分钟 |
| 3 | 加一个新的合法修复：不用下标，直接 `random.Random(seed).shuffle` 两次相同种子分别打乱 X 与 y | verifier 不应误拒 | 30 分钟 |
| 4 | `constraint.reshuffles_each_epoch` 靠记录样本的读取顺序判定。写一个会被它误拒的合法修复（提示：训练前先复制每条样本），再提出不误拒的判法 | 说明新判法需要对 fixture 或指令做什么改动，这个改动会不会泄露答案 | 45 分钟 |
| 5 | 再设计一个同族任务（另一个数据管线 bug，例如验证集与训练集重叠），填一张[审计表](../../Knowledge/task_dataset_design/README.md#7-任务审计表每个任务填一张) | 审计表每项都有实际运行依据 | 2 小时 |
| 6 | 用 [agent_harness 草图](../agent_harness/sketch/minimal_run.py) 的 run 目录合同，写出这个任务的一次 run 应落盘哪些文件、verifier 读哪些 | 能对上 Practice 00 §2.1 的每个文件 | 30 分钟 |

## 5. 未做

真实 agent 的运行；容器隔离；任务族（目前只有一个任务）；难度标定；污染检查。

## 已知问题与修正（2026-11-14 审计）

来源：[草图审计记录](../../Review/mirendil_takehome/草图审计_2026-11-14.md) 的缺陷 #13–#15 与一条“怀疑”项。修正后的 verifier 版本是 `trainbug-verifier-0.2`。下面的“已复现”指在副本上实际运行过。

| 缺陷 | 修正 | 仍不可靠之处与原因 |
|---|---|---|
| #13 候选抛异常或返回 `None` 时 verifier 崩溃 | 每项检查单独捕获 `BaseException`；`train` 的返回值必须是 3 个有限数；不满足时该项记为失败并附异常信息 | 没有超时：候选死循环会让 verifier 挂住。进程内做不了可靠的超时 |
| #14 退出码恒为 0；顶层 `sys.exit` 能让输出以 SUCCESS 结尾 | 导入与调用都捕获 `BaseException`；退出码 0／1 表示通过／失败；候选运行期间的 stdout 被丢弃；各项结果与 `VERDICT` 行在候选代码运行结束后写到 stderr | 候选与 verifier 同进程。候选调用 `os._exit(0)` 并自己往 stderr 写 `VERDICT: SUCCESS`，退出码就是 0（已复现）。候选往真实 stderr 写假的 `VERDICT` 行时，退出码与最后一行仍然正确（已复现），所以只应读退出码。真正的隔离需要把判定逻辑放在候选接触不到的进程里（子进程或容器），本草图没有做 |
| #15 `shuffle_kept` 只检查权重是否依赖 seed | 改名为 `constraint.seed_dependent_training`；新增 `constraint.reshuffles_each_epoch`（把样本包成记录读取的 `list` 子类，还原每个 epoch 的顺序）与 `constraint.order_matches_weights`（按记录的顺序重放参考 SGD，与返回的权重比对）。“只在循环外打乱一次”“不打乱加 seed 噪声”现在被拒 | 不完全可靠。训练前复制每条样本的合法修复会被误拒（已复现）。每个 epoch 只交换两条样本的实现能通过（已复现）：检查不衡量随机性的质量。重放检查假定零初始化的逐样本 SGD，指令没有明说不得更换算法 |
| #15 `api.unchanged` 不看默认值 | 比较完整签名字符串 `(X, y, epochs=20, lr=0.1, seed=0)` | 给参数加类型注解也会被拒；指令要求不改签名，按此处理 |
| 怀疑项：硬编码权重通过全部检查 | 新增 `capability.learns_on_flipped_data`、`capability.learns_on_rotated_data`：在两个不同的数据分布上训练并判定 | 只拒绝与数据无关的固定权重。由类均值直接算权重的候选能通过三项 `capability` 检查，靠 `constraint.order_matches_weights` 才被拒（已复现） |

审计脚本的变化：候选从 7 个增加到 16 个，每个都有预期判定；隐藏判定与预期不符、命令行退出码与进程内判定不一致、或命令行 stdout 非空时，`audit_task.py` 以退出码 1 结束。

新增候选在 0.1 版 verifier 上的结果（已复现，用修改前的 `verifier.py` 副本）：`wrong_shuffle_once`、`wrong_noshuffle_seed_noise`、`wrong_hardcoded_weights`、`wrong_changed_defaults` 被接受；`crash_toplevel_sys_exit` 使命令行输出以 SUCCESS 结尾、退出码 0；`crash_train_raises`、`crash_train_returns_none` 使 verifier 崩溃。

两个设计决定：

- **全批量梯度下降不要求通过**（`wrong_full_batch_gd`）。它在三个数据分布上都学会了，但打乱对结果不再有影响，“保留每个 epoch 的随机打乱”失去意义，所以判为错误修复。任务 v1 的指令没有明说“不得更换优化算法”；按 Knowledge §4.3，这是一条应当写进指令的隐含要求。任务 v2 已把它写进指令，版本号随之升级。
- **新增一个合法修复作为误拒的对照**（`fix_same_seed_twice`，即练习 3）：用同一个种子分别打乱 X 与 y 的副本，三个合法修复都通过。

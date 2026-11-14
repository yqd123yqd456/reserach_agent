# Research Agent：研究与面试准备材料库

每个研究专题在三个主目录下各有一个同名子文件夹；公司材料放在顶层，供多个专题共用。

```text
README.md                 # 本页：专题索引与目录约定
Knowledge/<专题>/         # 概念、机制、设计选择与证据；专题入口是该文件夹的 README.md
Practice/<专题>/          # 练习规格、实验设计与（日后的）运行记录
Review/<专题>/            # 差距与优先级、口述稿、自测
Companies/                # 公司与岗位：JD、面经、映射表（跨专题共用）
other/                    # 原始任务文件与其他资料
.claude/skills/           # topic-research 等四个 research skills
```

## 专题

| 专题 | 研究日期 | 入口 | 简介 |
|---|---|---|---|
| agent_harness | 2026-11-13 | [Knowledge/agent_harness/README.md](Knowledge/agent_harness/README.md) | 五个在面岗位（Mercor ×3、Mirendil、Resolution）所需的 agent harness、评估、post-training 与 scalable oversight 知识，含共用 harness 练习与口述自测 |
| grading | 2026-11-14 | [Knowledge/grading/README.md](Knowledge/grading/README.md) | 判分逻辑的三层结构、strict／loose、unknown 与解析失败、LLM judge 的偏差与验证；含可运行的报告判分器与 grader audit |
| task_dataset_design | 2026-11-14 | [Knowledge/task_dataset_design/README.md](Knowledge/task_dataset_design/README.md) | 从能力声明到任务、fixture、隐藏 verifier 与任务审计；含一个可运行的训练 bug 任务 |
| trace_viewer | 2026-11-14 | [Knowledge/trace_viewer/README.md](Knowledge/trace_viewer/README.md) | 日志标准化、调用与返回配对、静态 viewer 的状态与渲染；含单文件页面草图 |
| training_eval_diagnostics | 2026-11-14 | [Knowledge/training_eval_diagnostics/README.md](Knowledge/training_eval_diagnostics/README.md) | 可比性检查、配对比较、切片、从曲线下钻到样本；含合成日志与诊断脚本 |
| agent_failure_investigation | 2026-11-14 | [Knowledge/agent_failure_investigation/README.md](Knowledge/agent_failure_investigation/README.md) | 让 agent 辅助调查大量 rollout：证据绑定与校验、工具 schema、对调查助手自身的评估 |
| autoresearch_loop | 2026-11-14 | [Knowledge/autoresearch_loop/README.md](Knowledge/autoresearch_loop/README.md) | 读懂一个自动实验项目的真实机制，设计并验证范围明确的改动；含 CPU 上的 runner 草图 |

后六个专题共同服务于 Mirendil Model Evaluation take-home 的准备，总览与学习顺序见 [Companies/Mirendil.md §5](Companies/Mirendil.md#5-take-home-准备六个专题)。它们是可能的题型方向，不是已知考题。 跨专题的执行指南见 [Review/mirendil_takehome/执行指南.md](Review/mirendil_takehome/执行指南.md)。

## 新专题的约定

- 新研究用一个简短的英文小写名作为专题名（例如 `agent_harness`），在 `Knowledge/`、`Practice/`、`Review/` 下各建同名子文件夹；只建实际用到的。
- 专题入口写在 `Knowledge/<专题>/README.md`：任务、阅读顺序、证据状态、未核实事项、下一步。
- 公司信息更新 `Companies/` 中已有文件，不在专题里复制公司百科；专题文件链接过去。
- 在本页的“专题”表中加一行。

## 怎样调用 skills

在本仓库的会话中输入，例如：

```text
/topic-research <研究主题或任务文件>
```

```text
/research-review <要审阅的文件>
```

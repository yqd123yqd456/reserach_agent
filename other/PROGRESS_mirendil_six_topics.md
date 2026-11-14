# 进度：Mirendil take-home 六专题（2026-11-14 开始）

任务：grading、trace_viewer、autoresearch_loop、task_dataset_design、training_eval_diagnostics、agent_failure_investigation。
每个专题：Knowledge/<topic>/README.md（主文）、Practice/<topic>/（规格 + 可运行草图）、Review/<topic>/速查卡.md。

## 关键决定
- 复用 agent_harness 的 run 目录合同（task.json / initial_state / final_state / audit / events / run.json / verdict.json）与 CheckResult。
- 共用贯穿场景：`lab` 研究任务——agent 修一个训练 bug、跑实验、交实验报告。grading 判报告，task_dataset_design 定义任务，trace_viewer 看轨迹，diagnostics 比较 checkpoint，investigation 调查失败。
- 草图只用 Python 标准库；viewer 是单文件静态 HTML；不调用 API、不用 GPU。
- 来源状态标签沿用 Knowledge/agent_harness/10 的六级定义。

## 状态
- [x] grading（Knowledge/Practice/Review 完成，草图已运行）
- [x] task_dataset_design（完成，草图已运行）
- [ ] trace_viewer
- [ ] training_eval_diagnostics
- [ ] agent_failure_investigation
- [ ] autoresearch_loop
- [ ] 入口与根 README、统一审查、链接检查

## 来源调查（后台）
- IFEval + judge 实现；Inspect viewer；autoresearch 仓库；Terminal-Bench 任务路径 + 训练评估接口；失败调查论文与工具。

---
name: research-review
description: Review research notes and learning material for claim support, mechanism depth, experimental validity, practical transfer, and knowledge organization. Use for 研究材料审阅、深度检查、实验与来源核验 and checking readiness before delivery; provide actionable findings, not generic praise.
---

# Research Review

检查材料是否真正回答问题、依据是否足够、读者能否理解与应用。可独立审阅，也可作为 topic-research 的交付前步骤。

## 请求

$ARGUMENTS

读取实际待审内容，确认用户目标和范围；不要只凭标题或文件名评审。链接相对于本 SKILL.md。

按需读 [内容质量](../topic-research/references/content-quality.md)、[来源与验证](../topic-research/references/evidence-and-verification.md)、[知识维护](../topic-research/references/knowledge-maintenance.md)；用 [内容参照](../topic-research/references/golden-examples.md) 中相关行为作参照，而非照抄结构。

## 检查重点

1. **回答目标**：是否解决实际卡点？是否扩展成无关课程、公司分析或项目？
2. **事实与计算**：引用是否直接支持主张？关键公式、单位、分母、假设是否成立？版本和时效是否影响结论？
3. **机制深度**：能否从定义走到例子和解释？是否只罗列术语或“最佳实践”？
4. **设计与现实**：来源中的约束是否改变方案？有没有更简单的 baseline？哪些条件变化会改变选择？
5. **验证**：实验能否区分竞争解释？测试能否揭露错误？mock、静态检查和真实运行是否分开？
6. **迁移边界**：toy 结果是否被当作生产结论？个人经历、拟议实验和作者自报结果是否混在一起？
7. **知识维护**：保存时归属是否合理、链接是否有效、已知重复片段是否矛盾？历史记录是否被错误改写？
8. **可读与可用**：主线是否连贯？快速入口能否回想结论？练习和下一步是否具体？

针对关键风险实际做检查，例如打开被引用段落、重算小例子、读核心函数及测试，或运行获授权的验证。没有检查的维度标为未检查，不把缺工具自动判成内容错误。

## 反馈格式

发现问题时按重要性列：位置 → 问题 → 依据／反例 → 影响 → 最小修正。区分：

- **必须修正**：结论错误、证据不支持、伪造运行状态、遗漏关键约束等。
- **需要加强**：机制、案例、对照或适用条件不足，影响学习和判断。
- **可选改进**：表达或导航优化，不影响主要结论。

根据任务给“可交付／修正后可交付／证据不足”的判断，并写出检查范围。可用 0／1／2 做内部比较，但不把自评分或固定分数等同于正确性或面试通过。

## 修正循环与权限

作为主流程的内部步骤，返回具体缺口，主流程修正后复核受影响部分。用户只要求 review 时先报告发现，不直接改文档；用户要求修订或主流程已获写入授权时，完成相应修正。

不要以“一定要更多论文／更多测试”作为通用建议。完成必要检查后停止；保留真实不确定性，不用模糊措辞掩盖它。

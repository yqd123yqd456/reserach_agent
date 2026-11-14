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

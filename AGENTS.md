# AGENTS.md

# ChatBI AI Development Rules

本文件定义 Codex / AI Coding Agent 在本仓库中的项目规则。具体 Architecture（架构）、Domain（领域）、Spec（规格）和当前状态，以对应 Source of Truth（事实源）为准。

## Language

- 默认使用中文生成 Spec、Ticket、ADR、Code Review、工程报告和完成报告。
- Commit Message 使用 `<type>(<scope>): <中文摘要>`；`type`、`scope` 可以保持 Conventional Commit（约定式提交）格式，摘要必须使用中文。
- English 技术术语、Skill 名称、命令名、API、类名、函数名、文件路径和代码保持原样。
- 需要引用原始英文内容时，保留原文并补充中文解释。

## Agent skills

这里仅保留当前仓库的本地配置指针，不重复编写 Skill 的工作流程：

### Local task tracker

Spec、Ticket 和路径规划使用本地 Markdown，详见 `docs/agents/issue-tracker.md`。

### Domain docs

领域文档的读取位置和边界详见 `docs/agents/domain.md`。

## ChatBI Identity & Core Principles

ChatBI = Domain AI Engine（领域 AI 引擎）
Architecture = Modular Monolith（模块化单体）

始终遵循：

- Business First（业务优先）
- Domain Owns Business Truth（领域拥有业务事实）
- Model proposes, program decides（模型提出，程序裁决）
- Stable Core, Replaceable Edge（稳定核心，可替换边缘）
- Do Not Overbuild（不过度建设）

优先级为：

业务正确 → 最小完整闭环 → Test / Evaluation → 可维护 → Production Readiness。

## Source of Truth

职责：

- Architecture：系统结构、边界、不变量
- Engineering：长期工程规则
- Domain：业务事实、规则、口径
- Feature / Module Spec：行为契约
- Code：Contract 的实现
- Tests / Evaluation：正确性证据

规则：

- 上层事实源优先于下层实现。
- 不得用 Legacy Code、旧 Metadata 或 Derived Artifact 反向修改已确认的 Architecture、Domain 或 Contract。
- 实现与设计冲突时，先检查并修正实现。

## Architecture & Layer Boundary

以下变化必须先确认：

- 系统定位或边界
- 核心业务链
- 核心对象稳定语义
- Module 一级职责
- 分层 / 依赖方向
- Business Source of Truth
- 稳定公共 Contract
- Security / Authorization / State 不变量

稳定依赖：

```text
Interfaces
→ Application
→ Domain

Application
→ Port / Contract
← Infrastructure Adapter
```

禁止：

- Domain 依赖具体 Provider、Database 或 Platform SDK；
- Infrastructure 定义业务真相；
- 为假设中的未来提前建设复杂抽象。

## Semantic & Model Rule

保持：

```text
Natural Language
→ Business Semantic Resolution
→ SemanticQuery
→ Certified Physical Mapping
→ SQL
```

不得直接从 Natural Language 映射到 Database Column。

LLM 输出始终视为 Untrusted Candidate（不可信候选）。LLM 可以提出候选，但不得最终决定：

- Business Truth
- Metric Definition
- Authorization
- Data Scope
- SQL Safety

最终由 Authoritative Data、Contract 和 Deterministic Code 裁决。模型生成 SQL 必须经过确定性 SQL Guard。

## Quality Evidence

- 行为变化必须同步更新相应测试。
- Software Test 验证确定性软件正确性；AI Evaluation 验证 AI 行为；Business Acceptance 验证业务目标是否满足。
- 新的 Bad Case 应加入 Regression（回归）集合。
- 没有相应验证，不得声称目标行为已经完成。
- 具体 TDD、Code Review、测试执行和报告格式由对应 Skill 负责。

## Security Rule

真实 API Key、Token、Password、Connection String 和其他 Secret 不得进入：

- Source Code
- Git
- Logs
- Documentation
- Test Data

`.env` 是本地真实配置，`.env.example` 是可提交的安全模板。

## Delivery Boundary

- 每次修改只覆盖已确认的 Scope，不混入无关 Feature、重构、清理或未来能力。
- 保留用户已有修改，不覆盖、不删除、不回退，也不把无关文件加入当前提交。
- 默认只做本地 Commit，不 Push、不创建 PR、不创建外部 Issue，除非用户明确要求。
- 只有 Contract、相关验证和 Diff 检查完成后才提交；无法确认修改归属或验证失败时不提交。
- Commit Message 使用 `<type>(<scope>): <中文摘要>`，完成报告使用中文说明提交内容、验证结果和剩余问题。

## Final Principle

> Contract 内自主执行，Contract 外停止扩张。

> 先完成最小正确闭环，再根据真实需求演进。

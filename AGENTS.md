# ChatBI AI Development Rules

本文件是 ChatBI Coding Agent 的精简入口和必须遵守的稳定规则。Harness 的组成和读取方式见 [`docs/agents/agent-harness.md`](docs/agents/agent-harness.md)；详细流程和领域 Contract 以本文列出的 Source of Truth 为准。

## Language & Collaboration

- 默认用中文沟通、编写 Spec、Ticket、ADR、Review 和报告；Commit 摘要使用中文，格式为 `<type>(<scope>): <中文摘要>`。技术术语、Skill、命令、API、类名、函数名、路径和代码保持原样；引用英文时保留原文并补充中文解释。
- 先给结论，区分事实、决定、假设和建议；需要用户决定时一次只问最关键的问题。
- 保留用户已有修改，不覆盖、不删除、不回退，也不把无关文件加入当前交付。

## Project & Source of Truth

- ChatBI 是 Domain AI Engine（领域 AI 引擎），Architecture 是 Modular Monolith（模块化单体）。遵循 Business First、Domain Owns Business Truth、Model proposes, program decides、Stable Core, Replaceable Edge 和 Do Not Overbuild。
- 业务正确优先，其次是最小完整闭环、验证、可维护性和 Production Readiness。
- `docs/architecture.md` 定义架构；`docs/product-scope.md` 定义当前产品边界；`docs/specs/` 定义行为 Contract；`docs/designs/` 记录实现设计；`docs/acceptance/`、Tests 和 Evaluation 提供验收证据。
- 上层已确认的事实源优先于下层实现。Legacy Code、旧 Metadata 或派生产物不得反向修改已确认的 Architecture、Domain 或 Contract；实现冲突时先检查实现。
- 领域任务按 [`docs/agents/domain.md`](docs/agents/domain.md) 读取相关事实源。不要为补齐形式创建空文档。

## Architecture & Model Boundaries

- 保持依赖方向：`Interfaces → Application → Domain`；Application 依赖 Port / Contract，Infrastructure 提供 Adapter。
- Domain 不依赖具体 Provider、Database 或 Platform SDK；Infrastructure 不定义业务真相；不为假设中的未来需求建设复杂抽象。
- 系统边界、核心业务链、稳定对象语义、一级模块职责、依赖方向、Business Source of Truth、公共 Contract、Authorization / State 不变量发生变化前，先取得用户确认。
- 查询链路保持 `Natural Language → Business Semantic Resolution → SemanticQuery → Certified Physical Mapping → SQL`，不得从 Natural Language 直接映射到 Database Column。
- LLM 输出始终是 Untrusted Candidate；Business Truth、Metric Definition、Authorization、Data Scope 和 SQL Safety 由权威数据、Contract 和确定性代码裁决。模型生成的 SQL 必须经过确定性 SQL Guard。

## Workflow

- 工程请求先由 `ask-matt` 判断阶段、范围和风险。目标、成功标准、事实源或边界不清时进入 `grill-with-docs`；小范围、单会话且不改变稳定 Contract 的修改可直接实施。
- 多阶段 Feature 依次经过 Spec 确认、`design-review`、Ticket 草案与 Ticket Readiness Review、用户确认 Ticket 拆分，再进入实现。细节见 [`docs/agents/issue-tracker.md`](docs/agents/issue-tracker.md)。
- Ticket Readiness Review 在当前上下文只读执行，不启动独立 Agent；它不替代设计审查、实现后的 Code Review 或 PR Review。
- 仓库规则引用的 workflow Skills 可能由 Codex 环境中的 `engineering-workflow` Plugin 提供；Harness 的说明和依赖边界见 [`docs/agents/agent-harness.md`](docs/agents/agent-harness.md)。

## Quality & Security

- 行为变化同步更新相应 Software Test、AI Evaluation 或 Business Acceptance；新 Bad Case 加入 Regression。没有适用验证证据，不得声称目标行为已完成。
- Software Test 验证确定性软件行为；AI Evaluation 验证模型行为；Business Acceptance 验证业务目标。具体验证按改动风险选择。
- 真实 API Key、Token、Password、Connection String 和其他 Secret 不得进入 Source Code、Git、Logs、Documentation 或 Test Data。`.env` 是本地真实配置；`.env.example` 是安全模板。

## Git & Delivery

- 新的 Feature、Bug Fix 或工程目标从已同步的 `master` 和干净工作区开始；一个目标默认使用一个 active branch 和一个 active worktree。
- 默认只做本地 Commit。Push、创建或更新 PR 必须先取得用户明确确认；Agent 不直接 Merge。详细候选、验证、PR、Auto-merge 和清理规则见 [`docs/agents/git-pr-workflow.md`](docs/agents/git-pr-workflow.md)。
- 只提交当前目标相关改动；Contract、适用验证、Review 和 Diff 检查完成后才能 Commit。高风险链路及验证级别按 Git / PR 流程执行。
- 交付报告用中文列出提交内容、验证结果和剩余问题。未运行的验证要明确标注。

## Documentation Map

- Harness 组成、后续 AI 的读取入口和文档维护触发条件：[`docs/agents/agent-harness.md`](docs/agents/agent-harness.md)
- 架构和产品边界：[`docs/architecture.md`](docs/architecture.md)、[`docs/product-scope.md`](docs/product-scope.md)
- 行为 Contract、实现设计、验收证据：`docs/specs/`、`docs/designs/`、`docs/acceptance/`
- 本地开发、服务运行和评测：[`docs/runbook.md`](docs/runbook.md)、`evaluation/`、`reports/evaluation/`

> Contract 内自主执行，Contract 外停止扩张。

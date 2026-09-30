# ChatBI AI Development Rules

本文件是 ChatBI Coding Agent 的精简入口和必须遵守的稳定规则。Harness 的组成和读取方式见 [`docs/agents/agent-harness.md`](docs/agents/agent-harness.md)；详细流程和领域 Contract 以本文列出的 Source of Truth 为准。

## Language & Collaboration

- 默认用中文沟通、编写 Spec、Ticket、ADR、Review 和报告；Commit 摘要使用中文，格式为 `<type>(<scope>): <中文摘要>`。技术术语、Skill、命令、API、类名、函数名、路径和代码保持原样；引用英文时保留原文并补充中文解释。
- 先给结论，区分事实、决定、假设和建议；需要用户决定时一次只问最关键的问题。
- 涉及仓库外状态或本机配置（例如 Skill Plugin 的来源、安装、启用、版本和同步状态）时，先检查能证明该状态的配置与文件；无法核实的内容明确标为未确认，不凭对话记忆或局部线索断言。
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

- 每个进入本仓库的新会话，在首条回复前检查当前仓库、branch / worktree、`git status` 和活动工作记录；回复开头用一行状态栏说明阶段、工作项、工作区状态、上次停点和下一步。只读咨询标明“只读咨询 / 无实施阶段”。
- 以当前 branch / worktree 唯一匹配 `.scratch/<feature>/status.md` 中的活动记录；没有唯一匹配时，报告候选并请用户选择，不根据旧聊天或目录名猜测。
- 工作区有修改时先列明并判断归属。能由当前活动工作记录确认属于正在继续的任务时，可以恢复该任务；归属不明或属于其他任务时，暂停新的写入操作并请用户决定。不得自动 stash、reset、checkout、commit、覆盖或移动改动。
- 先判断用户是在需求发现、需求澄清、Spec 待确认、待拆 Ticket、待实施、实施、验证 / Review、PR 检查、合并后 Harness 复盘或其他状态。问题 / 机会尚无明确目标时进入需求发现，通过讨论和必要的只读查证整理候选目标；已有候选目标但行为、范围或验收仍不清时进入 `workflow-grill-with-docs`；不得把两者都称作需求澄清。
- 每个确定要实施的工程改动都有工作记录。小改动使用短 Spec 并经用户确认后直接实施；复杂改动经过完整 Spec 确认、`workflow-design-review`、`workflow-to-tickets` 草案、当前上下文的 `workflow-ticket-readiness` 和用户确认拆分，再进入实现。细节见 [`docs/agents/issue-tracker.md`](docs/agents/issue-tracker.md)。
- `ask-matt` 是用户主动要求流程导航时使用的可选 Skill，不是每个请求的必经入口。Ticket Readiness Review 在当前上下文只读执行，不启动独立 Agent；它不替代设计审查、实现后的 Code Review 或 PR Review。
- 仓库规则引用的 workflow Skills 由 Codex 环境中的 `engineering-workflow` Plugin 提供；调用时使用已安装 Plugin 暴露的精确名称。Harness 的说明和依赖边界见 [`docs/agents/agent-harness.md`](docs/agents/agent-harness.md)。

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

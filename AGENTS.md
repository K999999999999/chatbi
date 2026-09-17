# AGENTS.md

# ChatBI AI Development Rules

本文件定义 Codex / AI Coding Agent 在本仓库中的项目规则。具体 Architecture（架构）、Domain（领域）、Spec（规格）和当前状态，以对应 Source of Truth（事实源）为准。

## Language

- 默认使用中文生成 Spec、Ticket、ADR、Code Review、工程报告和完成报告。
- Commit Message 使用 `<type>(<scope>): <中文摘要>`；`type`、`scope` 可以保持 Conventional Commit（约定式提交）格式，摘要必须使用中文。
- English 技术术语、Skill 名称、命令名、API、类名、函数名、文件路径和代码保持原样。
- 需要引用原始英文内容时，保留原文并补充中文解释。

## Communication

- 先给直接结论，再说明原因和影响。
- 使用直白、完整的中文说明，不只给出“可以”“不可以”“需要澄清”等结论，必须说明对象、原因和下一步行动。
- 明确区分当前事实、已经确认的决定、待确认的问题、假设和建议，不得把假设表达成已确认结论。
- 讨论多个方案时，明确推荐方案、主要取舍和适用边界；存在不确定性时直接说明不确定点。
- 说明工作流程时，明确当前阶段、已经完成的内容、尚未完成的内容，以及是否需要用户确认。
- 每次需要用户决策时，只提出一个最关键的问题，并说明这个决定会影响什么。
- Skill 名称、阶段名称和技术术语不能替代解释；首次使用或容易混淆时，先用普通中文说明其作用。

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

## AI Agent Commit & Pull Request Workflow

本节定义 Agent（智能代理）在本仓库中的提交与 Pull Request（合并请求）协作流程。它是项目协作约定，不把 PR 或完整 Real E2E（真实端到端）绑定到固定的 commit 数量。

### Commit 数量与目标判断

- 一个 PR 只承载一个清晰、已确认的业务目标或工程目标；不以“几个 commit”作为拆分标准。
- Agent 根据 Scope、改动风险、逻辑完整性和是否已经形成可运行的 candidate commit（候选提交）判断是否适合进入 PR 阶段。
- 多个相关的小 commit 可以放在同一个 PR；较大的功能应按 Contract、实现、测试等逻辑边界形成多个 commit，只有能够独立验收且边界清楚时才拆成多个 PR。
- 开发过程中的每个逻辑阶段运行对应的 targeted tests（针对性测试）；不因为每个 commit 都完成就机械运行完整 Real E2E。

### PR 前的 Agent 门禁

Agent 判断当前改动已经形成适合提交 PR 的 candidate commit 后，必须先向用户发送明确提醒，说明确认后将执行本地最终验收，并在验收通过后 Push / 创建或更新 PR；提醒还必须说明：

- 当前 PR 的目标和包含的 commit 范围；
- 当前改动是否属于需要完整 Real E2E 的高风险范围；
- 仍然缺少哪些验证。

Agent 只能在用户明确确认后进入 PR 前验收。该次确认同时授权后续成功路径的 Push / 创建或更新 PR；确认后的顺序固定为：

```text
用户确认
→ 确认最终 candidate commit 和 git_dirty=false
→ 按风险运行 targeted tests
→ 高风险改动运行本地完整 Real E2E
→ 检查 21/21、Execution Accuracy 和评测报告
→ 验证通过后 Push / 创建或更新 PR
```

- 如果最终本地 E2E 失败，Agent 不得声称可以提交 PR；应报告失败案例和原因，修复后重新形成 candidate commit 并验证。
- 本地 E2E 通过后如果又修改了会影响行为的代码，必须重新验证；只修改文档、注释或不影响运行行为的内容时，可以按风险重新判断。
- 上述用户确认是 Push、创建或更新 PR，以及使用 GitHub CLI 创建 PR 级 Auto-merge request（自动合并请求）的外部状态授权。创建 Auto-merge request 可能在所有 required checks（必需检查）满足时立即合并，因此执行前必须确认目标 PR、合并策略和当前检查状态，并在执行后验证 PR 状态；生产部署仍需单独确认。

### 风险与验证级别

- Retrieval、Prompt、Semantic、RAG Offline Build、Embedding、Qdrant、LLM 配置、Evaluation cases 或 SQL 生成链路的改动，默认属于高风险，需要在最终 candidate commit 上运行本地完整 Real E2E。
- 文档、注释、纯测试、纯 CI 或不影响运行行为的整理，运行相关 targeted tests，不要求完整 Real E2E。
- 完整 Real E2E 使用本地 `.env`、本地 PostgreSQL、Qdrant、BGE-M3 和真实 LLM；不提交 `.env`，不在日志或报告中暴露 Secret。
- GitHub Actions 的快速 CI 在 Push / Pull Request 更新后自动运行；独立 Real E2E workflow 只按需手动触发，不作为普通 PR 的自动步骤。

## Final Principle

> Contract 内自主执行，Contract 外停止扩张。

> 先完成最小正确闭环，再根据真实需求演进。

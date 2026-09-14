# AGENTS.md

# ChatBI AI Development Rules

本文件定义 Codex / AI Coding Agent 在本仓库中的全局开发规则。

具体 Architecture（架构）、Domain（领域）、Spec（规格）和当前状态，以对应 Source of Truth（事实源）为准。

## Language

- 默认使用中文生成 Spec、Ticket、ADR、Code Review 和工程报告。
- English 技术术语、Skill 名称、命令名、API、类名、函数名、文件路径和代码保持原样。
- 需要引用原始英文内容时，保留原文并补充中文解释。

## Agent skills

### Issue tracker

本仓库的 Issue 和 Spec 统一存放在 GitHub Issues 中，所有操作使用 `gh` CLI。详见 `docs/agents/issue-tracker.md`。

### Domain docs

本仓库采用 single-context 结构。处理领域相关任务前，读取 `CONTEXT.md` 和 `docs/adr/` 下相关 ADR。详见 `docs/agents/domain.md`。

## 1. Core Principles

ChatBI = Domain AI Engine（领域 AI 引擎）
Architecture = Modular Monolith（模块化单体）

始终遵循：

- Business First（业务优先）
- Domain Owns Business Truth（领域拥有业务事实）
- Model proposes, program decides（模型提出，程序裁决）
- Stable Core, Replaceable Edge（稳定核心，可替换边缘）
- Do Not Overbuild（不过度建设）

优先完成：

业务正确 → 最小完整闭环 → Test / Evaluation → 可维护 → Production Readiness。

## 2. Source of Truth

职责：

- Architecture：系统结构、边界、不变量
- Engineering：长期工程规则
- Domain：业务事实、规则、口径
- Feature / Module Spec：行为契约
- Code：Contract 的实现
- Tests / Evaluation：正确性证据

规则：

- 上层事实源优先于下层实现。
- 不得用 Legacy Code、旧 Metadata 或 Derived Artifact 反向修改已确认的 Architecture / Domain / Contract。
- 实现与设计冲突时，先检查并修正实现。

## 3. Task Flow

每个 Task 默认执行：

Read
→ Understand Contract
→ Implement
→ Test / Evaluation
→ Review Diff
→ Commit
→ Report

开始前明确：

- Goal
- Source of Truth
- Scope
- Contract
- Out of Scope
- Done When

一次只完成一个可独立验证的 Task。

不得混入无关 Feature、重构、清理、架构变化或未来能力。

## 4. Architecture & Layer Boundary

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

Interfaces
→ Application
→ Domain

Application
→ Port / Contract
← Infrastructure Adapter

禁止：

- Domain 依赖具体 Provider / Database / Platform SDK
- Infrastructure 定义业务真相
- 为假设中的未来提前建设复杂抽象

## 5. Semantic & Model Rule

保持：

Natural Language
→ Business Semantic Resolution
→ SemanticQuery
→ Certified Physical Mapping
→ SQL

不得直接：

Natural Language
→ Database Column

LLM 输出始终视为 Untrusted Candidate（不可信候选）。

LLM 可以提出候选，但不得最终决定：

- Business Truth
- Metric Definition
- Authorization
- Data Scope
- SQL Safety

最终由 Authoritative Data + Contract + Deterministic Code 裁决。

模型生成 SQL 必须经过确定性 SQL Guard。

## 6. Test & Review

行为变化必须同步更新相应测试。

质量证据区分：

- Software Test：确定性软件正确性
- AI Evaluation：AI 行为正确性
- Business Acceptance：业务目标是否满足

发现新的 Bad Case，应加入 Regression（回归）集合。

没有相应验证，不得声明 Task 完成。

Review Diff 必须确认：

- Contract 满足
- Scope 未扩张
- Architecture / Domain 未破坏
- 无无关修改
- 无 Secret
- 文档与实际状态一致

## 7. Subagent Rule

Main Agent 默认负责实现、整合、修复和最终验证。

仅当能够：

- 独立处理
- 减少主上下文污染
- 提供独立验证
- 获得真实并行收益

时才使用 Subagent。

适合：

- Explorer：代码探索
- Tester：独立测试
- Reviewer：独立审查

Tester / Reviewer 应优先基于 Spec、Contract、Diff 和 Relevant Code 独立判断。

禁止为了并行而强行拆任务，或让多个 Agent 同时修改同一核心文件。

## 8. Secret Rule

真实 API Key、Token、Password、Connection String、Secret 不得进入：

- Source Code
- Git
- Logs
- Documentation
- Test Data

`.env` = 本地真实配置
`.env.example` = 可提交安全模板

## 9. Git Rule

每个独立 Task 原则上对应一个独立 Commit。

满足以下条件后自动 Commit，无需再次询问：

- Task 完成
- 必需 Test / Evaluation PASS
- Diff 正确
- 无无关修改
- 无 Secret
- 无 Ask First 冲突

Commit Message：

`<type>(<scope>): <summary>`

工作区存在用户已有修改时：

- 不覆盖
- 不删除
- 不回退
- 不 Stage 无关文件

能够隔离当前 Task 时，只 Commit 当前 Task 修改。

无法确认修改归属、验证失败或存在未解决问题时，不 Commit，并报告原因。

## 10. Completion

完成前确认：

- Contract 满足
- Scope 未扩张
- 必需 Tests PASS
- Evaluation PASS（适用时）
- Diff 已审查
- 无 Secret
- `git diff --check` PASS
- Commit 完成

成功报告保持简洁：

Status: PASS
Tests: <结果>
Commit: <hash> <message>
Changed: <核心变化>
Remaining: None / <剩余问题>

## Final Principle

> Contract 内自主执行，Contract 外停止扩张。

> 验证通过，自动提交。

> 先完成最小正确闭环，再根据真实需求演进。

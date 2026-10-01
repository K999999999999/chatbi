# Codex Harness Engineering：需求澄清与反馈闭环

## Problem Statement

本仓库已有较完整的 `AGENTS.md`、领域与工程文档、Spec / Ticket 工作流、测试和高风险验证门禁，也通过个人 `engineering-workflow` Plugin 使用通用工程 Skills。当前仍有两个影响持续改进的问题：

1. `workflow-grill-with-docs` 有澄清主题，但缺少可检查的需求覆盖与完成门槛，可能在仍有重要问题时结束澄清。
2. Codex 在具体任务中遇到上下文、事实源、工具、测试、反馈、架构约束或可观测性缺口后，没有统一机制将真实证据转成针对 Harness 的改进建议。

目标是让 Codex 作为本仓库的编码 Agent，能在项目事实和 Contract 内完成小范围实现、验证、依据失败反馈修复，并在任务后识别值得沉淀的工程缺口，使下一次同类任务更容易、更可靠。该目标不包括让 ChatBI 产品运行时 Agent 自主改进。

## Solution

采用渐进式改进，不替换现有工程工作流，也不引入一套新的 Harness 框架。

- `AGENTS.md` 继续作为 ChatBI 项目的轻量入口：映射项目事实源、关键边界、验证入口及适用的通用 Skill；详细业务事实和通用流程分别由现有领域文档 / Contract 与 Skill 承载。
- 改进现有通用需求澄清 Skill，使它先结合仓库证据判断已知事实，再按需求风险检查关键场景和边界。只有不存在会改变目标、可观察行为、范围、架构 / 安全约束或验收方式的未决问题，才可判定澄清完成。澄清结束时汇总已确认决定、假设、未决问题和有意留给实现阶段的选择。
- 在现有实现工作流中保留任务内的失败修复闭环：执行适用验证，根据失败输出继续定位、修改和重跑；通过或遇到明确阻塞后再结束任务。
- 在任务完成时，根据真实证据识别是否存在可复用的 Harness 缺口。缺口类别为：上下文、事实源、工具、测试、反馈、架构约束、可观测性。重复出现的问题，或一次但证据明确的结构性缺口，可以形成改进建议；由用户决定是否采纳，Codex 不自动修改 Harness 规则或 Skill。
- 通用澄清与实施流程继续使用现有个人 Skills / Plugin，不为 ChatBI 复制通用 Skill，也不新增 ChatBI 项目 Skill。Skill 当前按本地方式维护；本工作不要求上传云端或重建 Skill 仓库。
- 先用一个真实的小范围 Feature 或 Bug Fix 验证流程，再逐步扩展到全仓库上下文治理和 LLM / Retrieval / Evaluation 等高风险代码路径。扩展时沿用现有项目风险门禁，不降低已有审批和验证要求。

## User Stories

- 作为 ChatBI 维护者，我希望 Codex 在澄清需求时能检查重要行为、边界和验收问题是否覆盖，避免太早进入实现。
- 作为 ChatBI 维护者，我希望 Codex 在实现后依据测试和运行反馈继续修复，直到验证通过或清楚说明阻塞。
- 作为 ChatBI 维护者，我希望 Codex 从真实任务中发现 Harness 缺口并提出有证据的改进建议，同时由我决定是否修改工程规则。
- 作为后续维护者，我希望从 `AGENTS.md` 快速找到适用的项目事实源、工作流和验证入口，而不必把通用 Skill 或业务知识重复维护多份。

## Implementation Decisions

- 本工作面向 Codex 编码 Agent，不改变 ChatBI 运行时架构、业务行为或 AI 决策权边界。
- 保留现有 `ask-matt`、`workflow-grill-with-docs`、`workflow-to-spec`、`workflow-implement` 等工作流分工；优先改进现有 Skill，不创建新的通用 Skill 或项目 Skill。
- Spec 锁定可观察行为、范围、成功 / 失败验收、事实源和必要架构 / 安全约束；具体文件、类和步骤由后续 Ticket / 实施计划根据仓库调查确定。
- 反馈触发门槛是“重复出现的问题”或“一次但有明确证据的结构性缺口”。偶发、无证据或不改变后续正确性的偏好不自动形成工程规则。
- Skill 编辑前必须只读确认现有个人工作副本与 Plugin 安装缓存的路径，避免误改缓存或丢失本地改动。该检查不要求先解决云端同步，也不构成本 Spec 的云端发布授权。
- 首次验证采用真实小功能；不以先建设人工 benchmark 为前置条件。若试点触及 Retrieval、LLM、Embedding、Qdrant、Semantic 或 SQL 生成等既有高风险路径，按仓库既有门禁选择验证并遵循所需授权。

## Testing Decisions

- Harness 行为以一次真实小范围 Feature / Bug Fix 作为端到端试点，检查 Agent 是否找到并遵循项目事实源、覆盖重要需求问题、运行适用验证、根据失败反馈修复，并在任务后正确提出或不提出 Harness 改进建议。
- 试点记录实际运行的验证命令、结果、遇到的失败与修复证据；未执行的验证必须明确标记，不得声称通过。
- 若修改确定性脚本、规则检查或测试，增加并运行对应的软件测试 / 自动检查；是否需要新增检查由 Ticket 根据可机械判定的规则决定。
- 涉及 LLM 行为时，Software Test、AI Evaluation、Business Acceptance 和 Real E2E 按变更风险分别判断；遵循 `AGENTS.md` 中现有高风险路径和授权门禁。
- Harness 的第一阶段不要求建立独立的通用 benchmark。真实试点暴露的 Bad Case 可以成为后续回归用例；只有出现可重复、可客观判定的 Skill 行为需求时，才评估独立 Evaluation。

## Out of Scope

- 重构 ChatBI 目录、模块或业务架构。
- 将 `AGENTS.md` 扩写为知识大全，或为追求模板完整性新建大量文档、Skill、脚本、CI 工作流。
- 安装或整体迁移到第三方 Harness Kit / 新 Agent Runtime。
- Codex 未经用户决定就自动修改 Harness、Skills、Contract、规则或发布其变更。
- 改变现有 Feature / Ticket / Design Review / PR / E2E 审批门禁。
- 本 Spec 不包含业务 Feature 实现、云端同步、Git Push、PR 或发布。

## Further Notes

- 此 Spec 已由用户确认，并通过 `workflow-design-review`（`PASS WITH MINOR FIXES`）；三个实施 Ticket 均已完成，具体行为与验证证据见 `issues/`。项目稳定规则仍以 `AGENTS.md` 及其指向的 Architecture、Domain、Engineering、Spec、测试和 Evaluation 事实源为准。
- 两个通用 Skill 的修改位于个人 Plugin 的本地功能 worktree `/home/jojo/Projects/agent-plugins-codex-harness`；仅本地提交，未 Push、未安装到 Codex 缓存。Marketplace 临时目录和安装缓存保持原样。
- 真实试点为 ChatBI `AGENTS.md` 对 Plugin 阶段 Skill 使用简称、与实际 `workflow-*` 名称不一致的 Agent 路由 Bug；修复与走读证据见 `issues/03-chatbi-agents-adapter-and-pilot.md`。
- 没有新增通用 benchmark、自动化脚本或 CI 检查。Skill 结构由 `skill-creator` validator 验证；项目入口按实际路径 / Skill 名称核对并人工走读。后续真实任务若暴露可机械判定且重复的行为要求，再评估是否增加自动 Evaluation 或检查。

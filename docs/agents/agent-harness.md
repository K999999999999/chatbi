# Agent Harness Engineering 项目说明

本仓库采用 Harness Engineering 思路维护 AI Coding Agent 的项目工作环境。这样，后续进入仓库的 AI 不必依赖之前的对话，也能发现项目规则、事实源、验证方式和交付流程。

这里的 Harness 指围绕编码代理组织的仓库知识、工作规则、工具依赖和结果反馈。它是项目协作方式的说明，不是 ChatBI 产品功能的行为 Contract，也不取代下面列出的事实源。

## 从哪里开始

`AGENTS.md` 是本仓库规定的 AI 工作入口，也是项目稳定规则的精简索引。AI 进入仓库后应先读它，再按当前任务读取对应的架构、产品、领域、Spec、验证和交付文档。本文用于解释 Harness 的组成和文档边界；如果本文与 `AGENTS.md` 或对应的事实源不一致，以事实源为准。

## Harness 由什么组成

| 组成 | 仓库位置 | 用途 |
| --- | --- | --- |
| 项目入口与稳定边界 | `AGENTS.md` | 告诉 Agent 应遵循的核心原则和下一步读取位置 |
| 架构、产品与行为事实 | `docs/architecture.md`、`docs/product-scope.md`、`docs/specs/`、`docs/designs/` | 说明系统边界、当前产品范围、行为 Contract 和实现设计 |
| 领域事实读取边界 | `docs/agents/domain.md` | 说明领域任务的事实源读取顺序和文档边界 |
| 工程工作流程 | `docs/agents/issue-tracker.md`、`docs/agents/git-pr-workflow.md` | 说明 `.scratch/` 长期工作记录、本机实时状态、实施门禁、分支、PR 和交付规则 |
| 正确性反馈 | `tests/`、`evaluation/`、`.github/workflows/ci.yml`、`.github/workflows/real-e2e.yml` | 提供确定性测试、AI Evaluation、集成检查和真实 E2E 证据 |
| 本地运行说明 | `docs/runbook.md` | 说明开发环境、服务、数据库、RAG 构建、测试和评测的操作方式 |

ChatBI 产品本身也有模型输出的确定性护栏，例如业务语义解析、授权检查和 SQL Guard。它们属于产品架构；本说明关注的是 AI 如何在这个仓库里安全、可验证地协作开发。

## Workflow Skill 依赖

`AGENTS.md` 中引用的部分 workflow Skill 由 Codex 环境安装的 `engineering-workflow` Plugin 提供，Skill 实现没有复制进本仓库。新环境缺少该 Plugin 时，Agent 应先遵循仓库中已有的 `AGENTS.md` 和 `docs/agents/` 规则；无法执行某个 Skill 专属流程时，说明缺失，不应假设 Skill 已运行。阶段 Skill 可在目标和授权门槛满足时按流程调用；Skill 调用不会代替用户确认完整 Spec、实施范围、关键方案或发布授权。

## 会话状态与恢复

新会话开始时，Agent 检查实时 Git / worktree、长期 `.scratch/` 记录和 Git 公共目录中的本机共享进度，按工作项 ID 与真实 PR 身份核验恢复当前阶段、工作区状态、上次停点和下一步；不能仅按当前 branch 匹配。状态查找与冲突规则见 [`issue-tracker.md`](issue-tracker.md)。Plugin 安装本身不会修改项目规则；要让其他项目获得相同入口，应通过 `setup-engineering-workflow` 检查该项目现有约定，并经用户确认后写入其 Agent instructions。

PR 合并后按 [`git-pr-workflow.md`](git-pr-workflow.md) 执行 Harness 复盘；产品实现缺陷与 Agent 工作环境缺口分别记录，避免相互替代。

## 什么时候更新本文

- 当 `AGENTS.md`、文档地图、工程工作流程、验证入口或 Skill 依赖发生变化，且这些变化让本文的说明不再准确时，更新本文。
- 普通产品功能或业务规则变化，更新它所属的 Spec、Design、Domain 文档、测试、Evaluation 或验收记录；只有 Harness 入口或组成随之改变时才更新本文。
- 不把本文当作每次功能更新的变更日志，也不在这里重复维护各事实源里的规则。

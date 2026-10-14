# 后台执行、取消与流式状态：整理前的过程记录

来源：`docs/specs/execution-streaming-v1.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# R4 执行状态与流式反馈 Spec

Status: 用户确认的行为 Contract；R4 已完成本地实施；最终候选验收状态见 Git 公共目录的本机实时工作状态；远端发布未授权。
Owner: 当前主 Agent
Work item: execution-streaming-v1
Baseline: `2019443020bb7a20a8c3d1a578a613544ad8148b`
Implementation branch: `feat/execution-streaming-v1`

## Problem Statement

R1–R3 已提供电脑端问数、独立经营分析、结果展示及私人历史 / 成果。网页当前等待完整 JSON，仅能显示正在查询或分析；不能实时查看阶段或报告生成，也没有服务端取消接口。断连后后台可能仍执行，页面不能及时获取原执行的进度。

R4 在同一业务链路增加真实执行状态、SSE 反馈、取消与重连，先实现并验收执行状态与最终结果，再实现并验收分析文字真实增量展示。

事实源：[Roadmap](../../../docs/roadmap.md)、[产品范围](../../../docs/product-scope.md)、[Architecture](../../../docs/architecture.md)、[历史领域上下文快照](../../context-file-removal/history/domain-context-snapshot.md)、[R3 Spec](../../../docs/specs/history-results-v1.md)、[R3 Design](../../../docs/designs/history-results-v1.md)、[Query API](../../../docs/specs/query-api.md)、[Web Spec](../../../docs/specs/web-dialogue-v1.md)、[R2 Spec](../../../docs/specs/result-visualization-v1.md)、[Evaluation](../../../docs/specs/evaluation.md)、[Runbook](../../deployment-simplification/history/docs--runbook.md)。R4 确认后扩展网页执行 Contract；旧同步 API 的适用边界保持。

## Compatibility / Migration / Documentation

- `/api/v1/query` 仍为同步 JSON，旧 Bearer 客户端无需迁移；新能力不得意外改变默认查询 / 分析业务行为。
- 既有历史 / 成果、成功上下文、精度、TTL、owner 隔离与 5 MiB 快照限制保持。执行新增状态与存储如需迁移，在 Design 明确幂等升级、旧数据兼容与保留数据回滚。
- 不得通过旧入口或 checkpoint 直接恢复已取消分析，设计需证明共享执行语义的协调；原 API 的正常请求 / 响应兼容不免除防止同 run 冲突。
- 实施 Done When 包含正式 R4 Spec / Design / Acceptance、Query API / Web / R3 受影响 Contract、Architecture / Product Scope、README / Runbook / Roadmap 的维护或不适用理由。
- 本 Spec 是规划期间 R4 行为来源，确认后设计 / Tickets 引用它；正式 `docs/specs/` 在实施交付时承接 Contract，不留互相冲突副本。
- R4 不调整既定路线优先级。R3 文档收尾候选 `d93e7a7` 保留在独立分支，未发布；不把它的变更混入 R4 基线。

## Decision Record / Authorization

用户在本轮逐项确认范围、断连、取消、重启、草稿、重试、可见阶段、API 兼容、安全、SSE、时限、权限失效、并发、文字字段、受理幂等、内部重试与完整验收；上述决定由当前主 Agent 固化。行为 / 权限 / 单进程边界或容量要求变化时重新审视，不由 Legacy / Adapter 反向修改。

用户于 2026-10-05 确认六项 Ticket 拆分及完整 R4 本地实施，包含编码、适用测试 / 真实验收、当前上下文 Code Review 与本地 Commit；远端 Push / PR 和生产部署未授权。整体授权依据与实时阶段见 Git 公共目录 execution-streaming-v1/status.md。

## Contract 与实施状态

本 Spec 是 R4 的正式行为 Contract；实施前的确认、设计审查、Readiness 与 Ticket 拆分记录保留在 [工作目录](..)。实施与验收状态以本地 Git 公共目录 `work-items/execution-streaming-v1/status.md` 为准。该状态记录候选提交、适用验证及真实报告身份；本文件不把历史报告重标为当前候选，也不将本地验收表述为生产部署或远端发布。

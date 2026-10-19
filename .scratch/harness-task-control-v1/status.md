# Harness 改进规划状态

Status: in-progress
Stage: 验证 / Review 完成；Ticket 08 本地验收通过，Commit 收尾中

当前会话已逐项确认通用能力归 engineering-workflow Plugin、ChatBI 首轮适配、工具化状态管理、人工介入规则、3轮 / 30分钟无进展预算、聊天批准候选及显式项目接入方式。

用户已整体确认[Spec](spec.md)。[Design Review](design-review.md)为PASS WITH MINOR FIXES，D1–D4在[设计说明](design.md)中落实并核对；[8项Ticket草案](ticket-drafts.md)的[Readiness](ticket-readiness.md)为READY。用户于 2026-10-19 确认8项拆分并授权整体本地实施、验证、Review和Commit。未获Plugin安装更新、付费调用、Push / PR、远端设置或实验授权。

本目标 ID 为 `harness-task-control-v1`；实时进度以 Git 公共目录下同 ID 的主记录为准。相关问题发现 `long-task-progress-clarity` 保留原生命周期，关联不继承授权，也不提前标记解决。

正式 Tickets 已写入 [issues/](issues/)；Ticket 01–06 已完成本地候选及验证。Ticket 07 完成 ChatBI 阶段 / 动态文件清单、容器适配和旧检查兼容，12 项 adapter 测试通过。Ticket 08 的两仓联合验收、远端只读计划和 Code Review 已通过，证据见 [验收记录](acceptance.md)、[Review](code-review.md) 与 [远端计划](remote-release-plan.md)。Plugin 53 项 unittest 在 Python 3.14.4 与 3.11.16 均通过；ChatBI Python 范围 1118 passed / 61 skipped、无失败或错误，报告保留 incomplete 状态。Hosted CI、安装 / 同步、远端规则和隔离实验均未执行。ChatBI 当前工作区改动归本目标。Plugin 候选位于隔离 worktree，基于已核实远端 master；既有源 worktree及用户 7z 归档保持不动。当前只剩两仓本地 Commit 与提交后状态核对。

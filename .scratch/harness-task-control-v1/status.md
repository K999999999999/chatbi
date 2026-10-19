# Harness 改进规划状态

Status: local-complete
Stage: 本地实现、验证、Review 与 Commit 完成；远端发布 / 安装未授权

当前会话已逐项确认通用能力归 engineering-workflow Plugin、ChatBI 首轮适配、工具化状态管理、人工介入规则、3轮 / 30分钟无进展预算、聊天批准候选及显式项目接入方式。

用户已整体确认[Spec](spec.md)。[Design Review](design-review.md)为PASS WITH MINOR FIXES，D1–D4在[设计说明](design.md)中落实并核对；[8项Ticket草案](ticket-drafts.md)的[Readiness](ticket-readiness.md)为READY。用户于 2026-10-19 确认8项拆分并授权整体本地实施、验证、Review和Commit。未获Plugin安装更新、付费调用、Push / PR、远端设置或实验授权。

本目标 ID 为 `harness-task-control-v1`；实时进度以 Git 公共目录下同 ID 的主记录为准。相关问题发现 `long-task-progress-clarity` 保留原生命周期，关联不继承授权，也不提前标记解决。

正式 Tickets 01–08 均已完成本地实现 / 验收、Review 与 Commit。ChatBI 实现提交 `0e8189bf0eeace38cffdc2ca16debd103e7e1b19`；Plugin 提交 `140f2ef95f611f378047683c379ae3724e4f5826`。验收证据见 [acceptance.md](acceptance.md)、[code-review.md](code-review.md) 和 [remote-release-plan.md](remote-release-plan.md)。Plugin 53 项 unittest 在 Python 3.14.4 与 3.11.16 均通过；ChatBI Python 范围 1118 passed / 61 skipped、无失败或错误，报告保留 incomplete 状态。Hosted CI、Push / PR、安装 / 同步、远端规则和隔离实验均未执行，均不在本次授权内。原 Plugin 源 worktree 与用户 7z 归档保持不动。最终 ChatBI / Plugin HEAD 与工作区状态以 Git 公共目录主实时记录为准。

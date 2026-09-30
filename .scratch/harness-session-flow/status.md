# 工作状态

Status: in-progress
Stage: 实施中

## 当前目标

为 ChatBI 和外置 `engineering-workflow` Plugin 建立可见、可恢复的新会话入口与工作阶段流程。

## 已确认

- 新会话先检查 Git / worktree 与活动工作记录，并播报阶段、工作区状态、上次停点和下一步。
- 小型工程改动使用短 Spec；复杂改动使用完整 Spec 并拆分 Tickets。
- 需求发现与需求澄清是不同阶段；`ask-matt` 不再是每次会话的必经入口。
- 采用 `Ticket` 表示可追踪实施工作项；`Target` 表示目标。历史 Ticket 记录保留。
- 当前分支 / worktree 必须唯一匹配活动状态记录；匹配不唯一时先请用户选择。
- PR 检查与已合并待 Harness 复盘是不同阶段；合并后复盘纳入本次范围。

## 当前进度

- 已创建隔离 worktree：`/home/jojo/Projects/chatbi-engine-session-flow`。
- 当前分支：`codex/harness-session-flow`，基于同步的 `origin/master`。
- Spec 已获用户确认：`.scratch/harness-session-flow/spec.md`。
- Design Review 为 `PASS WITH MINOR FIXES`，已将轻微修订纳入 Spec。
- Ticket 草案已完成只读 readiness review：`READY`；草案位于 `.scratch/harness-session-flow/tickets-draft.md`。
- 用户已确认三项拆分；正式文件位于 `.scratch/harness-session-flow/issues/`。
- Ticket 01 已完成并通过文档链接检查；Ticket 02 正在实施。
- 当前实现基线：`c78cf06c3c37339720f32990ebdca9ea8e7a34a7`；初始 Git 状态只有本工作项 `.scratch/harness-session-flow/` 未跟踪。
- 原工作区中的 Harness 文档改动和 `.scratch/engineering-quality-gates/` 未移动、未修改。

## 未决事项

- Ticket 02：更新 Plugin 的需求发现 / 澄清 / 路由能力。

## 下一步

- 完成 Plugin 源变更、Skill / Plugin 校验和场景走查，再进入 Ticket 03。

# 工作状态

Status: in-progress
Stage: PR 检查中

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
- Ticket 01、02、03 均已完成，Plugin PR 和 ChatBI Draft PR 已创建。
- Plugin PR #1：`https://github.com/K999999999999/agent-plugins/pull/1`，状态 `OPEN`；无 CI checks。
- ChatBI PR #37：`https://github.com/K999999999999/chatbi/pull/37`，状态 `OPEN` / Draft；自动合并检查因 Draft 被跳过。
- ChatBI CI：确定性测试、代码质量、SQL Guard、PostgreSQL 集成、启动 Smoke、Secret scan、静态安全检查通过；Dependency audit 因 `urllib3 2.7.0` 报告 3 个 CVE 失败。该 PR 没有修改依赖文件。
- 当前实现基线：`c78cf06c3c37339720f32990ebdca9ea8e7a34a7`；初始 Git 状态只有本工作项 `.scratch/harness-session-flow/` 未跟踪。
- 原工作区中的 Harness 文档改动和 `.scratch/engineering-quality-gates/` 未移动、未修改。

## 未决事项

- ChatBI Draft PR 的 Dependency audit 未通过；需先决定是否另开依赖升级工作，不应将该 Draft 转为 Ready。

## 下一步

- Review 两个 PR；ChatBI 依赖审计问题解决并所有 required checks 通过后，再由用户决定是否将 Draft 标为 Ready。

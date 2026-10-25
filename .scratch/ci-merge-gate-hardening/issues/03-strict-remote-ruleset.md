# 启用 master 严格更新分支 Ruleset

Status: open
Owner: ChatBI 仓库管理员（用户）；实施执行：本会话 Codex
Change Profile: Lifetime 短期配置变更；Size S；Risk 高（远端合并门禁）；Evidence 远端 Ruleset 完整读回；Delivery 远端，需单独核实写入授权
Canonical Source: `.scratch/ci-merge-gate-hardening/spec.md`；远端 Ruleset `23564531`
Blocked by: Ticket 01、Ticket 02 合入 master 并通过现有 required checks；取得本目标范围的 Ruleset 写入授权。

## What to build

- 写前读取并保存 Ruleset `23564531` 完整快照，核对远端现状未被并发修改。
- 只将 `strict_required_status_checks_policy` 改为 `true`；不新增或删除 required check。
- 保留现有 8 项 required checks 及其 GitHub Actions 来源、Auto-merge、Squash、审批数 0、无 bypass、防强推 / 删除和线性历史。
- 写后读回完整 Ruleset，比对仅 strict 字段变化；核对其他 Open PR 的状态。
- 写入结果不符合预期时按本次快照恢复该字段，不删除整条 Ruleset或临时 bypass。

Owned files: 远端 `github.com/K999999999999/chatbi` Ruleset `23564531`。

## Acceptance criteria

- strict 字段为 true；现有 8 项 contexts 及 App 来源逐项不变；所有其他 Ruleset 字段保持原值。
- Auto-merge、Squash、审批数 0、无 bypass 与强推 / 删除保护维持原状。
- 若执行受控 PR 验证，只在另行授权后进行；不得把故意失败提交推入 master。

Verification evidence: 写前快照、精确 API 更新、写后完整 Ruleset 读回 Diff；受控 PR 结果（若另获授权）。
Migration / Rollback: 并发外部编辑时停止；需要回滚时只恢复本次修改的 strict 字段。
Result: Pending implementation and Ruleset write authorization.
Comments: 不新增 AI evaluation required check；Real E2E 仍由维护者手动运行。

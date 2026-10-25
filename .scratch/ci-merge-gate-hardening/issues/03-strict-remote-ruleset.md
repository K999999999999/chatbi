# 启用 master 严格更新分支 Ruleset

Status: done
Owner: ChatBI 仓库管理员（用户）；实施执行：本会话 Codex
Change Profile: Lifetime 短期配置变更；Size S；Risk 高（远端合并门禁）；Evidence 远端 Ruleset 完整读回；Delivery 远端，需单独核实写入授权
Canonical Source: `.scratch/ci-merge-gate-hardening/spec.md`；远端 Ruleset `23564531`
Blocked by: None (Ticket 01–02 completed; Ruleset write authorization received).

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

Verification evidence: Ruleset `23564531` 完整写前 / 写后快照及字段 Diff；8 个 required status contexts 和 GitHub Actions 来源逐项一致；其他 Ruleset 字段保持不变；写前与写后均无 Open PR。快照保存在本机 Git 公共目录的 `.git/harness/work-items/ci-merge-gate-hardening/`。
Migration / Rollback: 并发外部编辑时停止；需要回滚时只恢复本次修改的 strict 字段。
Result: 用户于 2026-10-25T16:51Z 明确授权后，已将 `strict_required_status_checks_policy` 从 `false` 改为 `true`。Ruleset 完整读回确认只改变该字段，其他规则、8 个 required checks、来源、Auto-merge 配置、审批要求、bypass 和线性历史均未改变。
Comments: 仅要求 PR 基于最新 master；不新增 AI evaluation required check；Real E2E 仍由维护者手动运行。

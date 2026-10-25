# Ticket Readiness Review：CI 与远端合并门禁加固

Ticket Readiness: READY
Scope: `.scratch/ci-merge-gate-hardening/spec.md` 与 `tickets-draft.md`（AI required check已移除）
Change Profile: Ticket 01–02 为本地CI / scripts与PR；Ticket 03为高风险远端Ruleset配置。
Owner: 本地变更由ChatBI维护者（用户）负责、Codex实施；远端Ruleset由仓库管理员（用户）负责授权。

## Findings

- 无未解决的Architecture、Domain、公共Contract、权限或状态决定。用户已明确不加AI评测required check；Real E2E保持手动可用且不参与PR门禁。
- Ticket 01、02可独立实施；Ticket 03依赖二者合入master并通过现有检查，再取得具体远端写入授权。依赖无循环。
- Ticket 01触及`.github/workflows/ci.yml`；Ticket 02复用既有Ruff入口，不必修改CI workflow。两个本地Ticket的Runbook更新位于数据库 / renderer 与Python质量说明部分。
- `docs/remove-roadmap-and-audit`活动分支也修改Runbook的一处观测日志命令；本次Ticket不触碰该段，实施时保留并核对其合并状态。
- Ticket 03只修改远端strict字段；现有8项required checks及其他字段都有明确读回验收。发布授权条件清楚，不属于未决设计。

## Migration / Rollback

- 本地CI / scripts改动可随候选提交回滚。
- Ruleset写前保存完整快照，写后完整读回；并发变化停止，回滚只恢复本次strict字段。
- 不涉及产品运行时、业务数据迁移、Feature Flag或部署。

## Evidence

- 已读取Spec、Design Review、Ticket草案、Runbook、Evaluation Spec、Git / PR流程、架构 / 产品范围，以及现有CI、Ruff入口、报告工具和相关测试文件。
- 接受标准对应确定性报告核验、PostgreSQL / renderer hosted CI、Python质量检查和Ruleset读回。
- 本Review未运行Software Test或真实AI Evaluation；当前无实现验证结果。

Next: 用户确认3项Ticket拆分；确认后写入正式Ticket，并按依赖连续实施。远端Ruleset写入仍需候选完成后的具体授权。

# 将 scripts 纳入现有 Ruff 质量门禁

Status: implemented locally; hosted verification pending
Owner: ChatBI 维护者（用户）；实施执行：本会话 Codex
Change Profile: Lifetime 短期；Size S；Risk 低；Evidence 本地质量检查 / hosted CI；Delivery 本地 PR
Canonical Source: `.scratch/ci-merge-gate-hardening/spec.md`；`docs/runbook.md`
Blocked by: None (can start immediately)

## What to build

- 将 `scripts/` 加入现有固定 Ruff 版本的 format 和 lint 范围，保持现有规则和统一本地 / CI 入口。
- 只做通过新覆盖范围所必需的格式及明确静态修复，不扩大为全仓类型系统或业务逻辑重构。
- 更新 Runbook 中 Python 质量检查范围的说明。

Owned files: `scripts/check_python_quality.sh`；必要的 `scripts/*.py` 格式修复；`docs/runbook.md` 的质量检查说明部分。

## Acceptance criteria

- 固定 Ruff 版本、现有 lint selectors 和调用入口不变；`scripts/` 同时受 format 与 lint 检查。
- 本地和 GitHub CI 继续使用同一脚本；`scripts/` 质量失败会阻止 required `Code quality` 通过。

Verification evidence: `./dev check python`、Ruff 目标目录检查、CI `Code quality`。
Migration / Rollback: 不适用；修改可随候选提交回滚。
Result: `scripts/`已纳入固定Ruff入口；全目录格式与lint、本地Python确定性套件通过。Hosted CI证据待取得发布授权后验证。
Comments: 不新增类型检查，也不重构业务逻辑。

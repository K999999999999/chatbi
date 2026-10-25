# Design Review：CI 与远端合并门禁加固

Review: PASS
Review Target: `.scratch/ci-merge-gate-hardening/spec.md` at base `64d2eae`
Reviewed: 2026-10-25

## Findings

无未解决的设计问题。用户将范围明确收窄为三项：必跑 PostgreSQL / renderer 证据校验、scripts Ruff 覆盖、远端要求分支更新到最新 master。AI Evaluation 不加入required check；现有 Real E2E 仍由用户手动运行，不改变其评测 Contract。

## 设计判断

- CI报告消费者检查真实测试计数、failure / error / skip 和证据一致性，不改变 `scripts.verification_report` 的退出码 Contract。
- scripts质量复用现有固定Ruff版本、规则和入口，仅扩大目录范围。
- 远端只切换 `strict_required_status_checks_policy`；保留现有8项 required checks / App来源、Squash Auto-merge、审批数0、无 bypass 和现有保护规则。
- 远端写入在本地候选形成后进行，写前完整快照、写后完整读回；具体写入授权仍需按仓库发布流程核实。
- 不增加服务、App、付费自动评测或产品运行时改动。

## Evidence Sources

- `AGENTS.md`、`docs/agents/git-pr-workflow.md`、`docs/agents/documentation.md`、`docs/agents/issue-tracker.md`。
- `docs/architecture.md`、`docs/product-scope.md`、`docs/runbook.md`。
- `.github/workflows/ci.yml`、`scripts/check_python_quality.sh`、`scripts/verification_report.py`、PostgreSQL / renderer 相关测试与artifact入口。
- 只读远端事实：Ruleset `23564531` 的8项required checks、GitHub Actions integration `15368`、`strict=false`和Squash Auto-merge。

## Architecture Knowledge Core

此前已读取。收窄后的方案不新增 Module、Service、Provider 或运行时边界；复用现有CI / 报告机制，失败证据由确定性代码判定，远端修改采用快照与读回保证可恢复。

Next: workflow-to-tickets 草案与当前上下文 Ticket Readiness。

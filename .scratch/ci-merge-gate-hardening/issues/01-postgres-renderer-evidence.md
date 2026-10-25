# 阻止不完整的 PostgreSQL / renderer 证据通过 CI

Status: done
Owner: ChatBI 维护者（用户）；实施执行：本会话 Codex
Change Profile: Lifetime 短期；Size M；Risk 中；Evidence 确定性软件测试 / hosted CI；Delivery 本地 PR
Canonical Source: `.scratch/ci-merge-gate-hardening/spec.md`；`docs/runbook.md`
Blocked by: None (can start immediately)

## What to build

- 在现有 CI 中核对 PostgreSQL CI、development 两个 JUnit 文件存在、结构有效、各自运行非零测试且无 failure、error 或 skipped。
- 核对 renderer JSON 摘要与 JUnit 相符：状态 passed、退出码为 0、有真实非零计数、无失败 / 错误 / 跳过 / 缺失产物且身份可信。
- 只在 CI 消费侧判定现有验证报告；不改变 `scripts.verification_report` 生成报告后返回 0 的 Contract。
- 更新 Runbook 中 CI 必跑测试及报告判定说明。

Owned files: `.github/workflows/ci.yml`；必要时新增 `scripts/` 报告核验工具；相关 `tests/scripts/`；忽略生成的 `reports/ci/` 证据目录；`docs/runbook.md` 的测试说明部分。

## Acceptance criteria

- 缺失、损坏、零计数、skip、failure / error、摘要与 XML 不一致分别失败；有效非零报告通过。
- PostgreSQL 两个 profile 独立核验，不以另一个 profile 通过代替缺失证据。
- 不固定 5 / 63 / 2 等当前数量；不改变普通确定性套件中有明确原因的条件性 skip。

Verification evidence: 核验器确定性测试；PostgreSQL 两个 profile 与 renderer hosted 产物；差异化失败报告。
Migration / Rollback: 不适用；CI 脚本 / job 可随候选提交回滚。
Result: PR #99 已于 2026-10-25T16:38:21Z 合入 master（merge commit `480adf94b34e6eb10406f5229b192e679e06ad88`）。首轮 Hosted run `40211914522` 发现 CI 生成的 `reports/ci/` 未被忽略；follow-up `d82f87b1339a0194e258019bd1eb61604ab8730e` 增加忽略规则和回归测试。二轮 Hosted run `40212394127` 的 PostgreSQL integration 与 renderer 证据核验通过，8 项 required checks 全部成功。
Comments: Real E2E 不纳入本 Ticket 的 PR required checks。CI 环境记录的提交、`uv.lock`摘要和测试镜像ID与renderer摘要逐项核对；核验器继续要求源码身份未变化。

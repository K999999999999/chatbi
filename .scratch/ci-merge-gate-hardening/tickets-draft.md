# Ticket 拆分草案：CI 与远端合并门禁加固

Status: 用户已于 2026-10-26 确认三项拆分；正式 Ticket 已写入 `issues/`。
Spec: `.scratch/ci-merge-gate-hardening/spec.md`
Design Review: `.scratch/ci-merge-gate-hardening/design-review.md` — PASS
Branch / Worktree: `chore/ci-merge-gate-hardening` / `/home/jojo/Projects/chatbi-ci-gates`

## Ticket 01：阻止不完整的 PostgreSQL / renderer 证据通过 CI

Change Profile: Lifetime 短期；Size M；Risk 中；Evidence 确定性软件测试 / hosted CI；Delivery 本地 PR。
Owner: ChatBI 维护者（用户）；实施：Codex；Backup Owner: 未指定；Owner变化时回到用户核实。
Blocked by: None (can start immediately)

What to build:

- 在现有 CI 中核对 PostgreSQL CI、development 两个 JUnit 文件存在、结构有效、各自运行非零测试且无 failure、error 或 skipped。
- 核对 renderer JSON 摘要与 JUnit 相符：状态 passed、退出码为0、有真实非零计数、无失败 / 错误 / 跳过 / 缺失产物且身份可信。
- 只在 CI 消费侧判定现有验证报告；不改变 `scripts.verification_report` 生成报告后返回0的 Contract。
- 更新 Runbook 中 CI 必跑测试及报告判定说明。

Owned files: `.github/workflows/ci.yml`；必要时新增 `scripts/` 报告核验工具；相关 `tests/scripts/`；`docs/runbook.md` 的测试说明部分。

Acceptance criteria:

- 缺失、损坏、零计数、skip、failure / error、摘要与XML不一致分别失败；有效非零报告通过。
- PostgreSQL两个profile独立核验，不以另一个profile通过代替缺失证据。
- 不固定5 / 63 / 2等当前数量；不改变普通确定性套件中有明确原因的条件性skip。

Verification evidence: 核验器确定性测试；PostgreSQL两个profile与renderer hosted产物；差异化失败报告。
Migration / Rollback: 不适用；CI脚本 / job可随候选提交回滚。
Done When: 接受标准通过，Runbook相关说明和链接检查完成，Review与Diff检查通过。

## Ticket 02：将 scripts 纳入现有 Ruff 质量门禁

Change Profile: Lifetime 短期；Size S；Risk 低；Evidence 本地质量检查 / hosted CI；Delivery 本地 PR。
Owner: ChatBI 维护者（用户）；实施：Codex；Backup Owner: 未指定；Owner变化时回到用户核实。
Blocked by: None (can start immediately)

What to build:

- 将 `scripts/` 加入现有固定Ruff版本的format和lint范围，保持现有规则和统一本地 / CI入口。
- 只做通过新覆盖范围所必需的格式及明确静态修复，不扩大为全仓类型系统或业务逻辑重构。
- 更新 Runbook 中Python质量检查范围的说明。

Owned files: `scripts/check_python_quality.sh`；必要的 `scripts/*.py` 格式修复；`docs/runbook.md` 的质量检查说明部分。

Acceptance criteria:

- 固定Ruff版本、现有lint selectors和调用入口不变；`scripts/` 同时受format与lint检查。
- 本地和GitHub CI继续使用同一脚本；`scripts/`质量失败会阻止required `Code quality`通过。

Verification evidence: `./dev check python`、Ruff目标目录检查、CI `Code quality`。
Migration / Rollback: 不适用；修改可随候选提交回滚。
Done When: 新覆盖范围通过，必要格式修复及Runbook更新完成，Review与Diff检查通过。

## Ticket 03：启用 master 严格更新分支 Ruleset

Change Profile: Lifetime 短期配置变更；Size S；Risk 高（远端合并门禁）；Evidence 远端Ruleset完整读回；Delivery 远端，需单独核实写入授权。
Owner: ChatBI 仓库管理员（用户）；实施：Codex；Backup Owner: 未指定；Owner变化时回到用户核实。
Blocked by: Ticket 01、Ticket 02 合入master并通过required checks；取得本目标范围的Push / PR / Ruleset写入授权。

What to build:

- 写前读取并保存Ruleset `23564531`完整快照，核对远端现状未被并发修改。
- 只将`strict_required_status_checks_policy`改为`true`；不新增或删除required check。
- 保留现有8项required checks及其GitHub Actions来源、Auto-merge、Squash、审批数0、无bypass、防强推 / 删除和线性历史。
- 写后读回完整Ruleset，比对仅strict字段变化；核对其他Open PR的状态。
- 写入结果不符合预期时按本次快照恢复该字段，不删除整条Ruleset或临时bypass。

Owned files: 远端 `github.com/K999999999999/chatbi` Ruleset `23564531`。

Acceptance criteria:

- strict字段为true；现有8项contexts及App来源逐项不变；所有其他Ruleset字段保持原值。
- Auto-merge、Squash、审批数0、无bypass与强推 / 删除保护维持原状。
- 若执行受控PR验证，只在另行授权后进行；不得把故意失败提交推入master。

Verification evidence: 写前快照、精确API更新、写后完整Ruleset读回Diff；受控PR结果（若另获授权）。
Migration / Rollback: 并发外部编辑时停止；需要回滚时只恢复本次修改的strict字段。
Done When: 取得所需远端授权，Ruleset完整读回通过，远端结果与残余限制记入实时工作状态。

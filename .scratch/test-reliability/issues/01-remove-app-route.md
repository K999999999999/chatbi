# 01 移除独立 APP 路线，保留 dev 与资源保护

Status: done
Canonical Source: [Spec](../spec.md)、[Design](../design.md)、[草案](../tickets-draft.md#01-移除独立-app-路线保留-dev-与资源保护)
Owner: 当前主 Agent
Change Profile: 单次退役；中等范围 / 中等风险；CLI、装配、专属构建、测试和文档闭环；无真实数据迁移。
Blocked by: None (can start immediately)

## What to build

移除 APP 正向命令 / 目标、专属 Compose / Dockerfile / 验收器和配置；无效调用必须在 Docker、SQL 或账号操作前失败。保留 dev 开发与测试镜像、前端静态构建 / startup smoke、公共 Python app、数据库角色，以及拒绝旧 APP 容器的目标校验。同步当前支持范围、恢复 / 容器 Contract、README / Runbook / Roadmap；归档独有历史内容并修复失效引用。

Owned files: `dev`、`.env.example`、`scripts/dev_environment.sh`、`scripts/dev_maintenance.sh`、`scripts/dev_compose.py`、`scripts/verify_container_app.sh`（删除）、根 `Dockerfile`（删除）、`docker-compose.app.yml`（删除）、`src/bootstrap/commands.py`、`src/bootstrap/doctor.py`、`src/bootstrap/admin_recovery.py`、`src/bootstrap/verification.py`（删除）、`src/authorization/auth_service.py` 的恢复环境限制；`tests/scripts/test_container_application.py`（删除）、`tests/scripts/test_container_dev.py`、`tests/scripts/test_dev_maintenance.py`、Bootstrap / Authorization 对应测试；README、`docs/agents/documentation.md`、架构 / 产品 / 路线图 / Runbook / Bootstrap / 容器 / 恢复 Contract、APP Contract 历史归档及受影响历史 Markdown。

Out of Scope: 删除或改写旧审计；删除本机 APP 容器、镜像、卷、配置、资产或备份；移除 dev 镜像、Dev Container、静态构建、来源码启动 smoke、公共 Python app、数据库角色、运行时保护。

## Acceptance criteria

- `app`、`verify app`、`doctor app`、`recover-admin app` 及相应底层新请求拒绝，且不触发 Docker / SQL / 账号操作；既有历史审计不改写。
- dev 对旧 APP / Stable 或未知资源仍拒绝；合法开发目标、诊断、恢复选择回归通过，不修改实际账号。
- Compose 实际解析，定向 scripts / bootstrap / authorization 回归和保留构建入口检查通过；残留 APP 文本经引用检索逐项归属。
- 正式事实源同步，独有历史已归档并修复链接；本机旧资源保持不变。

Migration / Rollback: 退役入口不自动映射为 dev；代码切片可由 Git 恢复，真实卷 / 配置 / 资产不迁移或删除。

## Result

Code Review: PASS；没有发现需修改的正确性或范围问题。TDD Red 阶段的回归用例曾暴露 9 处失败，包括旧 APP 路由仍触发操作、恢复目标校验晚于密码哈希；修复后 Green 阶段通过。

Verification: `uv run --locked pytest -q tests/scripts/test_container_dev.py tests/scripts/test_dev_maintenance.py tests/bootstrap/test_commands.py tests/bootstrap/test_admin_recovery_command.py tests/bootstrap/test_doctor.py tests/authorization/test_admin_recovery.py`（78 passed）；开发 Compose `config --quiet`（exit 0）；`bash -n dev scripts/dev_environment.sh scripts/dev_maintenance.sh`、Ruff format / check、`python3 -m scripts.check_documentation` 和 `git diff --check` 均通过。构建入口测试确认 `./dev build` 仍只构建 `api` / `web` 开发镜像。

Commit: `8a657dfb8df19bf0f2ff62af83ca20aa2798adb3`（Ticket 完成时为本地提交，后续随目标汇总至 [PR #86](https://github.com/K999999999999/chatbi/pull/86)）；没有修改本机镜像、容器、卷或备份。

## Comments

本 Ticket 不改变首次改密、账号权限、SQL Guard 或业务问数行为。

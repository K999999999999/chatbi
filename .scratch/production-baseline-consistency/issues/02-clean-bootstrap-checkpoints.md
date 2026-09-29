# 全新环境初始化 Business Analysis checkpoint

Status: done
Owner: ChatBI 仓库维护者
Backup Owner: None
Blocked by: None (can start immediately)

## Change Profile

- Lifetime: 长期维护的 PostgreSQL 初始化和健康检查行为。
- Size: M，涉及 Docker 初始化脚本、Control DB migration、权限和 Runbook。
- Risk: 高；缺失 checkpoint 表会使 Business Analysis 在全新环境无法安全运行。
- Evidence: migration 单元 / 集成测试、空 PostgreSQL volume 初始化和 clean-clone 全流程验收。
- Delivery: 同一 Feature branch 内独立切片；不改变管理员创建、安全和业务行为。

## Canonical Source

- 行为 Contract：`../spec.md`。
- 当前 Control DB 初始化实现：`src/chatbi_control/database.py`、`src/chatbi_control/cli.py`。
- 初始 SQL：`database/init/`、`database/control/`。
- 初始化和恢复说明：`docs/runbook.md`。

## What to build

让仓库的首次 PostgreSQL / Control DB 初始化在完成时应用当前 Control DB migrations，安装 LangGraph `PostgresSaver` 所需 checkpoint 表和运行权限。初始化健康检查必须验证这些关键对象，不能只凭旧的 migration 版本或 PostgreSQL 进程健康报告可用。

把首次初始化、健康检查和 Runbook 步骤编排为一条从 clean clone 可完成的路径。不得出现健康检查等待 checkpoint migration，而 migration 命令又等待数据库健康的相互阻塞。首次初始化不创建管理员；管理员仍使用现有显式安全命令创建。

## Acceptance criteria

- 全新 PostgreSQL volume 按 Runbook 初始化后，Control DB 所需 migration、LangGraph checkpoint 表和运行权限均存在。
- 缺少任一必需 checkpoint 表、migration 状态或权限时，健康检查失败，不报告初始化完成。
- 从 clean clone 执行文档步骤可以完成数据库初始化并使服务健康；初始化命令顺序不会因 healthcheck 和 migration 相互等待而死锁。
- 应用运行账号仅获得现有业务所需权限；迁移身份不进入 API 运行配置。
- 首次初始化不自动创建管理员；重复执行初始化不会重复播种业务数据、创建额外首位管理员或破坏既有 Control DB 数据。
- 日常 PostgreSQL restart 不重新初始化数据库或移除 checkpoint 状态。
- Runbook 清楚区分首次启动、更新 migration、管理员创建和数据库重置后的恢复顺序。

## Owned files

- `database/init/10_chatbi_dev_environment.sh`、`database/init/healthcheck.sh` 及必要的初始化编排。
- `src/chatbi_control/database.py`、`src/chatbi_control/cli.py`（仅在复用现有 migration 入口所需的最小范围内）。
- `tests/chatbi_control/`、必要的数据库初始化集成测试。
- `docs/runbook.md` 的首次初始化和重置步骤。

## Validation evidence

- 确定性测试验证 checkpoint schema 安装、幂等性、权限和缺失时的失败行为。
- 在全新 PostgreSQL volume 上运行完整初始化，确认 `checkpoints`、`checkpoint_blobs`、`checkpoint_writes` 及版本表可用。
- 删除测试环境中的 checkpoint 表或撤销必要权限，确认健康检查失败；恢复后确认健康。
- 执行 clean-clone 文档全流程及数据库重启验证；不删除或改写其他 Compose 项目或 PostgreSQL 数据。

## Migration / Rollback

- 对已有 Control DB 只应用幂等 migration / checkpoint setup，不重置用户、Session、审计或业务数据。
- 回滚初始化脚本时不自动删除已有 checkpoint 表或数据；健康检查不能因回滚而误报 Business Analysis 可用。

## Done When

全新数据库初始化完成后，Business Analysis 所需 checkpoint 表和权限已就绪；健康检查能准确报告缺失；Runbook 的 clean-clone 初始化无阻塞且可复现。

## Result

已完成。PostgreSQL 容器 healthcheck 和 API 的 Control DB startup check 均验证 Control DB v2、LangGraph checkpoint 表 / migration 记录及 `chatbi_control_user` 所需权限。clean bootstrap 与 PostgreSQL reset 都先等待 Sales Mart Seed 和 Control DB 基础 migration 完成，再运行 `src.chatbi_control migrate`，最后等待完整健康；这避免 `pg_isready` 早于 Docker 初始化脚本完成时的竞态，也避免 migration 与 healthcheck 相互等待。

验证证据：

- 确定性测试：22 passed；development PostgreSQL 集成测试：18 passed。
- 使用独立 Compose project 和 5543 端口验证空 volume 初始化、migration 后 healthy；撤销 checkpoint 权限后 API Schema 检查拒绝且容器变为 unhealthy；恢复权限后容器恢复 healthy。另一次隔离初始化在 PostgreSQL restart 后仍保留全部四张 checkpoint 表并恢复 healthy；第三次隔离运行验证 `reset_dev_postgres` 自身完成 volume 重建、migration 和 healthcheck。所有临时 Compose project 的 volume 和容器随后均已删除。
- 当前开发数据库执行幂等 migration 后，原数据卷健康恢复；未重置数据库或删除用户数据。
- Ruff CI 子集、Shell 语法检查通过。

## Comments

- 当前 `src.chatbi_control migrate` 已调用 `PostgresSaver.setup()` 并安装运行权限；优先复用该路径，避免复制 LangGraph migration SQL。

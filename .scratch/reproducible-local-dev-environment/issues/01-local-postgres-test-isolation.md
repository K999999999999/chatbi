# 本地 PostgreSQL 集成测试隔离

Status: done
Owner: ChatBI 仓库维护者
Backup Owner: None
Blocked by: None (can start immediately)

## Change Profile

- Lifetime: 短期，本地测试入口和对应说明。
- Size: S。
- Risk: 中；当前 opt-in 测试会从进程环境读取 PostgreSQL 连接配置。
- Evidence: 确定性测试、临时 PostgreSQL 集成测试、退出清理验证。
- Delivery: 当前 Feature branch 上的独立逻辑切片；不修改生产查询逻辑。

## Canonical Source

- 行为基线：`../spec.md`。
- 测试 fixture：`database/ci/bootstrap.sql`，只用于临时测试数据库和 CI。
- 本 Ticket 不改变 CI fixture 的测试专用定位。

## What to build

提供一个本地 PostgreSQL 集成测试命令，自动创建独立、临时的 PostgreSQL 测试实例，加载现有 CI fixture，运行当前由 `RUN_DATABASE_TESTS=1` 启用的数据库集成测试，并在成功、失败或中断时清理自己创建的资源。测试入口不得加载开发者 `.env` 后直接连接日常开发数据库。

更新 Runbook 的本地数据库集成测试说明，使测试目标、启动方式和自动清理行为明确。

## Acceptance criteria

- 本地测试命令只连接本次创建的临时 PostgreSQL 实例；Docker 不可用或初始化失败时明确失败，不回退到 `.env` 指定的服务。
- 测试正常结束、测试失败和启动中断后，临时实例均可清理；清理范围不包含日常开发 PostgreSQL / Qdrant volume 或其他 Compose 项目。
- 本地集成测试继续使用 `chatbi_app` 只读角色和 CI fixture；CI 当前已有的临时 PostgreSQL 生命周期保持隔离。
- 单元测试仍可在不启动 PostgreSQL 的情况下运行。

## Owned files

- `scripts/run_database_tests.py`（新增本地隔离测试入口）
- `tests/scripts/test_run_database_tests.py`（隔离入口确定性测试）
- `tests/online_query/test_database_integration.py`
- `tests/online_query/test_service_integration.py`
- `docs/runbook.md`（数据库测试说明）

## Validation evidence

- 运行确定性测试，不需要配置 `.env` 或本地数据库。
- 在临时 PostgreSQL 上运行两个 `RUN_DATABASE_TESTS` 集成测试类。
- 验证失败退出后临时测试资源被清理，日常开发服务仍可用且未被访问。

## Migration / Rollback

不迁移任何数据库。回滚测试入口和文档即可；测试 runner 只清理自身创建的临时资源。

## Done When

开发者有一个可重复执行的本地数据库集成测试命令，且测试不依赖或修改日常开发数据库。

## Result

真实验收中先发现 CI fixture 路径与只读 bind mount 目标不一致；增加回归测试并修正为 `/workspace/database/ci/bootstrap.sql`。最终 Windows 与 WSL/Linux 的默认 CI fixture profile 各通过 `5/5`，Windows 与 WSL/Linux 的 development profile 各通过 `15/15`。所有 runner 使用隔离的一次性 PostgreSQL，结束后容器清理；原 `chatbi-engine` 服务保持健康。临时失败 / 中断清理的确定性用例通过。最终全量回归为 `489 passed, 12 skipped, 123 subtests passed`。

## Comments

- 当前 `docs/runbook.md` 的 opt-in 命令使用 `.env`，测试通过 `PsycopgQueryExecutor.from_env()` 连接；需要将本地测试路径改为隔离实例。

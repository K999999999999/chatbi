# PostgreSQL 开发环境初始化与重置

Status: done
Owner: ChatBI 仓库维护者
Backup Owner: None
Blocked by: 01-local-postgres-test-isolation

## Change Profile

- Lifetime: 短期，开发 PostgreSQL 初始化、Seed 和重置行为。
- Size: L；包含 Sales Mart、Control DB 和同一实例的首次初始化闭环。
- Risk: 高；涉及 named volume、权限、迁移和可删除的本地数据。
- Evidence: 隔离 PostgreSQL 集成测试、从空 volume 初始化、重启及重置恢复验收。
- Delivery: 当前 Feature branch 上的逻辑切片；不变更生产查询逻辑或业务指标。

## Canonical Source

- 行为基线：`../spec.md`。
- 正式 Sales Mart / Control DB Schema 和指标定义继续以仓库现有 DDL、migration 与 semantic 源文件为准。
- `database/ci/bootstrap.sql` 继续是 CI / 测试 fixture，不作为开发 Seed。

## What to build

将 PostgreSQL 运行数据改为当前 Compose 项目的 named volume。从空 volume 首次启动时建立 `chatbi_mvp`、完整 Sales Mart Schema、确定性合成开发 Seed、Sales Mart 角色与权限，并初始化同一 PostgreSQL 服务中的 `chatbi_control` Schema、固定 RBAC、运行账号和 grants。

Control DB Schema / RBAC / grants 自动、可重复初始化，但不自动创建管理员。把首次管理员创建保留为单独、显式的一次性安全操作；复用现有 migration、`seed_rbac` 和隐藏密码输入能力，不提供仓库默认密码。

提供 PostgreSQL 独立重置方式：只删除当前 Compose 项目的 PostgreSQL named volume，随后可按首次初始化流程恢复。普通 `docker compose up` 不清空、不重播 Seed。

## Acceptance criteria

- 全新项目 PostgreSQL volume 首次初始化后，`chatbi_mvp` 和 `chatbi_control` 均可用；Sales Mart 查询、Control DB migration、应用账号和 grants 均符合 Spec。
- 开发 Seed 仅为合成数据，输入、ID、日期固定时可重复生成；覆盖已确认的时间、维度、状态、订单 / 明细和指标分布需求。
- `chatbi_app` 只能只读查询 Sales Mart；Control DB 运行用户只具有应用所需权限；migration 身份不进入应用运行进程。
- 日常 Compose restart 不会重播 Seed 或改变数据摘要；重复初始化的控制 Schema / RBAC 操作保持幂等。
- 首次自动初始化不创建管理员。显式安全命令可创建首个管理员，重复创建会失败；密码不以默认值写入 Compose、Seed、日志或 Git。
- PostgreSQL 重置只移除当前项目 PostgreSQL 数据卷，不删除 Qdrant 数据卷、其他 Compose 项目数据或旧 W11 目录。
- `database/ci/bootstrap.sql` 保持测试 fixture，不被升级成日常开发 Seed。

## Owned files

- `docker-compose.yml`
- `.env.example`
- `database/sales_mart/`、`database/control/`，以及新增的 `database/dev/seed_sales_mart.sql`
- `src/chatbi_control/cli.py`、`src/chatbi_control/database.py` 及必要的 Control DB bootstrap 代码
- `tests/chatbi_control/` 及新增的 PostgreSQL 开发初始化集成测试
- `docs/runbook.md`（PostgreSQL 初始化、日常启动、管理员创建和重置说明）

## Validation evidence

- 确定性测试验证 Seed 重复性、数据质量分布、Control DB migration / RBAC 幂等性及管理员一次性创建。
- 使用临时测试实例验证 `chatbi_app` 只读、Control DB 权限最小化和初始化失败行为。
- 在临时 Compose 项目及空 volume 上验证首次初始化、日常 restart 和 PG-only reset / recovery。
- 按仓库规则检查 `.env`、数据库物理数据和真实 Secret 未进入 Git。

## Migration / Rollback

- 不迁移、读取、覆盖或删除旧 `data/postgres` 与 W11 旧数据。
- 新重置命令只能删除当前 Compose 项目的 PostgreSQL named volume，不得使用会同时删除 Qdrant volume 的清理方式。
- 回滚代码配置后不自动删除新 volume；删除开发库必须通过本 Ticket 提供的显式重置行为。

## Done When

从空 PostgreSQL named volume 可按仓库流程恢复完整 Sales Mart 和 Control DB；日常启动保持数据；数据库重置边界和恢复结果均可验证。

## Result

Windows 与 WSL/Linux 的独立空 named volume 均完成首次初始化和健康检查：建立 `chatbi_mvp`、`chatbi_control`、Sales Mart schema、Control schema/RBAC、运行角色与授权。最终还从最新提交创建 clean clone，以 `.env.example` 生成本地配置和全新卷初始化成功。验收发现 Windows `core.autocrlf=true` 会把数据库 shell 初始化脚本转换成 CRLF，导致 Alpine shebang 失败；新增 `.gitattributes` 为 `database/init/*.sh` 固定 LF，并从 clean clone 实测通过。验证了 731 个日期、8 个客户、8 个产品、6 个区域、1166 条销售明细，以及销售额、成本、毛利、毛利率和年/季/月/日分组查询；`chatbi_app` 查询成功且无写权限，Control DB 运行账号可读固定 RBAC。PostgreSQL-only reset/recovery 已实测，Qdrant volume 保持；日常重启前后数据 Hash 稳定。Seed `chatbi-sales-mart-dev-v1`，实际摘要 Hash 为 `b727094dcd4fc3e285f483366949ef95527021e1e50092e9bd183c53d9d9c637`。首个管理员仍由显式命令创建，无仓库默认密码。

## Comments

- 当前 `src/chatbi_control/cli.py` 在同一命令中执行 migration 和创建管理员；需要将自动数据库初始化与显式管理员操作分开。

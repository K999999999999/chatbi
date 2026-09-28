# 03 中文化本地演示 Seed 并采用开发库全量重置

- Status: in-progress
- Owner: ChatBI Agent
- Blocked by: None (can start immediately)
- Change Profile: PostgreSQL 开发 Seed、metadata、初始化检查、RAG 资产和 Runbook；高风险；数据库集成测试、RAG 检索 Evaluation 与本地运行流程验收

## What to build

将本地演示 Seed 中客户名称、产品名称、客户类型、行业、国家及对应 `columns.json` 字段值示例改为中文。保留 Schema / 表 / 列标识、订单状态机器码、币种代码、区域代码及来源系统标识等技术值。所有数值事实、日期、键值、金额、数量、状态分布及固定 Business Analysis 评测结果保持不变。

Seed 版本从 `chatbi-sales-mart-dev-v2` 升级到新版本。已有本地开发环境采用现有 PostgreSQL 开发环境全量重置并重新初始化，不实现 v2→v3 定向迁移。

## Scope

- 更新开发 Seed 的用户可见文本和 Seed 版本。
- 同步 `columns.json` 中对应的 `value_examples`，保持其与 Seed 维表成员一致。
- 更新初始化 healthcheck、数据库测试 harness 中固定的 Seed 版本断言，以及 Runbook 的重置 / 重建步骤。
- 明确 PostgreSQL 重置会清除 `chatbi_mvp` 和 `chatbi_control` 的本地数据、管理员、账号、Session 和审计记录；管理员重置后须显式重建。
- 明确 PostgreSQL 重置不清理 Qdrant；必须按 Runbook 重新构建、验证并发布和新 metadata 匹配的 RAG 资产。
- 处理 Seed 文本引起的数据指纹变化：数值参考 SQL 结果应保持相同；旧 Baseline 报告保留为历史记录，并在新 Seed 上生成新的验证报告。

## Out of Scope

- 为共享、生产或需保留数据的环境实现自动迁移。
- 修改 CI-only Fixture、API / SQL 标识、机器码、业务计算、数值事实或黄金案例预期。
- 自动执行开发环境数据库重置，或在实施过程中清除任何用户数据库 / Qdrant volume。

## Acceptance criteria

- 新空 PostgreSQL volume 初始化后 Seed 版本为新版本，目标演示文本为中文，技术标识仍保持既有英文值。
- Seed 与 `columns.json` 的受管维度 `value_examples` 一致；确定性测试验证翻译范围及代码值保留。
- 数值、主键、日期、金额、数量、状态分布和固定 BA 案例参考 SQL 结果与修改前一致。
- PostgreSQL 初始化健康检查及数据库测试 harness 接受新 Seed 版本。
- Runbook 清晰记录 PostgreSQL 全量重置的数据清除范围、重置后显式创建管理员、Qdrant 不受影响以及重新构建 / 发布 RAG 的操作。
- 在新 Seed / metadata 上 RAG 构建和检索 Evaluation 可验证；不得把旧索引视作已更新。
- 不执行真实数据库或 Qdrant 重置；若验收需要对本地 volume 做破坏性操作，先另行取得明确授权。

## Owned files

- `database/dev/seed_sales_mart.sql`
- `database/init/healthcheck.sh`
- `scripts/run_database_tests.py`
- `src/structure/generated/columns.json`
- `tests/metadata/test_dev_seed_dimension_examples.py` 及必要的数据库初始化 / 集成测试
- `docs/runbook.md`
- 如新数据需要新检索验收证据，使用新的 RAG / Evaluation 报告，不覆盖旧 Baseline。

## 验证证据

- Seed / metadata 针对性测试：中文范围、机器码保留、维表成员与 `value_examples` 一致。
- 数据库初始化测试：Seed 新版本、表与权限健康检查通过；SQL 参考结果及固定 BA 数值断言未变化。
- RAG Offline Build 与检索 Evaluation：新资产完整校验并成功发布，能够检索到中文演示名称。
- Runbook 操作步骤和数据清除边界经 Diff Review 核对。依仓库风险规则，在 candidate 确认后执行对应本地真实链路验证。

## Migration / Rollback

- 不提供保留数据的迁移。仅支持可丢弃的本地开发 / 演示 PostgreSQL volume 全量重置。
- 重置不可恢复 `chatbi_mvp` / `chatbi_control` 内旧开发数据、管理员、Session 和审计记录；重置前使用者必须确认该环境数据可丢弃。
- Qdrant volume 不随 PostgreSQL 重置删除。若新 RAG 构建失败，仓库现有构建流程应保留旧已发布资产；但旧索引不得被当作新 Seed 的已验收资产。修复后重新构建并验证。
- 本 Ticket 的实现仅修改文件和验证流程，不运行清库命令。

## Done When

新 Seed、metadata、初始化检查和 Runbook 一致；测试及新数据上的 RAG 验证均有可检查证据；数值事实保持不变；数据清除范围和不执行重置的边界均写清楚。

## Result

Seed / metadata 已更新到 v3，初始化健康检查、数据库测试 harness 与 Runbook 已同步。临时隔离的完整开发 PostgreSQL 初始化和相关集成测试 18 项通过；全仓确定性测试为 536 passed、14 skipped、124 subtests。未清理本机开发数据库。新 RAG 资产构建 / Evaluation 仍待最终 candidate 验收。

## Comments

- Canonical Source: `.scratch/chinese-business-display-and-seed/spec.md`。
- PostgreSQL 开发重置的既有入口：`uv run python -m scripts.reset_dev_postgres`；Qdrant 索引构建步骤见 `docs/runbook.md` §7。

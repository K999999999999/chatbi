# 评测报告记录 Seed 版本与数据指纹

Status: done
Owner: ChatBI 仓库维护者
Backup Owner: None
Blocked by: 01-local-postgres-test-isolation, 02-postgres-development-environment

## Change Profile

- Lifetime: 短期，Golden Evaluation 报告 metadata 和 baseline comparability Contract。
- Size: M。
- Risk: 中高；错误可比性会导致错误的回归 / 改善结论。
- Evidence: 报告单元测试、隔离 PostgreSQL 数据快照测试、历史报告兼容性测试。
- Delivery: 当前 Feature branch 上的独立逻辑切片；不改黄金案例或增加评测数据库。

## Canonical Source

- 行为基线：`../spec.md`。
- 正式 Evaluation Contract：`docs/specs/evaluation.md`、`docs/designs/evaluation.md`。
- 报告和比较仍由现有 `src/evaluation/reporting.py` 及共享 metadata / baseline 能力负责。

## What to build

扩展现有评测报告 metadata，记录 Seed 版本、Sales Mart 数据摘要和反映当前数据库实际内容的可复算 Hash。保留现有 `test_set_hash`、`context_hash` 和 `reference_result_hash`，并将 Sales Mart 数据 Hash 纳入基线可比性判断。

标准 Query Evaluation 和 Business Analysis Evaluation 均使用现有共享报告 metadata / baseline 比较；不建立第二个 Evaluation 数据库、报告链路或重复的 Hash / 比较实现。

## Acceptance criteria

- 报告中的数据 Hash 基于规范化的实际 Sales Mart 数据快照，而非仅基于 Seed 源文件版本或黄金案例预期查询结果。
- 重复读取相同数据库状态产生相同 Hash；Sales Mart 业务数据插入、更新或删除会改变 Hash。
- 报告提供 Seed 版本和可读的数据摘要，同时不输出原始业务行、Secret、密码或完整连接地址。
- Baseline 缺少数据 Hash、当前与 Baseline 的 Hash 不同，或测试集 / 参考结果指纹不同时，比较结果标记为 `NOT_COMPARABLE`，不报告回退或改善。
- Seed 版本不同但完整数据 Hash 相同时，在报告中保留版本差异；是否可比较以实际数据 Hash 为准。
- Query 与 Business Analysis 报告共用相同的 metadata / comparability 行为；同步更新正式 Evaluation Spec / Design。
- 黄金评测仍在同一 `chatbi_mvp` 中执行 expected SQL 和模型 SQL；不修改黄金案例、不创建独立评测数据库。

## Owned files

- `src/evaluation/reporting.py`
- `src/evaluation/business_analysis_reporting.py`（仅在共享 Contract 需要显式调整时）
- `src/evaluation/__main__.py`（数据快照采集接线）
- `tests/evaluation/`
- `docs/specs/evaluation.md`
- `docs/designs/evaluation.md`

## Validation evidence

- 确定性测试覆盖相同数据、数据改变、缺少 Hash 的旧报告、测试集 / 参考结果差异及 Secret 防护。
- 用 Ticket 01 的隔离 PostgreSQL 验证 Hash 对实际记录的稳定性和敏感字段处理。
- 验证 Query 和 Business Analysis 报告都应用相同基线判定。
- 不调用真实 LLM；本 Ticket 验证报告与数据指纹 Contract。

## Migration / Rollback

- 不迁移数据库或重写既有报告。历史报告缺少数据 Hash 时保留文件，但不得与新报告直接比较。
- 回滚报告代码和文档不改变 `chatbi_mvp` 中的数据；不自动创建或清除任何数据库。

## Done When

每份数据库型评测报告能追溯对应 Seed 和实际数据状态；数据状态不一致或无法验证时，系统不会产生误导性的基线回归 / 改善结论。

## Result

Query 与 Business Analysis 报告均记录 Seed 版本、表行数 / 日期摘要、SHA-256 和算法标识。Windows 与 WSL/Linux 的真实开发数据库均得到相同指纹；重启、Qdrant-only reset 和 Dev Container 服务重建后 Hash 不变。隔离 PostgreSQL 测试实际修改并恢复业务行时，Hash 随数据改变并恢复。数据 Hash、参考结果或摘要不匹配时标记 `NOT_COMPARABLE`；Seed 版本不同但数据 Hash 相同时记录版本差异。没有调用真实 LLM，也没有创建第二个评测数据库。

## Comments

- 当前 `reference_result_hash` 只摘要标准 SQL 的执行结果，不能替代完整 Sales Mart 数据快照 Hash。

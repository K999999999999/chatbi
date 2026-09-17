# 01: SQL Guard 单次查询校验复用

**What to build:**

在现有 `SQL Guard` Module 内引入仅属于一次 `OnlineQueryService.query()` 调用的内部 `Validation Session`，使 `candidate_scope.validate` 与 `sql.guard` 共享同一次 AST Parse 结果及基础物理表 / 字段范围校验事实，同时保持两个校验阶段、失败顺序和 Trace Span 独立可观察。

该 Ticket 覆盖必要的实现、回归测试和 Evaluation 独立调用验证，形成一个完整可验收的纵向切片。

**Blocked by:**

`None (can start immediately)`

**Status:** done

## Acceptance criteria

- [ ] 一次合法 `OnlineQueryService.query()` 调用中，`candidate_scope.validate` 与 `sql.guard` 共享同一 AST Parse 结果，不重复维护基础范围事实。
- [ ] `candidate_scope.validate → sql.guard → database.execute` 的执行顺序保持不变。
- [ ] `candidate_scope.validate` 失败时，不执行后续 `sql.guard` 和数据库执行。
- [ ] Candidate Scope Check 通过但 SQL Guard 规则失败时，仍返回现有 `SQL_REJECTED` 行为，不执行数据库。
- [ ] `validate_candidate_scope(candidate, context)` 与 `validate_sql(candidate, context)` 的公共签名、独立可用性、错误类型和返回 Contract 保持不变。
- [ ] `validate_sql()` 被 Evaluation 或测试独立调用时，不依赖其他查询的 Session、AST 或隐式状态。
- [ ] 两次独立查询以及并发查询之间不共享 AST 或校验状态。
- [ ] 现有只读约束、禁止节点、CTE、危险函数、Join、Multi-Metric 和输出完整性校验不回归。
- [ ] `candidate_scope.validate` 和 `sql.guard` Trace Span 的名称、顺序、成功 / 失败边界和 SQL Hash 记录行为不回归。
- [ ] 相关 Software Test 通过，既有真实在线评测结果无回归，且 `git diff --check` 通过。
- [ ] Diff Review 确认没有新增公共安全 API、独立安全 Module、全局状态或无关重构。

## Result

- 在现有 `SQL Guard` Module 内增加私有 `_ValidationSession`，由 `OnlineQueryService` 在一次查询中持有；`candidate_scope.validate` 与 `sql.guard` 复用一次 AST Parse。
- 保持 `validate_candidate_scope()`、`validate_sql()` 公共入口、错误 Contract、Trace Span、校验顺序和 SQL 原文返回行为不变。
- Software Test：`255 passed, 6 skipped`。
- 真实在线 Evaluation：`21/21`，`Execution Accuracy: 100.00%`，`FAIL: 0`，`INVALID_CASE: 0`。报告：`reports/evaluation/20260917T004619Z-41eec28.json`；总结：`reports/evaluation/20260917T004619Z-41eec28.md`。
- `git diff --check` 通过；Diff Review 未发现公共安全 API、全局状态或无关重构。

## Comments

- 本 Ticket 来源于已确认的 `.scratch/sql-guard-validation-reuse/spec.md`。
- 具体内部 `Validation Session` 的类名、字段形状和 AST 生命周期实现方式不在 Ticket 中冻结，只要满足 Spec 的 Interface、生命周期、错误和测试边界即可。
- 本 Ticket 不包含 Prompt、LLM、Retrieval、RAG Offline Build、Qdrant、BGE-M3、PostgreSQL、业务规则或 SQL 能力扩展。

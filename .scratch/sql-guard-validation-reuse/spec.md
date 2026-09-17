# SQL Guard 单次查询校验复用 Spec

状态：已确认；已实现

## Problem Statement

当前 `OnlineQueryService` 对 LLM 生成的 SQL 候选执行两个连续的确定性校验阶段：

1. `candidate_scope.validate`：检查候选 SQL 是否只使用当前 `QueryContext` 允许的物理表和字段；
2. `sql.guard`：检查只读语义、禁止操作、危险函数、Join、Multi-Metric 公式和输出结构。

两个阶段职责不同，并且必须保持独立的 Trace Span 和失败顺序。但当前两个阶段都会重新执行 SQLGlot AST Parse，并重复进行基础物理表 / 字段范围校验。这样会使同一个 SQL 候选的基础事实在两个阶段分别维护，增加规则变更时的维护成本，也使 `SQL Guard` 的内部复杂度部分泄漏到调用流程。

本次工作是内部架构改进，不改变 ChatBI 的业务查询能力、SQL 安全边界或对外查询行为。

## Solution

在现有 `SQL Guard` Module 内部引入一次查询范围内的 Validation Session（校验会话）。该 Session 在一次 `OnlineQueryService.query()` 调用中持有一次 AST Parse 结果及其基础范围校验结果：

```text
一次 Query
  → 创建内部 Validation Session
  → candidate_scope.validate
      → AST Parse + Candidate Scope Check
  → sql.guard
      → 复用 AST，执行剩余 SQL Guard 规则
  → Session 生命周期结束
```

现有公共函数继续保持独立可用：

- `validate_candidate_scope(candidate, context)` 的公共签名不变；
- `validate_sql(candidate, context)` 的公共签名和返回 Contract 不变；
- Evaluation、测试及其他独立调用方不依赖其他请求的 Session；
- 独立调用 `validate_sql()` 时，由该调用自行创建和销毁内部校验状态。

## User Stories

1. 作为 `OnlineQueryService` 维护者，我希望两个 SQL 校验阶段共享同一个 AST Parse 结果，从而避免同一请求内重复解析和重复维护基础范围事实。
2. 作为 SQL 安全规则维护者，我希望 Candidate Scope Check 和 AST SQL Guard 的共用逻辑集中在现有 `SQL Guard` 内部，从而让安全规则变化具有更好的 Locality（局部性）。
3. 作为 Evaluation 和测试维护者，我希望继续独立调用 `validate_sql()`，从而不依赖在线查询的内部 Session 或请求生命周期。

正常场景：

- 合法的 SELECT SQL 通过 Candidate Scope Check；`sql.guard` 复用已解析 AST，完成全部安全校验并返回 `ValidatedSQL`。

边界场景：

- SQL 解析失败、表不在 allowlist 或字段不在 allowlist：在 Candidate Scope Check 阶段拒绝，不执行后续 `sql.guard`；
- Candidate Scope Check 通过，但 SQL 包含 CTE、危险函数、未认证 Join、错误指标公式或其他禁止结构：由 `sql.guard` 拒绝；
- 数据库执行和 SQL Guard 失败均不触发自动修复或重试；
- 两次独立查询之间不得复用 AST 或校验状态。

## Implementation Decisions

### Module、Interface 和 Seam

- 继续使用现有 `SQL Guard` Module，不新增独立安全 Module。
- 在 `SQL Guard` 内部隐藏 Validation Session、AST Parse 结果和基础范围校验结果。
- `OnlineQueryService` 继续拥有查询阶段顺序和 Trace Span；它不需要了解 SQLGlot AST 的结构。
- `candidate_scope.validate` 和 `sql.guard` 继续作为两个可观察阶段，且顺序不变。
- `validate_candidate_scope()` 和 `validate_sql()` 的公共签名、独立可用性和返回 Contract 不变。
- 主要测试 Seam 继续是 `OnlineQueryService.query()` 和 `validate_sql()`；不把内部 Validation Session 提升为公共 API。

### 生命周期与并发

- Validation Session 只属于一次查询调用。
- 不使用全局 Cache、跨请求 Cache、持久化 Cache 或隐式跨调用状态。
- 不使用共享可变 AST 状态；并发查询必须彼此隔离。
- 如果 Candidate Scope Check 失败，Session 不得被后续 `sql.guard` 使用。

### 校验行为

- Candidate Scope Check 仍然使用当前 `QueryContext.allowed_tables` 和 `QueryContext.allowed_columns`。
- SQL Guard 仍然负责现有的只读约束、禁止节点、CTE 限制、危险函数、Join 认证和 Multi-Metric 校验。
- 不改变 SQL 候选原文、不自动改写 SQL、不增加 SQL 语法支持。
- 不改变 `SQLRejectedError` 的错误类型和上层 `SQL_REJECTED` 映射。
- 不改变数据库执行前的确定性安全门禁。

### Observability

- 保留 `candidate_scope.validate` Trace Span。
- 保留 `sql.guard` Trace Span。
- 保留现有 Span 的创建顺序、成功 / 失败状态和 SQL Hash 记录边界。
- Candidate Scope Check 失败时不创建或执行后续 `sql.guard` 阶段，符合当前已确认的执行链路。

### 依赖与架构边界

- 依赖类型为 In-process（进程内）。
- 继续直接使用 SQLGlot，不新增 SQL Provider、远程服务或 Adapter。
- 不改变 `Online Query`、`Query API Adapter`、`Evaluation`、`RAG Offline Build` 或数据库的一级职责。
- 不建立完整 DDD 分层，不新增通用 `Port / Adapter` 体系。

## Testing Decisions

### Software Test

以现有公共测试 Seam 验证外部行为：

- `validate_sql()` 独立调用仍能完成完整 SQL 校验；
- `OnlineQueryService.query()` 仍按 `candidate_scope.validate → sql.guard → database.execute` 顺序执行；
- 合法 SQL 的返回 `ValidatedSQL`、SQL 原文和现有查询结果保持不变；
- Candidate Scope Check 拒绝未知表、未知字段或非法 SQL 时，不执行后续 SQL Guard 和数据库；
- Candidate Scope Check 通过但 SQL Guard 规则失败时，仍返回 `SQL_REJECTED`，不执行数据库；
- 只读限制、危险函数、CTE、Join、Multi-Metric 公式和输出完整性规则不回归；
- 两个独立查询不会复用彼此的 AST 或校验状态；
- 现有 `candidate_scope.validate` 和 `sql.guard` Trace Span 名称、顺序和失败边界保持不变；
- Evaluation 直接调用 `validate_sql()` 的标准 SQL 校验行为保持不变。

测试应断言公共结果、调用顺序、错误边界和 Trace Contract，不断言内部 Validation Session 的具体类名、字段或缓存实现。

### AI Evaluation

本次不改变 Prompt、LLM、Retrieval、指标口径或 SQL 能力，因此不新增 AI Evaluation 案例。由于 SQL Guard 属于查询安全链路，最终候选提交仍需按仓库高风险变更规则完成既有真实在线评测回归，确认 `Execution Accuracy` 和既有案例结果不受影响。

### Business Acceptance

本次属于内部架构改进，不新增 Business Acceptance 场景。已确认的业务查询、拒答、安全拒绝、空结果和数据库执行行为必须保持不变。

### Completion Evidence

- 相关 SQL Guard、Online Query、Observability 和 Evaluation Software Test 通过；
- 现有真实在线评测结果不回归；
- `candidate_scope.validate` 和 `sql.guard` Trace Contract 不回归；
- `git diff --check` 通过；
- Diff Review 确认没有新增公共安全 API、独立安全模块、全局状态或无关重构。

## Out of Scope

- 合并或删除 `validate_candidate_scope()` 和 `validate_sql()` 公共入口；
- 修改两个函数的公共签名、错误类型或返回类型；
- 改变 SQL Guard 支持的 SQL 语法、业务规则或安全策略；
- 新增 CTE、窗口函数、复杂分析 SQL、SQL 自动修复或自动重试；
- 修改 Prompt、LLM、Retrieval、RAG Offline Build、Qdrant、BGE-M3 或 PostgreSQL；
- 新增独立安全 Module、完整 DDD 分层、通用 `Port / Adapter` 或远程服务；
- 建立跨请求 AST Cache、全局 Cache 或持久化校验状态；
- 以性能基准优化为独立目标；
- 删除现有测试、历史验收证据或无关文件；
- 创建 Ticket、PR、远程 Issue 或修改 Git remote。

## Further Notes

- 本 Spec 的设计基线来自已确认的最小方案：在现有 `SQL Guard` 内部共享单次查询的 AST Parse，同时保留两个校验阶段和两个 Trace Span。
- 具体内部 Session 的类名、字段形状和 AST 生命周期实现方式不在本 Spec 中冻结，只要满足上述 Interface、生命周期、错误和测试边界即可。
- 相关事实来源包括当前 `OnlineQueryService` / `SQL Guard` 实现、Observability Implementation Design，以及 Online Retrieval 对 Candidate Scope Check 与 AST Parse 复用的既有设计说明。
- 当前状态为已确认；实现与验收证据记录在 Ticket 01。本 Spec 不替代代码、测试和 Evaluation（评测）证据。

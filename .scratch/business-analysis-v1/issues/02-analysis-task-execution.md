# Ticket 02：Task Semantic Adapter 与依赖感知执行

- Status: done
- Owner: Business Analysis Application / Query Orchestration
- Blocked by: Ticket 01
- Canonical Source: `.scratch/business-analysis-v1/spec.md`

## Change Profile

- Lifetime：经营分析 V1 的 Task 执行核心。
- Size：中等偏大；连接计划、授权查询和 Online Query。
- Risk：高；影响 Semantic、Retrieval、SQL Guard、授权和数据库执行边界。
- Evidence：确定性 Executor / Adapter 测试和授权查询集成测试。
- Delivery：本地 Feature branch；不新增 HTTP loopback。

## What to build

- 实现确定性的 Task Semantic Adapter。
- 将指标别名规范化为权威 Semantic 名称。
- 将 Task 转换为 `SemanticQueryCandidate` 和 `ValidatedSemanticQuery`。
- 根据现有完成日期、当前时间和时区规则规范化 `time_range`。
- 生成稳定的 `canonical_task_question`，作为 `QueryRequest.question` 和 Retrieval 问题文本。
- 不再次调用 Query Understanding LLM。
- 通过当前用户身份绑定的 `AuthorizedQueryService` 和 `OnlineQueryService` 执行 Task。
- 按依赖关系串行调度 Task。
- 实现 `completed`、`failed`、`skipped` 三种 `TaskResult` 状态。
- 实现独立 Task 失败继续执行、依赖失败下游跳过的规则。
- 保持空结果为 `completed`，不根据空结果生成新 Task。
- 每个 Task 遵守 Online Query 当前最多 100 行的返回边界。
- 不直接访问数据库、不生成 SQL、不绕过授权或 SQL Guard。

## Owned paths

- `src/business_analysis/`
- `tests/business_analysis/`

现有 `src/authorization/`、`src/online_query/` 和 SQL Guard 作为被调用的稳定边界；除非出现 Contract 缺口，不修改其业务职责。

## Acceptance criteria

- 合法 Task 能转换为 `ValidatedSemanticQuery` 和 `QueryRequest`。
- 非法指标、维度、时间和筛选条件在进入数据库前被拒绝。
- `QueryRequest.question` 使用规范化 Task 问题，不使用原始复杂经营问题重新解释。
- 每个 Task 都通过当前用户身份的授权查询入口。
- Executor 不通过 HTTP loopback，不复制 Prompt、Retrieval、SQL Guard 或数据库执行逻辑。
- 无依赖、依赖完成、依赖失败和独立 Task 失败时状态转换正确。
- 下游 Task 不从上游结果行动态生成查询条件。
- `TaskResult` 的错误只包含公开错误码和用户可读信息，不泄露 SQL、连接信息、异常堆栈或 Secret。
- `truncated=true` 被保留并可供最终报告判断。

## Verification evidence

- `tests/business_analysis/` 中的 Adapter、Executor 和状态转换测试。
- 使用假的 `AuthorizedQueryService` 验证调用次数、身份上下文和失败传播。
- 使用假的 `OnlineQueryService` 验证不会发生 HTTP loopback、SQL 生成重复或数据库直连。
- 覆盖空结果、失败、跳过、截断、授权拒绝和语义校验失败。
- 后续 Ticket 05 补充真实链路和业务验收证据。

## Migration / Rollback

不涉及持久化迁移。回滚时移除 Task Adapter / Executor，不改变现有授权、Online Query 和普通查询状态。

## Done When

- 静态分析计划可以通过现有授权和 Online Query 链路执行。
- TaskResult 状态、错误、空结果、失败传播和截断行为均有测试证据。
- 没有新增第二条数据库查询链路。

## Result

已完成 Task Semantic Adapter 与依赖感知 Executor：

- 通过现有 `validate_candidate` 将已校验的 `AnalysisTask` 转换为 `ValidatedSemanticQuery` 和 `QueryRequest`。
- 生成稳定的 `canonical_task_question`，不重新调用 Query Understanding LLM，不生成 SQL，不直接访问数据库。
- 使用注入的已绑定查询服务执行 Task，按依赖串行调度；独立失败继续执行，依赖失败下游标记为 `skipped`。
- 保留空结果和 `truncated` 状态，并将失败转换为不泄露内部细节的公开 Task 错误。

验证：`uv run pytest -q tests/business_analysis` → 14 passed；`uv run python -m compileall -q src/business_analysis tests/business_analysis` → 通过；`git diff --check` → 通过。

## Comments

- Ticket Readiness Review：READY。
- Task Adapter 的业务事实必须来自当前 Semantic Source of Truth，不允许用 LLM 结果覆盖指标口径或授权结论。

# 03: 上下文组装与 OnlineRetriever 编排整合

**What to build:**

把最终表、最终字段、Dynamic Schema、Indicator Context 和 QueryContext 的组装整理到清晰的内部 Module，并让 `OnlineRetriever` 继续作为统一编排入口。

在前两个内部 Module 的结果稳定后，完成内部编排整合，移除不再使用的重复私有实现，但不改变外部 Contract。

**Blocked by:**

- `01：确定性 Relationship Graph 解析 Module 加深`
- `02：候选资源检索 Module 加深`

**Status:** done

## Acceptance criteria

- [x] `OnlineRetriever.retrieve()` 的输入和返回 Contract 保持不变。
- [x] `OnlineRetrievalResult` 的状态、字段、指标、关系和告警语义保持不变。
- [x] `QueryContext.allowed_tables` 保持不变。
- [x] `QueryContext.allowed_columns` 保持不变。
- [x] Dynamic Schema 只包含既有最终资源闭包。
- [x] Indicator Context 的内容和指标顺序保持不变。
- [x] Trace Span 名称、数量、顺序和安全证据边界保持不变。
- [x] SQL Guard 和 Query API 不需要改变调用方式。
- [x] 现有 Online Query、Retrieval 和 Query API Software Test 不回归。
- [x] 既有 AI Evaluation 和 Business Acceptance 结果不回归。
- [x] 不引入 Token 优化、性能优化、业务规则或完整 DDD 分层。

## Result

已完成。最终表/字段闭包、关系键补充、Dynamic Schema、Indicator Context、allowlist 和 `QueryContext` 已移至 `src/online_query/retrieval_context.py`；单指标与 Multi-Metric 编排共用同一个内部 `assemble_context()`，公共 `OnlineRetriever.retrieve()` 保持不变。

验证：

- 全量 Software Test：`230 passed, 6 skipped, 79 subtests passed`。
- 真实在线 AI Evaluation：`Execution Accuracy 100%`，`PASS: 20, FAIL: 0, INVALID_CASE: 0`。
- 现有已确认 Business Acceptance 场景未改变，且公共 Retrieval 测试通过。
- 03 阶段 `git diff --check` 通过。

## Comments

- 本 Ticket 是内部模块整合，不是公共 API 变更。
- 测试仍优先通过 `OnlineRetriever.retrieve()` 观察行为，不为测试暴露新的公共入口。
- 只有确认旧私有实现没有调用方后，才能删除重复实现。

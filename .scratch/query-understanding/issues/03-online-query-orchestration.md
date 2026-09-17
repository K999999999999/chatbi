# Ticket 03：OnlineQueryService 主链路接入 Query Understanding

Status: done

## What to build

调整 `OnlineQueryService` 的在线主链路，在 Online Retrieval 前接入 Query Understanding 和程序校验。

目标链路：

```text
QueryRequest
→ QueryUnderstandingAdapter
→ SemanticQueryCandidate
→ Program Validation
→ ValidatedSemanticQuery
→ Online Retrieval
→ QueryContext
→ Prompt
→ SQLGenerator
→ SQL Guard
→ Database
```

实现内容包括：

- 保留原始问题和 `request_id`；
- 结构化理解失败返回 `LLM_ERROR`；
- 业务语义无法确定返回 `CANNOT_ANSWER`；
- 不再通过旧正则逻辑构造请求形态；
- `RetrievalRequest` 携带 `ValidatedSemanticQuery`；
- 内部 `reason` 写入 Trace / Evaluation，不泄露内部细节给用户；
- 保持 `QueryFailure` 现有公共错误码边界。

## Blocked by

Ticket 01：SemanticQuery Contract 和确定性校验

Ticket 02：QueryUnderstandingAdapter

## Acceptance criteria

- Query Understanding 失败时不触发 Retrieval、SQLGenerator 或 Database；
- 业务语义拒答时不触发 SQLGenerator 或 Database；
- 通过校验的请求才进入 Online Retrieval；
- 用户收到针对原因的中文提示，而不是直接看到 `CANNOT_ANSWER` 等机器错误码；
- SQL Guard 失败仍返回 `SQL_REJECTED`；
- Database 错误和超时保持现有错误码；
- Trace 能区分 Query Understanding、Retrieval、SQL Generation 和 SQL Guard 阶段。

## Result

- `OnlineQueryService` 在线模式已在 Retrieval 前调用 `QueryUnderstandingAdapter`，并通过 `validate_candidate` 生成 `ValidatedSemanticQuery`。
- Query Understanding 结构或调用失败返回 `LLM_ERROR`；业务语义拒答返回 `CANNOT_ANSWER`；两类失败均不会触发 Retrieval、SQLGenerator 或 Database。
- `RetrievalRequest` 已携带 `semantic_query`，请求形态由结构化指标数量确定，不再由服务层调用旧正则构造器。
- Query API 和 Evaluation 在线组合根已注入 Query Understanding Adapter；静态模式保持原行为，未纳入本 Ticket。
- Trace 增加 `query.understanding` 阶段及受安全白名单保护的查询理解属性和内部 `reason`。
- 验证：`279 passed, 6 skipped, 105 subtests passed`；`compileall` 和 `git diff --check` 通过。

## Comments

本 Ticket 只覆盖在线链路。静态全量 Schema 路径不接入新流程，后续删除另行处理。

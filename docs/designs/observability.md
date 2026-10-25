# Trace生命周期与安全传播

本文说明维护当前实现所需的机制；功能行为见 [可观测性Spec](../specs/observability.md)。开发方案比较、任务和历次验收保存在工作记录。

## 模块和依赖方向

新增一个小型 Cross-cutting Module（横切模块）：

```text
src/observability/
├─ __init__.py
├─ contracts.py
├─ config.py
└─ tracing.py
```

职责：

| 文件 | 职责 |
|---|---|
| `contracts.py` | 定义 `TraceRecorder`、`TraceScope`、`SpanScope` 和安全结果状态，不导入 OpenTelemetry |
| `config.py` | 从环境变量读取开关、服务信息、OTLP 端点和内容记录策略 |
| `tracing.py` | 实现 No-op、Safe Wrapper、OpenTelemetry Adapter 和测试用 In-memory Exporter 组装 |
| `__init__.py` | 只导出稳定构造函数和 Contract |

依赖方向：

```text
query_api / online_query / evaluation
                ↓
     observability contracts
                ↑
 OpenTelemetry infrastructure adapter
```

`online_query` 不直接导入 `opentelemetry.*`，也不导入 Langfuse 类型。

## 最小内部 Contract

### TraceRecorder

`TraceRecorder` 提供三类能力：

```text
query_trace(source, carrier?, attributes?) -> TraceScope
span(name, attributes?) -> SpanScope
enrich_current(attributes, outcome?, error?) -> None
```

Contract 不暴露 OpenTelemetry 的 `Span`、`TracerProvider` 或 Exporter 类型。

不变量：

- 所有公开方法必须 No-throw（不向业务链路抛异常）。
- `query_trace()` 在没有活动查询 Trace 时创建 `query.request`。
- 已有活动查询 Trace 时复用，不创建第二个 `query.request`。
- 每个 TraceScope 都能提供 32 位小写十六进制 `trace_id`。
- No-op 模式仍生成或继承 `trace_id`，但不保存和导出 Span。
- `span()` 只能创建实际执行的节点，不能预生成未来节点。

TraceScope 必须区分 Owning Scope（拥有根链路的作用域）和 Borrowed Scope（借用已有根链路的作用域）：

- 第一个创建 `query.request` 的调用方拥有 Root Trace，负责结束 Span 并清理上下文；
- 已有活动 Root Trace 时，后续调用方只能借用，退出时不得再次结束 Root Trace，也不得清理外层上下文；
- HTTP Middleware、Evaluation 外层和直接调用的 Service 三者只能有一个拥有者；
- Root Trace 必须在 `response.serialize` 或最后一个业务 Span 结束后最后关闭。

这个所有权规则是 Contract 的一部分，不依赖具体 OpenTelemetry 类型。

### Safe Wrapper

所有业务调用方只获得 Safe Wrapper。底层 Adapter 初始化、开始 Span、写属性或结束 Span 发生异常时：

1. 写一条不含配置值和 Secret 的安全 Warning；
2. 当前操作退化为 No-op；
3. 查询继续执行；
4. 不触发业务重试。

异常处理必须显式安全化：

- 每个 OTel Span 都使用 `record_exception=false` 和 `set_status_on_exception=false`；
- 不调用 `record_exception()`，不把 `str(exc)`、堆栈、连接信息或 Provider 原始响应写入 Span；
- 只允许写入固定枚举中的 `chatbi.error.type`、公开 `chatbi.error_code`、受控 Outcome，以及 Observability Spec 定义的 Provider 分类 / 有界 HTTP 状态 / 可重试分类和 SQL Guard 原因代码；
- Safe Warning 也只能写组件、阶段和固定错误分类，不得携带原始异常文本；
- 如果未来需要完整堆栈，只能进入单独的受保护、脱敏后的内部日志链路，不属于本 V1 Trace 和 Langfuse 数据。

OTLP 使用 `BatchSpanProcessor` 异步批量发送。不得在每次查询结束时调用 `force_flush()`，避免平台延迟进入查询响应时间。

### QuerySource

为记录请求来源，在内部 Contract 增加：

```text
QuerySource = HTTP | INTERNAL | EVALUATION
QueryRequest.source = INTERNAL
```

这是向后兼容的内部扩展：现有调用方不传时仍为 `INTERNAL`；HTTP Body 和 JSON Response 都不增加该字段。

## Trace 生命周期和上下文传播

### HTTP 路径

`src/query_api/app.py` 的 Middleware 覆盖 `/api/v1/query` 以及 histories、saved-results、executions、result-exports 命名空间。业务写请求建立 HTTP Root；GET / HEAD 读取和 SSE 观察只返回诊断编号，不创建业务 Root Trace。下面是旧同步查询的执行示意：

```text
读取或生成 request_id（早于请求体解析）
  -> 忽略客户端提供的 W3C traceparent / tracestate
  -> 创建带 request_id 的本地 query.request
  -> 调用 FastAPI 校验、路由和 AuthorizedQueryService
  -> 调用 OnlineQueryService.execute()
  -> response.serialize
  -> 在响应写入 X-Trace-ID
  -> 结束 query.request
```

规则：

- Middleware 在请求体解析前读取并规范化允许的 `X-Request-ID`；缺失时生成新的 `request_id`。同一个值必须传入后续 `QueryRequest` 和 Root Trace。
- V1 不信任公网或浏览器直接提交的 `traceparent` / `tracestate`，统一创建本地 Trace；也不接受调用方直接指定 `X-Trace-ID`。
- 内部函数调用可以通过当前进程的 Context 继续使用已有 Trace；这不等同于信任 HTTP Header。
- 将来只有在可信 Gateway 明确建立边界、完成认证并通过单独设计审查后，才能开放受控的上游 Trace 继承。
- 成功、业务失败、请求体校验失败和无效 JSON 都返回同一请求对应的 `X-Trace-ID`；响应体继续使用同一个 `request_id`。
- `/health` 不属于 Query Trace，不创建 `query.request`。
- `X-Trace-ID` 不加入现有成功或错误 JSON Body。

FastAPI Middleware 持有当前业务写请求的 HTTP Root Trace，覆盖请求解析和响应构造；同步下游复用活动 Trace。后台执行在 worker 中创建独立 Root，并以服务端进程内签发的 carrier 建立 Link，不能延长已结束的受理 Span。GET / SSE 观察不因轮询 / 重连产生新的业务 Root。

### 直接调用和 Evaluation 路径

直接调用没有 Middleware，因此 `BoundAuthorizedQueryService.query()` 进入的 `OnlineQueryService.execute()` 使用同一个 `query_trace()` Contract：

- 没有活动 Trace：创建 `query.request`；
- 已有活动 Trace：继续使用；
- Evaluation 创建 `QueryRequest(source=EVALUATION)`；
- Root Span 记录 `evaluation.case_id`，通过现有 `request_id=evaluation-<case_id>` 关联评测案例。
- 多轮 Evaluation 对每个实际请求轮次创建独立 Root Trace，同时记录固定 `evaluation.case_id`、`evaluation.turn_id` 和 `chatbi.request.id`；JSON / Markdown 报告写入对应 `trace_id`。没有实际执行请求的轮次保持 `null`。

Evaluation 外层拥有自己创建的 Root Trace；`OnlineQueryService` 只借用该 Trace。直接评测入口没有外层 Trace 时，由 Service 拥有并结束 Root Trace。所有拥有者退出时都必须清理 Context，避免下一次请求继承上一条链路。

直接调用没有 HTTP 序列化，因此不得伪造 `response.serialize` Span。

### Trace ID 与 Request ID

- `trace_id` 来自可信的进程内活动上下文或本次执行生成；V1 HTTP 不采信客户端传入的 W3C 上下文。
- `request_id` 继续由现有 `_resolve_request_id()` 产生。
- `query.request` 在 Root Trace 创建时写入 `chatbi.request.id`；因此请求体解析失败也能保持 `request_id` 与 `trace_id` 的关联。
- 两个编号可以互相检索，但不能互相替代。

## Span 落位

### Online Query 主链路

`src/online_query/service.py` 负责以下 Span：

| Span | 实际代码边界 | 成功输出 | 失败/拒绝 |
|---|---|---|---|
| `query.request` | 一次 `query()` 或整个 HTTP Query 生命周期 | 最终状态、行数、截断 | 公开错误码和安全失败分类 |
| `request.validate` | 请求编号和 question 校验 | 合法请求 | `INVALID_REQUEST` |
| `retrieval.plan` | `build_retrieval_request()` | shape、fallback policy | 安全技术分类 |
| `retrieval.execute` | `RetrievalProvider.retrieve()` 与结果处理 | asset、状态、候选数量 | 无候选、技术失败 |
| `prompt.build` | `build_prompt()` | Prompt 长度，不含正文 | 安全技术分类 |
| `llm.generate` | `SQLGenerator.generate()` | model、Token、耗时 | `LLM_ERROR` 或 `CANNOT_ANSWER` |
| `candidate_scope.validate` | `validate_candidate_scope()` | 通过 | `SQL_REJECTED` |
| `sql.guard` | `validate_sql()` | SQL Hash | `SQL_REJECTED` |
| `database.execute` | `QueryExecutor.execute()` | 行数、截断 | 超时或数据库错误 |

同步查询 / 分析的 `response.serialize` 在 `src/query_api/app.py` 的 `_result_response()` / `_analysis_result_response()` 中记录，范围是构造最终 `JSONResponse`，不延伸到 FastAPI/ASGI 网络发送。后台执行和文件交付按各自实际生命周期记录，不把持续 SSE 观察当作同步结果序列化。

### Retrieval 内部

`OnlineRetriever` 通过 resource / join stage 及 `_RetrievalExecution` 在实际调用位置记录：

| Span | 边界 |
|---|---|
| `asset.resolve` | `RagRuntime.get_snapshot()` |
| `embedding.query` | 实际 Query Embedding 调用；基线和多指标按真实调用次数记录 |
| `table.search` | 现有 TABLE Search 调用 |
| `metric.search` | 每个请求的指标说法实际触发的独立搜索；无指标时不记录 |
| `column.search` | 在候选表范围内执行现有 COLUMN Search |
| `join.resolve` | 现有确定性关系图路径解析 |
| `context.assemble` | Dynamic Schema、指标上下文和 `QueryContext` 组装 |

规则：

- Span 包裹现有调用，不能改变调用顺序和次数。
- 只有实际执行了对应动作才创建 Span。
- Multi-Metric 按请求的指标说法逐个检索；三个说法通常产生三个 `metric.search` Span，不能因观测增加额外检索。
- 在线 RAG 使用 `FAIL_CLOSED`；检索技术失败记录实际错误和 `fallback_used=false`，不生成静态回退或其 Span。显式无 Retrieval Provider 的静态模式独立装配，不是故障恢复路径。
- 不记录原始 `warnings` 文本，只记录受控状态和分类。

### LLM Token

`src/online_query/llm.py` 仍返回纯字符串，不扩展 `SQLGenerator.generate(prompt) -> str`。

`llm.generate` Span 同时写入标准 GenAI 属性：

```text
gen_ai.operation.name = "chat"
gen_ai.request.model
gen_ai.response.model       # Provider 返回时才写
gen_ai.usage.input_tokens
gen_ai.usage.output_tokens
gen_ai.usage.total_tokens   # Provider 返回时才写
```

Adapter 在收到模型响应时，按字段逐个提取非负整数 Token。优先使用 `usage_metadata`，某个字段缺失或无效时，再对该字段回退到兼容 Provider 的 `response_metadata["token_usage"]`：

| 统一字段 | 首选字段 | 回退字段 |
|---|---|---|
| input | `input_tokens` | `prompt_tokens` |
| output | `output_tokens` | `completion_tokens` |
| total | `total_tokens` | `total_tokens` |

`usage_metadata` 和 `token_usage` 中的字段都必须是非负 `int`，`bool` 不算有效整数；不估算、不自行分词、不因为缺失 Token 影响 SQL 返回。

Langfuse 验收必须确认上述属性能将 `llm.generate` 显示为 Generation（模型生成节点），并能看到模型标识和可用 Token。若通用 GenAI 属性不能完成映射，只能在 Infrastructure Adapter（基础设施适配器）中增加最小 Langfuse 兼容字段，不能污染 Online Query Contract。

## 属性和状态规则

### Resource 属性

由 SDK 初始化一次：

```text
service.name
service.version
deployment.environment.name
```

### ChatBI 属性命名

项目特有字段统一使用 `chatbi.*`：

```text
chatbi.request.id
chatbi.request.source
chatbi.outcome
chatbi.error_code
chatbi.error.type
chatbi.provider.error_category
chatbi.provider.http_status_code
chatbi.provider.retryable
chatbi.sql_guard.rejection_code
chatbi.content_capture.enabled
chatbi.rag.asset_version
chatbi.retrieval.request_shape
chatbi.retrieval.fallback_policy
chatbi.retrieval.status
chatbi.retrieval.fallback_used
chatbi.retrieval.table_count
chatbi.retrieval.column_count
chatbi.retrieval.metric_count
chatbi.sql.sha256
chatbi.database.row_count
chatbi.database.truncated
```

选中候选只记录 Spec 允许的 `document_id`、rank、score、表名和 `edge_id`，并受现有 Top K 上限约束。不得写入完整 RAG Document 或 Dynamic Schema。

### Outcome 与 OpenTelemetry Status

| ChatBI Outcome | OTel Status | 使用场景 |
|---|---|---|
| `SUCCESS` | `OK` | 查询或节点成功 |
| `BUSINESS_REJECTION` | `UNSET` | 无法回答、请求无效、SQL 被安全拒绝 |
| `TECHNICAL_FAILURE` | `ERROR` | LLM、Retrieval、数据库等技术失败 |
| `TIMEOUT` | `ERROR` | 数据库超时 |
| `FALLBACK_SUCCESS` | `OK` | 保留的兼容状态；当前在线 RAG 不走静态 fallback |

业务拒绝不冒充系统故障，但必须记录公开 `error_code`。当前在线 RAG 技术失败时，原失败 Span 与 Root 记录技术失败，不使用 `FALLBACK_SUCCESS` 冒充成功；业务资源不足则按受控拒绝分类。

OTel Status 也不能从异常自动带出原始文本：所有 `start_as_current_span()` 调用显式关闭自动异常记录和自动 Status 描述；业务代码只根据固定映射写入 `StatusCode.ERROR` 或受控的 `StatusCode.UNSET`。
Trace 仅记录固定的 `chatbi.error.type`、公开 `chatbi.error_code`、白名单 Provider 分类 / HTTP 状态 / 可重试分类和 SQL Guard 原因代码；不记录异常类名、`str(exc)`、完整堆栈、连接信息或 Provider 原始响应。


## 内容安全

默认模式：

- 不记录完整 question；
- 不记录 Prompt；
- 不记录候选 SQL；
- 通过 Guard 后只记录最终 SQL 的 SHA-256；
- 不记录查询结果行；
- 不记录 RAG 正文和完整 Metadata；
- 不记录 Header、API Key、数据库连接参数和 OTLP Authorization Header。

本地 Content Debug（内容调试）开启时，只额外记录：

- 完整 question；
- 通过 SQL Guard 后的最终 SQL。

即使开启也不记录 Prompt、候选 SQL 和结果行。
内容调试必须同时满足 `CHATBI_TRACE_CONTENT_ENABLED=true` 且 `CHATBI_RUNTIME_ENV` 明确属于 `local`、`dev` 或 `test`；环境值大小写不敏感，但缺失、空值、`production`、`staging`、未知值或重复冲突配置都按关闭处理。
若运行环境为生产或无法确认环境，必须强制记录 `chatbi.content_capture.enabled=false`。


生产边界：Trace/Langfuse 只记录固定错误类型、公开错误码和必要的耗时状态，不记录原始异常消息或堆栈。生产排障若需要堆栈，应由后续独立的受保护日志方案承担，并进行脱敏、访问控制、保留期和审计；不能通过放宽 Trace 内容开关实现。

## 配置设计

应用开关使用 ChatBI 前缀，Exporter 使用 OpenTelemetry 标准配置：

```text
CHATBI_OBSERVABILITY_ENABLED=false
CHATBI_TRACE_CONTENT_ENABLED=false
CHATBI_RUNTIME_ENV=
OTEL_SERVICE_NAME=chatbi-engine
OTEL_RESOURCE_ATTRIBUTES=deployment.environment.name=local
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=
OTEL_EXPORTER_OTLP_HEADERS=
CHATBI_OTLP_TIMEOUT_SECONDS=5
```

规则：

- 默认关闭 Export，保持现有本地启动和测试兼容。
- 开启但缺少或无法创建 Endpoint 时安全降级为 No-op，不阻止服务启动。
- `CHATBI_OTLP_TIMEOUT_SECONDS` 解析为正浮点秒数，并显式传给 Python OTLP/HTTP Exporter。
- `CHATBI_RUNTIME_ENV` 缺失或未知时按不允许内容采集处理；只有 `local`、`dev`、`test` 加上显式内容开关才允许内容调试。
- `.env.example` 只提供空模板，不写入 Langfuse Key 或 Authorization 值。
- 不在日志中打印 `OTEL_EXPORTER_OTLP_HEADERS`。
- Langfuse v4 所需的实时摄取 Header 通过环境变量配置，不硬编码到业务代码。

## 组装与生命周期

### Query API

`src/query_api/main.py` 只用 `create_app(runtime_factory=create_runtime)` 创建应用，导入时不加载配置或打开资源；装配与释放发生在 lifespan：

1. `src/bootstrap/runtime.py` 的 `create_runtime()` 加载本地配置，保留已有环境变量优先级；
2. 构建 Safe `TraceRecorder` 并立即登记 shutdown 清理；
3. 将同一 recorder 注入模型、检索和查询服务，通过 RuntimeDependencies 绑定到应用与后台能力；
4. `create_app()` 的 Middleware 按上文路径 / 方法区分业务写请求与只读观察，在解析请求体前建立编号及适用的 HTTP Root；
5. 关闭时先停止受理、结束 worker / 观察并释放业务资源，再由 Bootstrap 生命周期关闭 recorder；初始化局部失败也释放已取得资源，安全降级不改变业务结果。

### Evaluation

`evaluation/__main__.py` 使用相同构造函数创建 TraceRecorder，并将同一实例传入正式查询链路。
`run_evaluation()` 增加有默认值的可选 TraceRecorder 参数，每个实际调用 Online Query 的案例由 Evaluation 外层持有 TraceScope，Service 复用该 Trace。
CLI 在资源清理阶段最多关闭一次 recorder，完成适用的批量导出 / shutdown；不按案例数逐次 flush。案例范围与报告身份遵循[评测规则](../specs/evaluation.md)，不在此固定旧案例数量。


`CaseEvaluation` 和 JSON/Markdown 报告增加可选 `trace_id`：

- 实际执行 Online Query 的案例，无论成功、公开业务失败、Unexpected Return（非预期返回）还是捕获异常，都写入对应 Trace ID；
- 在案例格式、Gold SQL 或 Gold 结果阶段已判为 `INVALID_CASE`，且没有执行 Online Query 时为 `null`；
- JSON 明确输出 `trace_id`；Markdown 对每个实际执行案例列出 `case_id`、`request_id` 和 `trace_id`；
- 不在报告中复制整棵 Trace、Prompt 或 Span 属性；
- 旧 Baseline（基线）没有该字段时仍可读取和比较。

多轮评测的 `MultiTurnTurnEvaluation` 对每个实际请求轮次保存 Evaluation Root Trace ID，并按轮次写入 JSON / Markdown 报告；case / turn 编号经过安全标识符白名单处理。

### 电脑端 Web

`frontend/src/api.ts` 从成功与受控错误响应的 `X-Trace-ID` Header 读取并校验 Trace ID；页面展示请求编号和链路编号时只保存在内存，不将其伪装成业务响应字段。Header 缺失不改变业务结果。

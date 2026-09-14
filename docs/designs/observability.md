# Observability V1 Implementation Design

状态：T1～T4C 已完成并通过各自测试，已有独立提交；本地 API 与真实 Evaluation（评测）验收已完成。T5 Langfuse / Business Acceptance Gate（业务验收门禁）因 `.env` 未配置 OTLP/Langfuse Endpoint（端点）待补，不能记为 T5 PASS 或 Production Ready（生产可用）。

## 1. 结论

Observability V1（可观测性 V1）采用 OpenTelemetry（开放遥测）作为统一 Trace 标准，使用 OTLP/HTTP 导出，并以 Langfuse 作为第一个可视化验收平台。

V1 只实现 Trace：让一次 Online Query（在线查询）从 HTTP、RAG、LLM、SQL Guard 到 PostgreSQL 使用同一个 `trace_id`，能够定位失败节点和主要耗时节点。完整 Metrics、Logs、Alert（指标、日志、告警）以及 Grafana/Tempo 平台留到 Production Hardening（生产加固）阶段。

核心原则：

- ChatBI 核心代码不依赖 Langfuse SDK，只依赖项目自己的最小 Trace Contract（链路契约）。
- Infrastructure Adapter（基础设施适配器）使用 OpenTelemetry SDK 实现该 Contract。
- Langfuse 只作为可替换的 OTLP Backend（后端），不拥有 ChatBI 业务事实。
- Trace 是旁路能力；初始化、记录或导出失败不得改变查询结果、错误码和调用次数。
- 默认不记录完整问题、Prompt、SQL、结果或原始异常。

行为事实源为 [Observability V1 Module Spec](../specs/observability.md)。本设计只决定如何实现已确认行为。

## 2. 当前事实与目标行为

### 2.1 当前事实

- `OnlineQueryService.query()` 是同步查询唯一公共入口。
- Query API 使用 FastAPI，同步调用 `OnlineQueryService`。
- Evaluation（评测）直接调用同一个 `OnlineQueryService`，不经过 HTTP。
- `request_id` 已存在，但没有 `trace_id` 和统一 Span。
- `OnlineRetriever` 已能得到资产版本、候选、分数、Join 路径和 Retrieval 状态。
- `LangChainSQLGenerator` 当前丢弃模型响应里的 Token Metadata（元数据）。
- Query API、Streamlit、Evaluation、LLM 和 Retrieval 都没有可观测依赖。

### 2.2 目标行为

完成后：

```text
页面显示 trace_id
  -> 使用 trace_id 在 Langfuse 查找一次查询
  -> 展开 query.request
  -> 查看实际执行的 RAG / LLM / SQL Guard / Database Span
  -> 判断失败节点、fallback 路径和主要耗时节点
```

Trace 只能解释系统已经执行了什么。它不能替代代码调试、业务口径验证，也不能在 V1 解释 CPU、内存、容器或操作系统问题。

可见性边界：

- 正常成功、受控业务拒绝、已捕获技术异常、数据库超时和 Retrieval fallback 都必须形成可查看的完整已执行链路；
- 可观测后端断开时，查询仍成功，但该次 Trace 可能无法送达，这是 fail-open 的明确代价；
- 进程被强制终止、机器断电或尚未 Batch Export 就崩溃时，尾部 Span 可能丢失，V1 不承诺崩溃现场持久化；
- Trace 定位责任节点和安全错误分类；需要变量值、完整堆栈或资源使用率时，再结合后续受控日志和系统指标。

## 3. 已选技术与边界

### 3.1 应用依赖

实现阶段新增以下 Python 依赖，具体补丁版本由 `uv.lock` 锁定：

```text
opentelemetry-api>=1.44,<2
opentelemetry-sdk>=1.44,<2
opentelemetry-exporter-otlp-proto-http>=1.44,<2
```

V1 不新增：

- `langfuse` SDK；
- LangSmith SDK；
- OpenLLMetry / OpenInference 自动埋点；
- psycopg 或 LangChain 全量自动埋点；
- OTLP/gRPC Exporter。

原因是当前节点少、数据安全边界明确，Manual Instrumentation（手动埋点）更容易保证不重复 Span、不泄漏 Prompt/SQL，并能保持平台可替换。

### 3.2 导出协议和平台

V1：

```text
ChatBI
  -> OpenTelemetry SDK
  -> BatchSpanProcessor
  -> OTLP/HTTP Exporter
  -> Langfuse
```

后续生产化：

```text
ChatBI
  -> OTLP
  -> OpenTelemetry Collector
       ├─ Langfuse             AI Observability（AI 可观测）
       └─ Tempo -> Grafana     System Trace（系统链路）
```

V1 不在本仓库部署 Langfuse、Collector、Tempo、Prometheus 或 Loki，也不修改现有 Docker Compose。Langfuse Cloud 和 Self-hosted（自托管）对 ChatBI 都只是一个可配置 OTLP/HTTP Endpoint（端点），具体部署方式不影响本次代码 Contract。

### 3.3 为什么 AI 与系统链路共用一套 Trace

- AI Span 记录模型、Token、RAG 资产、候选和 Join 路径。
- System Span 记录 HTTP、数据库和外部调用耗时、状态。
- Business Outcome（业务结果）记录成功、业务拒绝、技术失败、超时或 fallback 成功。

三类信息共用一个 `trace_id`；不得为 Langfuse 和未来 Grafana 分别生成两条互不关联的 Trace。

### 3.4 第三方兼容性验证

2026-09-12 已使用未修改项目依赖的临时 Spike（探针）验证 OpenTelemetry Python `1.44.0`：

- `AlwaysOff` Sampler（采样器）不记录 Span，但仍产生合法 Trace ID；
- W3C `traceparent` 能继承指定 Trace ID；
- `InMemorySpanExporter` 可用于确定性测试；
- OTLP/HTTP Exporter 可显式接收秒单位的 `timeout=5.0`。

因此关闭 Export 时可以保留合法链路编号，测试可以直接检查完成的 Span。W3C 继承能力只用于内部上下文和测试；由于当前没有可信 Gateway（网关），V1 的 HTTP 边界不信任客户端传入的 `traceparent` / `tracestate`，不会直接继承它们。为避开通用 OTLP Timeout 环境变量在不同语言 SDK 中的单位差异，V1 使用明确标注秒的 ChatBI 配置，并把数值显式传给 Python Exporter。

## 4. 模块和依赖方向

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

## 5. 最小内部 Contract

### 5.1 TraceRecorder

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

### 5.2 Safe Wrapper

所有业务调用方只获得 Safe Wrapper。底层 Adapter 初始化、开始 Span、写属性或结束 Span 发生异常时：

1. 写一条不含配置值和 Secret 的安全 Warning；
2. 当前操作退化为 No-op；
3. 查询继续执行；
4. 不触发业务重试。

异常处理必须显式安全化：

- 每个 OTel Span 都使用 `record_exception=false` 和 `set_status_on_exception=false`；
- 不调用 `record_exception()`，不把 `str(exc)`、堆栈、连接信息或 Provider 原始响应写入 Span；
- 只允许写入固定枚举中的 `chatbi.error.type`、公开 `chatbi.error_code` 和受控 Outcome；
- Safe Warning 也只能写组件、阶段和固定错误分类，不得携带原始异常文本；
- 如果未来需要完整堆栈，只能进入单独的受保护、脱敏后的内部日志链路，不属于本 V1 Trace 和 Langfuse 数据。

OTLP 使用 `BatchSpanProcessor` 异步批量发送。不得在每次查询结束时调用 `force_flush()`，避免平台延迟进入查询响应时间。

### 5.3 QuerySource

为记录请求来源，在内部 Contract 增加：

```text
QuerySource = HTTP | INTERNAL | EVALUATION
QueryRequest.source = INTERNAL
```

这是向后兼容的内部扩展：现有调用方不传时仍为 `INTERNAL`；HTTP Body 和 JSON Response 都不增加该字段。

## 6. Trace 生命周期和上下文传播

### 6.1 HTTP 路径

Query API 增加只覆盖 `/api/v1/query` 的 Middleware（中间件）：

```text
读取或生成 request_id（早于请求体解析）
  -> 忽略客户端提供的 W3C traceparent / tracestate
  -> 创建带 request_id 的本地 query.request
  -> 调用 FastAPI 校验、路由和 OnlineQueryService
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

FastAPI Middleware 持有 HTTP 路径的 Root Trace（根链路），所以能够覆盖请求解析和响应序列化。`OnlineQueryService` 发现活动 Query Trace 后复用它。

### 6.2 直接调用和 Evaluation 路径

直接调用没有 Middleware，因此 `OnlineQueryService.query()` 使用同一个 `query_trace()` Contract：

- 没有活动 Trace：创建 `query.request`；
- 已有活动 Trace：继续使用；
- Evaluation 创建 `QueryRequest(source=EVALUATION)`；
- Root Span 记录 `evaluation.case_id`，通过现有 `request_id=evaluation-<case_id>` 关联评测案例。

Evaluation 外层拥有自己创建的 Root Trace；`OnlineQueryService` 只借用该 Trace。直接调用没有外层 Trace 时，由 Service 拥有并结束 Root Trace。所有拥有者退出时都必须清理 Context，避免下一次请求继承上一条链路。

直接调用没有 HTTP 序列化，因此不得伪造 `response.serialize` Span。

### 6.3 Trace ID 与 Request ID

- `trace_id` 来自可信的进程内活动上下文或本次执行生成；V1 HTTP 不采信客户端传入的 W3C 上下文。
- `request_id` 继续由现有 `_resolve_request_id()` 产生。
- `query.request` 在 Root Trace 创建时写入 `chatbi.request.id`；因此请求体解析失败也能保持 `request_id` 与 `trace_id` 的关联。
- 两个编号可以互相检索，但不能互相替代。

## 7. Span 落位

### 7.1 Online Query 主链路

`src/online_query/service.py` 负责以下 Span：

| Span | 实际代码边界 | 成功输出 | 失败/拒绝 |
|---|---|---|---|
| `query.request` | 一次 `query()` 或整个 HTTP Query 生命周期 | 最终状态、行数、截断 | 公开错误码和安全失败分类 |
| `request.validate` | 请求编号和 question 校验 | 合法请求 | `INVALID_REQUEST` |
| `retrieval.plan` | `build_retrieval_request()` | shape、fallback policy | 安全技术分类 |
| `retrieval.execute` | `RetrievalProvider.retrieve()` 与结果处理 | asset、状态、候选数量 | 无候选、技术失败、fallback |
| `prompt.build` | `build_prompt()` | Prompt 长度，不含正文 | 安全技术分类 |
| `llm.generate` | `SQLGenerator.generate()` | model、Token、耗时 | `LLM_ERROR` 或 `CANNOT_ANSWER` |
| `candidate_scope.validate` | `validate_candidate_scope()` | 通过 | `SQL_REJECTED` |
| `sql.guard` | `validate_sql()` | SQL Hash | `SQL_REJECTED` |
| `database.execute` | `QueryExecutor.execute()` | 行数、截断 | 超时或数据库错误 |

`response.serialize` 只在 `src/query_api/app.py` 的 `_result_response()` 中记录，范围是构造最终 `JSONResponse` 的 JSON 序列化，不延伸到 FastAPI/ASGI 的网络发送过程。

### 7.2 Retrieval 内部

`src/online_query/retrieval.py` 在现有调用位置记录：

| Span | 边界 |
|---|---|
| `asset.resolve` | `RagRuntime.get_snapshot()` |
| `embedding.query` | 实际 Query Embedding 调用；基线和多指标按真实调用次数记录 |
| `table.search` | 现有 TABLE Search 调用 |
| `metric.search` | 现有一次综合指标检索，不新增第二次检索 |
| `column.search` | 在候选表范围内执行现有 COLUMN Search |
| `join.resolve` | 现有确定性关系图路径解析 |
| `context.assemble` | Dynamic Schema、指标上下文和 `QueryContext` 组装 |

规则：

- Span 包裹现有调用，不能改变调用顺序和次数。
- 只有实际执行了对应动作才创建 Span。
- Multi-Metric（多指标）仍只做规格确认的一次综合指标检索。
- Static fallback（静态回退）的上下文组装在 Service 中记录 `context.assemble`，并标记 `context_source=static_fallback`。
- 不记录原始 `warnings` 文本，只记录受控状态和分类。

### 7.3 LLM Token

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

## 8. 属性和状态规则

### 8.1 Resource 属性

由 SDK 初始化一次：

```text
service.name
service.version
deployment.environment.name
```

### 8.2 ChatBI 属性命名

项目特有字段统一使用 `chatbi.*`：

```text
chatbi.request.id
chatbi.request.source
chatbi.outcome
chatbi.error_code
chatbi.error.type
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

### 8.3 Outcome 与 OpenTelemetry Status

| ChatBI Outcome | OTel Status | 使用场景 |
|---|---|---|
| `SUCCESS` | `OK` | 查询或节点成功 |
| `BUSINESS_REJECTION` | `UNSET` | 无法回答、请求无效、SQL 被安全拒绝 |
| `TECHNICAL_FAILURE` | `ERROR` | LLM、Retrieval、数据库等技术失败 |
| `TIMEOUT` | `ERROR` | 数据库超时 |
| `FALLBACK_SUCCESS` | `OK` | 原路径失败但允许的 fallback 成功 |

业务拒绝不冒充系统故障，但必须记录公开 `error_code`。发生 fallback 时，原失败 Span 标为 `ERROR`，上层 `retrieval.execute` 标为 `FALLBACK_SUCCESS`；如果最终查询成功，Root Trace 最终仍为 `SUCCESS`。

OTel Status 也不能从异常自动带出原始文本：所有 `start_as_current_span()` 调用显式关闭自动异常记录和自动 Status 描述；业务代码只根据固定映射写入 `StatusCode.ERROR` 或受控的 `StatusCode.UNSET`。Trace 仅记录固定的 `chatbi.error.type` 和公开 `chatbi.error_code`，不记录异常类名、`str(exc)`、完整堆栈、连接信息或 Provider 原始响应。

## 9. 内容安全

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

即使开启也不记录 Prompt、候选 SQL 和结果行。内容调试必须同时满足 `CHATBI_TRACE_CONTENT_ENABLED=true` 且 `CHATBI_RUNTIME_ENV` 明确属于 `local`、`dev` 或 `test`；环境值大小写不敏感，但缺失、空值、`production`、`staging`、未知值或重复冲突配置都按关闭处理。若运行环境为生产或无法确认环境，必须强制记录 `chatbi.content_capture.enabled=false`。

生产边界：Trace/Langfuse 只记录固定错误类型、公开错误码和必要的耗时状态，不记录原始异常消息或堆栈。生产排障若需要堆栈，应由后续独立的受保护日志方案承担，并进行脱敏、访问控制、保留期和审计；不能通过放宽 Trace 内容开关实现。

## 10. 配置设计

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

## 11. 组装和生命周期

### 11.1 Query API

`src/query_api/main.py`：

1. 继续使用 `load_local_environment()`，且不覆盖平台注入变量；
2. 构建一个 Safe `TraceRecorder`；
3. 将同一个实例传给 `LangChainSQLGenerator`、`OnlineRetriever`、`OnlineQueryService` 和 `create_app()`；
4. `create_app()` 注册只覆盖 Query API 的 Middleware：在 FastAPI 解析请求体前先解析或生成 `request_id`，再创建带该编号的 Root Trace，并把编号传入路由和 Service；
5. FastAPI shutdown 时尝试异步队列 Flush/Shutdown；失败只写安全 Warning。

### 11.2 Evaluation

`src/evaluation/__main__.py` 使用相同构造函数创建 TraceRecorder，并将同一实例传入正式查询链路。`run_evaluation()` 增加有默认值的可选 TraceRecorder 参数，每个实际调用 Online Query 的案例由 Evaluation 外层持有 TraceScope，Service 复用该 Trace。CLI 退出前只执行一次 Flush，使 20 个案例的 Span 能发送完成。

`CaseEvaluation` 和 JSON/Markdown 报告增加可选 `trace_id`：

- 实际执行 Online Query 的案例，无论成功、公开业务失败、Unexpected Return（非预期返回）还是捕获异常，都写入对应 Trace ID；
- 在案例格式、Gold SQL 或 Gold 结果阶段已判为 `INVALID_CASE`，且没有执行 Online Query 时为 `null`；
- JSON 明确输出 `trace_id`；Markdown 对每个实际执行案例列出 `case_id`、`request_id` 和 `trace_id`；
- 不在报告中复制整棵 Trace、Prompt 或 Span 属性；
- 旧 Baseline（基线）没有该字段时仍可读取和比较。

### 11.3 Streamlit

`src/streamlit_app.py` 从成功响应和 `HTTPError` 的 `X-Trace-ID` Header 读取 Trace ID：

- 成功页面显示“链路编号”；
- 错误页面同时显示请求编号和链路编号；
- Header 缺失时保持兼容，不把它当作查询失败；
- Trace ID 只保存在页面本地响应对象，不伪装成 Query API JSON 字段。

## 12. 影响分析

### 12.1 Caller 和 Contract

- Query API JSON Body、HTTP 状态和公开错误码不变。
- Query API 新增 `X-Trace-ID` Response Header。
- `QueryRequest` 增加有默认值的内部 `source` 字段。
- Evaluation 单案例和报告增加可选 `trace_id`，旧报告缺失时保持兼容。
- `SQLGenerator`、`QueryExecutor` 和 `RetrievalProvider` 的方法签名不变。
- 相关构造函数增加可选 `TraceRecorder`，默认使用 No-op，保持现有测试和内部调用兼容。

### 12.2 数据和数据库

- 不修改 PostgreSQL Schema、业务数据、结构 JSON、指标 JSON、RAG 资产或 Qdrant Collection。
- Trace 数据只发送到配置的可观测后端。

### 12.3 性能

- 业务线程只创建 Span 和写少量属性。
- OTLP 使用后台 Batch Export，不在请求结束时同步等待网络。
- 不增加 RAG、LLM 或数据库调用。
- V1 不设定性能提升目标；通过 C05 建立节点耗时 Baseline。

### 12.4 部署

- 不要求现有 Docker Compose 新增服务。
- 没有 Langfuse 时可以关闭 Export 正常运行。
- 将来插入 Collector 时只修改 OTLP Endpoint 和 Header，不修改业务节点代码。

## 13. 可验证开发任务

每个 Task 以完整可验证行为为边界，不按单个文件机械拆分。

### T1：Trace Core、生命周期与安全降级

范围：

- 增加 OTel 依赖并更新 `uv.lock`；
- 实现配置、Contract、No-op、Safe Wrapper、OTLP/HTTP Adapter；
- 实现 Root/Borrowed Scope 所有权、Context 清理和受控异常映射；
- 提供 In-memory 测试构造；
- 更新 `.env.example`。

完成标准：

- 能创建 Root/Child Span 和 32 位 Trace ID；
- 进程内活动上下文可以被内部调用继承；T1 不承担 HTTP Header 解析或 HTTP Trace Context 信任边界；
- 关闭模式使用本地 OTel SDK 的 `AlwaysOff`，仍生成非零合法 Trace ID；
- 关闭、错误配置和故障 Adapter 不影响调用方；
- 默认属性不包含配置值、Secret、原始异常消息和堆栈；
- 同一请求只有一个 `query.request`，借用者不结束外层 Root，Root 最后结束且 Context 不泄漏；
- T1 测试独立通过。

### T2：Online Query 主链路

范围：

- 扩展 `QuerySource`；
- 接入 `query.request` 到 `database.execute` 的主链路 Span；内部 Retrieval 细分 Span 留给 T3A；
- 实现 Outcome、错误分类、SQL Hash 和 fallback 状态。

完成标准：

- 成功和每个公开错误分支产生正确的实际 Span；
- SQL Guard 拒绝时没有 `database.execute`；
- Retrieval 总体状态、fallback 原失败和最终路径同时可见；
- 注入故障 Recorder 时业务结果完全一致；
- “公开错误分支”仅指 `OnlineQueryService` 内部业务/技术分支；HTTP 无效 JSON 和请求校验失败归 T4A；
- T2 测试独立通过。

### T3A：Retrieval 细分信息

范围：

- 接入 asset、embedding、TABLE、METRIC、COLUMN、Join、Context Span；
- 记录资产版本、候选数量、选中资源和 Join Edge；
- 保持一次综合指标检索。

完成标准：

- Span 次数与真实调用次数一致；
- 多指标检索没有新增调用；
- 默认 Trace 不含问题、Prompt、SQL 正文、RAG 正文和结果行；
- T3A 测试独立通过。

### T3B：LLM Generation 与 Token

范围：

- 记录 `llm.generate` 的标准 GenAI 模型、操作和 Token 属性；
- 提取可选 Token，并按字段逐个回退；
- 验证 Langfuse Generation 映射所需字段，不改变 `SQLGenerator` 返回 Contract。

完成标准：

- 模型标识和 `llm.generate` Span 正确记录；
- Token 存在时记录，缺失或无效时忽略；
- 默认 Trace 不含问题、Prompt、SQL 正文和 Provider 原始响应；
- T3B 测试独立通过。

### T4A：Query API Header 与 HTTP 生命周期

范围：

- 在请求体解析前读取或生成 `request_id`，再创建带该编号的 Root Trace；
- Query API 忽略不可信客户端 `traceparent` / `tracestate`，创建本地 Trace 并返回 `X-Trace-ID`；
- 将同一个 `request_id` 传入路由、Service、响应体和 Root Trace；
- 在 `app.py` 的 `_result_response()` 中记录 `response.serialize`，只覆盖最终 JSONResponse 构造，不追踪网络发送；

完成标准：

- HTTP 成功、公开失败、空问题和无效 JSON 都有 `X-Trace-ID`；
- 上述请求都能关联同一个 `request_id`，包括请求体解析失败；
- Header 与本地 Root Trace 一致，客户端伪造 Header 不会改变 Root Trace；
- `response.serialize` 是 `query.request` 的子 Span，Root 最后结束；
- T4A 测试独立通过。

### T4B：Evaluation Trace 关联与报告

范围：

- Evaluation 标记来源和案例关联；
- 为 JSON/Markdown 报告增加兼容的 `trace_id` 展示；

完成标准：

- 成功、公开失败、非预期返回和异常案例保留 `trace_id`；
- 未执行 Online Query 的非法案例 `trace_id=null`；
- Evaluation 每个实际查询可以按 `case_id`、`request_id` 和 `trace_id` 找到 Trace；
- 旧 Baseline 仍可读取和比较；
- T4B 测试独立通过。

### T4C：Streamlit 展示与 Runbook

范围：

- Streamlit 显示 Trace ID；
- 更新 Runbook（运行手册）。

完成标准：

- 成功和错误页面都能显示 Header 中的 Trace ID；
- Header 缺失时保持兼容，不把它当作查询失败；
- Runbook 明确说明如何使用 Trace ID 定位节点，以及生产环境不查看原始异常内容；
- T4C 测试独立通过。

### T5：Langfuse / 业务验收 Gate

范围：

- 这是最终验收 Gate，不是普通编码任务，不单独引入业务代码或独立 Commit；
- 前置依赖 T1、T2、T3A、T3B、T4A、T4B、T4C 均已完成并通过各自测试；
- 通过 `.env` 连接一个可用 Langfuse OTLP/HTTP Endpoint；
- 执行 C05 成功查询和一个受控失败请求；
- 运行 20 条真实 Online RAG Evaluation；
- 记录验收证据，不提交 Secret 和原始敏感 Trace 内容。

完成标准：

- C05 能通过页面 Trace ID 在 Langfuse 找到完整实际链路；
- 能明确指出 C05 最慢的节点；
- 受控失败能定位到决定节点；
- `llm.generate` 在 Langfuse 中显示为 Generation，并能看到模型和可用 Token；
- 20 条 Evaluation 的业务结果不因接入 Trace 变化；
- 全量 Software Test、AI Evaluation、Diff Review 和 Secret 检查通过；
- T5 只产出验收证据和结论，不产生普通实现 Commit。

## 14. 验证证据

### 14.1 Software Test

- `tests/observability/`：Contract、No-op、上下文继承、Safe Wrapper、Exporter 配置和安全字段。
- `tests/online_query/`：全部成功、拒绝、失败、超时和 fallback Span。
- `tests/query_api/`：Trace Header、无效请求和响应序列化。
- `tests/streamlit/`：成功和错误 Header 显示及缺失兼容。
- `tests/evaluation/`：Evaluation 来源和案例关联。
- T1～T4C 已分别完成并通过各自测试，独立提交为 `97a2d15`、`9935731`、`1243796`、`d23f8e4`、`e187282`、`eb56975`、`c60e073`。
- 当前全量确定性测试：230 passed、6 skipped、79 subtests。
- 本地 Query API 的 C05 成功请求和空问题受控失败均已验证返回 `X-Trace-ID`。

### 14.2 AI Evaluation

- 使用原有 20 条案例和正式 Online Query 链路，评测运行标识为 `20260912T145505Z-c60e073`，结果为 20/20，C05 为 PASS；对应 JSON / Markdown 原始报告按仓库本地策略忽略；
- Evaluation 报告已记录每个实际查询的 `request_id` 和 `trace_id`，C05 为 `request_id=evaluation-C05`、`trace_id=b88a9d4e50ffd73a7f05cd62c573e4fb`；
- 只建立 Latency/Token Baseline，不预设优化结论。

### 14.3 Business Acceptance

- 本地 API 已完成 C05 成功和空问题受控失败验收，均验证 `X-Trace-ID`；
- 外部 Langfuse Endpoint 未配置，按 T5 完成条件要求的 Langfuse 链路查询、Generation 映射和外部业务验收 Gate 待补；当前不能宣称 T5 PASS 或 Production Ready。

## 15. 回滚

运行时优先回滚：

```text
CHATBI_OBSERVABILITY_ENABLED=false
```

关闭后不导出 Trace，但本次 V1 已实现的 Trace ID、Header 和埋点代码仍存在；它不是完整代码回滚，只是 Export Kill Switch（停止导出开关）。

完整代码回滚必须按已提交任务的逆序移除：`T4C -> T4B -> T4A -> T3B -> T3A -> T2 -> T1`；T5 是验收 Gate，不产生需要回滚的代码。完成后重新验证 API Body/Status、调用次数、原有日志和全量确定性测试。回滚不需要修改数据库、Qdrant、RAG 资产或指标目录；可观测后端中的历史 Trace 与业务数据库相互独立。

## 16. 非目标和后续演进

V1 不实现：

- Prometheus/Mimir Metrics；
- Loki Logs；
- Tempo/Grafana Dashboard；
- Alert（告警）、SLO、采样和长期保留策略；
- Langfuse Prompt Management、Dataset、Online Judge 或费用核算；
- 用户、租户和数据权限；
- Collector、Kubernetes 和 Gateway 部署。

这些能力后续仍复用相同 OpenTelemetry/OTLP Contract 和 `trace_id`，不重新建设第二套埋点。

## 17. 设计决定

| 编号 | 决定 |
|---|---|
| ID1 | 使用 OpenTelemetry SDK，业务模块只依赖项目 Trace Contract |
| ID2 | V1 使用 OTLP/HTTP，Langfuse 是第一个验收平台 |
| ID3 | V1 不引入 Langfuse SDK、LangSmith 或全量自动埋点 |
| ID4 | AI、系统和业务观察共用一个 `trace_id` |
| ID5 | HTTP Middleware 持有 HTTP Root Trace，Service 为直接调用补建 Root Trace |
| ID6 | TraceRecorder 必须 No-throw，Exporter 使用后台 Batch，不进入业务延迟 |
| ID7 | 默认不记录内容；本地调试只允许问题和已校验 SQL |
| ID8 | Collector、Tempo/Grafana、Metrics、Logs 和 Alert 后续建设 |
| ID9 | 实现任务按可独立验证的 T1、T2、T3A、T3B、T4A～T4C 实施，每个任务验证通过后单独提交；T5 只作为最终验收 Gate |
| ID10 | V1 HTTP 不信任客户端 Trace Context；可信 Gateway 接入后再单独开放上游继承 |
| ID11 | OTel/Langfuse 只记录安全错误分类和错误码；原始异常不进入 Trace |
| ID12 | Root Trace 采用明确所有权；借用者不结束、不清理外层上下文 |

## 18. 待设计审查事项

以下事项不改变业务规格，但在编码前必须由下一轮 Design Review 检查：

- `TraceRecorder` Contract 是否足够小，是否存在可以删除的抽象；
- HTTP Root Trace、Evaluation Root Trace 与直接 Service Root Trace 的所有权是否严格互斥；
- HTTP 是否在请求体解析前完成 `request_id -> query.request -> trace_id` 绑定；
- 客户端伪造 `traceparent` 时是否始终生成本地 Root Trace，且不会泄漏到下一次请求；
- `response.serialize` 是否只覆盖 `_result_response()` 的 JSONResponse 构造；
- Retrieval 各分支能否在不改变调用次数的情况下落 Span；
- LangChain 不同 Provider 的 Token Metadata 兼容处理是否按字段逐个回退且严格 fail-open；
- 异常路径是否显式关闭 OTel 自动异常记录，并且没有任何原始异常文本进入 Trace 或 Warning；
- Evaluation 的 success/failure/unexpected/exception 与未执行案例的 `trace_id` 是否符合报告契约；
- Streamlit 保存 Trace ID 的方式是否会误改 API JSON 契约；
- T5 使用 Langfuse Cloud 还是已有 Self-hosted Endpoint；该选择只影响运行配置，不影响代码设计。

## 19. 第三方事实来源

核对日期：2026-09-12。

- [OpenTelemetry 是什么](https://opentelemetry.io/docs/what-is-opentelemetry/)：OTel 负责生成、收集和导出 Telemetry，不是存储与可视化后端。
- [OpenTelemetry Python Exporters](https://opentelemetry.io/docs/languages/python/exporters/)：Python OTLP/HTTP Exporter、Batch Processor 和测试 Exporter 的官方用法。
- [Langfuse OpenTelemetry Integration](https://langfuse.com/integrations/native/opentelemetry)：Langfuse 的 OTLP/HTTP Endpoint、Header、GenAI Attribute Mapping 和当前不支持 OTLP/gRPC 的边界。
- [Grafana Tempo](https://grafana.com/docs/tempo/latest/)：后续通用分布式 Trace Backend 与 Grafana、Logs、Metrics 的关联能力。

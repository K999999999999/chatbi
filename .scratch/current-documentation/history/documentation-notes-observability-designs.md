# Trace生命周期与安全传播：整理前的过程记录

来源：`docs/designs/observability.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# Observability V1 Implementation Design

状态：T1～T5 已完成并通过验收；T1～T4C 已有独立提交，本地 API、真实 Evaluation（评测）和阿里云 OTLP / Trace 外部验收均已完成。当前仍不能称为 Production Ready（生产可用）。

## 1. 结论

Observability V1（可观测性 V1）采用 OpenTelemetry（开放遥测）作为统一 Trace 标准，使用 OTLP/HTTP 导出，并以 Langfuse 作为第一个可视化验收平台。

V1 只实现 Trace：让一次 Online Query（在线查询）从 HTTP、RAG、LLM、SQL Guard 到 PostgreSQL 使用同一个 `trace_id`，能够定位失败节点和主要耗时节点。完整 Metrics、Logs、Alert（指标、日志、告警）以及 Grafana/Tempo 平台留到 Production Hardening（生产加固）阶段。

核心原则：

- ChatBI 核心代码不依赖 Langfuse SDK，只依赖项目自己的最小 Trace Contract（链路契约）。
- Infrastructure Adapter（基础设施适配器）使用 OpenTelemetry SDK 实现该 Contract。
- Langfuse 只作为可替换的 OTLP Backend（后端），不拥有 ChatBI 业务事实。
- Trace 是旁路能力；初始化、记录或导出失败不得改变查询结果、错误码和调用次数。
- 默认不记录完整问题、Prompt、SQL、结果或原始异常。

行为事实源为 [Observability V1 Module Spec](../../../docs/specs/observability.md)。本设计只决定如何实现已确认行为。

## 2. 当前事实与目标行为

### 2.1 当前事实

- `AuthorizedQueryService.query()` 是用户查询的唯一正式 Application Entry；`OnlineQueryService.execute()` 只是授权后的同步下游执行操作。
- Query API 使用 FastAPI，同步调用 `AuthorizedQueryService`，再进入 `OnlineQueryService`。
- Evaluation（评测）调用绑定测试身份的 `BoundAuthorizedQueryService`，不经过 HTTP。
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

### T5：Langfuse / 业务验收 Gate（已完成）

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
- `frontend/tests/query.spec.ts`：成功和错误 Header / 请求编号展示；`tests/query_api/test_browser_auth.py`：CSRF 拒绝仍保留关联。
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
- 阿里云 Trace 控制台已确认 C05 成功链路和空问题受控失败链路可查询：C05 为 `eb14f55bbe07d6f15bdd69d48b440430`，失败请求为 `92d99ceb7aa39d25140b444379eba6d5`；
- C05 HTTP 结果为 200、返回 3 行且未截断；受控失败 HTTP 结果为 400，错误码为 `INVALID_REQUEST`；
- 独立 OTLP Endpoint 探针返回 `SUCCESS`，`llm.generate` 的 Generation 映射、节点耗时和失败定位已按阿里云控制台完成核对；
- T5 Business Acceptance Gate 已通过，但不因此宣称 Production Ready（生产可用）。

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
- Web 客户端保存 Header Trace ID 的方式不得误改 API JSON 契约；
- T5 使用 Langfuse Cloud 还是已有 Self-hosted Endpoint；该选择只影响运行配置，不影响代码设计。

## 19. 第三方事实来源

核对日期：2026-09-12。

- [OpenTelemetry 是什么](https://opentelemetry.io/docs/what-is-opentelemetry/)：OTel 负责生成、收集和导出 Telemetry，不是存储与可视化后端。
- [OpenTelemetry Python Exporters](https://opentelemetry.io/docs/languages/python/exporters/)：Python OTLP/HTTP Exporter、Batch Processor 和测试 Exporter 的官方用法。
- [Langfuse OpenTelemetry Integration](https://langfuse.com/integrations/native/opentelemetry)：Langfuse 的 OTLP/HTTP Endpoint、Header、GenAI Attribute Mapping 和当前不支持 OTLP/gRPC 的边界。
- [Grafana Tempo](https://grafana.com/docs/tempo/latest/)：后续通用分布式 Trace Backend 与 Grafana、Logs、Metrics 的关联能力。

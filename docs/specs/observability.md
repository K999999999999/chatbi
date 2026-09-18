# Observability V1 Module Spec

状态：行为规格已补充 request_id/trace_id 时序和 HTTP 观测边界；T1～T4C 已完成并通过各自测试。T5 Langfuse / Business Acceptance Gate（业务验收门禁）已通过阿里云 OTLP / Trace 外部验收；当前仍不代表 Production Ready（生产可用）。本规格行为和生产边界保持不变。

## 1. 目标

为现有同步 Online Query（在线查询）建立端到端可观测链路，使开发者和运维人员能够根据一次请求判断：

- 请求成功还是失败；
- 时间主要花在哪个处理节点；
- 失败、拒绝或 fallback（回退）发生在哪个节点；
- 使用了哪个 RAG 资产版本、哪些候选资源和哪个模型；
- 查询业务结果是否在接入可观测能力后保持不变。

Observability 只记录和关联已有业务行为，不决定业务事实、RAG 候选、SQL、权限或查询结果。

## 2. 使用者

- 开发者：定位 RAG、LLM、SQL Guard（SQL 安全检查）和数据库问题。
- 运维人员：根据请求编号查找 Trace（链路）并判断慢点和故障节点。
- 评测执行者：关联评测用例、运行耗时、模型和 RAG 资产版本。
- API 调用方：获得可以用于问题反馈的请求编号和 Trace 标识。

## 3. 当前事实

- Query API 和 Online Query 已使用 `request_id` 关联请求，Streamlit 会展示该编号。
- Evaluation（评测）只记录一次查询的总耗时，没有节点耗时。
- Online Query 只在部分 Retrieval fallback 场景写入日志，没有完整成功和失败 Trace。
- Online Retrieval 已返回 `asset_version`、状态、候选命中、分数、Join 路径和原始检索证据。
- 当前 LLM Adapter（适配器）只向核心链路返回 SQL 文本，模型返回的 Token 信息未被记录。
- 当前没有 `trace_id`、统一 Span（链路节点）、可观测后端或告警。

## 4. 运行方式

- 沿用同步、单次请求/响应的 Online Query 运行方式。
- API 请求和调用 `BoundAuthorizedQueryService.query()` 的评测路径都必须可以形成完整 Trace；下游 `OnlineQueryService.execute()` 继续复用活动 Trace。
- 进程内已有可信活动 Trace 时继续使用；HTTP 客户端传入的 `traceparent` / `tracestate` 在 V1 不视为可信上游，不直接继承；没有可信活动 Trace 时由系统创建。
- HTTP Middleware 必须在请求体解析前先读取或生成 `request_id`，再创建带该编号的 Root Trace；同一个 `request_id` 必须传入后续 Service 和响应体。
- 可观测记录属于旁路行为，不增加业务重试，不改变节点顺序和调用次数。
- 可观测能力关闭、配置错误或后端不可用时，查询主链路继续按原 Contract 运行。

## 5. 标识契约

### 5.1 request_id

- 保留现有语义，用于 API 响应、用户反馈和业务请求关联。
- 可以由调用方提供，也可以由系统生成。
- 相同 `request_id` 不代表相同 Trace，不得用它代替 `trace_id`。

### 5.2 trace_id

- 标识一次实际执行链路，由可信的进程内活动上下文继承或由系统生成。
- Root Trace（根链路）必须记录对应的 `request_id`。
- HTTP 成功和失败响应都必须通过 `X-Trace-ID` Header（响应头）返回 `trace_id`。
- 现有成功和失败 JSON Body（响应体）保持不变，不新增公开业务字段和错误码。
- 无效请求和请求体解析失败也必须产生 `trace_id`。
- V1 不接受客户端直接指定 `X-Trace-ID`，也不把客户端 `traceparent` / `tracestate` 作为根链路来源；将来只有在可信 Gateway 建立边界并完成单独设计审查后，才能开放受控继承。
- Root Trace 的 `request_id` 绑定发生在请求体解析前；`response.serialize` 仅表示 API Adapter 构造最终 JSONResponse，不包含 FastAPI/ASGI 网络发送。

## 6. 观察范围

Root Trace 覆盖一次查询从接收到返回的完整生命周期。实际执行到的节点必须记录独立 Span：

```text
query.request
  -> request.validate
  -> retrieval.plan
  -> retrieval.execute
       -> asset.resolve
       -> table.search
       -> metric.search
       -> column.search
       -> join.resolve
       -> context.assemble
  -> prompt.build
  -> llm.generate
  -> candidate_scope.validate
  -> sql.guard
  -> database.execute
  -> response.serialize
```

规则：

- 没有执行的节点不得伪造 Span。
- METRIC 路线仍然只执行既有的一次综合指标检索，记录 Span 不得导致重复检索。
- Retrieval 总 Span 和已执行的内部 Span 都要记录耗时，便于区分 Embedding、搜索、Join 和上下文组装问题。
- fallback 必须同时记录原失败状态、实际采用的路径和最终结果。
- 业务拒绝、技术失败和成功必须使用不同状态表达，不得都记录为普通成功。

## 7. 最小观察数据

### 7.1 全链路

- `request_id`、`trace_id`；
- 服务和应用版本；
- 运行环境；
- 请求来源：HTTP、内部调用或 Evaluation；
- 开始时间、结束时间和总耗时；
- 最终状态、公开 `error_code` 和安全的内部失败分类。

### 7.2 Retrieval

- `request_shape`、`fallback_policy` 和 Retrieval 状态；
- `asset_version`；
- TABLE、COLUMN、METRIC 候选数量；
- 被选择候选的 `document_id`、rank 和 score；
- Join 路径涉及的表和 `edge_id`；
- 是否发生 fallback 及其安全原因分类。

不得记录完整 `page_content`、完整 Metadata（元数据）或 Dynamic Schema（动态结构）文本。

### 7.3 LLM

- 模型标识；
- 调用耗时和成功、失败状态；
- Provider 返回时记录输入、输出和总 Token 数；
- Token 信息缺失不得导致查询失败；
- `llm.generate` 使用标准 GenAI 操作、模型和 Usage 属性；若通用属性不能被验收平台识别，只能在基础设施适配器中增加最小平台兼容字段；
- V1 不计算或承诺费用。

### 7.4 SQL 与数据库

- Candidate Scope Check（候选范围检查）是否通过；
- SQL Guard 是否通过及安全失败分类；
- 默认只记录 SQL 摘要或 Hash（哈希），不记录完整 SQL；
- 数据库执行耗时、成功、错误或超时状态；
- 返回行数和 `truncated`；
- 不记录完整结果行。

## 8. 内容和安全边界

默认不得记录：

- LLM API Key、数据库密码、Token、证书和连接字符串；
- 完整用户问题、Prompt、候选 SQL、最终 SQL；
- 完整查询结果；
- RAG 文档正文和完整 Metadata；
- 可能包含 Secret 或敏感数据的原始异常消息和堆栈。

异常安全规则：

- OTel/Langfuse 不自动记录完整异常、堆栈或 `str(exc)`；
- 只记录固定错误类型、公开错误码和受控状态；
- 生产环境如果未来需要完整排障堆栈，应进入独立的受保护、脱敏内部日志系统，不通过放宽 Trace 内容开关实现；该日志系统不属于本 V1。

本地受控调试可以通过独立配置临时记录完整问题和最终校验 SQL，但必须满足：

- 默认关闭；
- 只有运行环境明确为 `local`、`dev` 或 `test` 且独立开关显式开启时允许；缺失、空值、`production`、`staging` 或未知环境一律关闭；
- 不记录完整 Prompt、完整查询结果和 Secret；
- 关闭后无需修改代码或业务 Contract；
- Trace 中明确标识当前是否启用了内容记录。

## 9. 成功、失败和降级

- 查询成功：Root Trace 和全部已执行 Span 标记成功，并记录最终行数和截断状态。
- 业务无法回答：在发生决定的节点记录业务拒绝，最终状态关联 `CANNOT_ANSWER`。
- SQL 被拒绝：对应检查 Span 标记拒绝，数据库 Span 不得出现。
- LLM、Retrieval 或数据库技术故障：对应 Span 标记技术失败并记录安全分类。
- 数据库超时：数据库 Span 标记超时，最终状态关联 `QUERY_TIMEOUT`。
- Retrieval fallback：原失败 Span 和 fallback 路径都必须可见。
- 可观测后端不可用：不得改变原 QuerySuccess、QueryFailure、HTTP 状态和错误码，不得触发业务重试。
- 可观测功能关闭：查询输入、输出、调用次数和原有日志行为保持兼容。

## 10. 不负责

- 用户登录、用户管理、角色、租户、数据权限和安全审计。
- 限流、Quota（配额）、熔断、模型路由和自动 Failover（故障切换）。
- 多轮对话、经营分析和 Agent。
- Prompt 管理、在线自动评判和自动修复。
- 完整系统 Log/Metric/Alert（日志、指标和告警）平台。
- 前端浏览器性能追踪。
- 可观测数据长期保存、采样和生产容量规划。
- Secret 管理、Kubernetes、Gateway（网关）和发布平台。
- 具体 SDK、平台产品、部署方式和代码目录。

## 11. 验收标准

### 11.1 Software Test（软件测试）

- 成功请求生成一个 Root Trace，并包含全部实际执行的必需 Span。
- 每个现有公开失败分支都能在决定节点和 Root Trace 上得到正确状态。
- SQL Guard 拒绝时不会出现数据库执行 Span。
- 无效 HTTP 请求仍返回原错误 JSON，并包含 `X-Trace-ID`。
- `request_id` 与 `trace_id` 能稳定关联，但保持不同语义。
- Token 信息存在时被记录，缺失时不影响查询。
- 默认 Trace 不包含完整问题、Prompt、SQL、结果、Secret 或原始敏感异常。
- 客户端伪造 Trace Context 不会改变 V1 HTTP Root Trace；一次请求只产生一个 Root Trace，且上下文不会泄漏到下一次请求。
- OTel 自动异常记录关闭时，异常消息和堆栈不会进入 Trace、Langfuse 或安全 Warning。
- 可观测后端抛出异常、超时或不可用时，原查询结果不变。
- 可观测能力关闭时，原有确定性测试继续通过。

### 11.2 AI Evaluation（AI 评测）

- 现有 20 条真实 Online RAG Evaluation 使用原查询链路运行，业务结果不因可观测接入而变化。
- 每个评测请求能够关联模型、RAG 资产版本、总耗时和实际执行节点。
- 本阶段只建立节点延迟和 Token Baseline（基线），不预设性能提升目标。

### 11.3 Business Acceptance（业务验收）

- 使用 C05 查询完成一次真实 Trace。
- 能明确指出延迟主要位于 Retrieval、LLM、SQL Guard 还是数据库。
- API 和页面返回的业务结果与接入前一致。
- 至少一个受控失败请求能够定位到具体失败节点。

## 12. 实现设计阶段再决定

- 具体可观测 SDK、后端和部署方式；
- Span 与代码函数的落位；
- Trace 上下文传播方式和框架集成；
- Token Metadata（元数据）的提取方式；
- 配置项名称和 No-op（空实现）Adapter；
- 测试替身、Exporter（导出器）和验收运行方式；
- 后续采样、保留时间、Dashboard（看板）、告警和系统指标方案。

## 13. 已确认决定

| 编号 | 决定 |
|---|---|
| D1 | 保留 `request_id`，新增独立 `trace_id`，HTTP 通过 `X-Trace-ID` 返回 |
| D2 | 默认不记录完整问题、Prompt、SQL 和结果；本地调试只允许受控开启问题和最终 SQL |
| D3 | Token 为可选观察数据，Provider 未返回时不得失败；V1 不计算费用 |
| D4 | 可观测能力采用 fail-open（记录失败不影响查询）的旁路原则 |
| D5 | V1 覆盖成功、拒绝、技术失败、超时和 Retrieval fallback |
| D6 | 用户、租户、权限、生产告警和具体技术产品不属于本规格 |
| D7 | V1 HTTP 不信任客户端 Trace Context；可信 Gateway 接入后再单独开放上游继承 |
| D8 | OTel/Langfuse 只记录安全错误分类和错误码；原始异常不进入 Trace |

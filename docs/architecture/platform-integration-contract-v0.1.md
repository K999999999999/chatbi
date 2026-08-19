# ChatBI 平台接入通用契约 v0.1

状态：Proposed（设计草案，尚未启用运行时接入）
适用范围：ChatBI 查询应用与外部 API Gateway / AI Platform 的边界

## 1. 目标

ChatBI 核心查询链不依赖 HiMarket、Higress、公司自研中台或其他具体平台。

不同平台通过 Adapter（适配器）接入同一组稳定 Contract（契约）：

```text
Local CLI Adapter
Company Platform Adapter
HiMarket Adapter
Higress Adapter
Other Platform Adapter
          │
          ▼
    ChatBI Application
          │
          ▼
  Domain + Ports + Infrastructure
```

核心原则：

- Stable Core, Replaceable Edge（核心稳定，边缘可替换）。
- 平台负责外围接入能力，ChatBI 负责业务语义、数据权限和 SQL 安全。
- Domain（领域层）和 Application（应用层）不得导入任何平台 SDK。
- 平台特有字段只能存在于 Adapter 和配置层。

## 2. 背景与边界

当前 ChatBI 是本地、单用户、同步执行的 Text2SQL POC：

```text
自然语言问题
→ Prompt
→ LLM 生成 SQL
→ SQL Guard
→ chatbi_app 只读执行
→ 结构化结果
```

本契约只定义未来平台接入边界，不改变当前 POC 的查询行为。

### In Scope（范围内）

- 外部调用者身份如何进入 ChatBI。
- 查询请求和查询响应的稳定结构。
- 统一错误码和可重试语义。
- 平台访问审计与 ChatBI 业务审计的事件边界。
- Gateway、HiMarket、公司中台和本地 CLI 的 Adapter 责任。
- 后续 HTTP 接入时的兼容约束。

### Out of Scope（范围外）

- 当前安装或部署 HiMarket / Higress。
- 当前实现 HTTP API、登录页或多租户系统。
- 当前实现完整 Authorization（授权）引擎。
- 当前实现平台级 Rate Limit（限流）和计费系统。
- 当前选择日志、指标或 Trace 后端。
- 将 HiMarket 或 Higress SDK 引入 ChatBI 核心。
- 将外部平台权限直接当作 ChatBI 数据权限。

## 3. 两个独立的接入边界

平台接入不能设计成一个“大而全”的接口，至少分为两个独立 Contract。

### 3.1 External Access Contract（外部访问契约）

解决：

```text
用户 / 其他系统 / 外部平台
→ ChatBI
```

职责是把外部调用者转换成 ChatBI 可以理解的调用上下文。

### 3.2 Model Provider Contract（模型提供方契约）

解决：

```text
ChatBI
→ 直接模型服务 / AI Gateway / HiMarket / 公司模型中台
→ LLM
```

当前已有的 `LlmClient` 属于这一边界。模型网关以后可以通过 OpenAI-Compatible API 或其他 Adapter 接入，不得与外部用户访问契约混合。

## 4. External Access Contract

### 4.1 RequestContext（请求上下文）

ChatBI 应用层只接收平台无关的上下文：

```text
RequestContext
├── request_id       必填，请求唯一标识
├── trace_id         可选，链路追踪标识
└── caller           可选的调用者身份
```

### 4.2 CallerIdentity（调用者身份）

```text
CallerIdentity
├── subject_id       调用者稳定标识
├── client_id        调用客户端标识，可选
├── tenant_id        租户标识，可选
├── roles            角色集合，可选
├── scopes           权限范围集合，可选
└── identity_source  身份来源标识，可选
```

约束：

- 不保存原始 Token、Secret 或 Authorization Header。
- 不把 `HiMarketConsumer`、`HigressConsumer` 等平台对象传入 Domain。
- `roles` 和 `scopes` 只能作为授权输入，不能直接等同于数据访问权限。
- `tenant_id` 在当前单用户 POC 中不启用；字段保留不代表当前实现多租户。

### 4.3 QueryRequest（查询请求）

```text
QueryRequest
├── question         必填，自然语言问题
└── context          必填，RequestContext
```

Application（应用层）入口应围绕该用例设计：

```text
QueryService.execute(QueryRequest) -> QueryResponse
```

CLI、未来 HTTP API、公司中台 Adapter 和 HiMarket Adapter 都调用同一个 `QueryService`。

### 4.4 QueryResponse（查询响应）

```text
QueryResponse
├── request_id
├── success
├── data
│   ├── columns
│   └── rows
├── metadata
│   ├── metric_codes，可选
│   ├── duration_ms，可选
│   └── debug_sql，可选且默认不对外暴露
└── error，可选
```

约束：

- 执行失败时不得伪造数据。
- `debug_sql` 与原始 Prompt 只允许在受控调试场景返回或记录。
- 对外响应不得泄露数据库密码、Token、完整连接串或内部堆栈。
- 平台适配器可以把该结构映射为平台自己的 HTTP / API Product 响应，但不能改变业务结果语义。

## 5. Authorization Boundary（授权边界）

外部平台认证调用者，ChatBI 判断调用者是否能访问业务数据。

```text
平台身份认证
→ CallerIdentity
→ ChatBI AuthorizationPolicy
→ 指标 / 主题域 / 表 / 字段 / 行级范围判断
→ QueryPipeline
```

ChatBI 内部授权结果至少需要表达：

```text
AuthorizationDecision
├── allowed
├── reason_code
├── policy_version，可选
└── data_scope，可选且必须经过确定性校验
```

安全不变量：

- 外部平台的 API Product 订阅不等于 ChatBI 数据授权。
- LLM 不得决定授权结果。
- 外部平台不得通过传入一段未经校验的 SQL Filter 绕过 ChatBI 授权。
- SQL Guard、数据库只读账号、超时和结果行数限制继续由 ChatBI 保持。

## 6. Unified Error Contract（统一错误契约）

平台和 ChatBI 之间使用稳定的错误类别，不暴露平台或数据库内部细节。

| 错误码 | 含义 | 是否可重试 |
|---|---|---|
| `invalid_request` | 请求为空或格式错误 | 否 |
| `unauthenticated` | 未认证或身份无效 | 否，需重新认证 |
| `forbidden` | 无权访问 ChatBI 或业务数据 | 否 |
| `rate_limited` | 平台或应用达到流量限制 | 是，遵循 `retry_after` |
| `unsupported_question` | 当前 POC 不支持该问题 | 否 |
| `query_rejected` | SQL Guard 或确定性策略拒绝 | 否，需修改问题 |
| `query_execution_failed` | 数据库执行失败 | 视错误类型而定 |
| `provider_unavailable` | LLM 或外部模型服务不可用 | 是 |
| `internal_error` | 未分类的应用错误 | 由运行策略决定 |

错误响应可以包含：

```text
Error
├── code
├── message       面向用户的安全消息
├── retryable
└── retry_after   可选，秒数
```

## 7. Rate Limit 与资源保护

平台级限流和应用级资源保护是两层能力，不互相替代。

### 平台级

由 HiMarket、Higress 或公司网关负责：

- Consumer / client 限流。
- IP 或租户限流。
- API Product 配额。
- Token 或调用次数配额。
- 外部流量熔断。

### ChatBI 应用级

由 ChatBI 自己保证：

- LLM 调用超时。
- 数据库 Statement Timeout。
- 最大返回行数。
- SQL 只读约束。
- 并发查询上限。
- 单次 Prompt 大小限制。

即使没有外部平台，应用级保护也必须存在；即使有外部平台，应用级保护也不能删除。

## 8. Audit 与 Observability Contract

### 8.1 统一事件外壳

```text
PlatformEvent
├── event_id
├── event_type
├── occurred_at
├── request_id
├── trace_id，可选
├── subject_id，可选
├── tenant_id，可选
├── outcome
├── duration_ms，可选
├── error_code，可选
└── attributes，可扩展但不得包含 Secret
```

### 8.2 ChatBI 业务事件

```text
query_received
authorization_denied
llm_call_started
llm_call_completed
llm_call_failed
sql_guard_rejected
query_execution_completed
query_execution_failed
query_completed
```

建议记录：

- 模型名称和版本。
- Prompt 版本。
- SQL Hash，而不是默认记录完整 SQL。
- SQL Guard 结果。
- 数据库耗时。
- 返回行数。
- 结果是否超过限制。

禁止默认记录：

- API Key、Token、密码。
- 完整数据库连接串。
- 未脱敏的敏感业务数据。
- 未经评估就长期保存的完整自然语言问题和完整 SQL。

平台可以记录“谁调用了哪个 API”；ChatBI 必须记录“谁查询了什么业务范围以及查询是否被业务规则拒绝”。

## 9. Adapter Responsibilities（适配器职责）

### LocalCliAdapter

- 当前唯一入口。
- 使用本地调用者上下文。
- 不模拟真实企业登录。

### CompanyPlatformAdapter

- 读取公司标准 Token 或可信身份声明。
- 转换成 `CallerIdentity`。
- 传递请求和 Trace 标识。
- 映射公司平台错误到统一错误码。

### HiMarketAdapter

- 转换 Developer / Consumer / OIDC 身份。
- 映射 API Product 调用信息。
- 接收平台请求限制和平台级错误。
- 不把 HiMarket 产品编号写入 Domain。

### HigressAdapter

- 转换 JWT、API Key 或 OAuth2 调用身份。
- 传递 Consumer 和 Trace 信息。
- 适配网关返回的限流、认证和路由错误。

### OtherPlatformAdapter

- 按相同 `QueryRequest`、`CallerIdentity`、`QueryResponse` 和错误契约接入。
- 平台差异只保留在 Adapter 和配置中。

## 10. Dependency Direction（依赖方向）

目标依赖关系：

```text
Interfaces / Adapters
          ↓
Application QueryService
          ↓
Domain + Ports
          ↑
Infrastructure Adapters
```

禁止依赖：

```text
Domain → HiMarket SDK
Domain → Higress SDK
Domain → HTTP Header
Domain → PostgreSQL Driver
Application → Vendor-specific Consumer Object
```

## 11. Compatibility and Versioning（兼容与版本）

- 当前版本：`platform-integration-contract: 0.1`。
- `QueryRequest`、`QueryResponse` 和错误码的已有字段不随意改名。
- 新字段优先采用向后兼容的可选字段。
- 平台适配器版本与 ChatBI 契约版本分开管理。
- 任何平台特有扩展必须放在 `attributes` 或 Adapter 内，不进入核心领域对象。
- 当前契约不是 HTTP 专属；未来可以映射到 CLI、HTTP、消息或其他调用方式。

## 12. Acceptance Criteria（验收标准）

本契约进入实现阶段前，必须满足：

1. CLI 能通过 `LocalCliAdapter` 调用同一个 `QueryService`。
2. 未来增加 HiMarket 或公司中台 Adapter 时，Application 和 Domain 无平台 SDK 导入。
3. 身份、权限、限流、业务审计和网关访问审计边界清晰。
4. 认证失败、无权访问、限流、SQL 拒绝、数据库失败和模型不可用可以统一表达。
5. 当前 `mart_sales`、`chatbi_app` 只读、SQL Guard、超时和最大行数等安全不变量不改变。
6. 当前 POC 的执行准确率验收不因接入契约而退化。

## 13. 下一步

本契约只完成平台无关边界设计，尚未进入代码实现。

下一步应单独处理：

1. 把当前代码映射到 Interfaces / Application / Domain / Ports / Infrastructure。
2. 确认 `QueryService`、`QueryRequest`、`QueryResponse` 的代码落位。
3. 先实现 `LocalCliAdapter`，保证当前 CLI 行为不变。
4. 再考虑 HTTP Adapter；暂不安装或接入具体中台。

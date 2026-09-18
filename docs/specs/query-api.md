# Query API Adapter Spec

## 目标

使用 FastAPI（Web 框架）把现有 Online Query（在线查询）能力暴露为同步 HTTP JSON 接口，供未来前端、内部应用或 API Gateway（API 网关）调用。

API Adapter（接口适配层）只负责 HTTP 与内部类型之间的转换：

```text
HTTP 请求
  -> server-side AuthContext
  -> Application 会话边界（读取、校验当前会话状态）
  -> AuthorizedQueryService.authorize()
  -> Application 语义修订（已有会话）
  -> AuthorizedQueryService.execute_authorized()
  -> QueryRequest
  -> OnlineQueryService.execute()
  -> 成功后提交 Structured Query State
  -> QuerySuccess / QueryFailure
  -> HTTP JSON 响应
```

不得在 API 层复制或改写 Prompt、LLM 调用、SQL Guard（SQL 安全校验）和数据库执行逻辑。

## 运行方式

- 同步、每次请求/响应；每次下游执行仍然只处理一条有效查询。
- 当前使用 JSON，不使用 SSE（流式推送）或 WebSocket（双向实时连接）。
- API 通过 `AuthorizedQueryService.authorize()` 完成身份与数据授权；已有会话在授权通过后完成语义修订，再由 `execute_authorized()` 调用下游 `OnlineQueryService.execute()`。
- API 不改变 Online Query 的业务规则、超时和结果行数上限；短期会话边界使用本 Spec 定义的 Application 错误码。

## 接口

### 查询

```text
POST /api/v1/query
Content-Type: application/json
X-Request-ID: 可选
```

请求体接受必填 `question` 和可选 `conversation_id`：

```json
{
  "question": "按销售区域拆开。",
  "conversation_id": "server-generated-id"
}
```

- `question` 必填，必须是去除首尾空白后非空的字符串。
- `conversation_id` 可选，只接受服务端生成的会话编号；不接受 `user_id`、`tenant_id`、对话历史、结构化状态、SQL、分页参数或网关内部信息。
- 请求体格式错误、缺少 `question`、`question` 为空或存在未知字段时，返回 `INVALID_REQUEST`。
- `X-Request-ID` 可由调用方或未来网关传入；未传入或为空时沿用 Online Query 自动生成的 `request_id`。

成功响应：

```json
{
  "request_id": "req-123",
  "sql": "SELECT ...",
  "columns": ["product_name", "sales_amount"],
  "rows": [["产品A", 10000]],
  "row_count": 1,
  "truncated": false,
  "conversation_id": "server-generated-id"
}
```

- `rows` 是二维 JSON 数组，顺序与 `columns` 对应。
- 查询成功但没有数据仍返回 `200`、空 `rows` 和 `row_count: 0`。
- `truncated`、`row_count` 和 `sql` 的语义完全沿用 `QuerySuccess`。
- `conversation_id` 是成功响应中的新增字段；既有响应字段和语义不变，既有 JSON 调用方无需改变请求即可继续使用并可忽略该字段。
- 没有传入 `conversation_id` 的首轮成功请求在提交结构化状态后创建会话，并返回服务端生成的 `conversation_id`。

失败响应：

```json
{
  "request_id": "req-123",
  "error_code": "CANNOT_ANSWER",
  "error_message": "当前结构和指标无法回答该问题"
}
```

- `error_code` 和 `error_message` 完全沿用 `QueryFailure`。
- 失败响应不创建新的会话，也不返回新的 `conversation_id`；已有会话的调用方继续使用原编号重试。
- 响应不得包含 Python 异常堆栈、数据库连接信息、API Key 或其他 Secret（密钥）。

### Multi-Turn Query V1（受控多轮查询）

- 没有 `conversation_id` 的请求按单轮查询执行；只有成功结果提交后才创建短期会话。
- 带 `conversation_id` 的请求必须先由当前认证身份校验会话归属、过期状态和并发状态；失败时不得进入 `AuthorizedQueryService`、Retrieval、LLM、SQL Guard 或数据库。
- 会话只保存最后一次成功查询的指标、时间范围、维度和过滤条件，不保存原始对话、候选 SQL、最终 SQL 或结果行。
- 会话使用 30 分钟无成功状态更新的 Idle TTL；服务重启后会话失效。
- 同一会话同一时刻只允许一个进行中的轮次；并发请求返回 `CONVERSATION_CONFLICT`，不调用下游、不提交状态。
- 同一语义槽位的新值替换旧值，不同语义槽位的新条件叠加；歧义和超出单条查询修订范围的问题不执行查询。
- 每一轮都重新使用当前认证身份和当前授权策略；历史状态不能赋予新的权限。

### 健康检查

```text
GET /health
```

响应：

```json
{
  "status": "ok"
}
```

该接口只表示 HTTP 服务正在运行；当前不检查 LLM、数据库或结构文件是否可用。

## HTTP 状态映射

| 情况 | HTTP 状态 | error_code |
|---|---:|---|
| 查询成功（包括空结果） | `200` | 无 |
| 请求格式、字段或问题无效 | `400` | `INVALID_REQUEST` |
| 当前知识无法回答 | `422` | `CANNOT_ANSWER` |
| SQL 候选未通过安全校验 | `422` | `SQL_REJECTED` |
| LLM 上游调用失败 | `502` | `LLM_ERROR` |
| 结构或指标上下文不可用 | `503` | `CONTEXT_ERROR` |
| 数据库执行或连接失败 | `503` | `DATABASE_ERROR` |
| 数据库查询超时 | `504` | `QUERY_TIMEOUT` |
| 未知、过期或不属于当前用户的会话 | `404` | `CONVERSATION_UNAVAILABLE` |
| 无法唯一解析的多轮追问 | `422` | `CLARIFICATION_REQUIRED` |
| 超出 V1 单条查询修订范围 | `422` | `UNSUPPORTED_ANALYSIS` |
| 同一会话存在并发轮次 | `409` | `CONVERSATION_CONFLICT` |

API 对请求体解析失败时，也必须返回上述 `QueryFailure` 形状，而不是 FastAPI 默认的 `detail` 响应。

## 边界与不变量

- API Adapter 是外层 Interface（接口层），只能通过 `AuthorizedQueryService` 的授权门禁和 `execute_authorized()` 进入 Online Query。
- 一个可执行的 HTTP 查询最多调用一次授权入口；会话不存在、过期、越权或并发冲突时不得调用授权入口，不得维护第二条查询链路。
- API Adapter 不直接调用 LLM、SQL Guard 或数据库。
- 会话状态由 Application 边界拥有；API Adapter 不让客户端提交完整状态，也不把会话状态当作授权凭证。
- API Adapter 不实现认证、授权、租户隔离、限流、审计、重试、熔断或成本控制。
- 当前仅信任 `X-Request-ID` 作为追踪标识，不把它当作身份或授权信息。
- 未来 API Gateway 位于 API Adapter 之外，负责验证身份、传入可信的追踪上下文和流量治理；核心 Online Query 不绑定具体网关产品。

## 不负责

- SSE、WebSocket、流式输出和自然语言总结。
- Streamlit、Gradio、React 或 Vue 前端页面。
- 用户登录、`user_id`、`tenant_id`、权限控制和数据行级隔离。
- 长期聊天历史、跨服务恢复、复杂分析 Agent、RAG、自动修复和模型重试。
- 健康检查之外的部署、监控、告警和生产运维。

## 验收标准

### Software Test（软件测试）

- `GET /health` 返回 `200` 与固定响应。
- 合法 HTTP 请求能通过授权入口映射为 `QueryRequest`，并且只调用一次假的下游 Online Query Service。
- `QuerySuccess` 能正确转换为 JSON；列、行、行数和截断标识不丢失。
- 每个 `QueryErrorCode` 能转换为约定 HTTP 状态和 `QueryFailure` JSON。
- 无效 JSON、缺少字段、空问题和未知字段返回 `400 / INVALID_REQUEST`，不泄露 FastAPI 默认错误体。
- `X-Request-ID` 能传入核心请求；未传入时响应包含系统生成的 `request_id`。
- 首轮成功请求返回服务端生成的 `conversation_id`；首轮失败不创建会话。
- 多轮成功请求保留结构化状态；失败、澄清、范围拒绝、权限失败和下游失败不提交新状态。
- 未知、过期、越权会话和并发轮次分别返回约定错误码，且不调用下游查询。
- 原有 Online Query 与 Evaluation 测试继续通过。

### End-to-End（端到端）

- 至少一次真实 HTTP 请求完成“HTTP 问题 -> Online Query -> SQL Guard -> PostgreSQL -> JSON 结果”闭环。

## 实现状态

- API Adapter 已落位于 `src/query_api/`。
- `app.py` 提供应用工厂、请求/响应模型、路由和错误映射。
- `main.py` 组装现有 `LangChainSQLGenerator`、`PsycopgQueryExecutor` 和 `OnlineQueryService`，再由 `create_app()` 包装为 `AuthorizedQueryService`。
- FastAPI 运行依赖已写入 `pyproject.toml`，具体解析版本由 `uv.lock` 锁定。
- API 确定性测试与原有 Online Query、Evaluation 回归测试已通过。
- 已使用真实 `.env` 完成一次 HTTP 到 LLM、SQL Guard 和 PostgreSQL 的闭环验证，返回 `200` 和 1 行结果。
- Multi-Turn Query V1 的公共 Contract 已确认并完成文档同步；Ticket 01～04 已完成会话生命周期、结构化语义修订、Streamlit 当前会话联动和分层验收；真实 AI Evaluation、Real E2E 及本次三轮场景的 Business Acceptance 证据见 `docs/acceptance/multi-turn-query-v1-20260919.md`。

当前 Streamlit POC 页面通过 HTTP 调用本 API；正式前端是否采用 React、Vue 或其他方案，仍属于后续范围。

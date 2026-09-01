# Query API Adapter Spec

## 目标

使用 FastAPI（Web 框架）把现有 Online Query（在线查询）能力暴露为同步 HTTP JSON 接口，供未来前端、内部应用或 API Gateway（API 网关）调用。

API Adapter（接口适配层）只负责 HTTP 与内部类型之间的转换：

```text
HTTP 请求
  -> QueryRequest
  -> OnlineQueryService
  -> QuerySuccess / QueryFailure
  -> HTTP JSON 响应
```

不得在 API 层复制或改写 Prompt、LLM 调用、SQL Guard（SQL 安全校验）和数据库执行逻辑。

## 运行方式

- 同步、单次请求/响应。
- 当前使用 JSON，不使用 SSE（流式推送）或 WebSocket（双向实时连接）。
- API 通过现有 `OnlineQueryService.query()` 调用正式在线查询链路。
- API 不改变 Online Query 的业务规则、超时、结果行数上限和错误码。

## 接口

### 查询

```text
POST /api/v1/query
Content-Type: application/json
X-Request-ID: 可选
```

请求体只接受 `question`：

```json
{
  "question": "查询各产品销售额"
}
```

- `question` 必填，必须是去除首尾空白后非空的字符串。
- 不接受 `user_id`、`tenant_id`、对话历史、分页参数或网关内部信息。
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
  "truncated": false
}
```

- `rows` 是二维 JSON 数组，顺序与 `columns` 对应。
- 查询成功但没有数据仍返回 `200`、空 `rows` 和 `row_count: 0`。
- `truncated`、`row_count` 和 `sql` 的语义完全沿用 `QuerySuccess`。

失败响应：

```json
{
  "request_id": "req-123",
  "error_code": "CANNOT_ANSWER",
  "error_message": "当前结构和指标无法回答该问题"
}
```

- `error_code` 和 `error_message` 完全沿用 `QueryFailure`。
- 响应不得包含 Python 异常堆栈、数据库连接信息、API Key 或其他 Secret（密钥）。

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

API 对请求体解析失败时，也必须返回上述 `QueryFailure` 形状，而不是 FastAPI 默认的 `detail` 响应。

## 边界与不变量

- API Adapter 是外层 Interface（接口层），只能依赖并调用 Online Query 的公开 Contract（契约）。
- 一次 HTTP 查询只能调用一次 `OnlineQueryService.query()`；不得维护第二条查询链路。
- API Adapter 不直接调用 LLM、SQL Guard 或数据库。
- API Adapter 不实现认证、授权、租户隔离、限流、审计、重试、熔断或成本控制。
- 当前仅信任 `X-Request-ID` 作为追踪标识，不把它当作身份或授权信息。
- 未来 API Gateway 位于 API Adapter 之外，负责验证身份、传入可信的追踪上下文和流量治理；核心 Online Query 不绑定具体网关产品。

## 不负责

- SSE、WebSocket、流式输出和自然语言总结。
- Streamlit、Gradio、React 或 Vue 前端页面。
- 用户登录、`user_id`、`tenant_id`、权限控制和数据行级隔离。
- 分页、多轮对话、复杂分析 Agent、RAG、自动修复和模型重试。
- 健康检查之外的部署、监控、告警和生产运维。

## 验收标准

### Software Test（软件测试）

- `GET /health` 返回 `200` 与固定响应。
- 合法 HTTP 请求能映射为 `QueryRequest`，并且只调用一次假的 `OnlineQueryService`。
- `QuerySuccess` 能正确转换为 JSON；列、行、行数和截断标识不丢失。
- 每个 `QueryErrorCode` 能转换为约定 HTTP 状态和 `QueryFailure` JSON。
- 无效 JSON、缺少字段、空问题和未知字段返回 `400 / INVALID_REQUEST`，不泄露 FastAPI 默认错误体。
- `X-Request-ID` 能传入核心请求；未传入时响应包含系统生成的 `request_id`。
- 原有 Online Query 与 Evaluation 测试继续通过。

### End-to-End（端到端）

- 至少一次真实 HTTP 请求完成“HTTP 问题 -> Online Query -> SQL Guard -> PostgreSQL -> JSON 结果”闭环。

## 实现状态

- API Adapter 已落位于 `src/query_api/`。
- `app.py` 提供应用工厂、请求/响应模型、路由和错误映射。
- `main.py` 组装现有 `LangChainSQLGenerator`、`PsycopgQueryExecutor` 和 `OnlineQueryService`。
- FastAPI 运行依赖已写入 `pyproject.toml`，具体解析版本由 `uv.lock` 锁定。
- API 确定性测试与原有 Online Query、Evaluation 回归测试已通过。
- 已使用真实 `.env` 完成一次 HTTP 到 LLM、SQL Guard 和 PostgreSQL 的闭环验证，返回 `200` 和 1 行结果。

当前 Streamlit POC 页面通过 HTTP 调用本 API；正式前端是否采用 React、Vue 或其他方案，仍属于后续范围。

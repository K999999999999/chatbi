# Query API Adapter Implementation Design

## 结论

API Adapter（接口适配层）实现为一个最小的 `src/query_api/` 模块，使用 FastAPI 暴露 HTTP 接口。它只负责协议转换，不进入 Online Query（在线查询）内部，也不重复 Prompt、LLM、SQL Guard 或数据库逻辑。

正式接口契约见 [Query API Spec](../specs/query-api.md)。本设计只说明如何实现该契约。

## 模块位置

```text
外部 HTTP 调用方
        ↓
src/query_api/                 Interface Adapter（接口适配层）
        ↓
src/online_query/              Online Query（在线查询核心）
        ↓
LLM / SQL Guard / PostgreSQL
```

依赖方向只能是：

```text
query_api → online_query
```

`online_query` 不得反向依赖 `query_api`。

## 最小代码结构

代码只新增一个模块和三个文件：

| 文件 | 职责 |
|---|---|
| `src/query_api/__init__.py` | 导出 `create_app()`，不在导入时创建真实服务 |
| `src/query_api/app.py` | FastAPI 应用工厂、请求模型、响应转换、HTTP 状态映射和 `/health`、`/api/v1/query` 路由 |
| `src/query_api/main.py` | 创建真实 `LangChainSQLGenerator`、`PsycopgQueryExecutor`、`OnlineQueryService`，提供 Uvicorn/FastAPI 入口 `app` |

不新增 `ports/`、`middleware/`、`schemas/`、`container/` 或独立 DTO 目录。当前接口数量和转换逻辑都很少，直接放在 `app.py` 最清楚。

测试放在：

```text
tests/query_api/test_app.py
```

## 运行链路

### 正常查询

```text
HTTP JSON
  -> QueryBody
  -> QueryRequest
  -> OnlineQueryService.query()
  -> QuerySuccess / QueryFailure
  -> JSONResponse
```

一次 HTTP 查询只能调用一次 `OnlineQueryService.query()`。

### 请求解析失败

FastAPI 的请求校验异常由 Adapter 统一处理。它将无效请求转换为一个空问题的 `QueryRequest`，让现有 `OnlineQueryService` 保持 `INVALID_REQUEST` 和 `request_id` 的唯一业务判断入口；不会调用 LLM 或数据库。

## `app.py` 设计

### 应用工厂

提供：

```text
create_app(service) -> FastAPI
```

`service` 只要求具有：

```text
query(QueryRequest) -> QuerySuccess | QueryFailure
```

生产运行时传入真实 `OnlineQueryService`；软件测试传入 Fake Service（假服务）。这样测试导入 `app.py` 时不读取 API Key、不连接数据库。

`app.py` 不创建真实 LLM、数据库或环境配置对象。

### 请求模型

使用 Pydantic（请求数据校验）定义一个严格请求模型：

```text
QueryBody
└─ question: string
```

未知字段、缺少字段、错误 JSON、非字符串和空问题都必须返回 `INVALID_REQUEST`。空问题由 Online Query 现有逻辑判断，其他 HTTP 解析问题由 Adapter 转换成同样的失败形状。

### 响应转换

使用两个只属于 HTTP 层的响应模型：

```text
QuerySuccessResponse
QueryFailureResponse
```

字段与现有 `QuerySuccess`、`QueryFailure` 一一对应，不增加业务字段。`rows` 转换为 JSON 二维数组，保留列顺序、行顺序、行数和 `truncated`。

Adapter 使用 `JSONResponse` 显式返回状态码，避免错误响应变成 FastAPI 默认的 `detail` 结构。

### Request ID

- 从 `X-Request-ID` Header（请求头）读取可选追踪标识。
- 放入现有 `QueryRequest.request_id`。
- 没有或为空时由 Online Query 生成。
- 不把它当作用户身份或授权信息。

### 路由

```text
GET  /health
POST /api/v1/query
```

查询路由使用同步函数，直接调用同步 `OnlineQueryService`，不使用 `async`、SSE 或 WebSocket。

## `main.py` 设计

`main.py` 只负责生产组装：

```text
LangChainSQLGenerator.from_env()
PsycopgQueryExecutor.from_env()
OnlineQueryService(generator, executor)
create_app(service)
```

它复用 Online Query 当前的环境变量和初始化逻辑，不新增 `.env` 读取器，不改变 LLM 或 PostgreSQL 配置。

缺少 LLM 或数据库必要配置时，真实服务启动失败并尽早暴露配置问题。测试不导入生产 `main.app`，而是使用 `create_app(fake_service)`。

## 依赖

新增 FastAPI 的标准运行依赖，但不加入 FastAPI Cloud CLI：

```text
fastapi[standard-no-fastapi-cloud-cli]
```

它提供 FastAPI、Uvicorn 和 TestClient 所需的基础依赖。具体版本由 `uv.lock` 锁定。当前不新增 SSE、WebSocket、ORM、连接池或配置管理库。

## 错误映射

Adapter 只负责把已有错误码映射为 HTTP 状态：

| 错误码 | HTTP 状态 |
|---|---:|
| `INVALID_REQUEST` | `400` |
| `CANNOT_ANSWER` | `422` |
| `SQL_REJECTED` | `422` |
| `LLM_ERROR` | `502` |
| `CONTEXT_ERROR` | `503` |
| `DATABASE_ERROR` | `503` |
| `QUERY_TIMEOUT` | `504` |

错误响应仍然只包含：

```text
request_id
error_code
error_message
```

## 测试设计

所有确定性 API 测试使用 Fake Service，不调用真实 LLM 或数据库。

| 测试 | 证明内容 |
|---|---|
| `health` | 服务健康接口返回固定 JSON，且不调用查询服务 |
| 成功响应 | HTTP 请求转换为 `QueryRequest`，服务只调用一次，成功字段完整返回 |
| Request ID | `X-Request-ID` 能传入；未传入时响应仍有请求编号 |
| 空结果 | 空 `rows`、`row_count=0` 和 `truncated=false` 正确返回 |
| 错误映射 | 每个 `QueryErrorCode` 都返回约定 HTTP 状态和失败 JSON |
| 请求校验 | 缺字段、空问题、未知字段、非字符串和错误 JSON 不调用 LLM/数据库 |
| 错误结构 | 不出现 FastAPI 默认 `detail`、异常堆栈或 Secret |
| 原有回归 | Online Query 与 Evaluation 测试继续通过 |

最后增加一次真实本地 HTTP 验证：启动真实 API，发送一个已知问题，确认请求经过现有 Online Query、SQL Guard 和 PostgreSQL 后返回 JSON。该验证需要已有 LLM 和数据库环境，不把外部调用写成确定性单元测试。

## 开发任务

### T1：依赖、应用工厂和健康检查

- 增加 FastAPI 依赖并更新 `uv.lock`。
- 创建 `src/query_api/` 和应用工厂。
- 实现 `/health`。
- 先写测试，再实现。

### T2：查询请求、成功响应和 Request ID

- 实现 `POST /api/v1/query` 的正常请求路径。
- 转换 `QueryRequest` 和 `QuerySuccess`。
- 验证 `X-Request-ID` 传递和空结果。

### T3：请求校验和错误映射

- 处理 FastAPI 请求校验异常。
- 实现全部错误码的 HTTP 状态映射。
- 确保不返回默认 `detail`，不泄露内部异常。

### T4：真实服务组装和 HTTP 验证

- 在 `main.py` 复用现有 LLM、数据库和 Online Query 组装逻辑。
- 验证配置失败的启动行为。
- 完成一次真实 HTTP 端到端验证。

每个 Task 都执行：TDD 测试、实现、测试、Diff Review（差异审查）和独立 Commit（提交）。T4 完成后再做一次 API 全量审查。

## 影响与回滚

### 影响范围

- 新增 FastAPI 运行依赖和 `uv.lock` 记录。
- 新增 `src/query_api/` 和 `tests/query_api/`。
- 不改数据库、结构文件、指标文件、Online Query 和 Evaluation 逻辑。
- 不增加认证、网关、限流、审计或部署配置。

### 回滚

删除 API Adapter 文件、测试和 FastAPI 依赖即可；现有 Python 调用入口、数据库和评测链路不受影响。

## 设计状态

已根据 `docs/specs/query-api.md` 确认，无待决策项，进入实现阶段。

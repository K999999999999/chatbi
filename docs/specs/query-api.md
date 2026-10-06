# Query API Adapter Spec

当前 Web 长期状态以 [R3 History Spec](history-results-v1.md) 为准：显式 `/api/v1/histories` 与 `/api/v1/saved-results` 保存私人快照，刷新只读，续聊恢复完整条件；旧 `/api/v1/query` 继续原短期 Contract。网页执行使用 R4 后台执行受理、正式结果读取和 SSE 状态观察；完整行为见 [R4 Spec](execution-streaming-v1.md)，实现设计见 [R4 Design](../designs/execution-streaming-v1.md)。本文的 R1 / R2 阶段状态描述保留历史边界，不能用来否定 R3 / R4。
## 目标

使用 FastAPI（Web 框架）把现有 Online Query（在线查询）能力暴露为同步 HTTP JSON 接口，供电脑端 Web、内部应用或 API Gateway（API 网关）调用。

API Adapter（接口适配层）只负责 HTTP 与内部类型之间的转换：

```text
HTTP 请求
  -> server-side AuthContext
  -> mode=query：现有 Application 会话边界和普通查询链路
  -> mode=analysis：Business Analysis Application Workflow
  -> QuerySuccess / AnalysisSuccess / QueryFailure
  -> HTTP JSON 响应
```

不得在 API 层复制或改写 Prompt、LLM 调用、SQL Guard（SQL 安全校验）和数据库执行逻辑。

## 运行方式

- 本文定义的 `/api/v1/query` 与分析查询接口仍是同步 JSON、每次请求/响应；每次下游执行仍然只处理一条有效查询。
- R4 网页执行接口采用异步受理与 GET/SSE 观察；SSE 观察已受理执行状态，也可以携带标明尚未校验的报告文字候选，不改变下游查询规则。当前不使用 WebSocket（双向实时连接）。
- `mode=query` 通过 `AuthorizedQueryService.authorize()` 完成身份与数据授权；已有会话在授权通过后完成语义修订，再由 `execute_authorized()` 调用下游 `OnlineQueryService.execute()`。
- `mode=analysis` 只调用被注入的 Business Analysis Application Workflow；Task 的授权、执行和报告生成不下沉到 API Adapter。
- API 不改变 Online Query 的业务规则、超时和结果行数上限；短期会话边界使用本 Spec 定义的 Application 错误码。

## 接口

### R4 网页执行路由（增量接口）

R4 保留上面的同步接口，并为网页历史增加独立执行路由：

```text
POST /api/v1/histories/{history_id}/executions
POST /api/v1/histories/{history_id}/requery-executions
POST /api/v1/saved-results/{result_id}/requery-executions
GET  /api/v1/executions/by-operation/{operation_id}
GET  /api/v1/executions/{execution_id}
GET  /api/v1/executions/{execution_id}/events
POST /api/v1/executions/{execution_id}/cancel
```

执行创建路由返回 `202` 受理身份；取消路由接受空 JSON body，返回 `202 stopping` 或 `200` 已有终态，重复请求幂等且不会改写成功终态。读取路由以只读身份检查现有 Session 和当前权限。`events` 使用版本化 SSE `snapshot` / `progress` / `text_delta` / `draft_reset` / `terminal` 帧与心跳，响应设为 `no-store`，身份失效时以不含私有字段的 `auth_lost` 帧关闭。分析报告生成期间仅发布六个白名单文字字段，并在快照中携带当前 generation 的完整未校验草稿；正式报告仍须经过原结构、证据引用与业务校验，并成功保存后才交付。网页重连只重新 GET，不重放业务 POST。完整阶段名称、缓冲上限、停止与草稿行为以正式 R4 Spec 为准；本文说明同步 API 兼容边界与新增网页路由。

### R5 成果导出路由（增量接口）

```text
POST /api/v1/result-exports
```

请求指定 owner 可读的 `history_turn`（历史 ID + 成功轮次 ID）或 `saved_result`（成果 ID）及格式。XLSX 不接受图表选择；PNG 必须带 `chart_id` 和 `chart_type`，分析任务图可带 `task_id`，因素图必须带当前产品的 `product_index`。这些值只选择服务端成功快照中已有的图，不接受 SQL、文件路径、客户端结果值或 ECharts option。服务端从持久化快照构建文件，不调用模型 / 查询，不改写历史或成果。当前实现 XLSX / PNG；PDF 未实施时返回受控 `422`。PNG 不可用、选择无效或完整图形超出资源上限时分别返回受控 `503`、`422` 或 `413`。成功响应为实际文件，使用适用 MIME、`Cache-Control: no-store`、`X-Content-Type-Options: nosniff`；文件名由服务端按安全短标题、格式和 UTC 导出时间生成；失败遵循现有 `request_id` 和错误 JSON。

导出沿用当前登录 Session、查询权限与 Cookie / CSRF 检查；在生成前和发送前重新核验 owner / 来源。导出 runtime 当前限定单 API 进程并持有私有临时目录锁；来源最多 5 MiB、每账号同时生成 1 个文件、API 同时 2 个、生成预算 60 秒、文件最多 20 MiB。PNG 使用固定离线 bundle、Playwright / Chromium sandbox 与本地中文字体；活动和失败路径都会回收临时文件。完整来源、精度、权限竞态与错误 Contract 见 [R5 Spec](result-export-v1.md) 和 [Design](../designs/result-export-v1.md)；PDF 与 R5 最终真实验收仍待完成。

### 查询

```text
POST /api/v1/query
Content-Type: application/json
X-Request-ID: 可选
```

请求体接受必填 `question`、可选 `conversation_id` 和可选 `mode`：

```json
{
  "question": "按销售区域拆开。",
  "conversation_id": "server-generated-id",
  "mode": "query"
}
```

- `question` 必填，必须是去除首尾空白后非空的字符串。
- `conversation_id` 可选，只接受服务端生成的会话编号；不接受 `user_id`、`tenant_id`、对话历史、结构化状态、SQL、分页参数或网关内部信息。
- `mode` 可选，只能是 `query` 或 `analysis`；缺失时默认为 `query`。未知值返回 `INVALID_REQUEST`。
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

### Business Analysis V1（经营分析）

当 `mode=analysis` 时，API 只负责校验模式、认证当前用户、调用 Business Analysis Application Workflow 和序列化响应：

```json
{
  "question": "2025年3月毛利为什么比2月下降？",
  "mode": "analysis",
  "analysis_run_id": "f5607b24-84cf-4f09-b7c5-9ea5a332e225"
}
```

- `mode=analysis` 不读取、不创建、不修改普通查询 `conversation_id`；如果请求携带该字段，必须在会话 Store、授权查询、Task Decomposer、Retrieval、LLM、SQL Guard 或数据库之前返回 `400 / INVALID_REQUEST`。
- `analysis_run_id` 是调用方为一次经营分析生成的 UUID；使用同一 ID 和相同认证用户 / 问题恢复或读取已完成结果。不同用户或问题不得复用该 ID，24 小时过期后拒绝重启。
- `analysis_run_id` 是 LangGraph `thread_id`，不等于每次 HTTP 请求的 `request_id` 或 `X-Trace-ID`。恢复调用会生成新的请求和 Trace ID，并通过 Trace 属性关联运行 ID。
- `mode=analysis` 不提交普通查询 `QueryState`，不与普通查询 Multi-Turn 共用状态；分析工作流的可恢复状态只保存在独立 `chatbi_control` 数据库。
- 经营分析 Application 内部负责 Task Decomposer、计划校验、绑定当前用户身份的 Task 执行、TaskResult 汇总和 Summary LLM；API 不直接调用这些组件。
- 成功响应不返回 SQL 或普通查询 `conversation_id`，只返回自然语言报告和有界的结构化 TaskResult：

```json
{
  "request_id": "analysis-123",
  "analysis_run_id": "f5607b24-84cf-4f09-b7c5-9ea5a332e225",
  "mode": "analysis",
  "report": {
    "title": "销售额趋势分析",
    "executive_summary": "销售额在观察期内下降。",
    "key_findings": ["整体销售额下降"],
    "trend_judgment": "呈下降趋势",
    "root_causes": ["华东区域贡献下降"],
    "action_suggestions": ["进一步检查华东区域产品结构"],
    "evidence_task_ids": ["trend"],
    "incomplete_tasks": [],
    "attribution": {
      "metric_name": "人民币毛利",
      "direction": "increase",
      "reconciliation_passed": true
    }
  },
  "task_results": [
    {
      "task_id": "trend",
      "status": "completed",
      "columns": ["month", "sales"],
      "rows": [["2026-09", 90]],
      "row_count": 1,
      "truncated": false,
      "error": null
    }
  ]
}
```

- 成功、失败响应均回显 `analysis_run_id`。过期、身份 / 问题不匹配及 checkpoint 不可用使用现有 QueryFailure 结构和错误码，不暴露运行内容或 Secret。
- Checkpoint 保留 24 小时；清理后保留最小过期登记，防止同一 UUID 被当成新分析重新执行。

- `task_results` 只保留结构化数据、状态和安全公开错误，不包含 SQL、连接信息、异常堆栈或 Secret；返回行数仍受 Online Query 当前边界约束。
- 经营分析失败沿用 `QueryFailure` 形状和本 Spec 的 HTTP 错误映射；分析报告不写入普通查询时间线。

### Multi-Turn Query V1（受控多轮查询）

- 没有 `conversation_id` 的请求按单轮查询执行；只有成功结果提交后才创建短期会话。
- 带 `conversation_id` 的请求必须先由当前认证身份校验会话归属、过期状态和并发状态；失败时不得进入 `AuthorizedQueryService`、Retrieval、LLM、SQL Guard 或数据库。
- 会话只保存最后一次成功查询的指标、时间范围、维度和过滤条件，不保存原始对话、候选 SQL、最终 SQL 或结果行。
- 会话使用 30 分钟无成功状态更新的 Idle TTL；服务重启后会话失效。
- 同一会话同一时刻只允许一个进行中的轮次；并发请求返回 `CONVERSATION_CONFLICT`，不调用下游、不提交状态。
- 同一语义槽位的新值替换旧值，不同语义槽位的新条件叠加。维度默认追加；用户明确说“分组维度改成 / 换成 / 替换为 / 替换成某维度”时，替换全部已有维度。维度操作同时包含互相冲突的替换与追加措辞，或否定了替换表达时，必须澄清且不执行查询。歧义和超出单条查询修订范围的问题不执行查询。
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
| 指标口径不明确或无法唯一解析的多轮追问 | `422` | `CLARIFICATION_REQUIRED` |
| 超出 V1 单条查询修订范围 | `422` | `UNSUPPORTED_ANALYSIS` |
| 同一会话存在并发轮次 | `409` | `CONVERSATION_CONFLICT` |

API 对请求体解析失败时，也必须返回上述 `QueryFailure` 形状，而不是 FastAPI 默认的 `detail` 响应。

## 边界与不变量

- API Adapter 是外层 Interface（接口层），只能通过 `AuthorizedQueryService` 的授权门禁和 `execute_authorized()` 进入 Online Query。
- 一个可执行的 HTTP 查询最多调用一次授权入口；会话不存在、过期、越权或并发冲突时不得调用授权入口，不得维护第二条查询链路。
- API Adapter 不直接调用 LLM、SQL Guard 或数据库，也不在适配层生成经营分析报告；这些职责属于被注入的 Application Workflow。
- 会话状态由 Application 边界拥有；API Adapter 不让客户端提交完整状态，也不把会话状态当作授权凭证。
- API Adapter 提取当前身份并调用既有认证 / 授权 / 审计服务；不自行定义权限、租户隔离、业务真相，不提供限流、隐式重试、熔断或成本控制。
- 当前仅信任 `X-Request-ID` 作为追踪标识，不把它当作身份或授权信息。
- 未来 API Gateway 位于 API Adapter 之外，负责验证身份、传入可信的追踪上下文和流量治理；核心 Online Query 不绑定具体网关产品。

## 不负责

- WebSocket 与同步 `/api/v1/query` 的执行状态流；R4 SSE 由独立执行路由提供，经营分析仍由 Business Analysis Application Workflow 负责。
- Streamlit、Gradio、React 或 Vue 前端页面。
- 账号 / 权限业务真相由既有账号与授权模块维护；本 Adapter 提供登录 HTTP 边界，不新增 tenant_id 或数据行级隔离。
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
- `main.py` 仅创建无运行资源副作用的应用，`src/bootstrap/` 在 lifespan 内装配真实依赖并执行就绪门禁，`create_app()` 将查询服务绑定为 `AuthorizedQueryService`；失败清理与关闭规则见 [初始化与运行资源 Spec](bootstrap.md)。
- FastAPI 运行依赖已写入 `pyproject.toml`，具体解析版本由 `uv.lock` 锁定。
- API 确定性测试与原有 Online Query、Evaluation 回归测试已通过。
- 已使用真实 `.env` 完成一次 HTTP 到 LLM、SQL Guard 和 PostgreSQL 的闭环验证，返回 `200` 和 1 行结果。
- Multi-Turn Query V1 的公共 Contract 已确认并完成文档同步；Ticket 01～04 已完成会话生命周期、结构化语义修订、Streamlit 当前会话联动和分层验收；真实 AI Evaluation、Real E2E 及本次三轮场景的 Business Acceptance 证据见 `docs/acceptance/multi-turn-query-v1-20260919.md`。

当前 React + TypeScript + Vite 电脑端网页通过同源 HTTP 调用本 API；Streamlit 已移除。历史多轮验收仍按对应运行日期与提交解释。

## R1 浏览器入口

浏览器登录使用 `/auth/browser/login`、`/auth/browser/me`、`/auth/browser/logout`、`/auth/browser/change-password`，旧 `/auth/*` Bearer 路由继续兼容。查询 body / result Contract 不变；Cookie 身份、CSRF 门禁和网页入口见 [Web Spec](web-dialogue-v1.md) 及 [Web Design](../designs/web-dialogue-v1.md)。账号与授权事实仍由既有模块维护；浏览器路由不复制核心业务。认证 / 查询响应均 no-store，Cookie 查询即使 CSRF 拒绝也保留 request_id / X-Trace-ID 关联。

## 结果说明扩展（R2）

成功query响应和已完成分析 `task_results` 可含 `result_metadata`；缺该字段的旧结果仍有效，已有字段不变。API仅序列化Online Query的确定性说明，不自行认证或调用额外模型。完整行为见[R2 Spec](result-visualization-v1.md)。

| 字段 | Contract |
| --- | --- |
| `version` | 当前为1；未知版本保留原始表格 |
| `status` | `complete / partial / unavailable`，说明的认证程度，不是查询状态 |
| `columns` | 与输出列一一按位置对应；`index / name / data_type / role / semantic_name / definition / unit / format / certified / reason_code` |
| `data_type` | `number / string / boolean / date / unknown`；单独不能证明业务含义 |
| `role` | `metric / dimension / identifier / unknown` |
| `unit` | `{key,label}`或null，null表示单位未确认 |
| `format` | `money / count / ratio / number / raw`；认证金额为CNY元，比例为ratio百分比；编号保持raw |
| `scope` | `status / time / time_status / filters / grouping / warnings` |
| `scope.time` | 实际 `{start,end_exclusive,time_basis}` 半开日期区间，无法证明为null |
| `time_status` | `confirmed / unbounded / unknown` |
| `filters` | 实际已确认的 `{label,operator,values}`，值是文本 |
| `grouping` | 逻辑业务分组 `{semantic_name,kind,column_indices}`；kind为time/category，物理年/月可绑定同一逻辑分组 |
| `warnings` | 稳定原因码；`GROUPING_UNCONFIRMED`不得显示总体指标卡或猜图 |
| `time_axis` | `{granularity,keys}`或null；day/week/month/quarter/year，ISO日期键与返回行对齐 |

说明失败只降级显示，不改变查询成功、会话提交、数据授权或SQL Guard。每次请求绑定本轮说明，不能复用上一轮元数据冒充本轮；不存在任何说明时仍保留表格。分析旧Checkpoint未含可选字段时默认为None，新说明不进入报告模型输入。

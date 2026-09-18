# Online Query Module Spec

状态：当前 Online Query 已接入并通过 Online Retrieval V1（在线检索 V1）验收。Online Retrieval 的当前行为以 [V1 Feature Contract（V1 功能契约）](../../.scratch/online-retrieval-v1/spec.md) 为准；本文继续负责 Online Query 的输入、输出、执行和错误边界。

## 目标

接收一个针对 `mart_sales` 的自然语言问题，生成一条 SQL 候选，完成安全校验和只读执行，并返回真实数据库结果或明确错误。

## 运行方式

- 同步、每次执行一条有效查询。
- 核心模块只负责一次有效查询的语义解析、检索、SQL 生成、安全校验和只读执行；短期多轮会话的状态读取、组合和提交由 API/Application 边界负责，Online Query 不拥有会话。
- 本地启动入口自动读取项目根目录的 .env，且不覆盖已经存在的环境变量。
- 正式环境不依赖 .env 文件，由部署平台注入环境变量或 Secret。

`OnlineQueryService.execute()` 是授权后的内部下游执行操作，不是用户查询入口。Query API 和 Evaluation 必须分别通过 `AuthorizedQueryService.query()` 或绑定身份后的 `BoundAuthorizedQueryService.query()` 进入；Online Query 模块本身不接收身份授权职责。

## 输入契约

```text
QueryRequest
├─ question：必填，去除首尾空白后不能为空
└─ request_id：可选，没有时由系统生成
```

`conversation_id`、`user_id`、`tenant_id`、对话历史、网关信息和分页参数不属于当前输入。Multi-Turn Query V1 由外层根据已授权的结构化状态生成本次有效问题，再以同一 `QueryRequest` 调用本模块；未来接入网关时，由外层提供经过验证的身份和追踪上下文。

## 成功输出

```text
QuerySuccess
├─ request_id
├─ sql
├─ columns
├─ rows
├─ row_count
└─ truncated
```

- `row_count` 表示本次实际返回的行数。
- 超过 100 行时只返回前 100 行，并设置 `truncated = true`。
- SQL 正常执行但没有数据仍然算成功，返回空 `rows`、`row_count = 0` 和 `truncated = false`。
- 当前不生成自然语言总结。

## 失败输出

```text
QueryFailure
├─ request_id
├─ error_code
└─ error_message
```

错误分类：

| error_code | 含义 |
|---|---|
| `INVALID_REQUEST` | 问题为空或格式错误 |
| `CONTEXT_ERROR` | 结构或指标上下文无法加载 |
| `LLM_ERROR` | LLM 配置、调用、空响应或超时失败 |
| `CANNOT_ANSWER` | 当前结构和指标无法支持该问题 |
| `SQL_REJECTED` | SQL 未通过安全校验 |
| `DATABASE_ERROR` | 数据库连接或执行失败 |
| `QUERY_TIMEOUT` | 数据库查询超时 |

以下错误由 Query API/Application 的多轮边界产生，不由 `OnlineQueryService.execute()` 产生，但沿用公共 `QueryFailure` 形状：

| error_code | 含义 |
|---|---|
| `CONVERSATION_UNAVAILABLE` | 会话未知、已过期或不属于当前认证用户 |
| `CLARIFICATION_REQUIRED` | 多轮追问无法唯一解析，需要用户澄清 |
| `UNSUPPORTED_ANALYSIS` | 请求超出 V1 单条查询修订范围 |
| `CONVERSATION_CONFLICT` | 同一会话已有进行中的轮次 |

响应不得泄露异常堆栈、数据库连接信息、API Key 或其他 Secret。

## 主链路

```text
QueryRequest
  -> 输入检查并确定 request_id
  -> 读取已发布 RAG 资产快照并执行 Online Retrieval，获取动态结构和指标上下文
  -> 组装 Prompt
  -> LLM 生成 SQL 或表示无法回答
  -> SQL Guard 提取并校验 SQL
  -> PostgreSQL 只读执行
  -> QuerySuccess 或 QueryFailure
```

多轮请求在进入本链路前由 Application 读取并校验当前会话状态，形成一次有效的 `question`；本链路不读取原始对话历史、不接收 `conversation_id`，也不提交会话状态。

## 上下文规则

- 应用可以在没有装配 Retrieval Provider（检索提供者）的显式静态模式下加载 `tables.json`、`columns.json`、`relationships.json` 和 `metrics.json`，用于确定性软件评测；字段典型值位于 `columns.json.value_examples`。在线 RAG 模式不把静态全量 Schema 作为技术故障 fallback。
- 每次查询默认从同一已发布 `asset_version` 的 TABLE、COLUMN、METRIC 集合和 Relationship Graph（关系图）中按问题检索并组装最小动态上下文，不再默认使用完整结构和完整指标。
- 在线 RAG 的 Qdrant、Embedding、资产版本或关系图技术故障统一返回 `CONTEXT_ERROR`，不调用 LLM；业务资源缺失、关系不可达或关系歧义返回 `CANNOT_ANSWER`。实体类、单指标和多指标均遵循同一条 `metrics=0/1/N` 检索流程。
- 静态事实文件修改后通过重启应用重新加载，当前不支持静态文件热更新；已发布 RAG 资产按 `current.json` 的新版本在后续请求中加载，不要求重启。
- 发布资产或静态文件不存在、JSON 无法解析或内容完全为空时，不允许继续调用 LLM；无法建立合法上下文时返回 `CONTEXT_ERROR`。
- 多指标最多支持用户明确请求的 5 个指标；全部请求指标必须覆盖并兼容，否则返回 `CANNOT_ANSWER`。指标依赖不在线展开，公式字段不由程序静默补入。

## LLM 行为

- 能回答时只返回一条 PostgreSQL SQL，不返回解释、Markdown、分析过程或多个候选。
- 无法根据当前结构和指标回答时，触发 `CANNOT_ANSWER`，不得编造表、字段或指标。
- 不使用 Few-shot、对话历史、自动修复、第二轮反思或多模型投票。
- Query Understanding 的 Provider 调用异常或超时最多重试一次；非法 JSON、结构化 Contract 错误和 `CANNOT_ANSWER` 不重试。SQLGenerator 保持不自动重试。

## SQL 安全规则

- 只允许一条 SQL。
- V1 只允许单层 `SELECT`；事实表作为主表时，维表只能使用 Relationship Graph（关系图）认证的直接 `LEFT JOIN`，禁止中间表、多跳 Join、`RIGHT JOIN`、`FULL JOIN` 和 `CROSS JOIN`。
- 只能访问 `mart_sales`。
- 表和字段必须存在于当前结构目录。
- 禁止 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER`、`TRUNCATE` 和 `COPY`。
- 禁止访问 `pg_catalog`、`information_schema` 和其他 Schema。
- 校验失败返回 `SQL_REJECTED`，不得执行、自动修改或自动重试。
- SQL 通过校验后仍然必须使用 `chatbi_app` 只读数据库身份执行。

## 运行限制

- LLM 调用超时：30 秒，超时返回 `LLM_ERROR`。
- 数据库查询超时：10 秒，超时返回 `QUERY_TIMEOUT`。
- 最多返回 100 行；执行端最多读取 101 行用于判断是否截断。
- 当前不支持用户分页；除 Query Understanding 的一次受控 Provider 重试外，SQL 生成、SQL Guard 和数据库执行不自动重试。

## 业务规则

- 数据源固定为 PostgreSQL `mart_sales`。
- 数据库物理结构以 `src/structure/generated/` 为准。
- 指标口径以 `src/semantic/metrics.json` 为准。
- 当前指标统一使用完成日期口径：`completion_date_key -> dim_date.full_date`。
- LLM 只提出 SQL 候选，不决定业务真相、授权和 SQL 安全。
- 数据库正常执行即为成功，即使结果为空；数据库失败或无数据时不得编造结果。

## 不负责

- 数据库结构导出和指标维护。
- RAG 离线资产构建、Online Retrieval 检索算法、Schema Linking 和 Relationship Graph 维护；这些能力由对应模块负责，Online Query 只消费其结果。
- 会话所有权、短期状态存储、并发控制、长期聊天历史和多轮交互编排；这些由 Query API/Application 边界负责。
- SQL 自动修复和结果自然语言总结。
- API、UI、网关、认证、租户、限流、审计和生产运维。
- Evaluation 的批量执行和评测报告。

## 验收标准

### Software Test（软件测试）

- 输入、上下文、错误转换、SQL Guard、数据库执行和完整链路测试全部通过。

### Safety Test（安全测试）

- 已定义的危险、越界和多语句 SQL 必须 100% 被拒绝，且不得进入数据库。

### End-to-End（端到端）

- 至少一个真实问题能够完成“问题 -> SQL -> 安全校验 -> PostgreSQL 结果”的完整闭环。

### AI Evaluation（AI 评测）

- 21 条标准测试全部能够通过同一条 Online Query 链路运行并统计 Execution Accuracy（执行准确率）。
- 第一轮只建立真实模型 Baseline（基线），暂不设置准确率门槛。

## 实现设计阶段再决定

- 代码目录和文件落位。
- 节点 Typed Contract（类型契约）。
- LangChain 模型类、模型名称和 Provider 配置。
- SQL 解析库和 SQL Guard 的具体算法。
- 数据库连接和超时的具体实现方式。
- 单元测试文件和 Task 拆分。

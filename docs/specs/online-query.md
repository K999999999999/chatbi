# Online Query Module Spec

状态：当前 Online Query 已接入并通过 Online Retrieval V1（在线检索 V1）验收；实体类和单指标基线行为以本文及 `docs/specs/online-retrieval.md` 为准。基础 Multi-Metric Retrieval（多指标在线检索）是独立的增量规格，见 `docs/specs/multi-metric-retrieval.md`，尚未实现。

## 目标

接收一个针对 `mart_sales` 的自然语言问题，生成一条 SQL 候选，完成安全校验和只读执行，并返回真实数据库结果或明确错误。

## 运行方式

- 同步、单次问答。
- 核心模块只负责同步、单次问答；API、UI 和流式输出由外部适配层负责，多轮对话不在当前范围内。
- 本地启动入口自动读取项目根目录的 .env，且不覆盖已经存在的环境变量。
- 正式环境不依赖 .env 文件，由部署平台注入环境变量或 Secret。

## 输入契约

```text
QueryRequest
├─ question：必填，去除首尾空白后不能为空
└─ request_id：可选，没有时由系统生成
```

`user_id`、`tenant_id`、对话历史、网关信息和分页参数不属于当前输入。未来接入网关时，由外层提供经过验证的身份和追踪上下文。

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

## 上下文规则

- 应用仍可在启动时加载 `tables.json`、`columns.json`、`relationships.json` 和 `metrics.json`，作为静态上下文 fallback（回退）；字段典型值位于 `columns.json.value_examples`。
- 每次查询默认从同一已发布 `asset_version` 的 TABLE、COLUMN、METRIC 集合和 Relationship Graph（关系图）中按问题检索并组装最小动态上下文，不再默认使用完整结构和完整指标。
- 对已确定为实体类或单指标基线的请求，Qdrant、Embedding 或资产加载等技术故障可以沿用静态上下文 fallback；业务资源缺失不得用静态上下文掩盖。多指标请求按多指标规格直接返回 `CONTEXT_ERROR`，不走静态 fallback。
- 静态事实文件修改后通过重启应用重新加载，当前不支持静态文件热更新；已发布 RAG 资产按 `current.json` 的新版本在后续请求中加载，不要求重启。
- 发布资产或静态文件不存在、JSON 无法解析或内容完全为空时，不允许继续调用 LLM；无法建立合法上下文时返回 `CONTEXT_ERROR`。
- 单指标基线不做任意 SQL 数学等价证明；基础多指标所需的有限公式、固定过滤和请求指标覆盖检查，以多指标规格的后置校验为准。

## LLM 行为

- 能回答时只返回一条 PostgreSQL SQL，不返回解释、Markdown、分析过程或多个候选。
- 无法根据当前结构和指标回答时，触发 `CANNOT_ANSWER`，不得编造表、字段或指标。
- 不使用 Few-shot、对话历史、自动修复、第二轮反思或多模型投票。
- 当前不自动重试 LLM 调用。

## SQL 安全规则

- 只允许一条 SQL。
- 只允许 `SELECT` 或 `WITH ... SELECT`。
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
- 当前不支持用户分页和自动重试。

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
- 复杂分析 Agent 和多轮对话。
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

- 20 条标准测试全部能够通过同一条 Online Query 链路运行并统计 Execution Accuracy（执行准确率）。
- 第一轮只建立真实模型 Baseline（基线），暂不设置准确率门槛。

## 实现设计阶段再决定

- 代码目录和文件落位。
- 节点 Typed Contract（类型契约）。
- LangChain 模型类、模型名称和 Provider 配置。
- SQL 解析库和 SQL Guard 的具体算法。
- 数据库连接和超时的具体实现方式。
- 单元测试文件和 Task 拆分。

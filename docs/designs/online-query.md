# Online Query Implementation Design

## 结论

Online Query（在线查询）使用一个扁平模块完成，不增加 `ports/`、`infrastructure/`、`poc/` 等目录，也不使用 LangGraph（工作流框架）或 Agent（智能体）。

公共入口只有 `OnlineQueryService.query()`。模块内部保持同步顺序执行，未来 API 或 Gateway（网关）只需要调用这个入口，不进入核心链路。

## 实现链路

```text
QueryRequest
  -> 校验 question 并生成 request_id
  -> 读取已缓存的结构和指标上下文
  -> 组装 Prompt
  -> LangChain 调用 LLM 生成 SQL
  -> SQLGlot 解析并校验 SQL
  -> psycopg 使用 chatbi_app 只读执行
  -> QuerySuccess 或 QueryFailure
```

- 上下文在 Service（服务）创建时读取一次，保存成功结果或加载失败状态。
- 上下文失败时，查询直接返回 `CONTEXT_ERROR`，不得调用 LLM。
- LLM 返回精确的 `CANNOT_ANSWER` 时，直接返回同名错误。
- SQL 未通过校验时，直接返回 `SQL_REJECTED`，不得访问数据库。
- 不自动重试、不修复 SQL、不生成第二次自然语言总结。

## 最小代码结构

代码放在 `src/online_query/`。保留模块目录是因为以后还会有 Evaluation（评测）模块，但模块内部不再继续分层建目录。

| 文件 | 职责 |
|---|---|
| `contracts.py` | 请求、成功结果、失败结果、错误码、上下文、已校验 SQL、查询数据，以及两个外部能力接口 |
| `context.py` | 读取五个 JSON 文件，生成 Prompt 上下文及允许的表字段集合，并缓存结果 |
| `prompt.py` | 把用户问题、数据库结构、字段值、关系和指标组装成 Prompt |
| `llm.py` | 使用 LangChain `ChatOpenAI` 调用模型，只返回 SQL 文本或 `CANNOT_ANSWER` |
| `sql_guard.py` | 使用 SQLGlot 对 PostgreSQL SQL 做确定性安全校验 |
| `database.py` | 使用 psycopg 进行只读查询、超时控制和结果截断 |
| `service.py` | 串联完整链路并统一转换错误 |
| `__init__.py` | 只导出公共请求、结果和 Service |

## 核心 Contract（契约）

`contracts.py` 只保留这些核心类型：

- `QueryRequest`、`QuerySuccess`、`QueryFailure`、`QueryErrorCode`
- `QueryContext`：保存 Prompt 文本、允许访问的表和字段
- `ValidatedSQL`：只能由 SQL Guard 创建
- `QueryData`：数据库列、数据行和是否截断
- `SQLGenerator.generate(prompt) -> str`
- `QueryExecutor.execute(sql) -> QueryData`

`OnlineQueryService` 只依赖后两个能力接口，不直接依赖 LangChain 或 psycopg 类型。接口直接放在 `contracts.py`，不单独创建 Ports（端口）目录。

## 技术决定

- LLM：增加 `langchain-openai`，使用同步 `ChatOpenAI.invoke()`；显式设置 30 秒超时和 `max_retries=0`。
- SQL Guard：增加 `sqlglot`，指定 PostgreSQL 方言并检查 AST（抽象语法树）。解析成功不等于安全，仍需执行项目自己的白名单规则。
- Database（数据库）：继续使用现有 `psycopg`，不增加 ORM（对象关系映射）和连接池。
- 依赖调整：项目代码不再直接调用 OpenAI SDK 时，用 `langchain-openai` 替换 `pyproject.toml` 中直接声明的 `openai`，并更新 `uv.lock`。

## SQL Guard 规则

- 必须是纯 SQL，且只能有一条语句。
- 顶层只能是 `SELECT` 或 `WITH ... SELECT`。
- 禁止所有写入、结构修改、`COPY` 和系统 Schema。
- 物理表只能来自 `mart_sales`，表和字段必须存在于 `QueryContext`。
- 校验时处理表别名、CTE（公共表表达式）和输出别名，不能只做字符串匹配。
- 校验只通过或拒绝，不改写 SQL。

## 数据库执行

- 连接身份固定为 `chatbi_app`。
- 每次执行使用只读事务，并把 `statement_timeout` 设置为 10 秒。
- 最多读取 101 行，返回前 100 行；存在第 101 行时设置 `truncated=true`。
- 查询正常但没有数据仍返回成功。
- 数据库超时映射为 `QUERY_TIMEOUT`，其他连接或执行错误映射为 `DATABASE_ERROR`。

## 测试设计

| 测试 | 证明内容 |
|---|---|
| `test_context.py` | 五个 JSON 正常加载；缺失、损坏或空内容返回 `CONTEXT_ERROR` |
| `test_sql_guard.py` | 合法查询通过；多语句、写操作、越权 Schema、未知表字段全部拒绝 |
| `test_service.py` | 成功链路、全部错误映射、上下文失败不调用 LLM、SQL 拒绝不访问数据库 |
| `test_integration.py` | 使用真实 PostgreSQL 验证只读执行、空结果、100 行截断和至少一条完整查询链路 |

真实模型的 20 条标准测试属于 AI Evaluation（AI 评测），后续通过同一个 `OnlineQueryService` 执行，不复制另一条查询链路。

## 后续任务顺序

1. 核心 Contract 和上下文加载。
2. Prompt 与 LangChain LLM Adapter（适配器）。
3. SQL Guard。
4. PostgreSQL 执行。
5. Service 链路组装、完整测试和真实闭环验证。

每一步完成后单独验证，再进入下一步。API、Gateway、RAG、Evaluation 批处理和生产运维不属于本轮实现。

## 设计状态

Implementation Design（实现设计）已完成，无阻塞技术问题。下一步进入 Design Review（设计检查），确认后再拆具体开发任务。

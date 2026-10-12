# 评测结果比较与报告身份

本文说明维护当前实现所需的机制；功能行为见 [评测Spec](../specs/evaluation.md)。开发方案比较、任务和历次验收保存在工作记录。

## 实现链路

```text
加载并检查标准测试集
  -> 标准 SQL 经过现有 SQL Guard
  -> 使用现有只读 QueryExecutor 生成标准结果
  -> question 调用 BoundAuthorizedQueryService
  -> 比较系统结果与标准结果
  -> 汇总 Execution Accuracy
  -> 记录运行指纹并保存 JSON 报告
  -> 可选：与明确指定的上一份报告比较
```

- 标准案例无效时，不调用 LLM，记为 `INVALID_CASE`。
- 有效案例顺序调用真实 Online Query，单条失败后继续下一条。
- 标准结果只用于评测，不进入 Online Query Prompt。
- 不复制 Prompt、LLM、SQL Guard、Database 或 Service 代码。

## 复用现有系统

入口创建一次现有对象：

```text
QueryContext = load_query_context()
SQLGenerator = LangChainSQLGenerator.from_env()
QueryExecutor = PsycopgQueryExecutor.from_env()
RetrievalProvider = OnlineRetriever(RagRuntime.from_environment())  # 仅 --online-retrieval
OnlineQueryService(
    SQLGenerator,
    QueryExecutor,
    same QueryContext,
    retrieval_provider=RetrievalProvider,
)
```

未指定 `--online-retrieval` 时，`retrieval_provider` 为 `None`，保持软件测试的静态上下文模式；指定后，查询必须先经过在线 RAG，Multi-Metric（多指标）请求的技术故障遵循既有 `FAIL_CLOSED` 规则。

评测 Runner 接收：

- 绑定显式测试身份的 `BoundAuthorizedQueryService`
- 同一个 `QueryExecutor`
- 同一个 `QueryContext`
- 已加载的标准案例

系统结果必须来自：

```python
service.query(QueryRequest(question=case.question))
```

标准结果使用：

```text
validate_sql(case.expected_sql, context)
  -> query_executor.execute(validated_sql)
```

这样两边使用相同数据库身份、超时、行数限制和 SQL 安全边界，但只有系统结果经过 LLM。

## 结果比较实现

先检查：

1. 两边都未截断。
2. 列数一致。
3. 行数一致。

然后逐单元格比较：

- 列名忽略，列顺序保留。
- `NULL` 只与 `NULL` 相等。
- 字符串、日期、布尔值等按实际值比较。
- 数值使用绝对误差和相对误差 `1e-6`。

行比较：

- `order_sensitive=true`：按返回顺序逐行比较。
- 默认：在未匹配标准行中寻找完整相等行，匹配后移除；最多 100 行，使用简单的平方复杂度匹配即可，能够保留重复行数量。

不通过排序实现无序比较，避免 `NULL`、字符串、日期和数值混合时产生不可比较问题。

## 报告与版本

开发过程继续使用 Git Commit Hash（Git 提交哈希）作为精确代码版本。每次提交信息不额外加入语义版本号。

每份报告记录：

```text
run_id
created_at
git_commit
git_dirty
model
temperature
max_tokens
model_endpoint_hash
test_set_hash
context_hash
reference_result_hash
sales_mart_seed_version
sales_mart_data_summary
sales_mart_data_hash
sales_mart_data_hash_algorithm
```

- `git_commit`：当前代码提交。
- `git_dirty`：运行开始前是否存在未提交改动。
- `model_endpoint_hash`：只记录地址指纹，不把真实 Endpoint（端点）写入报告。
- `test_set_hash`：标准测试集内容指纹。
- `context_hash`：五个结构和指标文件的整体内容指纹。
- `reference_result_hash`：21 条标准 SQL 结果的整体指纹，用于识别相关数据库数据是否变化。
- `sales_mart_seed_version`：开发 Seed 中登记的版本。
- `sales_mart_data_summary`：Sales Mart 固定业务表的行数、总行数和日期范围，不包含明细记录。
- `sales_mart_data_hash`：在 `chatbi_app` 只读连接的同一 `REPEATABLE READ READ ONLY` 事务中，按固定表名、字段名和稳定主键顺序规范化实际行值后计算的 SHA-256。它反映实际数据状态，不依赖 Seed 文件版本或评测结果。
- `sales_mart_data_hash_algorithm`：数据 Hash 的算法标识；算法升级后，新旧报告不可直接比较。
- API Key、数据库密码和完整连接地址不得进入报告。

`uv.lock`、Prompt 和代码都由 `git_commit` 定位，不再分别建立版本号。

报告保存到：

```text
reports/evaluation/<run_id>.json
reports/evaluation/<run_id>.md
```

JSON 是机器可读评测证据；Markdown 是由同一份 JSON 数据确定性生成的人类可读总结，不重新调用 LLM 或数据库。

报告文件是评测证据，可以单独 Commit。版本 Tag 遵循仓库整体版本规则，不由 Evaluation 模块单独决定；不自动 Push（推送）远程仓库。

## Baseline 与回归比较

第一轮不提供上一份报告，只输出 Baseline。

后续通过命令参数显式指定：

```text
--baseline <report-path>
```

不自动选择“最新报告”，避免误用错误基线。

数据库型 Query 与 Business Analysis Evaluation 复用日常开发库 `chatbi_mvp` 和 `chatbi_app` 只读账号。expected SQL 与模型 SQL 都通过同一配置创建的 Query Executor 执行，不创建独立评测数据库。Query Understanding 语义评测不连接数据库。

比较前必须确认：

- `test_set_hash` 相同
- Sales Mart 数据 Hash、Hash 算法和摘要均存在且一致
- `reference_result_hash` 相同

任何必要指纹缺失或不同，本次仍可生成独立报告，但 `baseline_comparison.status` 必须为 `NOT_COMPARABLE`，并说明原因，不得声明能力回退或改善。历史报告没有 Sales Mart 数据指纹时也不可比较。Seed 版本改变但实际数据 Hash 相同时可继续比较，并通过 `seed_version_changed` 标明版本差异。

模型、代码或上下文可以变化，因为它们正是被评测的系统组成；报告必须明确列出这些指纹变化。

有效比较按 `case_id` 判断：

- `PASS -> FAIL`：Regression
- `FAIL -> PASS`：Improvement
- 其他：Unchanged

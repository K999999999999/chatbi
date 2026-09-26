# Evaluation Implementation Design

## 结论

Evaluation（评测）实现为一个离线回归评测 Runner（运行器），不建设新的查询系统，不提供 API 或常驻服务。

它读取固定测试集，逐条调用绑定测试身份的 `BoundAuthorizedQueryService.query()`，由其执行现有 `OnlineQueryService.execute()`，再执行标准 SQL 得到标准结果，比较两边数据并输出 JSON 报告。第一份报告建立 Baseline（基线），后续报告识别 Regression（能力回退）。

评测入口支持两种装配模式：Software Test（软件测试）默认使用静态 `QueryContext`，保证确定性测试不依赖本地模型和 Qdrant；真实 AI Evaluation（AI 评测）通过 `--online-retrieval` 显式装配与生产入口一致的 `OnlineRetriever`，用于验证在线 RAG 和后续 SQL 链路。

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

## 最小代码结构

继续使用现有 `src/evaluation/`，内部不再分层建目录。

| 文件 | 职责 |
|---|---|
| `eval_cases.json` | 已确认的 21 条标准案例 |
| `evaluator.py` | 加载案例、比较结果、运行案例、汇总准确率和比较上一份报告 |
| `__main__.py` | 创建现有 Online Query 依赖，可选装配在线 RAG、收集运行指纹、保存 JSON 报告并打印摘要 |
| `__init__.py` | 只导出评测入口和结果类型 |

测试放在 `tests/evaluation/`：

| 文件 | 职责 |
|---|---|
| `test_evaluator.py` | 案例加载、结果比较、失败隔离、汇总和能力回退测试 |
| `test_evaluation_entrypoint.py` | 依赖组装、运行指纹和报告写入测试，不调用真实 LLM |

当前不拆 `loader.py`、`comparator.py`、`runner.py`、`version.py` 和 `ports/`。只有一个文件出现明确独立复杂度后再拆分。

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

## 最小类型

类型直接放在 `evaluator.py`，不新增公共 Contract 目录：

- `EvaluationCase`：标准案例和 `order_sensitive`
- `CaseEvaluation`：单条状态、生成 SQL、原错误码、失败原因和耗时
- `EvaluationSummary`：数量、总体准确率和分类准确率
- `EvaluationReport`：运行指纹、单条结果、汇总和可选回归比较

状态只有：

- `PASS`：结果一致
- `FAIL`：Online Query 失败或结果不一致
- `INVALID_CASE`：标准案例或标准结果无效

不建立状态机、基类、注册表或 Evaluation Service 类层级。一个顶层 `run_evaluation(...)` 函数顺序执行完整评测。

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

## 运行入口

软件测试不调用真实 LLM。

真实评测命令设计为：

```text
uv run --env-file .env python -m src.evaluation --online-retrieval
uv run --env-file .env python -m src.evaluation --online-retrieval --baseline <report-path>
```

运行时从现有 `.env` 获取 LLM 和 PostgreSQL 配置。没有明确授权时，不执行真实命令。

终端只打印简短摘要和两份报告路径；完整数据写入 JSON，清晰总结写入 Markdown。

## 测试设计

### Software Test（软件测试）

- 非数组、空数组、缺字段、重复 `id` 和错误 `order_sensitive` 被识别为无效输入。
- 列名不同但数据一致时通过。
- 列数、列顺序、行数或数据不同则失败。
- 默认忽略行顺序并保留重复行数量。
- `order_sensitive=true` 时检查行顺序。
- `NULL` 和 `1e-6` 数值误差规则正确。
- 标准案例无效时不调用 Online Query。
- Online Query 单条失败不影响后续案例。
- 汇总准确率和分类准确率正确。
- 基线比较能识别回退、改善和不可比较状态。
- 报告不包含 Secret。

测试使用假的 SQL Generator、假的 QueryExecutor 或假的查询入口，不调用外部模型。

### Real AI Evaluation（真实 AI 评测）

- 使用配置的真实模型顺序运行 21 条案例。
- 生成第一份 Baseline 报告。
- 真实运行结果不作为确定性单元测试，因为外部模型结果可能变化。

## 开发任务

| Task | 目标 | 完成标准 |
|---|---|---|
| T1 案例与比较 | 加载标准案例，实现确定性结果比较 | 格式、行列、顺序、重复值、`NULL` 和数值误差测试通过 |
| T2 Runner 与汇总 | 复用现有 Service 和 Executor 顺序运行案例 | 单条失败隔离、状态和准确率汇总测试通过 |
| T3 报告与回归 | 生成运行指纹、JSON 报告并比较明确基线 | 指纹、Secret 防护、回退和改善测试通过 |
| T4 运行入口 | 组装现有真实依赖并提供模块命令 | 不复制查询链路；假的依赖端到端测试通过 |
| T5 真实 Baseline | 经明确授权后以在线 RAG 模式运行 21 条真实模型案例 | 报告生成并人工确认；随后按仓库整体版本规则决定是否创建 Tag |

T1 至 T4 是软件实现任务，完成后分别测试、审查和 Commit。T5 是有外部调用的评测运行，不在未授权情况下自动执行。

## 不做

- 不修改 Online Query。
- 不新增数据库表、消息队列、Web 服务或任务调度器。
- 不并发、不重试、不自动优化 Prompt。
- 不引入 pandas、评测框架或新的第三方依赖。
- 不把报告系统建设成新的平台。

## 设计状态

Implementation Design（实现设计）已完成，无阻塞技术问题，等待人工确认后进入实现。

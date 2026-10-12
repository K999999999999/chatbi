# 评测结果比较与报告身份：整理前的过程记录

来源：`docs/designs/evaluation.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 结论

Evaluation（评测）实现为一个离线回归评测 Runner（运行器），不建设新的查询系统，不提供 API 或常驻服务。

它读取固定测试集，逐条调用绑定测试身份的 `BoundAuthorizedQueryService.query()`，由其执行现有 `OnlineQueryService.execute()`，再执行标准 SQL 得到标准结果，比较两边数据并输出 JSON 报告。第一份报告建立 Baseline（基线），后续报告识别 Regression（能力回退）。

评测入口支持两种装配模式：Software Test（软件测试）默认使用静态 `QueryContext`，保证确定性测试不依赖本地模型和 Qdrant；真实 AI Evaluation（AI 评测）通过 `--online-retrieval` 显式装配与生产入口一致的 `OnlineRetriever`，用于验证在线 RAG 和后续 SQL 链路。

## 最小代码结构

评测工具从运行时代码 `src/` 中独立出来，根目录 `evaluation/` 只承载离线评测代码。共享能力与具体评测套件分开；每个套件的案例文件和实现代码放在同一目录。

| 路径 | 职责 |
|---|---|
| `evaluation/__main__.py` | CLI 入口和依赖装配，按参数调度对应套件 |
| `evaluation/common/` | 各套件共用的报告、指纹、错误处理和 Markdown 渲染 |
| `evaluation/suites/single_turn/` | 单轮标准案例、加载 / 比较逻辑和顺序运行器 |
| `evaluation/suites/multi_turn/` | 多轮 Conversation 案例、API 客户端、运行与报告逻辑 |
| `evaluation/suites/business_analysis/` | 经营分析案例、Judge、运行与报告逻辑 |
| `evaluation/suites/query_understanding/` | 查询理解语义案例与评测逻辑 |

Software Test（软件测试）按相同分类放在 `tests/evaluation/`：

| 路径 | 职责 |
|---|---|
| `tests/evaluation/test_entrypoint.py` | CLI 参数分派、依赖装配和入口级报告行为 |
| `tests/evaluation/common/` | 共享报告、数据指纹与 Observability 行为 |
| `tests/evaluation/single_turn/` | 单轮案例加载、结果比较、运行器和验收测试 |
| `tests/evaluation/multi_turn/` | 多轮案例、Conversation API 客户端和运行行为 |
| `tests/evaluation/business_analysis/` | 经营分析案例、Judge、运行器和报告行为 |
| `tests/evaluation/query_understanding/` | 查询理解语义评测行为 |

调整只改变目录和导入边界，不改变已有评测行为或案例 Contract。

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

## 运行入口

软件测试不调用真实 LLM。

真实评测命令设计为：

```text
uv run --env-file .env python -m evaluation --online-retrieval
uv run --env-file .env python -m evaluation --online-retrieval --baseline <report-path>
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

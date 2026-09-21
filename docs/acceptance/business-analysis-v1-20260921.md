# Business Analysis V1（经营分析 V1）验收记录

初始记录：2026-09-21；Real E2E 补充验收：2026-09-22

## 结论

本记录确认 Business Analysis V1 的确定性 Software Test、标准案例评测器、边界行为和本地完整 Real E2E 证据已经形成。普通查询、Multi-Turn、授权和 Online Query 回归未改变。

本次已获得用户授权并执行本地真实 LLM、BGE-M3、Qdrant、Retrieval、SQL Guard、只读 PostgreSQL、认证和 HTTP API 串联的 Real E2E。结论为 `PASS（本地真实链路）`；该结论不替代 hosted CI、完整 21-case Real E2E、人工业务复核或 Production Readiness。

## Software Test（软件测试）

执行命令：

```text
uv run --with pytest python -m pytest -q
uv run python -m compileall -q src tests
git diff --check
```

Software Test 覆盖：

- Plan Contract、指标别名、维度、依赖图、循环依赖、下钻深度和 Task 数量限制；
- Task Semantic Adapter、规范化查询问题、语义校验、授权查询入口调用边界；
- `completed`、`failed`、`skipped`，依赖失败传播、独立 Task 继续、空结果和 `truncated`；
- Summary LLM 结构化报告、证据引用、失败/跳过/空结果/截断标记和 `CANNOT_ANSWER` / `LLM_ERROR`；
- `mode=query` 向后兼容、`mode=analysis`、未知模式、`conversation_id` 冲突和统一 API 错误响应；
- Streamlit 普通查询与经营分析的模式提交、普通 `conversation_id` 隔离和独立分析时间线；
- 原有 Query API、Multi-Turn、Online Query、Authorization、Evaluation 回归。

最终命令结果以本次 candidate commit 的终端输出和提交前测试记录为准；没有通过的测试不得被解释为通过。

本次最终结果：`445 passed, 6 skipped, 123 subtests passed`；`compileall` 和 `git diff --check` 均通过。

## AI Evaluation（AI 评测）

标准案例文件：`src/evaluation/business_analysis_cases.json`。

案例范围：

| 案例 | 目标 | 确定性检查 |
|---|---|---|
| `trend-sales-q1-2025` | 2025 Q1 趋势 Task、人民币净销售额 | Task 计划、Task 结果和报告证据 |
| `compare-2024-and-2025` | 2024 / 2025 年份对比 | Task 计划、Task 结果和报告证据 |
| `breakdown-sales-region-q1-2025` | 2025 Q1 销售区域拆解 | Task 计划、Task 结果和报告证据 |
| `root-cause-by-product-line-q1-2025` | 趋势后按产品线下钻 | Task 数量、依赖、Task 结果和报告证据 |
| `ambiguous-profit` | “利润”无法唯一确定 | 必须返回 `CLARIFICATION_REQUIRED`，不得改写为毛利 |

评测器分层比较结构化计划、每个 Task 的真实查询结果和报告证据，不评分自然语言流畅度，也不把 Fake Decomposer 的结果当成真实模型准确率。真实 5-case 批量评测已执行，命令为：

```text
uv run --env-file .env python -c "import os, runpy; os.environ['LLM_TEMPERATURE']='0'; runpy.run_module('src.evaluation', run_name='__main__')" --business-analysis --online-retrieval
```

结果：`5/5 PASS`、`INVALID_CASE=0`；Plan Accuracy、Task Execution Accuracy、Report Grounded Accuracy、End-to-End Accuracy 均为 `100%`。报告：`reports/evaluation/20260921T184034Z-b4bb546-business-analysis.json`。该评测证明当前 5 条 Golden Case 的真实链路通过，不等价于任意自然语言问题的业务准确率；Summary 自然语言质量仍需人工 Business Review 或后续 LLM Judge。

## Business Acceptance（业务验收）

已通过确定性 Contract 场景验证：

1. 正常多 Task：计划可拆为多个 Task，按依赖执行，结构化结果交给最终自然语言报告；
2. 依赖 Task 失败：下游变为 `skipped`，独立 Task 仍继续执行；
3. 空结果：保持 `completed`，不自动新增 Task，并在报告不完整性中标记；
4. 截断结果：保留 `truncated=true`，报告不得声称完整排名或确定性原因；
5. 失败/跳过/不存在的 Task 不能作为 `evidence_task_ids`；
6. “利润”没有唯一业务口径时触发澄清，不自动解释为“毛利”；
7. 经营分析不读取、创建或修改普通查询会话，切回普通查询后原会话仍可继续；
8. 没有显式时间过滤但按年份、季度或月份分组时，Retrieval 能依据指标 `time_field` 选择唯一日期 Join。

上述是软件 Contract 和固定结果的业务行为验收；真实数据场景见下方 Real E2E，仍不替代业务人员对报告数值和经营解释的复核。

## Real E2E（真实端到端）

状态：`PASS（本地真实链路）`。

验收环境和资产：

- 本地 `.env` 和真实 LLM 配置；不记录 API Key、Token、Password 或连接字符串；
- PostgreSQL 容器健康，业务库只读查询；Qdrant 容器健康；
- 本地 BGE-M3 模型 `models/bge-m3`；
- 依据当前结构 / Semantic 事实重新构建并发布 RAG 资产：`20260921-bge-m3-business-analysis-e2e`，TABLE 7、COLUMN 69、METRIC 6、Relationship Graph 边 9；
- 真实 FastAPI 启动检查：`GET /health` 返回 `{"status":"ok"}`。

执行的真实链路：

1. 真实 Task Decomposer 生成计划，确定性 Plan Validator 校验，Task Executor 通过授权查询入口进入 Online Retrieval、SQL 生成、SQL Guard 和只读 PostgreSQL，Summary LLM 生成自然语言报告。
2. 有数据的明确期间案例“请分析 2025 年第一季度按销售区域统计人民币净销售额”返回 `BusinessAnalysisSuccess`，3 个 Task 均为 `completed`，行数为 `[1, 3, 6]`，报告引用全部 3 个完成 Task，`incomplete_tasks=[]`。
3. 空结果案例“请分析最近三个月的人民币净销售额趋势，并按销售区域拆解可能原因”相对于本地数据最大完成日期 `2025-12-31` 的当前时间范围没有数据；2 个 Task 均完成但行数为 0，报告将 Task 标记为不完整，没有把空结果包装为结论。
4. 真实 HTTP / Auth：使用唯一临时 analyst 身份调用 `POST /auth/login` 返回 `200`，随后携 Bearer Token 调用 `POST /api/v1/query` 且 `mode=analysis` 返回 `200`；单 Task 明确案例返回 6 行、Task 为 `completed`，报告字段齐全，响应不包含 `sql` 或 `conversation_id`。临时身份、Session 和本次测试审计记录已清理，数据库核对 `TEMP_USER_COUNT=0`。
5. 失败传播案例：同一 HTTP 链路的一次动态多 Task 调用返回 `200`，Task 状态为 `completed / failed / completed / skipped`；报告仍生成并标记不完整，证明依赖失败不会伪装为完整成功。
6. 真实 5-case Golden Set 批量评测全部通过：趋势、年份比较、区域拆解、两级下钻和利润歧义澄清；每个计划的参考 SQL 先经过 SQL Guard 并在只读 PostgreSQL 执行，Task 结果按行列和值与参考结果比较，报告按证据 Task 和不完整 Task 标记比较。

本次真实验收过程中发现并修复的 Contract 问题：

- 补充 `最近 N 个月`（含“最近三个月”）的确定性时间标准化，并在 Task Decomposer Prompt 中明确 `time_range` 对象格式；
- 补充“月份/年份”到结构事实“月/年”的时间维度别名匹配，避免合法时间维度被 Retrieval 错误判为不可达；
- 修复没有显式时间过滤但按日历维度分组时未启用指标 `time_field` 的问题，避免 `dim_date` 的多个日期关系产生 Join 歧义；
- 修复年份单字 alias 把无关表扩大为日期维度候选的问题，并补充离散年份比较的 canonical query 规则；
- 对未定义口径的“利润”增加程序级澄清门禁，对 Task 失败保留内部失败原因，便于 Evaluation 定位链路层级；
- 明确 Summary LLM 的列表字段类型，并规定 `incomplete_tasks` 只输出 task_id，不拼接 reason 或输出对象。

以上修复均有确定性回归测试；旧的 RAG 资产未删除，新的本地资产使用独立 build id 发布。

未覆盖范围：`.github/workflows/real-e2e.yml` 的 hosted CI 21-case、人工业务人员对报告数值和经营解释的复核、Summary 自然语言质量的独立 LLM Judge、生产部署 / 负载 / 多租户 / Secret 管理。因此不能据此声称 Production Ready 或所有问题上的业务准确率达标。

## 变更追踪

- Ticket 01：`f776e14`，计划结构与确定性校验；
- Ticket 02：`8fb1afc`，Task Semantic Adapter 与依赖执行；
- Ticket 03：`b1fc4db`，报告 Contract 与 Summary LLM；
- Ticket 04：`c72c4e4`，API、Streamlit 和会话隔离；
- Ticket 05：本记录、标准案例和评测器完成后形成独立提交。
- Real E2E 补充修复：时间范围 Prompt / 标准化、时间维度别名和 Summary 列表 Contract；待最终验收后形成独立本地提交。

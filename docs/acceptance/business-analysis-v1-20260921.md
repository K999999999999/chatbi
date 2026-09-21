# Business Analysis V1（经营分析 V1）验收记录

日期：2026-09-21

## 结论

本记录确认 Business Analysis V1 的确定性 Software Test、标准案例评测器和边界行为证据已经形成。普通查询、Multi-Turn、授权和 Online Query 回归未改变。

本次没有执行真实 LLM、RAG、SQL Guard、PostgreSQL 串联的 Real E2E，也没有把固定模型、Fake Query Service 或静态样例结果当作真实业务准确性证据。Real E2E 需要单独授权，当前状态为 `NOT RUN`。

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

本次结果：`433 passed, 6 skipped, 121 subtests passed`。

## AI Evaluation（AI 评测）

标准案例文件：`src/evaluation/business_analysis_cases.json`。

案例范围：

| 案例 | 目标 | 确定性检查 |
|---|---|---|
| `trend-sales-last-three-months` | 趋势 Task、人民币净销售额 | Task 类型和指标 |
| `compare-current-and-previous-year` | 期间对比、年份维度 | Task 类型、指标和维度 |
| `breakdown-by-sales-region` | 销售区域拆解 | Task 类型、指标和维度 |
| `root-cause-by-product-line` | 趋势后按产品线下钻 | Task 数量、依赖、Task 类型和维度 |
| `ambiguous-profit` | “利润”无法唯一确定 | 必须返回 `CLARIFICATION_REQUIRED`，不得改写为毛利 |

评测器只比较结构化计划和确定性校验结果，不评分自然语言流畅度，也不把 Fake Decomposer 的结果当成真实模型准确率。真实 LLM 评测本次未执行，状态为 `NOT RUN`。

## Business Acceptance（业务验收）

已通过确定性 Contract 场景验证：

1. 正常多 Task：计划可拆为多个 Task，按依赖执行，结构化结果交给最终自然语言报告；
2. 依赖 Task 失败：下游变为 `skipped`，独立 Task 仍继续执行；
3. 空结果：保持 `completed`，不自动新增 Task，并在报告不完整性中标记；
4. 截断结果：保留 `truncated=true`，报告不得声称完整排名或确定性原因；
5. 失败/跳过/不存在的 Task 不能作为 `evidence_task_ids`；
6. “利润”没有唯一业务口径时触发澄清，不自动解释为“毛利”；
7. 经营分析不读取、创建或修改普通查询会话，切回普通查询后原会话仍可继续。

上述是软件 Contract 和固定结果的业务行为验收，不等价于真实业务数据上的数值验收。真实数值、Retrieval 命中、SQL Guard 和 PostgreSQL 结果需要 Real E2E 与业务人员复核。

## Real E2E（真实端到端）

状态：`NOT RUN`。

未使用真实 `.env`、真实 LLM、Qdrant、BGE-M3 或 PostgreSQL 执行经营分析链路，因此不声称 Business Analysis V1 已完成真实生产数据验收，也不声称报告数值准确率已经达标。

## 变更追踪

- Ticket 01：`f776e14`，计划结构与确定性校验；
- Ticket 02：`8fb1afc`，Task Semantic Adapter 与依赖执行；
- Ticket 03：`b1fc4db`，报告 Contract 与 Summary LLM；
- Ticket 04：`c72c4e4`，API、Streamlit 和会话隔离；
- Ticket 05：本记录、标准案例和评测器完成后形成独立提交。

# Ticket 06：Query Understanding 回归、Evaluation 和文档同步

Status: done

## What to build

补齐 Query Understanding Feature 的验证证据，并完成与已确认 Contract 相关的最小文档同步。

验证内容包括：

- 结构化候选、校验失败、业务拒答和技术失败的确定性测试；
- 日期、过滤、指标数量、指标歧义、字段歧义和 Join 不可达回归案例；
- Query Understanding 到 Retrieval 到 SQL Guard 的链路测试；
- 真实 LLM Evaluation（评测）和现有案例回归；
- 旧文档中“最多 3 个”同步为已确认的“最多 5 个”；
- 记录未测试的真实 Provider、数据库或外部服务范围。

## Blocked by

Ticket 01：SemanticQuery Contract 和确定性校验

Ticket 02：QueryUnderstandingAdapter

Ticket 03：OnlineQueryService 主链路接入 Query Understanding

Ticket 04：Online Retrieval 消费 ValidatedSemanticQuery

Ticket 05：Prompt 和 SQL Generation 接入已确认语义

## Acceptance criteria

- 新增行为有确定性 Software Test（软件测试）覆盖；
- 结构化理解失败不进入 Retrieval、SQL 或 Database；
- 指标、维度、日期、过滤条件和 Join 关键 Bad Case（坏案例）加入 Regression（回归）集合；
- 真实 LLM Evaluation 能报告 Query Understanding 和最终 Execution Accuracy（执行准确率）影响；
- 旧 Online Query、Online Retrieval、SQL Guard 安全边界无回归；
- 文档不再保留已确认的指标数量冲突；
- 报告明确区分确定性测试、真实服务连通性、端到端结果和未验证范围。

## Result

- 已补齐 Query Understanding 结构化候选、校验失败、业务拒答、技术失败和链路停止边界的确定性回归；既有日期、过滤、指标数量、指标歧义、字段歧义和 Join 不可达案例继续纳入回归集合。
- `QueryFailure` 和 `CaseEvaluation` 记录内部 `failure_stage` 与 `internal_reason`；Evaluation JSON / Markdown 报告可以区分 `query_understanding`、`retrieval`、`sql_generation`、`sql_guard` 和 `database` 阶段，同时保留对外中文错误提示，不暴露内部细节。
- 已验证 Query Understanding → Retrieval → Prompt / SQL Generation → SQL Guard 的既有主链路没有确定性回归；结构化理解失败不会进入 Retrieval、SQL 或 Database。
- 已将当前 Online Query 相关文档中的指标上限统一为最多 5 个；历史验收记录仍保留原始时间点和原始证据，不篡改历史结果。
- 验证：定向测试 `18 passed`；全量确定性测试 `286 passed, 6 skipped, 99 subtests passed`。
- 本 Ticket 未调用真实 LLM、Qdrant、Embedding、PostgreSQL 或 BGE-M3；因此没有声称真实 Query Understanding 准确率、Execution Accuracy、业务验收或 Production Readiness。真实 Evaluation 需在明确授权外部调用后单独执行并保存不含 Secret 的报告。

本次真实评测后的系统修复：

- 修复绝对季度日期的标准化，统一生成半开区间；补充中文季度、数字季度和 `Q` 表达式回归。
- Retrieval 失败将内部原因传递到 `QueryFailure` 和 Evaluation 报告；对外仍返回受控中文提示。
- 在权威指标目录增加“已完成订单明细行数”指标，并重建、发布新的 BGE-M3 / Qdrant 资产；未修改评测集。
- 收紧 Query Understanding 的指标表达规则：普通上下文不拼入指标，决定口径的修饰词保留，避免把“已完成订单数量”压缩成“订单数量”。
- 本次验证：定向测试 `41 passed, 26 subtests passed`；全量确定性测试 `288 passed, 6 skipped, 102 subtests passed`；candidate commit 上最近一次真实在线 RAG Evaluation 为 `20/21`，Execution Accuracy 为 `95.24%`。唯一失败为一次 S04 的 `Query Understanding LLM_ERROR`，同问题单例真实调用已成功；此前 S02 单例真实调用也已成功；不将该结果表述为 21/21 或 Production Readiness。

## Comments

本 Ticket 不负责删除静态全量 Schema；静态路径清理和迁移另建 Feature。本 Ticket 的确定性验证和本次真实外部评测已完成并可形成本地 candidate commit；后续若要评估稳定准确率或 Production Readiness，仍需独立的重复评测与业务验收。

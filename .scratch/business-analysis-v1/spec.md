# Business Analysis V1（经营分析 V1）

Status: draft

## Problem Statement

当前 ChatBI 的 Online Query 负责把一个自然语言问题转换为一次安全查询并返回结构化结果。它适合单指标、单次聚合和简单筛选，但不能稳定处理趋势、期间对比、维度拆解和原因归因等需要多次查询的问题。

Business Analysis V1 需要在保留现有普通查询能力、授权边界、Semantic 业务口径和 SQL 安全边界的前提下，将一个复杂经营问题拆解为多个可执行的普通查询任务，按依赖关系执行，并根据任务结果生成便于人工阅读的自然语言分析报告。

## Solution

用户在当前 ChatBI 页面通过两个明确的模式入口选择能力：`普通查询` 或 `经营分析`。两个模式属于同一个 ChatBI 系统，共用授权和普通查询执行能力，但 V1 使用各自独立的 Application Workflow（应用流程）和状态边界。

```text
普通查询入口
  -> 现有 Multi-Turn 身份、会话和并发校验
  -> 现有多轮语义修订和普通查询链路
  -> 提交 QueryState

经营分析入口
  -> 当前用户认证和授权
  -> Task Decomposer
  -> Plan Validator / Planner
  -> 依赖感知的 Task Executor
  -> TaskResult 汇总
  -> Summary LLM
  -> BusinessAnalysisReport
```

V1 不增加自动 `QueryRouter`。用户选择的模式就是顶层路由，避免额外的 LLM 判断、普通查询与经营分析之间的误判，以及两种会话状态在同一轮中的隐式切换。

### Application Request Contract

继续使用现有 `POST /api/v1/query` 作为当前 ChatBI 的 HTTP 入口，请求增加可选的 `mode`：

```json
{
  "question": "最近三个月销售额为什么下降",
  "mode": "analysis"
}
```

允许的模式为：

- `query`：普通查询；
- `analysis`：单轮经营分析。

兼容规则：

- `mode` 缺失时默认为 `query`，旧调用方无需修改；
- `mode=query` 可以携带现有 `conversation_id`；
- `mode=analysis` 携带 `conversation_id` 时返回 `400 / INVALID_REQUEST`，并且在进入会话 Store、授权查询、Task Decomposer、Retrieval、LLM、SQL Guard 或数据库前结束；
- `mode=analysis` 不读取、不创建和不修改 `conversation_id`；
- `mode=query` 的成功和失败响应保持现有 Contract；
- 未知 `mode` 按现有请求校验规则返回 `400 / INVALID_REQUEST`；
- `mode=analysis` 返回 `AnalysisSuccessResponse` 或现有形状的 `QueryFailure`；
- `AnalysisSuccessResponse` 至少包含 `request_id`、固定值为 `analysis` 的 `mode`、`BusinessAnalysisReport` 形式的自然语言 `report` 和有界的结构化 `task_results`；
- 两种模式都必须经过当前认证和授权边界。

两个 UI 按钮只负责提交不同的 `mode`，不在前端实现查询、分析、授权或任务调度。

这是对当前 Query API Application Contract（应用契约）的有意扩展，不改变 Query API Adapter 的职责边界：API 只负责请求校验、模式分派、调用对应 Application Workflow 和响应序列化，不拥有 Task Decomposer、Task Executor、Summary LLM、业务指标或 SQL 事实。进入实现前，`docs/specs/query-api.md` 必须同步记录该扩展及普通查询响应保持兼容的规则。

经营分析错误沿用现有 `QueryFailure` 形状，并按以下规则归类：

- 请求字段、模式和 `conversation_id` 组合不合法：`INVALID_REQUEST`；
- 指标或维度无法唯一确定，需要用户补充信息：`CLARIFICATION_REQUIRED`；
- 计划不合法、超过任务/深度限制或当前 Semantic 无法支持：`CANNOT_ANSWER`；
- 结构、指标或 Retrieval 上下文不可用：`CONTEXT_ERROR`；
- Task Decomposer 或 Summary LLM 的 Provider 调用失败、超时或输出 Contract 无法校验：`LLM_ERROR`。

### 普通查询模式

普通查询入口继续复用现有 Multi-Turn Query：

- 支持当前 `conversation_id`、会话归属、TTL 和并发控制；
- 支持同一查询语义范围内的指标、维度、时间和过滤条件修订；
- 继续提交和读取现有 `QueryState`；
- 继续返回现有普通查询结果 Contract。

普通查询模式不负责趋势、原因归因、多查询拆解和经营分析报告。

### 经营分析模式

经营分析入口是 V1 的单轮分析流程：

- 不读取或提交现有 Multi-Turn 的 `conversation_id`；
- 不读取普通查询的 `QueryState`；
- 不保存 `AnalysisState`；
- 每次点击经营分析并提交问题，都独立生成一个分析计划；
- 用户可以在报告中查看任务状态和关键结果，但 V1 不支持基于报告继续追问。
- UI 可以继续保留普通查询当前的 `conversation_id`，但提交经营分析请求时必须省略它；
- 从经营分析切回普通查询时，恢复原来的普通查询会话；经营分析报告不写入 `QueryState`，也不作为普通查询的隐式上下文。

经营分析模式仍然使用当前用户认证和授权，每个 Task 都必须通过现有授权查询入口执行。

### Task Decomposer

进入 `business_analysis` 后，Task Decomposer 使用 LLM 将用户问题拆解为多个业务语义层面的普通查询任务。输入至少包括：

- 用户原始问题；
- 当前时间和时间范围上下文；
- 已登记的指标、定义、别名、公式和时间口径；
- 当前可用的业务维度和结构上下文；
- 任务拆解规则和结构化输出 Contract。

输出为 `AnalysisPlan` 候选，任务至少包含：

```text
task_id
task_type
description
metrics
dimensions
time_range
filters
depends_on
expected_output
```

Task 只描述需要查询什么，不生成 SQL，不直接访问数据库，不自行创造指标或维度。指标和维度使用业务语义名称；Task Decomposer 不负责生成最终的 `QueryRequest.question`，后续由确定性的 Task Semantic Adapter 生成规范化查询文本和结构化语义。

### Plan Validator / Planner

程序对 `AnalysisPlan` 进行确定性校验，并将合法任务转换为可执行步骤：

- 指标必须来自当前 `src/semantic/metrics.json` 或其他已确认的 Semantic Source of Truth；
- 维度必须来自当前已确认的结构和语义事实；
- `task_id` 必须唯一；
- `depends_on` 必须引用存在的任务；
- 依赖关系不得形成循环；
- Task 必须包含足以调用普通查询链路的信息；
- 计划必须受到下钻深度、有限任务数量和结果规模约束，不能无限扩张；V1 单个分析最多包含 12 个 Task（包括所有层级，不能由 LLM 提高）；
- 根任务计为第 0 层，V1 最多允许向下钻取两层；最终报告不计入下钻层级；
- 计划生成阶段只能根据最大深度、Task 数量、已登记指标/维度和结构化任务信息停止继续下钻；结果为空、证据不足或已经形成结论属于执行后的报告判断，不触发新 Task 生成。

V1 使用静态 `Plan-and-Execute`：计划生成并校验后开始执行，执行过程中不新增 Task、不进行结果驱动的动态 `Replanning`，也不由 LLM 自动重写整个计划。

### Task Executor

`Task Executor` 依赖现有 `AuthorizedQueryService` 和 `OnlineQueryService` 执行每个任务，不通过 HTTP loopback（回环调用）重复调用 API，不复制 Prompt、Retrieval、SQL Guard 或数据库执行逻辑。

V1 按依赖关系串行执行：

1. 找到所有依赖已完成或没有依赖的待执行任务；
2. 调用现有授权查询入口执行一个普通查询；
3. 保存该任务的结构化结果；
4. 继续执行依赖条件已满足的任务；
5. 所有必要任务完成或进入终态后，交给结果汇总和报告生成。

V1 不要求并行执行无依赖任务；后续可以在不改变 Task 和 TaskResult Contract 的前提下增加并行调度。

V1 中的 `depends_on` 只表达执行顺序和失败传播：

- 下游 Task 等待上游 Task 完成；
- 上游失败时，下游可以被标记为 `skipped`；
- 下游 Task 的查询参数必须在计划生成时已经完整具备；
- V1 不使用上游结果行动态改写下游查询，也不增加 `input_refs` 或动态重新规划；
- 最终 Summary LLM 可以读取全部 `TaskResult`，但它不改变任务执行计划。

任务执行结果统一为 `TaskResult`：

```text
task_id
status: completed | failed | skipped
columns
rows
row_count
truncated
error
```

`TaskResult` 保存结构化查询数据，不在每个任务完成后单独调用 LLM 生成自然语言总结。结构化结果是最终报告的事实依据。`error` 只允许安全的公开错误码和用户可读信息，不包含 SQL、数据库连接信息、异常堆栈或 Secret（密钥）。每个 Task 继续遵守当前 Online Query 最多返回 100 行的边界；超过时保留 `truncated=true`，不得被报告当作完整数据集。

### Task to Online Query Contract

每个 `AnalysisTask` 由 Application 层的确定性 Task Semantic Adapter（任务语义适配器）转换为现有 `ValidatedSemanticQuery` 和 `QueryRequest`，再交给绑定当前用户身份的 `AuthorizedQueryService` 执行：

```text
AnalysisTask
  -> Task Semantic Adapter
  -> ValidatedSemanticQuery
  -> QueryRequest
  -> AuthorizedQueryService
  -> OnlineQueryService
```

该适配器必须：

- 将指标别名规范化为已确认的 Semantic 名称；
- 根据现有时间口径、当前时间和时区规则规范化 `time_range`；
- 将 Task 的指标、维度、时间和筛选条件转换为 `SemanticQueryCandidate`，再通过现有确定性校验生成 `ValidatedSemanticQuery`；
- 生成稳定的 `canonical_task_question`，并将其同时作为 `QueryRequest.question` 和 Retrieval 的问题文本；
- 将 `ValidatedSemanticQuery.original_question` 设置为该规范化任务问题，而不是重新拼接原始复杂问题；
- 在语义不合法、指标不明确或时间条件无法校验时，在进入数据库前结束该 Task，并返回对应的公开错误。

适配器不调用第二个 Query Understanding LLM，不直接映射数据库字段，不生成 SQL，不绕过现有 Semantic 校验、Retrieval、SQL Guard 或只读数据库身份。

### Dependency and Failure Behavior

- 无依赖或依赖已完成的任务可以进入执行；
- 依赖未完成的任务必须等待；
- 独立任务失败时，不阻止其他独立任务继续执行；
- 依赖失败任务的下游任务标记为 `skipped`；
- 任务最终失败后，最终报告可以基于已完成结果生成，但必须标明分析不完整；
- 失败、跳过和空结果不能被包装成完整成功结论；
- 空结果按照现有 Online Query 规则仍是 `completed`，不会自动生成新 Task，也不会自动改变已经校验通过的依赖调度；报告必须标记证据不足；
- `truncated=true` 的结果可以作为有限证据，但报告必须说明数据被截断，不能据此声称完整排名、完整覆盖或确定性原因；
- 依赖调度、状态转换和失败传播由程序决定，不由 LLM 临时决定。

下钻深度以任务依赖图中的最长有效链路计算：

```text
第 0 层：整体指标趋势
  -> 第 1 层：按销售区域拆解
     -> 第 2 层：对重点区域按产品线继续拆解
```

V1 不允许在执行过程中递归生成新的下钻任务。总 Task 数量上限为 12，且在进入执行前由程序校验；执行结果只能影响已有 Task 的终态和最终报告，不能扩大计划。

### Summary and BusinessAnalysisReport

所有任务进入终态后，Summary LLM 读取结构化 `TaskResult`，生成自然语言经营分析报告。报告使用结构化外壳，字段内容面向人工阅读：

```text
title
executive_summary
key_findings
trend_judgment
root_causes
action_suggestions
evidence_task_ids
incomplete_tasks
```

最终报告必须：

- 用自然语言说明趋势、对比、拆解和原因；
- 为关键发现关联来源 Task；
- 只使用已完成任务返回的数据；
- 说明失败、跳过、空结果或证据不足的情况；
- `evidence_task_ids` 只能引用 `completed` Task，`incomplete_tasks` 必须由程序记录的失败、跳过、空结果或截断状态决定；
- Summary LLM 输出必须通过结构化 Contract 校验；引用不存在的 Task、缺少不完整性标记或输出非法结构时，不得返回分析成功；
- 不让 LLM 自行创造指标口径或凭空计算数据。

数值聚合、变化率、同比/环比和贡献度等计算由现有 SQL 查询链路或确定性程序完成，LLM 负责任务规划和结果表达。

所有 Task 进入终态后，如果至少存在一个 `completed` Task，才允许调用 Summary LLM；如果没有任何可用完成结果，系统返回 `CANNOT_ANSWER` 的 `QueryFailure`，不生成空的成功报告。程序以实际 Task 状态为准校验或生成 `incomplete_tasks`，不信任 Summary LLM 自行改变失败、跳过、空结果或截断状态。Summary LLM 调用失败或输出校验失败时，同样返回 `LLM_ERROR`，不能把已有 Task 成功包装成报告成功。

## User Stories

### 普通查询

用户选择“普通查询”，输入“本月销售额是多少”，系统继续执行现有普通查询链路，返回原有查询结果，并允许用户在当前 Multi-Turn 会话中继续追问。

### 多任务经营分析

用户选择“经营分析”，输入“最近三个月销售额为什么下降”。系统生成整体趋势、区域拆解、产品拆解等任务，按依赖执行，最后生成自然语言报告。

### 指标口径不明确

用户输入“最近利润为什么下降”，但当前 Semantic Catalog 没有能够唯一确定的“利润”指标时，系统不能自动将其映射为“毛利”，而应返回 `CLARIFICATION_REQUIRED`，由用户重新提交一个明确的经营分析问题；V1 不通过 AnalysisState 实现澄清多轮。

### 任务部分失败

区域拆解任务失败、产品拆解任务成功时，系统继续保留可用结果，跳过依赖区域结果的下游任务，并在最终报告中说明报告只基于部分证据。

## Implementation Decisions

- 两个模式入口属于同一个 ChatBI 系统；普通查询入口保留现有 Multi-Turn，经营分析入口 V1 采用单轮报告流程。
- V1 不增加自动 `QueryRouter`；模式选择由 UI 和 Application Contract 明确表达。
- Task Decomposer 和 Summary LLM 的输出都是不可信候选；程序负责校验任务、依赖、授权、数据范围和状态。
- 经营分析不是第二套数据库查询能力，而是对现有普通查询能力的编排。
- 每个 Task 直接复用现有授权和 Online Query 链路；不重新生成自然语言再让另一个 LLM 解释，不通过 HTTP 回环复制查询。
- 业务事实以现有结构记录和 `src/semantic/metrics.json` 为准。当前已登记指标包括已完成订单数、已完成订单明细行数、人民币净销售额、人民币销售成本、人民币毛利和毛利率；未登记或口径不明确的指标必须澄清。
- 当前指标的业务时间口径继续遵守现有完成日期规则；本 Feature 不静默修改指标定义。
- LLM 不负责 SQL 安全、授权、业务口径或最终数值事实。
- 现有 `POST /api/v1/query` 的普通查询行为和 Multi-Turn 会话安全边界必须向后兼容；经营分析使用显式 `mode=analysis`，不携带或修改普通查询 `conversation_id`。
- 经营分析最多执行 12 个 Task，每个 Task 复用 Online Query 当前最多 100 行的结果边界；超过深度、Task 数量或结果边界时，由程序拒绝、截断或标记不完整，不由 LLM 放宽限制。
- Query API 的 Module Contract 扩展必须在实现该 Feature 时同步更新 `docs/specs/query-api.md`，但不改变 Online Query 的单次查询职责和普通查询响应。

## Testing Decisions

### Software Test

- UI / Application 能明确区分普通查询和经营分析模式；模式选择不会调用额外的 Router LLM；
- 缺失 `mode` 默认按 `query` 处理；`analysis` 模式拒绝 `conversation_id`；旧的普通查询请求和响应继续通过回归测试；
- `analysis + conversation_id` 在会话 Store、授权查询和任何 LLM 调用前返回 `400 / INVALID_REQUEST`；切换回普通查询时保留原普通查询会话；
- `analysis` 成功响应包含报告和有界的结构化 TaskResult，失败响应保持统一错误形状；
- Task Decomposer 能生成满足 Contract 的 `AnalysisPlan`；不生成 SQL；
- 指标、维度、Task 类型、依赖引用和循环依赖校验正确；
- 根任务、第 1 层和第 2 层下钻可以执行，超过第 2 层的任务被拒绝或要求收敛；
- 超过最大深度或 12 个 Task 时在执行前被拒绝；执行后结果为空、无可用证据或已形成结论时不生成新 Task，而是由报告标记证据不足或分析不完整；
- 任务没有依赖、依赖已完成、依赖未完成和依赖失败时，Executor 的状态转换正确；
- `depends_on` 只控制顺序和失败传播，下游任务不会从上游结果行动态生成查询条件；
- Task Semantic Adapter 能将合法 AnalysisTask 转换为现有 `ValidatedSemanticQuery`，非法指标、维度和时间条件在进入数据库前被拒绝；
- 独立任务失败不会阻止其他独立任务；下游任务会正确标记为 `skipped`；
- `TaskResult` 正确保存成功、空结果、失败和跳过状态；
- `TaskResult` 的错误不泄露 SQL、数据库连接信息、异常堆栈或 Secret；`truncated=true` 会进入报告的不完整性判断；
- 普通查询继续正确提交和读取 `QueryState`；经营分析不会创建、读取或修改 `QueryState`；
- Summary 只能使用输入的 TaskResult，并能标记证据来源和不完整任务；不存在的 `evidence_task_ids`、非法结构和 Summary LLM 失败不能返回成功报告；
- `direct_query` 继续通过现有 Online Query、授权、Retrieval、SQL Guard 和数据库测试；
- 现有普通查询 API 和 Evaluation 回归不被破坏；经营分析请求不会创建或修改普通查询会话。

### AI Evaluation

- 建立普通查询模式、简单经营分析、趋势、对比、维度拆解、原因归因、歧义指标和无法回答问题的标准案例；
- 评估 Task 拆解完整性、指标和维度遵循度、依赖关系合理性以及最终报告是否引用真实 TaskResult；
- 不把自然语言报告流畅度单独当作业务正确性证据。

### Business Acceptance

- 至少完成一个正常的多任务分析案例；
- 至少覆盖一个依赖任务和一个独立任务失败的案例；
- 用户能够读懂最终自然语言报告，并能从报告中的 Task 引用查看对应查询结果；
- 报告不会把不明确的“利润”自动解释成“毛利”。

## Out of Scope

- 自动 `QueryRouter` 和基于 LLM 的顶层模式判断；
- 经营分析 `conversation_id`、AnalysisState 和分析报告后的多轮追问；
- 预测、模拟测算、预算规划和自动执行经营动作；
- 执行过程中由 LLM 自主动态重写完整计划；
- 执行结果驱动的新增 Task、动态下钻和动态 `Replanning`；
- V1 的并行 Task 执行优化；
- 让 LLM 直接生成 SQL、直接访问数据库或直接决定权限；
- 为每个 Task 单独生成自然语言总结；
- 自动新增或猜测 Semantic 指标、维度和业务口径；
- 多数据源、多 Schema、多租户和企业 Production Readiness；
- 替换现有 Online Query、SQL Guard、授权或 RAG Retrieval 实现。

## Further Notes

- `docs/architecture.md`、`docs/specs/online-query.md`、`docs/specs/query-api.md`、`docs/adr/0001-multi-turn-query-v1-boundaries.md` 和 `src/semantic/metrics.json` 是本 Spec 使用的主要事实源。
- 当前 `Online Query` 的成功结果是结构化列和行，且当前模块本身不生成自然语言总结；Business Analysis 通过上层编排和 Summary LLM 增加报告能力，不修改该模块的基本职责。
- 当前 ADR-0001 明确把 Business Analysis 留给后续 Feature；本 Spec 将 Business Analysis 作为独立的单轮 Feature，保留 ADR-0001 对普通 Multi-Turn 的现有边界，不把经营分析状态静默并入 Multi-Turn。
- 本 Spec 会扩展 Query API 的 Application Contract，但不把业务分析职责下沉到 Query API Adapter 或 Online Query；实现该 Feature 时必须同步更新 `docs/specs/query-api.md` 的职责与响应说明。
- 本 Spec 是 `.scratch` 下的当前 Feature Contract 草稿。本次修复后仍必须通过 `workflow-design-review`，再拆分 Ticket；本 Spec 本身不授权实现。

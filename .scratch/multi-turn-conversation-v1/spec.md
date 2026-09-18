# Multi-Turn Conversation V1（受控多轮查询）Feature Spec

状态：已确认；`design-review` 为 `PASS WITH MINOR FIXES`；可进入 `to-tickets`

## Problem Statement

当前 ChatBI 已经能够完成一次“自然语言问题 → 业务语义解析 → Online Retrieval → SQL 生成 → SQL Guard → PostgreSQL 结果”的单轮查询。用户在查看结果后，如果想继续分析，必须重新重复时间范围、指标、维度和过滤条件，不能自然地表达“按销售区域拆开”或“改看毛利率”。

这会增加用户操作成本，也无法验证 ChatBI 是否能够在不丢失业务条件、不越权和不污染状态的前提下支持连续分析。

本 Feature 面向内部或受控用户，目标是提供一个带有生产安全约束的短期多轮查询闭环；它不宣称已经完成面向所有企业用户的最终 `Production Ready（生产可用）` 能力。

已确认的正常场景：

```text
用户：2025 年第一季度的人民币销售额是多少？
用户：按销售区域拆开。
用户：改看毛利率。
```

## Solution

在现有 Query API 和 Streamlit Reference Client（参考客户端）上增加短期 `Active Conversation（当前会话）` 能力：

- 第一次成功请求可以不携带 `conversation_id`，由服务端在成功提交状态后创建会话；首轮失败不创建会话，也不返回新的会话编号；
- 后续请求携带服务端返回的 `conversation_id` 和新的自然语言问题；
- 服务端只保留最后一次成功查询的 `Structured Query State（结构化查询状态）`；
- 新问题在上一轮状态的基础上新增或替换查询条件，然后重新执行一次单条受控查询；
- 每一轮都经过当前认证身份和授权策略，并复用现有授权、Online Query、SQL Guard 和数据库执行链路；
- 查询失败时不提交新的会话状态；
- Streamlit 维护一个当前会话，并提供“新建会话”操作。

第一版不把多轮对话扩展为长期聊天、经营分析 Agent 或多查询编排。

## User Stories

1. As an internal or controlled user, I want to ask a follow-up question using the previous query context, so that I do not repeat the same time range and business conditions.
2. As an internal or controlled user, I want to change or add a metric, dimension, time range or filter in a follow-up question, so that I can refine one analysis result safely.
3. As a user, I want a failed or ambiguous follow-up not to destroy my last successful query state, so that I can correct the question and continue.
4. As an authorized user, I want every turn to use my current identity and data authorization, so that a conversation cannot grant access beyond my current scope.
5. As an existing API or Streamlit caller, I want single-turn requests to continue working without a conversation identifier, so that this Feature does not break the existing entry point.

### 正常场景

```text
第 1 轮：2025 年第一季度的人民币销售额是多少？
第 2 轮：按销售区域拆开。
第 3 轮：改看毛利率。
```

- 第 2 轮继承第 1 轮的完成状态和季度范围，增加“销售区域”维度。
- 第 3 轮继承时间范围、完成状态和销售区域维度，把指标替换为“毛利率”。

### 边界与失败场景

- 同一语义槽位的新值替换旧值；不同语义槽位的新条件叠加。
- 无法唯一理解的追问必须请求澄清，不执行查询，不改变状态。
- 同比、环比、趋势、原因分析和其他需要多次查询的请求被受控拒绝，不改变状态。
- LLM、Retrieval、SQL Guard、授权或数据库失败时，不提交本轮候选状态，继续保留最后一次成功状态。
- 查询合法但结果为空时，仍视为成功轮次，可以成为下一轮基础。
- 其他用户、未知会话或过期会话不能触发查询。

## Implementation Decisions

### 1. Architecture（架构）和 Module 职责

- `Query API Adapter` 负责 HTTP 请求/响应转换和 `conversation_id` 的外部 Contract，不复制 Prompt、LLM、SQL Guard 或数据库逻辑。
- Application 层负责当前会话的状态读取、当前问题与结构化状态的组合、成功状态提交和失败状态保持。
- `AuthorizedQueryService` 仍是每一轮用户查询的授权入口；多轮状态不能绕过该入口。
- `Online Query` 继续负责一次查询的语义解析、检索、SQL 生成、安全校验和只读执行，不承担会话所有权、长期历史或 UI 状态管理。
- Streamlit 只保存服务端返回的 `conversation_id` 并发起后续请求，不保存或提交完整结构化状态，不直接连接 LLM、SQL Guard 或 PostgreSQL。
- 会话状态存储必须由服务端拥有，并通过 Application 边界与具体存储实现隔离；30 分钟 Idle TTL、单会话单并发轮次和失败语义已由本 Spec 固定，具体状态 Adapter、锁或 Compare-and-Swap（比较并交换）实现留到 Implementation Design（实现设计）阶段决定。

保持既有语义链路：

```text
Natural Language
→ Business Semantic Resolution
→ SemanticQuery
→ Certified Physical Mapping
→ SQL
```

多轮能力不能把 Natural Language 直接映射为数据库字段，也不能把上一轮 SQL 当作下一轮可信输入。

### 2. Domain 术语和状态规则

- `Conversation（对话）`：围绕同一分析目标的连续查询上下文，不等于长期聊天记录。
- `Active Conversation（当前会话）`：当前可以继续追问的短期会话。
- `Turn（轮次）`：一次问题与一次查询结果或受控失败的完整交互。
- `Structured Query State（结构化查询状态）`：最后一次成功查询的指标、时间范围、维度和过滤条件。
- 只有成功查询轮次才能更新状态；失败轮次不更新状态。
- 合法但为空的结果是成功状态。
- 会话状态不能替代当前身份、授权策略或数据范围。
- 会话采用 30 分钟无成功状态更新的 Idle TTL（空闲过期时间）；服务重启后会话失效，不保证恢复。
- 同一会话同一时刻只允许一个进行中的轮次；并发轮次返回 `CONVERSATION_CONFLICT`，不进入下游查询，也不改变会话状态。

### 3. API Contract（接口契约）

继续使用现有 `POST /api/v1/query`：

```json
{
  "question": "按销售区域拆开。",
  "conversation_id": "server-generated-id"
}
```

- `question` 仍然必填，并保持现有非空和请求体校验规则。
- `conversation_id` 可选；缺少时按无状态首轮执行，成功后创建新的当前会话，存在时尝试继续该会话。
- 服务端生成并返回 `conversation_id`；客户端不提交完整对话、结构化状态、身份字段、数据范围或 SQL。
- 成功响应保留现有查询结果字段，并返回当前会话编号。
- `conversation_id` 是成功响应中的新增字段；既有响应字段和语义不变，现有 JSON 调用方无需改变请求即可继续使用并可忽略该新增字段。
- 首轮失败不创建会话，也不在失败响应中返回新的 `conversation_id`；已有会话的失败响应不返回新的会话编号，客户端继续使用原编号重试。
- 失败响应保留现有受控错误形状；失败不得提交新状态。
- 未知、已过期或不属于当前用户的会话统一返回 `CONVERSATION_UNAVAILABLE`（HTTP `404`），不暴露会话是否存在，也不进入下游查询。
- 歧义追问返回 `CLARIFICATION_REQUIRED`（HTTP `422`）；超出 V1 单条查询修订范围返回 `UNSUPPORTED_ANALYSIS`（HTTP `422`）；两者都不改变状态。
- 同一会话的并发轮次返回 `CONVERSATION_CONFLICT`（HTTP `409`），不改变状态。
- 只提交 `question` 的既有单轮调用继续可用，不要求现有调用方升级。
- `X-Request-ID` 和 `X-Trace-ID` 的现有语义保持不变。

### 4. 身份、权限和数据边界

- 会话只能由创建它的当前认证用户继续。
- 每一轮都重新获取或验证当前 `AuthContext`，并执行当前授权策略。
- 历史会话状态不构成权限凭证；权限变化必须在下一轮生效。
- 未知、过期或不属于当前用户的会话不得进入 Retrieval、LLM、SQL Guard 或数据库执行。
- 客户端传入的 `conversation_id`、问题和其他请求字段都属于不可信输入；程序和权威授权策略最终裁决身份、数据范围和 SQL 安全。

### 5. 会话生命周期和交互范围

- V1 只保证当前会话内的连续追问。
- 页面关闭、30 分钟无成功状态更新或服务重启后不保证历史恢复；过期会话按 `CONVERSATION_UNAVAILABLE` 处理。
- Streamlit 只维护一个当前会话，提供“新建会话”操作，不提供会话历史列表、搜索、重命名或删除。
- V1 不增加正式 Web 前端，不引入 SSE、WebSocket 或第二条查询链路。

### 6. 失败、歧义和范围拒绝

- 无法唯一解析的追问返回受控澄清提示，不猜测、不执行、不改变状态。
- 超出单条查询修订范围的比较、趋势、原因分析和多查询需求返回受控拒绝，不自动进入 `Business Analysis`。
- 下游授权、上下文、LLM、SQL Guard、数据库或超时失败沿用现有错误边界，并保持最后一次成功状态。
- `CONVERSATION_UNAVAILABLE`、`CLARIFICATION_REQUIRED`、`UNSUPPORTED_ANALYSIS` 和 `CONVERSATION_CONFLICT` 的 HTTP 状态与失败语义固定，不由 LLM 或存储 Adapter 自行决定。
- 错误信息不得泄露原始异常、Secret、完整 Prompt、未经允许的 SQL 或其他用户数据。

## Testing Decisions

### Software Test（软件测试）

最高测试 seam（测试接缝）是 Application/Query API 的可观察请求-响应边界，使用确定性的授权、下游查询服务和会话状态替身验证状态转换；不依赖真实 LLM、Qdrant 或 PostgreSQL 来证明状态不变量。

必须验证：

1. 三轮正常场景能够保留时间范围和完成状态，增加销售区域维度，再替换为毛利率。
2. 同一语义槽位替换、不同语义槽位叠加。
3. 第一次请求不带 `conversation_id` 时创建会话；后续请求带编号时继续会话。
4. 旧的只提交 `question` 的单轮 API 调用继续成功。
5. 成功响应返回会话编号；失败响应不提交新状态。
6. 合法空结果可以作为下一轮的成功状态。
7. LLM、Retrieval、SQL Guard、数据库和授权失败后，下一轮仍基于最后一次成功状态。
8. 当前认证用户可以继续自己的会话，其他用户、未知会话和过期会话不能触发下游查询。
9. 每一轮都重新执行授权；历史状态不能绕过授权拒绝。
10. 歧义追问请求澄清并保持状态；比较、趋势、原因分析等范围外问题被拒绝并保持状态。
11. Streamlit 可以连续追问；“新建会话”后不再携带旧会话编号。
12. 响应不泄露异常堆栈、Secret、完整 Prompt、未经允许的 SQL 或其他用户数据。
13. 首轮失败不创建会话；已有会话的失败、澄清、范围拒绝和授权/下游失败均保留最后一次成功状态。
14. 30 分钟无成功状态更新后，会话不可继续且不触发下游查询；服务重启后会话同样不可恢复。
15. 同一会话并发请求最多允许一个进入下游；其他并发请求返回 `CONVERSATION_CONFLICT`，不改变状态。
16. 未知、过期或其他用户的会话统一返回 `CONVERSATION_UNAVAILABLE`，不泄露会话存在性。

测试应复用仓库现有 Query API TestClient、授权测试替身和 Streamlit 页面数据转换测试的方式；测试外部行为、Contract 和状态不变量，不绑定具体存储类或内部函数形状。

### AI Evaluation（AI 评测）

- 现有单轮 Evaluation 回归继续运行，不能因为新增会话逻辑而改变既有查询语义。
- 在实现完成后增加受控的多轮案例，验证真实 LLM 是否能在明确的上一轮结构化状态下正确完成“增加维度”和“替换指标”。
- 真实多轮评测使用与正式入口一致的授权、Online Query、RAG、SQL Guard 和数据库链路；报告必须区分单轮基线与多轮案例结果。

### Business Acceptance（业务验收）

- 通过现有 Streamlit Reference Client 完成确认的三轮场景。
- 业务验收确认第二轮保留第一轮时间/状态条件，第三轮保留时间/维度条件并替换指标。
- 业务验收确认澄清、拒绝和失败后，用户可以继续修正，不会被错误状态锁死。

### Real E2E（真实端到端）

在获得单独运行授权后，执行一次真实三轮 E2E，使用真实 LLM、已发布 RAG 资产和 PostgreSQL。该验证是行为证据，不自动替代完整 21 条 AI Evaluation、完整 Production Readiness 或正式企业上线验收。

## Out of Scope

- `Business Analysis V1`：同比、环比、趋势、原因归因、多查询拆解、多查询汇总和证据编排。
- 长期聊天历史、跨天恢复、服务重启恢复和会话历史管理。
- 多个当前会话并行切换、会话搜索、重命名和删除。
- 自主 Agent、自动规划、自动 SQL 修复、自然语言结果总结和模型多轮反思。
- 真实企业 SSO、持久化审计中心、租户平台、限流平台、完整负载治理、正式部署、监控告警和回滚体系。
- 正式 React、Vue 或其他 Web 前端。
- 修改业务指标事实、数据库结构、RAG 离线构建、SQL 安全原则或授权业务真相。
- 为多轮能力复制一套新的 Query、LLM、Retrieval、SQL Guard 或数据库执行链路。

## Further Notes

- `docs/specs/query-api.md` 和 `docs/specs/online-query.md` 已同步本 Feature 的公共边界；`Online Query` 仍只执行单次有效查询，不拥有会话状态。
- 当前正式 API 的 `conversation_id` 只属于 Query API/Application 边界；`Online Query` 的 `QueryRequest` 仍只承担单次有效查询输入，不接收原始会话历史或会话编号。
- V1 的 30 分钟 Idle TTL、首轮成功后创建会话、单会话单并发轮次和四个新增公开错误码属于已确认行为；具体状态存储 Adapter、锁或 Compare-and-Swap（比较并交换）的实现方式留给 Implementation Design。
- 本 Spec 未授权编写业务代码、测试代码、Ticket、Commit、Push、PR 或真实 E2E。
- 本 Spec 已根据审查 Finding 修正；`design-review` 结果为 `PASS WITH MINOR FIXES`，可使用 `to-tickets` 拆分实现 Ticket。实现阶段必须保留状态 Adapter、并发锁或 Compare-and-Swap、四个公开错误码的代码映射及对应确定性测试。

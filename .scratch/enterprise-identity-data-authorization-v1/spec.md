# 企业身份与数据授权 V1

状态：已确认，可进入 to-tickets

## Problem Statement

当前 ChatBI 的 Query API 只接收用户问题，Streamlit 通过 HTTP 调用 Query API；系统尚未建立用户身份、数据授权和授权审计边界。当前 POC / 内部入口可以用于可信环境，但不能直接宣称支持企业级生产访问。

如果只在前端隐藏按钮或展示登录状态，调用方仍然可以绕过页面直接请求 API。因此需要在服务端建立稳定、可替换的身份与数据授权核心，并保证未授权请求不会进入 LLM、Online Retrieval、SQL 生成或 PostgreSQL 执行链路。

当前尚未确定具体企业 SSO、部署平台或正式 Web 前端。Feature 不能把 ChatBI 核心绑定到 Feishu、GitHub、Microsoft Entra ID、Keycloak 或其他具体 Provider，也不能为了未来平台提前建设账号中心或自建 SSO。

## Solution

为 ChatBI 增加 provider-neutral（与身份 Provider 无关）的企业身份与数据授权核心：

1. 由服务端 Identity Provider Adapter 将外部身份转换为统一的 AuthContext。
2. Application Service 在进入 LLM、Online Retrieval、SQL 和数据库之前执行确定性授权。
3. V1 只允许已授权用户查询 mart_sales 的认证指标、维度和关系，并且只允许只读查询。
4. 授权策略由外部注入的静态策略文件提供，核心依赖 AuthorizationPolicyStore，不建设用户权限管理 UI 或权限数据库。
5. 允许和拒绝请求都生成最小授权审计事件，由 AuditSink 输出；不记录 Token、原始问题、完整 SQL 或查询结果。
6. Demo/Test IdentityProvider 只用于显式的 development/test 环境，生产环境没有有效外部身份时一律拒绝，不自动回退到 Demo 身份。
7. FastAPI Query API 和 Streamlit Reference Client 复用同一个 Application Service 与授权 Contract；Streamlit 不直接连接 LLM 或数据库，也不维护第二套权限规则。

本 Feature 的目标是先形成可验证的企业级核心边界，而不是在当前阶段完成某个具体企业 SSO 或正式 Web 前端。

## User Stories

1. As an approved ChatBI user, I want to query the certified mart_sales dataset, so that I can obtain authorized business data without exposing other schemas or unpublished fields。
2. As an unauthenticated or unauthorized caller, I want the service to reject my request before query execution, so that I cannot use the API, LLM or SQL chain to bypass data permissions。
3. As a deployment operator, I want to select an identity Provider through an Adapter, so that a future enterprise SSO can be integrated without changing the ChatBI domain core。
4. As a developer or portfolio demonstrator, I want to use an explicit Demo/Test Provider in a non-production environment, so that the authorization flow can be demonstrated without pretending that a real enterprise SSO is already integrated。
5. As an auditor or maintainer, I want both allowed and denied authorization decisions to emit structured audit events, so that access behavior can be traced without storing Secrets or sensitive query payloads。

## Implementation Decisions

### 1. Architecture and module responsibilities

- 保持 ChatBI 的 Modular Monolith（模块化单体）架构。
- 保持稳定依赖方向：Interfaces → Application → Domain；Infrastructure Adapter 实现 Application / Domain 需要的 Port / Contract。
- Identity Provider Adapter 属于边缘能力，负责验证外部身份并生成统一的 AuthContext；Domain 不依赖具体 Provider SDK、Token 格式或平台对象。
- Application Service 是授权的最终裁决边界。Query API Adapter、Streamlit 和未来正式 Web 前端都不能各自实现业务授权。
- Query API Adapter 可以接收服务端已经生成的 AuthContext 并传给 Application Service，但继续负责 HTTP 协议转换，不把具体 SSO 逻辑写入查询接口。
- Streamlit 继续作为 Reference Client，通过 Query API 访问查询能力；它可以展示登录或拒绝状态，但不能把前端状态当作安全边界。
- 未来 API Gateway 可以承担外部认证入口、流量治理或审计传输，但 Gateway 产品不是本 Feature 的 Domain 概念；接入 Gateway 不能移除 Application Service 的确定性授权检查。

### 2. AuthContext Contract

业务核心只接收以下规范化身份字段：

~~~text
subject_id
identity_provider
~~~

Contract 约束：

- subject_id 是外部身份系统中的稳定用户标识。
- identity_provider 标识生成该身份的 Provider 或 Adapter。
- 原始 Access Token、Refresh Token、密码和其他 Secret 不进入 Domain 或 Online Query 核心。
- 原始 claims 不直接参与业务授权；Adapter 负责验证、清洗和规范化身份信息。
- role、group、department、region 和 tenant 不属于 V1 的授权决策字段。
- request_id、时间戳和审计信息属于服务端请求 / 审计上下文，不由客户端身份字段提供。
- 客户端请求体不得提交或覆盖 subject_id、identity_provider、角色、群组或数据范围。
- Demo/Test 身份只能由服务端在显式非生产配置中生成，客户端不能通过请求参数切换 Provider。

### 3. Authentication and authorization flow

在线查询请求遵循以下顺序：

~~~text
HTTP / Streamlit request
  → server-side identity Adapter / Middleware
  → AuthContext
  → AuthorizationPolicyStore
  → deterministic authorization decision
  → AuditSink
  → Online Query Application Service
  → Retrieval / LLM / SQL Guard / PostgreSQL
~~~

约束：

- 没有有效身份时，不生成可用于业务查询的 AuthContext。
- 未通过身份认证或数据授权的请求，不得进入 LLM、Online Retrieval、SQL Guard 或 PostgreSQL。
- 授权判断不能由 LLM、用户问题、模型生成的表名或 SQL 片段决定。
- 授权检查必须先于检索和上下文组装，不能先检索全库再在末尾过滤。
- 已授权请求仍然必须经过现有 Semantic、SQL Guard 和只读数据库执行边界；身份授权不替代 SQL 安全校验。

### 4. Authorization resource and policy

V1 只定义一项授权能力：

~~~text
resource = mart_sales
action   = query
mode     = read_only
~~~

授权规则：

- 只有显式授权的 subject_id 可以执行该资源和动作。
- 认证指标、维度、关系和 SQL 允许范围继续由当前已发布 Semantic / Structure / Relationship Graph 与 SQL Guard 决定。
- 其他数据集、Schema、未发布字段、任意 SQL、写入、更新和删除操作全部默认拒绝。
- 不引入部门、区域、tenant 或行级隔离规则。
- 不允许 LLM 临时扩大授权资源或生成新的数据范围。

AuthorizationPolicyStore 负责提供静态授权策略；策略文件由部署环境注入，仓库只保留安全的示例模板，真实用户标识不进入 Git。V1 不建设权限管理 UI、账号中心或权限数据库。

### 5. Authorization decision and error behavior

授权失败必须使用确定性的服务错误边界：

- 没有身份、身份无效或身份校验失败：HTTP 401 Unauthorized。
- 身份有效但没有 mart_sales 查询权限：HTTP 403 Forbidden。
- Identity Provider、策略存储或关键认证配置不可用：Fail Closed（失败关闭），HTTP 503 或统一的服务错误。
- 上述错误都必须在 LLM、Retrieval、SQL 和 PostgreSQL 之前返回。
- HTTP 响应继续使用现有受控错误响应形状，至少包含 request_id、面向调用方的 error_code 和有限的 error_message。
- 内部策略版本、详细拒绝原因和基础设施故障信息不直接暴露给客户端，只通过受控审计 / 追踪信息关联。

### 6. Authorization audit

每次认证授权决策都生成最小结构化审计事件，至少包含：

~~~text
request_id
subject_id
identity_provider
action
resource
decision
reason_code
policy_version
timestamp
~~~

审计约束：

- allow 和 deny 都必须记录。
- 不记录 Access Token、Refresh Token、密码或其他 Secret。
- 不记录原始用户问题、完整 SQL、查询结果或不必要的个人敏感信息。
- V1 只提供 AuditSink Contract 和可测试的结构化输出；不建设独立审计中心、审计查询 UI 或报表系统。

### 7. Environment and Provider boundary

- 生产、开发和测试必须显式选择身份 Provider / Adapter。
- 生产环境启用 Demo/Test Provider 时，系统必须在启动阶段或请求阶段拒绝，而不能静默回退。
- 开发 / 测试环境可以使用 Demo/Test Provider 验证授权流程。
- 当前不选择 Feishu、GitHub 或其他具体企业 SSO，也不创建自建 SSO 容器。
- 未来具体 Provider 接入应通过新的 Adapter 完成，不修改 AuthContext、AuthorizationPolicy 和 Online Query 业务核心。

### 8. Testing seam

最高测试 Seam（接缝）为 Application-level query entry 与其注入的 Identity Provider Adapter、AuthorizationPolicyStore、AuditSink 和下游查询依赖。该 Seam 可以同时观察授权结果、调用顺序、拒绝时的下游调用抑制和审计事件。

Query API Adapter 保留针对 HTTP 状态码、错误响应和客户端不可伪造身份字段的边界测试；Streamlit 只验证它调用 Query API、正确展示受控失败，不复制授权规则。

## Testing Decisions

### Software Test

必须验证以下可观察行为：

1. 已授权 subject_id 使用正确 identity_provider 查询 mart_sales 时，授权允许并进入正式 Online Query 链路。
2. 缺少身份、身份无效或身份过期时返回 401，且不调用 LLM、Retrieval、SQL Guard 或数据库执行器。
3. 身份有效但未命中授权策略时返回 403，且不调用任何查询下游。
4. Identity Provider、策略存储或关键认证配置不可用时 Fail Closed，返回 503 或统一服务错误，且不执行查询。
5. 客户端提交伪造的 subject_id、Provider、角色或数据范围时，不能改变服务端生成的 AuthContext。
6. mart_sales:query:read_only 之外的资源、动作、Schema、未发布字段和写操作均被拒绝。
7. 允许和拒绝决策都生成审计事件，事件字段完整且不包含 Token、原始问题、完整 SQL 或查询结果。
8. 生产配置启用 Demo/Test Provider 时被拒绝；开发 / 测试配置显式启用时可以验证允许和拒绝路径。
9. Query API 只把服务端身份上下文传给同一个 Application Service；Streamlit 不直接调用 LLM、SQL Guard 或数据库。
10. 健康检查等不执行用户数据查询的运维端点不因本 Feature 被意外接入用户查询授权链路；其最终暴露策略按部署边界另行确认。

### AI Evaluation

- 本 Feature 不改变指标定义、Retrieval、Prompt、SQL 生成或 SQL Guard 的业务行为，因此不新增 AI 评测目标。
- 既有 Online Query / Evaluation 回归路径应在显式测试身份上下文下保持可运行。
- 不使用 Demo/Test Provider 的成功结果证明真实企业 SSO 已集成，也不把本 Feature 宣称为企业身份平台验收。

### Business Acceptance

正向场景：

1. 已授权用户查询认证的 mart_sales 指标，得到现有只读查询结果。
2. Streamlit 通过 Query API 发起相同查询，并复用服务端的授权决策。
3. 开发 / 测试环境显式启用 Demo/Test Provider，能够演示授权允许和拒绝。

负向场景：

1. 未登录调用 Query API。
2. 已登录但不在白名单中的用户调用 Query API。
3. 客户端伪造其他用户的 subject_id。
4. 查询其他 Schema、未发布字段或写操作。
5. Provider 或策略存储不可用。
6. 生产配置尝试使用 Demo/Test Provider。

业务验收必须观察：

- 返回正确的 401、403 或 503 边界。
- 拒绝请求没有 LLM、Retrieval、SQL 或数据库副作用。
- 审计事件能够关联 request_id，但没有 Secret 或敏感查询内容。
- 合法查询仍然经过原有 Semantic、SQL Guard 和 PostgreSQL 只读链路。

## Out of Scope

- Feishu、GitHub、Microsoft Entra ID、Keycloak 或其他具体企业 SSO 的生产接入。
- 自建 ChatBI SSO、账号中心、密码体系或身份平台容器。
- 正式 React、Next.js、Vue 或其他 Web 前端重写。
- Streamlit 的第二套认证授权逻辑；Streamlit 只作为 Reference Client。
- 权限管理 UI、用户权限数据库、用户生命周期管理和管理员后台。
- RBAC、角色、群组、部门、区域、tenant 或行级数据隔离。
- 多数据集、多 Schema、多租户和写操作。
- 独立审计数据库、审计中心、审计查询 UI 和复杂报表。
- API Gateway、限流、生产部署、Secret 管理、TLS、负载和集群治理的完整建设。
- 修改指标、Semantic、Retrieval、Prompt、LLM、SQL Guard 或数据库业务规则。
- 多轮对话、复杂分析 Agent、SQL 自动修复和其他后续路线能力。
- 创建外部 Issue、Ticket、PR 或部署到真实生产环境。

## Further Notes

- 当前 docs/architecture.md 和 docs/product-scope.md 仍将登录、审计和正式前端列为未来能力；本 Spec 是对已确认新 Feature 的规划 Contract，不在 to-spec 阶段直接改写这些事实文档。
- 本 Feature 会扩展当前 Query API / Application 边界：现有请求只包含 question，后续需要由服务端认证链路补充可信 AuthContext，而不是让客户端把身份字段放入请求体。
- Ticket 02 已固定最小静态策略文件格式为 JSON object：`policy_version` 字符串和 `allowed_subjects` 字符串数组；策略挂载方式、热更新方式和策略版本发布流程仍未确认，不能因此引入权限管理平台。
- AuditSink 不可用时是否阻断已授权查询，当前对话未确认；实现前必须选择 Fail Closed 或受控降级策略，并记录安全取舍。
- /health 等运维端点是否由外部 Gateway 保护，不属于用户数据查询授权 Contract；本 Spec 只要求它们不能成为用户查询授权的旁路。
- 真实企业 IdP、正式 Web 前端和 RBAC 应根据实际部署环境和用户规模另建 Feature，不应提前写入当前核心 Contract。
- 本 Spec 仍是待确认草稿。用户确认后，下一步才进入 to-tickets；不自动创建 Ticket 或开始实现。

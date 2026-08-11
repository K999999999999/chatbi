```
# Platform Integration（平台集成规格）

> **Status（状态）**：Design Baseline（设计基线）  
> **Scope（范围）**：Enterprise AI Platform（企业 AI 平台） ↔ ChatBI Domain AI Engine（ChatBI 领域 AI 引擎）  
> **API Contract Source of Truth（接口契约事实源）**：TypeSpec（`main.tsp` / `models.tsp` / `operations.tsp`）  
> **Generated API Artifact（生成接口产物）**：`generated/openapi.{version}.yaml`

---

# 1. Purpose（目的）

本文档定义 Enterprise AI Platform（企业 AI 平台）与 ChatBI 之间的集成语义和责任边界。

本文档负责说明：

- Platform 与 ChatBI 各自负责什么
- Authentication（身份认证）与 Domain Authorization（领域授权）如何分工
- Product Conversation（产品会话）与 Domain State（领域状态）如何分工
- 一次 Run（执行实例）代表什么
- Result（结果）由谁负责
- Platform 与 ChatBI 如何处理连续对话和 Clarification（澄清）
- 什么时候直接对接，什么时候需要 Adapter（适配器）
- 企业已有统一平台规范时如何处理

具体：

- Endpoint（端点）
- HTTP Method（请求方法）
- Header（请求头）
- Parameter（参数）
- Request / Response Schema（请求 / 响应结构）
- Authentication Scheme（认证方式）
- Error Schema（错误结构）
- HTTP Status（HTTP 状态码）
- Streaming Protocol（流式协议）
- API Version（接口版本）

统一由 TypeSpec API Contract（TypeSpec 接口契约）定义：

```text
main.tsp
models.tsp
operations.tsp
```

`generated/openapi.{version}.yaml` 由 TypeSpec 自动生成，不单独维护。

------

# 2. Integration Positioning（集成定位）

ChatBI 是：

> **Domain AI Engine（领域 AI 引擎）**

不是完整 Enterprise AI Platform（企业 AI 平台）。

基本关系：

```
Enterprise AI Platform
        │
        ▼
Platform Integration Contract
        │
        ▼
ChatBI Domain AI Engine
        │
        ▼
Certified Business Data
```

核心原则：

> Platform 负责企业通用平台能力。

> ChatBI 负责经营数据领域能力和领域正确性。

------

# 3. Responsibility Boundary（责任边界）

## 3.1 Platform Responsibility（平台责任）

Platform 负责通用平台能力，包括：

- Authentication（身份认证）
- 用户和组织体系
- Platform Permission（平台权限）
- Product Conversation（产品会话）
- Chat UI（聊天界面）
- Model Gateway（模型网关）
- API Gateway（接口网关）
- Rate Limit / Quota（限流 / 配额）
- Platform Observability（平台可观测）
- Deployment / Scaling（部署 / 扩缩容）
- Secret Management（密钥管理）
- CI/CD（持续集成 / 持续交付）

------

## 3.2 ChatBI Responsibility（ChatBI 责任）

ChatBI 负责：

- Natural Language Query（自然语言查询）
- Business Analysis（经营分析）
- Business Semantics（业务语义）
- Domain Authorization（领域授权）
- Data Scope（数据范围）
- Query Safety（查询安全）
- Domain State（领域状态）
- Query Result（查询结果）
- Evidence（证据）
- Business Evaluation（业务评估）

------

# 4. Authentication and Authorization（认证与授权）

必须保持：

```
Authentication
（身份认证）

        ≠

Domain Authorization
（领域授权）
```

标准关系：

```
Enterprise Identity System
        ↓
Platform Authentication
        ↓
Authenticated Principal
        ↓
ChatBI Domain Authorization
        ↓
Authorized Data Scope
        ↓
Business Execution
```

Platform 负责确认：

> **这个用户是谁。**

ChatBI 负责判断：

> **这个用户在当前业务领域中可以访问什么。**

Platform Role / Attribute（平台角色 / 属性）可以作为 ChatBI 授权输入。

但：

> Platform Role 不直接等于最终 Data Scope（数据范围）。

最终领域授权必须由 ChatBI 或企业正式 Authorization Service（授权服务）确定。

## 4.1 Trust Boundary（信任边界）

通过 Platform Integration Contract（平台集成契约）传入的：

- Principal（主体）
- Role（角色）
- Attribute（属性）
- Tenant（租户）

必须来自受信任的 Enterprise AI Platform（企业 AI 平台）。

ChatBI：

> 不得把终端用户自行声明的身份、角色或权限信息直接作为可信授权依据。

稳定关系：

```
Enterprise Identity System
        ↓
Trusted Platform
        ↓
Authenticated Principal Context
        ↓
ChatBI Domain Authorization
        ↓
Authorized Data Scope
```

------

# 5. Product Conversation and Domain State（产品会话与领域状态）

必须保持：

```
Product Conversation
（产品会话）

        ≠

Domain State
（领域状态）
```

## 5.1 Product Conversation（产品会话）

由 Platform 负责，包括：

- Conversation（会话）
- Message（消息）
- Message History（消息历史）
- 会话生命周期
- UI 展示

------

## 5.2 Domain State（领域状态）

由 ChatBI 负责其业务含义。

可能包括：

- 上一轮查询语义
- 上一轮结果引用
- Pending Clarification（待澄清状态）
- 当前分析状态
- 当前业务上下文

具体保存内容由 Feature Spec（功能规格）定义。

------

## 5.3 State Reference（状态引用）

ChatBI 可以向 Platform 返回 Opaque State Reference（不透明状态引用）。

关系：

```
ChatBI
生成 Domain State
        ↓
State Reference
        ↓
Platform 保存
        ↓
后续请求原样回传
        ↓
ChatBI 恢复 Domain State
```

Platform：

> 不解析 ChatBI 内部 Domain State。

ChatBI：

> 使用状态引用前必须重新执行必要的身份和权限校验。

------

# 6. Run Semantics（执行实例语义）

Platform 每次调用 ChatBI 完成一个业务任务，视为一次：

> **Run（执行实例）**

Run 表示：

> 一次完整的 ChatBI 业务执行。

例如：

- 一次 Natural Language Query（自然语言查询）
- 一次 Business Analysis（经营分析）
- 一次需要 Clarification（澄清）的业务执行

Run 不等于：

- 一次 LLM Call（模型调用）
- 一条 SQL
- 一次 Retrieval（检索）
- 一个 LangGraph Node（图节点）
- 一个内部 Module（模块）调用

这些属于 ChatBI 内部实现。

------

# 7. Run Outcome（执行结果）

一次 Run 最终可以形成以下 Business Outcome（业务结果）：

```
Query Result
Analysis Result
Clarification
Unsupported Request
```

## 7.1 Query Result（查询结果）

表示：

> Natural Language Query 已得到可信业务数据结果。

## 7.2 Analysis Result（分析结果）

表示：

> Business Analysis 已基于可信数据得到分析结果。

## 7.3 Clarification（澄清）

表示：

> 当前信息不足以唯一确定业务语义，需要用户补充信息。

## 7.4 Unsupported Request（不支持请求）

表示：

> 当前请求超出 ChatBI 已支持的 Product / Domain（产品 / 领域）范围。

------

# 8. Clarification（澄清协作）

当业务语义无法唯一确定时：

> ChatBI 不应自行猜测。

标准关系：

```
Platform
        ↓
User Request
        ↓
ChatBI Run
        ↓
Requires Clarification
        ↓
Platform 展示问题
        ↓
User 补充信息
        ↓
New Run
```

Platform 负责：

- 展示澄清问题
- 获取用户回答
- 再次调用 ChatBI

ChatBI 负责：

- 判断是否需要澄清
- 保存必要 Domain State
- 根据补充信息继续业务任务

Platform 不需要理解 ChatBI 内部 Workflow State（工作流状态）。

------

# 9. Result and Evidence（结果与证据）

ChatBI 对业务结果的：

- Business Meaning（业务含义）
- Correctness（正确性）
- Data Scope（数据范围）
- Evidence（证据）
- Traceability（可追溯性）

负责。

Platform 负责：

- 展示结果
- UI 交互
- 产品级消息呈现

稳定关系：

```
Business Question
        ↓
Trusted Query
        ↓
Query Result
        ↓
Evidence
        ↓
Business Analysis
```

Business Analysis：

> 必须建立在可信业务数据结果上。

不得建立独立绕过 Trusted Query（可信查询）的数据访问路径。

------

# 10. Business Outcome and System Error（业务结果与系统错误）

必须区分：

```
Business Outcome
（业务结果）

        ≠

System Error
（系统错误）
```

以下属于正常 Business Outcome：

- 查询成功
- 查询结果为空
- 需要澄清
- 请求超出当前业务领域
- 正常分析结果

以下属于 System Error：

- 请求协议错误
- Authentication Failure（认证失败）
- Authorization Failure（授权失败）
- 内部程序异常
- 数据源不可用
- 模型服务不可用
- Timeout（超时）
- Runtime Failure（运行故障）

正常业务结果不得作为 Internal Server Error（内部服务器错误）处理。

具体 Error Contract（错误契约）由 TypeSpec API Contract（TypeSpec 接口契约）定义。

OpenAPI 仅作为 TypeSpec 生成的接口交换产物。

------

# 11. Execution Modes（执行方式）

当前 V1 Platform Integration Contract（平台集成契约）支持：

- Blocking（阻塞）
- SSE Streaming（SSE 流式）

## 11.1 Blocking（阻塞）

Platform 等待 Run 完成后获取最终 Run Outcome（执行结果）。

Blocking：

> 不改变 ChatBI 的领域授权、查询安全和业务正确性规则。

------

## 11.2 SSE Streaming（SSE 流式）

Platform 通过 SSE（Server-Sent Events，服务器发送事件）接收 Run 执行期间允许提前展示的流式内容以及最终结果。

Streaming：

> 只是结果传输方式，不改变业务正确性和安全规则。

Streaming 必须继续遵守：

- Domain Authorization（领域授权）
- Data Scope（数据范围）
- Query Safety（查询安全）
- Business Correctness（业务正确性）

未经授权或未经必要校验的数据不得提前输出。

具体 SSE Event（SSE 事件）、Terminal Event（终止事件）及传输结构由 TypeSpec API Contract 定义。

------

## 11.3 Async（异步）

当前 V1：

> **不提供 Async API（异步接口）。**

未来只有出现真实长任务需求时，再通过新的 API Contract Version（接口契约版本）演进加入。

------

# 12. Query Safety（查询安全）

LLM 可以：

- 理解问题
- 推理
- 生成 Candidate（候选）
- 辅助分析

LLM 不得最终决定：

- Domain Permission（领域权限）
- Data Scope（数据范围）
- Query Safety（查询安全）
- 最终数据执行权限

必须保持：

```
Model Candidate
        ↓
Deterministic Validation
（确定性校验）
        ↓
Allowed / Rejected
```

原则：

> **Model proposes, program decides.**

------

# 13. Integration Strategy（集成策略）

## 13.1 Contract Alignment First（优先契约统一）

如果企业已有正式 Platform Integration Standard（平台接入规范）：

> 优先遵守企业统一规范。

正常情况：

```
Company Platform
        ↓
ChatBI Public Contract
        ↓
ChatBI
```

不增加无意义 Adapter（适配器）。

------

## 13.2 Adapter When Required（必要时适配）

只有以下情况才增加 Adapter：

- 外部协议无法修改
- ChatBI 已存在稳定 Public Contract（公共契约）
- 同时支持多个不同 Platform
- 接入 Legacy System（遗留系统）
- 系统迁移或重构
- 外部模型与 ChatBI 模型存在真实差异

关系：

```
External Platform
        ↓
Adapter
        ↓
ChatBI Public Contract
        ↓
ChatBI
```

------

## 13.3 Anti-Corruption Layer（防腐层）

当差异已经涉及两个系统的语义模型，而不只是字段名称不同，可以使用：

> **Anti-Corruption Layer（防腐层）**

用于隔离外部系统模型，防止其直接侵入 ChatBI Core（ChatBI 核心）。

Adapter 是实现 Anti-Corruption Layer 的常见方式之一。

------

## 13.4 Contract Correction（契约修正）

Adapter 不用于保护错误设计。

如果 ChatBI Contract 本身设计错误：

> 应修改 Contract，而不是继续增加 Adapter。

原则：

> **Contract Alignment First, Adapter When Required.**

------

# 14. Enterprise Adoption（企业接入）

ChatBI 进入具体企业时：

```
Company Platform Standard
        ↓
Gap Analysis
（差异分析）
        ↓
Contract Alignment
（契约对齐）
        ↓
Direct Integration
或
Adapter / Anti-Corruption Layer
```

Gap Analysis 至少检查：

- Authentication（认证）
- Identity（身份）
- Authorization（授权）
- API Version（接口版本）
- Error Model（错误模型）
- Trace（链路追踪）
- Streaming（流式协议）
- Timeout（超时）
- Idempotency（幂等）

如果企业规范和 ChatBI Contract 可以直接统一：

> 直接对接。

如果存在真实协议或语义差异：

> 在系统边界进行转换。

ChatBI Core 不因外部 Platform 改变而重写领域逻辑。

------

# 15. API Contract Boundary（接口契约边界）

Platform Integration 的正式 API Contract Source of Truth（接口契约事实源）是：

> **TypeSpec**

当前正式契约由：

```
main.tsp
models.tsp
operations.tsp
```

共同组成。

## 15.1 main.tsp

负责全局 Contract（契约）定义，包括：

```
Service
Authentication
Versioning
```

即：

- Service（服务）
- Authentication Scheme（认证方式）
- API Versioning（接口版本管理）

------

## 15.2 models.tsp

负责 Data Contract（数据契约），包括：

```
Request
Response
Result
Error
State
SSE Event
```

即：

- Request Schema（请求结构）
- Response Schema（响应结构）
- Business Outcome（业务结果）
- Error Schema（错误结构）
- Domain State Reference（领域状态引用）
- SSE Event（SSE 事件）

------

## 15.3 operations.tsp

负责 Operation Contract（操作契约），包括：

```
Endpoint
HTTP Method
Parameter
HTTP Status
Blocking
SSE Streaming
```

即：

- Endpoint（端点）
- HTTP Method（请求方法）
- Parameter（参数）
- HTTP Status（HTTP 状态码）
- Blocking Operation（阻塞操作）
- SSE Streaming Operation（SSE 流式操作）

------

## 15.4 Compilation and Generated Artifact（编译与生成产物）

`tspconfig.yaml` 定义：

- Contract Compilation（契约编译）
- OpenAPI Emitter（OpenAPI 生成器）
- OpenAPI Version（OpenAPI 规范版本）
- Generated Output（生成目录）

标准关系：

```
TypeSpec
        ↓
TypeSpec Compiler
        ↓
OpenAPI 3.2
        ↓
generated/openapi.{version}.yaml
```

`generated/openapi.{version}.yaml` 是：

> **Generated Artifact（生成产物）**

不是 API Contract Source of Truth。

禁止：

> 直接手工修改生成的 OpenAPI。

API Contract 发生变化时：

```
修改 TypeSpec
        ↓
Compile / Validate
        ↓
重新生成 OpenAPI
```

------



### SSE OpenAPI 3.2

当前 V1 生成 OpenAPI 3.2。

SSE（Server-Sent Events，服务器发送事件）
由 TypeSpec Source Contract（TypeSpec 源契约）定义。

OpenAPI 3.2 通过 `itemSchema` 表达
Streaming Media Type（流式媒体类型）中每个数据项的 Schema。

完整 SSE Event Contract 包括：

- started
- delta
- completed
- failed

其中：

- completed
- failed

为 Terminal Event（终止事件）。

OpenAPI 为 TypeSpec 自动生成产物，
不得单独手工维护。

不要在本 SPEC 中重复具体生成的 YAML Schema；
具体机器结构仍以 TypeSpec 为 Source of Truth。

### SSE Generated Artifact Limitation（SSE 生成产物限制）

当前 V1 使用 TypeSpec 1.14.0 生成 OpenAPI 3.2。

TypeSpec Source Contract（TypeSpec 源契约）完整定义：

- started
- delta
- completed
- failed

其中 completed 与 failed 为 Terminal Event（终止事件），
并分别携带最终 RunResponse 与 ErrorResponse。

当前 OpenAPI emitter（OpenAPI 生成器）
对携带 Model Payload（模型载荷）的 Terminal Event
存在生成信息不完整的限制。

因此：

> SSE Event Contract 以 TypeSpec Source Contract 为准。

不得为了适配当前 emitter 而改变业务事件语义。

未来只有在下游工具明确依赖完整 Terminal Event Schema 时，
再评估升级 TypeSpec 稳定版本或其他生成方案。

## 15.5 Source of Truth（事实源）

长期保持：

```
SPEC.md
        ↓
Integration Semantics
（集成语义事实源）


main.tsp
models.tsp
operations.tsp
        ↓
Formal API Contract
（正式 API 契约事实源）


generated/openapi.{version}.yaml
        ↓
Generated Interchange Artifact
（生成的接口交换产物）
```

本 `SPEC.md` 不重复维护：

- Endpoint 的精确结构
- HTTP Method
- 字段类型
- HTTP Status
- SSE Event 结构
- Authentication Scheme 细节
- API Version 参数结构

这些内容以 TypeSpec 为准。

实现必须同时满足：

```
Integration Semantics
        +
TypeSpec API Contract
```

------

# 16. Core Principles（核心原则）

必须长期保持：

> **Platform owns generic platform capabilities; ChatBI owns domain correctness.**

> **Authentication ≠ Domain Authorization.**

> **Product Conversation ≠ Domain State.**

> **Trusted Data Before Analysis.**

> **Model proposes, program decides.**

> **Contract Alignment First, Adapter When Required.**

> **Platform-specific models must not penetrate ChatBI Core.**

> **SPEC defines semantics; TypeSpec defines the formal API contract; OpenAPI is a generated artifact.**

即：

> **SPEC 定义集成语义；TypeSpec 定义正式接口契约；OpenAPI 是生成产物。**
>
> ```
> 
> ```

------

# Platform Integration Spec

# ChatBI 平台集成规格

> **Status（状态）：** Design Baseline（设计基线）
> **Scope（范围）：** Enterprise AI Platform（企业 AI 平台） ↔ ChatBI Domain AI Engine（ChatBI 领域 AI 引擎）
> **System Architecture Reference（系统架构引用）：** `../ARCHITECTURE.md`
> **API Contract Source of Truth（接口契约事实源）：** TypeSpec
> **TypeSpec Sources（TypeSpec 源文件）：** `main.tsp` / `models.tsp` / `operations.tsp`
> **Generated API Artifact（生成接口产物）：** `generated/openapi.{version}.yaml`

------

# 1. Purpose（目的）

本文档定义 Enterprise AI Platform（企业 AI 平台）与 ChatBI 之间的：

- Integration Semantics（集成语义）；
- Responsibility Boundary（责任边界）；
- Authentication / Authorization Boundary（认证 / 授权边界）；
- Conversation / Domain State Boundary（会话 / 领域状态边界）；
- Run Semantics（执行实例语义）；
- Business Outcome（业务结果）；
- Clarification Collaboration（澄清协作）；
- Result / Evidence Ownership（结果 / 证据所有权）；
- Error Boundary（错误边界）；
- Execution Mode（执行方式）；
- Integration Strategy（集成策略）；
- API Contract Source of Truth（接口契约事实源）。

本文档定义：

> **Platform 与 ChatBI 如何协作。**

不定义具体：

- Endpoint（端点）；
- HTTP Method（请求方法）；
- Header（请求头）；
- Parameter（参数）；
- Request / Response Schema（请求 / 响应结构）；
- Field Type（字段类型）；
- Authentication Scheme（认证协议细节）；
- HTTP Status（HTTP 状态码）；
- SSE Event Schema（SSE 事件结构）；
- API Version Parameter（接口版本参数）。

这些由：

> **TypeSpec API Contract（TypeSpec 接口契约）**

定义。

原则：

> **SPEC defines integration semantics; TypeSpec defines the formal API contract.**
> **规格定义集成语义，TypeSpec 定义正式接口契约。**

------

# 2. Integration Positioning（集成定位）

ChatBI 是：

> **Domain AI Engine（领域 AI 引擎）。**

不是：

> Enterprise AI Platform（企业 AI 平台）。

稳定关系：

```
Enterprise AI Platform
（企业 AI 平台）

        ↓

Platform Integration Contract
（平台集成契约）

        ↓

ChatBI Domain AI Engine
（ChatBI 领域 AI 引擎）

        ↓

Certified Business Data
（认证业务数据）
```

责任原则：

> **Platform owns generic platform capabilities.**
> **平台负责企业通用平台能力。**

> **ChatBI owns domain capabilities and domain correctness.**
> **ChatBI 负责领域能力和领域正确性。**

具体系统定位和总体责任边界：

> 继承 `ARCHITECTURE.md（系统架构）`。

本规格不重复定义完整系统架构。

------

# 3. Responsibility Boundary（责任边界）

## 3.1 Platform Responsibility（平台责任）

Platform（平台）负责通用平台能力，主要包括：

- Authentication（身份认证）；
- User / Organization（用户 / 组织体系）；
- Platform Permission（平台权限）；
- Product Conversation（产品会话）；
- Chat UI（聊天界面）；
- Model Gateway（模型网关）；
- API Gateway（接口网关）；
- Rate Limit / Quota（限流 / 配额）；
- Platform Observability（平台可观测性）；
- Deployment / Scaling（部署 / 扩缩容）；
- Secret Management（密钥管理）；
- CI/CD（持续集成 / 持续交付）。

------

## 3.2 ChatBI Responsibility（ChatBI 责任）

ChatBI 负责领域能力和领域正确性，主要包括：

- Natural Language Query（自然语言查询）；
- Business Analysis（经营分析）；
- Business Semantics（业务语义）；
- Domain Authorization（领域授权）；
- Data Scope（数据范围）；
- Query Safety（查询安全）；
- Domain State Semantics（领域状态语义）；
- QueryResult（查询结果）；
- AnalysisResult（分析结果）；
- Evidence（证据）；
- Business Evaluation（业务评估）。

原则：

> **Platform capability（平台能力）不得替代 ChatBI 的 Domain Correctness（领域正确性）。**

------

# 4. Authentication & Authorization（认证与授权）

必须保持：

```
Authentication
（身份认证）

        ≠

Domain Authorization
（领域授权）
```

稳定流程：

```
Enterprise Identity System
（企业身份系统）

        ↓

Platform Authentication
（平台身份认证）

        ↓

Authenticated Principal
（已认证主体）

        ↓

ChatBI Domain Authorization
（ChatBI 领域授权）

        ↓

Authorized Data Scope
（授权数据范围）

        ↓

Business Execution
（业务执行）
```

Platform（平台）负责确认：

> **用户是谁。**

ChatBI 负责确定：

> **该用户在当前业务领域能够访问什么。**

Platform Role / Attribute（平台角色 / 属性）：

> 可以作为 Domain Authorization（领域授权）的输入。

但：

> **Platform Role ≠ Final Data Scope（平台角色不等于最终数据范围）。**

最终 Domain Authorization（领域授权）必须由：

- ChatBI；

或：

- 企业正式 Authorization Service（授权服务）

确定。

------

## 4.1 Trust Boundary（信任边界）

通过 Platform Integration Contract（平台集成契约）传递的：

- Principal（主体）；
- Role（角色）；
- Attribute（属性）；
- Tenant（租户）；

必须来自：

> **Trusted Enterprise Platform（受信任企业平台）。**

ChatBI 不得把终端用户自行声明的：

- Identity（身份）；
- Role（角色）；
- Permission（权限）

直接作为可信授权事实。

稳定关系：

```
Enterprise Identity System
（企业身份系统）

        ↓

Trusted Platform
（受信任平台）

        ↓

Authenticated Principal Context
（已认证主体上下文）

        ↓

ChatBI Domain Authorization
（领域授权）

        ↓

Authorized Data Scope
（授权数据范围）
```

------

# 5. Product Conversation & Domain State（产品会话与领域状态）

必须保持：

```
Product Conversation
（产品会话）

        ≠

Domain State
（领域状态）
```

------

## 5.1 Product Conversation（产品会话）

Platform（平台）拥有：

- Conversation（会话）；
- Message（消息）；
- Message History（消息历史）；
- 产品级会话生命周期；
- UI Presentation（界面展示）。

------

## 5.2 Domain State（领域状态）

ChatBI 拥有：

> **完成领域业务任务所需状态的业务含义。**

可以包括：

- Previous Query Semantics（上一轮查询语义）；
- Previous Result Reference（上一轮结果引用）；
- Pending Clarification（待澄清状态）；
- Current Analysis State（当前分析状态）；
- Current Business Context（当前业务上下文）。

具体保存哪些 Domain State（领域状态）：

> 由对应 Feature Spec（功能规格）定义。

------

## 5.3 State Reference（状态引用）

ChatBI 可以向 Platform（平台）返回：

> **Opaque State Reference（不透明状态引用）。**

稳定关系：

```
ChatBI
生成 Domain State
（领域状态）

        ↓

Opaque State Reference
（不透明状态引用）

        ↓

Platform
保存引用

        ↓

后续请求
原样回传引用

        ↓

ChatBI
恢复 Domain State
```

Platform（平台）：

> 不解析或修改 ChatBI 内部 Domain State（领域状态）。

ChatBI：

> 不信任 State Reference（状态引用）本身携带的历史权限。

每次使用 State Reference（状态引用）恢复业务状态时：

> 必须重新执行当前请求所需要的 Authentication / Authorization Validation（认证 / 授权校验）。

原则：

> **State continuity does not bypass security validation.**
> **状态连续性不得绕过安全校验。**

------

# 6. Run Semantics（执行实例语义）

Platform（平台）每次调用 ChatBI 完成一个完整业务任务，称为：

> **Run（执行实例）。**

Run（执行实例）表示：

> **一次完整 ChatBI 业务执行。**

例如：

- 一次 Natural Language Query（自然语言查询）；
- 一次 Business Analysis（经营分析）；
- 一次最终产生 Clarification（澄清）的业务执行。

Run 不等于：

- LLM Call（大语言模型调用）；
- SQL Execution（单次 SQL 执行）；
- Retrieval（单次检索）；
- LangGraph Node（LangGraph 节点）；
- Module Invocation（模块调用）。

这些属于：

> ChatBI Internal Implementation（ChatBI 内部实现）。

Platform（平台）：

> 只依赖稳定 Run Contract（执行实例契约）。

不依赖 ChatBI 内部工作流结构。

------

# 7. Run Outcome（执行结果）

一次成功进入 ChatBI 业务执行语义的 Run（执行实例）最终可以形成以下 Business Outcome（业务结果）：

```
Business Outcome
（业务结果）

├── QueryResult
│   （查询结果）
│
├── AnalysisResult
│   （分析结果）
│
├── Clarification
│   （澄清）
│
└── UnsupportedRequest
    （不支持请求）
```

------

## 7.1 QueryResult（查询结果）

表示：

> Natural Language Query（自然语言查询）已经得到可信业务数据结果。

------

## 7.2 AnalysisResult（分析结果）

表示：

> Business Analysis（经营分析）已经基于可信业务数据得到分析结果。

------

## 7.3 Clarification（澄清）

表示：

> 当前业务信息不足以唯一确定业务语义，需要用户补充必要信息。

Clarification（澄清）：

> 是正常 Business Outcome（业务结果）。

不是：

> System Error（系统错误）。

------

## 7.4 UnsupportedRequest（不支持请求）

表示：

> 用户请求已经明确，但超出当前 ChatBI 支持的 Product / Domain（产品 / 领域）范围。

UnsupportedRequest（不支持请求）：

> 是正常 Business Outcome（业务结果）。

不是：

> Internal Failure（内部失败）。

------

# 8. Clarification Collaboration（澄清协作）

当 ChatBI 判断用户业务语义无法唯一确定时：

> **不得自行猜测。**

标准协作：

```
Platform
（平台）

        ↓

User Request
（用户请求）

        ↓

ChatBI Run
（ChatBI 执行）

        ↓

Clarification
（澄清）

        ↓

Platform
展示澄清问题

        ↓

User
补充信息

        ↓

New Run
（新的执行实例）
```

Platform（平台）负责：

- 展示 Clarification Question（澄清问题）；
- 获取 User Response（用户回答）；
- 发起新的 ChatBI Run（执行实例）。

ChatBI 负责：

- 判断是否需要 Clarification（澄清）；
- 产生必要的业务澄清信息；
- 保存必要 Domain State（领域状态）；
- 基于用户补充信息继续业务任务。

Platform（平台）：

> 不需要理解 ChatBI 内部 Workflow State（工作流状态）。

原则：

> **Platform manages the conversation; ChatBI owns clarification semantics.**
> **平台管理产品会话，ChatBI 负责澄清的业务语义。**

------

# 9. Result & Evidence（结果与证据）

ChatBI 对业务结果的以下内容负责：

- Business Meaning（业务含义）；
- Business Correctness（业务正确性）；
- Data Scope（数据范围）；
- Evidence（证据）；
- Traceability（可追溯性）。

Platform（平台）负责：

- Presentation（展示）；
- UI Interaction（界面交互）；
- 产品级消息呈现。

稳定关系：

```
Business Question
（业务问题）

        ↓

Trusted Query
（可信查询）

        ↓

QueryResult
（查询结果）

        ↓

Evidence
（证据）

        ↓

Business Analysis
（经营分析）

        ↓

AnalysisResult
（分析结果）
```

原则：

> **Trusted Data Before Analysis（可信数据先于分析）。**

Business Analysis（经营分析）：

> 不得建立绕过 Trusted Query Capability（可信查询能力）的独立数据访问路径。

------

# 10. Business Outcome & System Error（业务结果与系统错误）

必须区分：

```
Business Outcome
（业务结果）

        ≠

System Error
（系统错误）
```

正常 Business Outcome（业务结果）包括：

- QueryResult（查询结果）；
- Empty Query Result（空查询结果）；
- AnalysisResult（分析结果）；
- Clarification（澄清）；
- UnsupportedRequest（不支持请求）。

System Error / Error Path（系统错误 / 错误路径）包括：

- Protocol / Contract Error（协议 / 契约错误）；
- Authentication Failure（认证失败）；
- Authorization Failure（授权失败）；
- Internal Program Failure（内部程序错误）；
- Data Source Unavailable（数据源不可用）；
- Model Service Unavailable（模型服务不可用）；
- Timeout（超时）；
- Runtime Failure（运行故障）。

原则：

> **正常业务结果不得伪装成 Internal Server Error（内部服务器错误）。**

反之：

> **系统失败也不得伪装成正常 Business Outcome（业务结果）。**

具体：

- Error Schema（错误结构）；
- HTTP Status（HTTP 状态码）；
- Error Code（错误码）

由 TypeSpec API Contract（TypeSpec 接口契约）定义。

------

# 11. Execution Modes（执行方式）

ChatBI Platform Integration V1（平台集成第一版）支持：

```
Execution Mode
（执行方式）

├── Blocking
│   （阻塞）
│
└── SSE Streaming
    （服务器发送事件流式）
```

V1（第一版）：

> **不提供 Async API（异步接口）。**

------

## 11.1 Blocking（阻塞）

Blocking（阻塞）模式：

> Platform 等待当前 Run（执行实例）结束，并获取最终 Run Outcome（执行结果）。

Blocking（阻塞）：

> 只是调用方式。

不得改变：

- Domain Authorization（领域授权）；
- Data Scope（数据范围）；
- Query Safety（查询安全）；
- Business Correctness（业务正确性）。

------

## 11.2 SSE Streaming（SSE 流式）

SSE Streaming（服务器发送事件流式）允许 Platform 在 Run（执行实例）过程中：

> 接收允许提前展示的流式信息，并最终接收 Terminal Outcome（终止结果）。

Streaming（流式）：

> **只是传输方式。**

不得改变：

- Domain Authorization（领域授权）；
- Data Scope（数据范围）；
- Query Safety（查询安全）；
- Business Correctness（业务正确性）。

未经：

- Authorization（授权）；
- Required Validation（必要校验）

的数据：

> 不得因为 Streaming（流式）而提前泄露。

具体：

- SSE Event（SSE 事件）；
- started / delta / completed / failed；
- Terminal Event（终止事件）；
- Event Payload（事件载荷）

由：

> **TypeSpec API Contract（TypeSpec 接口契约）**

定义。

原则：

> **Transport mode must not change business semantics.**
> **传输方式不得改变业务语义。**

------

## 11.3 Async（异步）

V1（第一版）：

> **No Async API（不提供异步接口）。**

未来只有出现真实 Long-Running Task（长任务）需求时：

> 通过新的 API Contract Version（接口契约版本）演进。

不得在当前 V1 Contract（第一版契约）中提前设计未使用的异步任务体系。

------

# 12. Query Safety Boundary（查询安全边界）

LLM（大语言模型）可以：

- Understand（理解）；
- Reason（推理）；
- Generate Candidate（生成候选）；
- Assist Analysis（辅助分析）。

但 LLM 不得最终决定：

- Domain Authorization（领域授权）；
- Data Scope（数据范围）；
- Query Safety（查询安全）；
- Final Data Execution Permission（最终数据执行权限）。

稳定关系：

```
Model Candidate
（模型候选）

        ↓

Deterministic Validation
（确定性校验）

        ↓

Allowed / Rejected
（允许 / 拒绝）
```

原则：

> **Model proposes, program decides.**
> **模型提出，程序裁决。**

具体 Query Safety Rule（查询安全规则）：

> 由对应 Feature Architecture / Feature Spec / Module Spec（功能架构 / 功能规格 / 模块规格）定义。

Platform Integration（平台集成）只要求：

> 安全规则在跨平台调用方式变化后仍然成立。

------

# 13. Integration Strategy（集成策略）

总体原则：

> **Contract Alignment First, Adapter When Required.**
> **契约对齐优先，必要时才使用适配器。**

------

## 13.1 Direct Integration（直接集成）

如果 Enterprise Platform Standard（企业平台规范）和 ChatBI Public Contract（ChatBI 公共契约）能够直接对齐：

```
Enterprise Platform
（企业平台）

        ↓

ChatBI Public Contract
（ChatBI 公共契约）

        ↓

ChatBI
```

应：

> **直接集成。**

不得因为“架构看起来更完整”而增加无意义 Adapter（适配器）。

------

## 13.2 Adapter（适配器）

存在真实 Protocol / Contract Difference（协议 / 契约差异）时才增加 Adapter（适配器）。

典型情况：

- External Protocol（外部协议）无法修改；
- ChatBI 已有稳定 Public Contract（公共契约）；
- 同时支持多个不同 Platform（平台）；
- Legacy System Integration（遗留系统集成）；
- System Migration（系统迁移）；
- 外部模型与 ChatBI Public Model（公共模型）存在真实差异。

关系：

```
External Platform
（外部平台）

        ↓

Adapter
（适配器）

        ↓

ChatBI Public Contract
（ChatBI 公共契约）

        ↓

ChatBI Core
（ChatBI 核心）
```

------

## 13.3 Anti-Corruption Layer（防腐层）

当两个系统差异涉及：

> **Semantic Model（语义模型）**

而不只是：

> 字段名称或传输格式

时，可以使用：

> **Anti-Corruption Layer（防腐层）。**

目的：

> 防止 External Platform Model（外部平台模型）直接侵入 ChatBI Core（ChatBI 核心）。

Adapter（适配器）：

> 可以作为 Anti-Corruption Layer（防腐层）的实现方式。

------

## 13.4 Contract Correction（契约修正）

Adapter（适配器）：

> 不用于保护错误 Contract（契约）。

如果 ChatBI Public Contract（公共契约）本身存在设计问题：

> 应修改 Contract。

不得：

```
错误 Contract
        ↓
增加 Adapter
        ↓
继续保护错误设计
```

------

# 14. Enterprise Adoption（企业接入）

ChatBI 接入具体企业时采用：

```
Company Platform Standard
（企业平台标准）

        ↓

Gap Analysis
（差异分析）

        ↓

Contract Alignment
（契约对齐）

        ↓

Direct Integration
（直接集成）

        或

Adapter / Anti-Corruption Layer
（适配器 / 防腐层）
```

Gap Analysis（差异分析）至少检查：

- Authentication（认证）；
- Identity（身份）；
- Authorization（授权）；
- API Version（接口版本）；
- Error Model（错误模型）；
- Trace（链路追踪）；
- Streaming（流式）；
- Timeout（超时）；
- Idempotency（幂等）。

如果双方 Contract（契约）能够统一：

> **直接对接。**

如果存在真实协议或语义差异：

> **在 Integration Boundary（集成边界）转换。**

原则：

> **ChatBI Core（ChatBI 核心）不得因为外部 Platform（平台）变化而重写 Domain Logic（领域逻辑）。**

------

# 15. API Contract Boundary（接口契约边界）

Platform Integration（平台集成）存在三个不同层次的事实源：

```
Platform Integration SPEC.md
        ↓
Integration Semantics
（集成语义）

TypeSpec
        ↓
Formal API Contract
（正式接口契约）

Generated OpenAPI
        ↓
Generated Interchange Artifact
（生成的接口交换产物）
```

必须明确：

> **这三者不是同一个东西。**

------

## 15.1 Integration Semantic Source（集成语义事实源）

`Platform Integration SPEC.md` 定义：

- Responsibility Boundary（责任边界）；
- Authentication / Authorization Semantics（认证 / 授权语义）；
- Conversation / State Ownership（会话 / 状态所有权）；
- Run Semantics（执行语义）；
- Outcome Semantics（结果语义）；
- Clarification Collaboration（澄清协作）；
- Execution Mode Semantics（执行方式语义）；
- Integration Strategy（集成策略）。

即：

> **为什么双方这样协作，以及这些概念分别意味着什么。**

------

## 15.2 Formal API Contract Source（正式接口契约事实源）

正式 Machine-Readable API Contract（机器可读接口契约）使用：

> **TypeSpec。**

当前由：

```
main.tsp
models.tsp
operations.tsp
```

共同组成。

概念职责：

```
main.tsp
→ Service / Authentication / Versioning
  （服务 / 认证 / 版本）

models.tsp
→ Request / Response / Result / Error / State / Event
  （请求 / 响应 / 结果 / 错误 / 状态 / 事件）

operations.tsp
→ Operations / Transport
  （操作 / 传输）
```

具体结构：

> 只在 TypeSpec 中维护。

本 SPEC（规格）不重复定义。

------

## 15.3 Generated API Artifact（生成接口产物）

稳定关系：

```
TypeSpec
（正式接口契约）

        ↓

Compile / Validate
（编译 / 校验）

        ↓

OpenAPI
（开放接口规范）

        ↓

generated/openapi.{version}.yaml
```

Generated OpenAPI（生成的 OpenAPI）：

> **不是 API Contract Source of Truth（接口契约事实源）。**

禁止：

> 手工修改生成 OpenAPI 来代替 TypeSpec 变更。

API Contract（接口契约）变化时：

```
修改 TypeSpec
        ↓
Compile / Validate
（编译 / 校验）
        ↓
重新生成 OpenAPI
```

------

## 15.4 TypeSpec / Generated Artifact Difference（TypeSpec 与生成产物差异）

如果当前 Generator / Emitter（生成器）无法完整表达 TypeSpec Source Contract（TypeSpec 源契约）：

> **TypeSpec Source Contract 仍然是正式机器契约事实源。**

不得为了适配某个 Generated Artifact Limitation（生成产物限制）：

> 反向修改正确的业务集成语义。

具体：

- TypeSpec Version（TypeSpec 版本）；
- OpenAPI Emitter Limitation（OpenAPI 生成器限制）；
- Tool Compatibility（工具兼容性）

属于：

> Engineering / Tooling Concern（工程 / 工具问题）。

除非它们真正改变正式 Integration Contract（集成契约），否则不进入长期集成语义。

------

# 16. Integration Invariants（集成不变量）

以下规则长期保持。

### Invariant 1 — Platform / ChatBI Responsibility Boundary（平台 / ChatBI 责任边界）

> **Platform owns generic platform capabilities; ChatBI owns domain correctness.**

------

### Invariant 2 — Authentication ≠ Domain Authorization（身份认证不等于领域授权）

Platform（平台）确认：

> 用户是谁。

ChatBI 确定：

> 用户能访问什么业务数据。

------

### Invariant 3 — Product Conversation ≠ Domain State（产品会话不等于领域状态）

Platform（平台）拥有 Product Conversation（产品会话）。

ChatBI 拥有 Domain State Semantics（领域状态语义）。

------

### Invariant 4 — State Reference Is Opaque（状态引用不透明）

Platform（平台）：

> 不解析 ChatBI 内部 Domain State（领域状态）。

------

### Invariant 5 — State Does Not Bypass Authorization（状态不得绕过授权）

恢复历史 Domain State（领域状态）：

> 不得跳过当前身份和权限校验。

------

### Invariant 6 — One Run Represents One Business Execution（一次运行代表一次完整业务执行）

Run（执行实例）：

> 不暴露内部 LLM / SQL / Retrieval / Module（模型 / SQL / 检索 / 模块）调用结构。

------

### Invariant 7 — Business Outcome ≠ System Error（业务结果不等于系统错误）

Clarification / UnsupportedRequest（澄清 / 不支持请求）：

> 不得作为系统内部错误处理。

System Failure（系统失败）：

> 不得伪装成正常业务结果。

------

### Invariant 8 — Transport Does Not Change Semantics（传输方式不改变语义）

Blocking / SSE（阻塞 / 流式）：

> 只能改变传输方式。

不得改变：

- Authorization（授权）；
- Safety（安全）；
- Data Scope（数据范围）；
- Business Correctness（业务正确性）。

------

### Invariant 9 — Model Proposes, Program Decides（模型提出，程序裁决）

LLM（大语言模型）：

> 不承担最终权限和安全裁决。

------

### Invariant 10 — Trusted Data Before Analysis（可信数据先于分析）

Business Analysis（经营分析）：

> 建立在可信业务数据结果之上。

------

### Invariant 11 — Contract Alignment First（契约对齐优先）

优先：

> 对齐 Public Contract（公共契约）。

只有存在真实差异时：

> 使用 Adapter / Anti-Corruption Layer（适配器 / 防腐层）。

------

### Invariant 12 — Platform-Specific Model Must Not Penetrate Core（平台私有模型不得侵入核心）

External Platform Private Model（外部平台私有模型）：

> 不得直接成为 ChatBI Core（ChatBI 核心）内部 Domain Contract（领域契约）。

------

### Invariant 13 — SPEC / TypeSpec / OpenAPI Have Different Roles（规格 / TypeSpec / OpenAPI 职责不同）

必须保持：

```
SPEC
→ Integration Semantics
  （集成语义）

TypeSpec
→ Formal API Contract
  （正式接口契约）

OpenAPI
→ Generated Artifact
  （生成产物）
```

------

# 17. Integration Baseline（集成基线）

当前 V1（第一版）稳定关系：

```
Enterprise AI Platform
（企业 AI 平台）

负责：
Authentication
Product Conversation
UI
Model Gateway
API Gateway
Platform Governance

        ↓

Platform Integration Contract
（平台集成契约）

        ↓

ChatBI Domain AI Engine
（ChatBI 领域 AI 引擎）

负责：
Domain Authorization
Business Semantics
Domain State Semantics
Query Safety
QueryResult / AnalysisResult
Evidence
Business Correctness
```

运行语义：

```
Platform Request
（平台请求）

        ↓

ChatBI Run
（一次完整业务执行）

        ↓

Business Outcome

├── QueryResult
├── AnalysisResult
├── Clarification
└── UnsupportedRequest

或

System Error Path
（系统错误路径）
```

调用方式：

```
V1 Execution Mode
（第一版执行方式）

├── Blocking
└── SSE Streaming

Async
→ Not Supported in V1
  （第一版不支持）
```

契约事实源：

```
Platform Integration SPEC
（平台集成规格）
→ Integration Semantics
  （集成语义）

TypeSpec
→ Formal API Contract
  （正式接口契约）

OpenAPI
→ Generated Artifact
  （生成产物）
```

最终原则：

> **Platform 负责企业通用能力，ChatBI 负责领域正确性。**

> **身份认证不等于领域授权。**

> **产品会话不等于领域状态。**

> **一次 Run（执行实例）代表一次完整 ChatBI 业务执行，而不是内部技术步骤。**

> **Business Outcome（业务结果）与 System Error（系统错误）严格分离。**

> **Blocking / SSE（阻塞 / 流式）只能改变传输方式，不能改变业务语义和安全规则。**

> **契约优先对齐，存在真实差异时才使用 Adapter / Anti-Corruption Layer（适配器 / 防腐层）。**

> **Platform Integration SPEC（平台集成规格）定义集成语义，TypeSpec 定义正式接口契约，OpenAPI 是生成产物。**

------


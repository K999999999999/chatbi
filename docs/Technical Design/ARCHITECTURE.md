```
# ChatBI Architecture（系统架构）

> **Status（状态）**：Design Baseline（设计基线）  
> **Scope（范围）**：ChatBI 系统级架构  
> **Architecture Style（架构形态）**：Modular Monolith（模块化单体）  
> **Primary Capabilities（核心能力）**：Natural Language Query（自然语言查询）、Business Analysis（经营分析）

---

# 1. 文档目的

本文档定义 ChatBI 的稳定系统架构：

- System Positioning（系统定位）
- Responsibility Boundary（责任边界）
- Capability Boundary（能力边界）
- Integration Boundary（集成边界）
- Technical Layering（技术分层）
- Dependency Rules（依赖规则）
- Code Organization（代码组织）
- Architecture Invariants（架构不变量）

本文档只描述系统级稳定边界。

以下内容不在 Architecture（架构）中展开：

- Platform API（平台接口）字段和协议
- Feature Pipeline（功能流程）
- Module（模块）内部设计
- Class / Function（类 / 函数）
- Prompt（提示词）
- Retrieval / RAG（检索 / 检索增强）
- SQL 生成算法
- LangGraph（图工作流）节点
- 具体模型、数据库、向量库和部署产品

这些内容由后续 Platform Integration（平台集成）、Feature Spec（功能规格）、Module Spec（模块规格）和 Implementation（实现）定义。

---

# 2. System Positioning（系统定位）

ChatBI 定位为：

> **Domain AI Engine（领域 AI 引擎）**

用于承载企业经营数据场景中的领域 AI 能力。

当前一级产品能力：

```text
ChatBI
├── Natural Language Query（自然语言查询）
└── Business Analysis（经营分析）
```

核心职责：

> 将自然语言经营问题转换为可信、可追溯的数据结果，并基于可信数据完成经营分析。

ChatBI 不定位为完整 Enterprise AI Platform（企业 AI 平台）。

整体关系：

```
Enterprise AI Platform
        │
        │ Integration Contract
        ▼
ChatBI Domain AI Engine
        │
        ▼
Certified Business Data
```

责任原则：

> Platform（平台）负责企业通用能力。

> ChatBI 负责领域能力和领域正确性。

------

# 3. System Form（系统形态）

ChatBI 当前采用：

> **Modular Monolith（模块化单体）**

保持：

```
Single Repository（单代码仓库）
+
Single Application（单应用）
+
Single Deployment Unit（单部署单元）
+
Clear Internal Boundaries（清晰内部边界）
```

当前不提前拆分 Microservice（微服务）。

只有出现真实需求时才重新评估服务拆分，例如：

- 独立部署
- 独立扩缩容
- 独立团队边界
- 独立故障隔离
- 明确性能瓶颈
- 明确容量瓶颈

原则：

> **先建立清晰模块边界，再根据真实需求决定是否服务化。**

------

# 4. Responsibility Boundary（责任边界）

整体责任：

```
Enterprise AI Platform
        │
        │ 通用平台能力
        ▼
Integration Boundary
        │
        │ 领域能力
        ▼
ChatBI
```

## 4.1 Platform Owned（平台负责）

Enterprise AI Platform（企业 AI 平台）或企业基础设施负责：

### Identity（身份）

- Authentication（身份认证）
- 用户登录
- 用户与组织目录
- SSO（单点登录）
- Platform Permission（平台权限）

### Product Conversation（产品会话）

- Chat UI（聊天界面）
- Conversation（会话）
- Message History（消息历史）
- 产品级会话生命周期

### Model Platform（模型平台）

- Model Gateway（模型网关）
- 模型供应商接入
- API Key / Secret（密钥）
- 模型路由
- 配额和成本治理

### Platform Governance（平台治理）

- API Gateway（接口网关）
- Rate Limit（限流）
- Quota（配额）
- Platform Observability（平台可观测）
- Deployment（部署）
- Scaling（扩缩容）
- High Availability（高可用）
- Secret Management（密钥管理）
- Backup / Disaster Recovery（备份 / 灾难恢复）
- CI/CD（持续集成 / 持续交付）

以上能力不属于 ChatBI Core（ChatBI 核心）。

------

# 5. ChatBI Owned（ChatBI 负责）

ChatBI 负责：

```
ChatBI
│
├── Natural Language Query
│   （自然语言查询）
│
├── Business Analysis
│   （经营分析）
│
└── Shared Domain Capabilities
    （共享领域能力）
```

## 5.1 Natural Language Query（自然语言查询）

职责：

> 将自然语言经营问题转换为可信、可追溯的数据查询结果。

Architecture 只定义该能力存在以及它的责任边界。

具体：

- Semantic Resolution（语义解析）
- Schema Linking（结构关联）
- Metric Retrieval（指标检索）
- Join Reasoning（关联推理）
- SQL Generation（SQL 生成）
- SQL Validation（SQL 校验）
- Query Execution（查询执行）
- Clarification（澄清）
- Result Construction（结果构造）

由对应 Feature Spec（功能规格）定义。

------

## 5.2 Business Analysis（经营分析）

职责：

> 基于可信经营数据完成经营分析。

包括：

- Trend Analysis（趋势分析）
- Comparison（对比）
- Breakdown（拆解）
- Drill-down（下钻）
- Cause Validation（原因验证）
- Analysis Conclusion（分析结论）

稳定关系：

```
Trusted Business Data
        ↓
Business Analysis
        ↓
Analysis Result
```

Business Analysis 不建立一套绕过 Trusted Query（可信查询）的独立数据访问链。

原则：

> **Trusted Data Before Analysis（可信数据先于分析）。**

------

# 6. Shared Domain Capabilities（共享领域能力）

## 6.1 Business Semantics（业务语义）

负责：

- Business Domain（业务领域）
- Business Object（业务对象）
- Metric（指标）
- Dimension（维度）
- Business Rule（业务规则）
- Business Meaning（业务含义）

业务事实由 Business Domain（业务领域）定义。

必须保持：

```
Business Meaning
        ↓
Stable

Technical Mapping
        ↓
Replaceable
```

数据库字段、模型输出和检索结果不能反向决定业务事实。

------

## 6.2 Domain Authorization（领域授权）

必须区分：

```
Authentication
（你是谁）

        ≠

Domain Authorization
（你能访问什么业务数据）
```

Platform 负责身份认证。

ChatBI 根据领域规则决定：

- 可访问的 Business Domain
- 可访问的 Metric
- 可访问的 Dimension
- Data Scope（数据范围）
- Detail Access（明细权限）
- Sensitive Data Access（敏感数据权限）

流程：

```
Platform Authentication
        ↓
Principal
        ↓
ChatBI Domain Authorization
        ↓
Authorized Data Scope
```

Platform Role（平台角色）可以作为授权输入，但不能直接等同于最终 Data Scope。

------

## 6.3 Query Safety（查询安全）

LLM（大语言模型）可以提出候选结果，但不能最终决定：

- 权限
- Data Scope
- Query Safety
- 最终数据执行边界

必须保持：

```
Model Candidate
        ↓
Deterministic Validation
        ↓
Allowed / Rejected
```

原则：

> **Model proposes, program decides.**

------

## 6.4 Domain State（领域状态）

必须区分：

```
Product Conversation
（产品会话）

        ≠

Domain State
（领域状态）
```

Platform 负责完整产品会话。

ChatBI 负责完成业务任务所需的领域状态，例如：

- 上一轮成功查询语义
- 上一轮结果引用
- Pending Clarification（待澄清状态）
- 当前分析状态
- 当前业务上下文

具体保存哪些状态由 Feature Spec 决定。

Architecture 不提前规定具体 State Store（状态存储）产品。

------

## 6.5 Result / Evidence（结果 / 证据）

稳定关系：

```
Natural Language Query
        ↓
Query Result
        ↓
Evidence
        ↓
Business Analysis
        ↓
Analysis Result
```

ChatBI 负责：

- 结果业务含义
- 结果正确性
- 数据范围
- 必要追溯信息
- Evidence（证据）关联

Platform 负责：

- 展示
- UI 交互
- 产品级消息呈现

------

## 6.6 Evaluation（评估）

ChatBI 负责：

- Query Evaluation（查询评估）
- Analysis Evaluation（分析评估）
- Business Correctness（业务正确性）
- Regression（回归）
- Bad Case（错误案例）

必须区分：

```
Observability（可观测性）
= 系统运行得怎么样

Evaluation（评估）
= 业务结果做得对不对
```

平台可观测能力不能替代 ChatBI 的业务评估。

------

# 7. Integration Boundary（集成边界）

正常情况下：

```
Enterprise AI Platform
        ↓
ChatBI Public Contract
        ↓
ChatBI Interfaces
        ↓
ChatBI Core
```

如果 Platform 与 ChatBI 存在真实协议或语义差异：

```
External Platform
        ↓
Adapter / Anti-Corruption Layer
（适配器 / 防腐层）
        ↓
ChatBI Public Contract
        ↓
ChatBI Core
```

原则：

> **Contract Alignment First（优先契约统一）。**

> **Adapter When Required（真实存在差异时才使用适配器）。**

Platform Adapter（平台适配器）不是固定架构层。

------

# 8. External Capability Boundaries（外部能力边界）

ChatBI Core 通过稳定 Port / Contract（端口 / 契约）使用外部能力。

主要边界：

```
Platform Integration
Model
Business Data
State
Telemetry
Audit
Runtime
```

## 8.1 Platform Integration（平台集成）

Platform ↔ ChatBI 的语义和正式 API Contract（接口契约）由：

```
Technical Design/
└── Platform Integration/
    ├── SPEC.md
    └── openapi.yaml
```

维护。

`SPEC.md` 定义：

- Platform / ChatBI 责任语义
- Authentication / Authorization 边界
- Conversation / Domain State 边界
- Run / Result 等集成语义
- Adapter 使用原则

`openapi.yaml` 定义：

- Endpoint（端点）
- HTTP Method（请求方法）
- Authentication Scheme（认证结构）
- Header / Parameter（请求头 / 参数）
- Request / Response Schema（请求 / 响应结构）
- Error Schema（错误结构）
- Streaming（流式接口）
- API Version（接口版本）

------

## 8.2 Model Boundary（模型边界）

ChatBI Core 不直接绑定：

- OpenAI
- DeepSeek
- Qwen
- 某个 Model Gateway
- 某个供应商 SDK

具体模型接入由 Infrastructure（基础设施层）实现。

------

## 8.3 Business Data Boundary（业务数据边界）

ChatBI 通过稳定 Data Access Contract（数据访问契约）访问：

> **Certified Business Data（认证业务数据）**

ChatBI 不负责：

- ETL（数据抽取转换加载）
- 企业数据仓库建设
- 原始数据加工
- 企业数据调度平台

ChatBI 负责按照 Domain（领域）规则正确使用业务数据。

------

## 8.4 State / Telemetry / Audit / Runtime

ChatBI 只定义自身需要的能力和语义。

具体：

- State Store（状态存储）
- Observability Backend（可观测后端）
- Audit Backend（审计后端）
- Runtime Platform（运行平台）

可以替换。

ChatBI Core 不依赖具体产品。

------

# 9. Technical Layering（技术分层）

ChatBI 内部采用：

```
Interfaces
（接口层）
        ↓
Application
（应用层）
        ↓
Domain
（领域层）

Application
        ↓
Ports / Contracts
        ↑
Infrastructure
（基础设施层）

Bootstrap
（装配层）
        ↓
Assembly
```

## 9.1 Interfaces（接口层）

负责：

- 接收外部请求
- 协议转换
- 基础输入校验
- 调用 Application
- 返回外部响应

不负责：

- 核心业务规则
- 完整 Feature Workflow（功能流程）

------

## 9.2 Application（应用层）

负责：

- Use Case（用例）
- Feature Workflow（功能流程）
- Orchestration（编排）
- 分支和状态流转
- 调用 Domain
- 调用外部 Port / Contract

Application 描述：

> 完成一个 Feature 需要哪些能力。

不描述：

> 某个供应商具体如何实现这些能力。

------

## 9.3 Domain（领域层）

负责：

- Business Object
- Metric / Dimension
- Business Rule
- Domain Authorization
- Domain State Semantics
- Result Semantics
- 稳定领域模型

Domain 不依赖：

- LLM SDK
- Database SDK
- Vector Database SDK
- FastAPI
- LangGraph
- Redis
- Platform SDK
- 具体供应商

------

## 9.4 Infrastructure（基础设施层）

负责技术实现，例如：

- Model Adapter
- Retrieval Adapter
- Business Data Adapter
- State Adapter
- Database Access
- Telemetry
- Audit
- Platform Adapter（可选）

Infrastructure：

> 实现技术能力。

Infrastructure：

> 不定义业务事实。

------

## 9.5 Bootstrap（装配层）

负责：

- Configuration（配置）
- Dependency Injection（依赖注入）
- Adapter Assembly（适配器装配）
- Application Startup（应用启动）

Bootstrap 不承载业务逻辑。

------

# 10. Dependency Rules（依赖规则）

稳定方向：

```
Interfaces
        ↓
Application
        ↓
Domain
```

外部能力：

```
Application
        ↓
Port / Contract
        ↑
Infrastructure
```

必须保持：

1. Domain 不依赖 Infrastructure。
2. Domain 不依赖具体框架和供应商。
3. Application 不直接依赖供应商 SDK。
4. Application 通过 Port / Contract 使用外部能力。
5. Infrastructure 实现外部技术能力。
6. Interfaces 不绕过 Application 完成业务流程。
7. Infrastructure 不定义业务指标和业务规则。
8. Bootstrap 只负责装配。
9. Platform 私有对象不得穿透系统边界进入 ChatBI Core。

------

# 11. Code Organization（代码组织）

运行代码保持：

```
src/
└── chatbi/
    ├── interfaces/
    ├── application/
    ├── domain/
    ├── infrastructure/
    └── bootstrap/

resources/
tests/
evaluation/
scripts/
```

职责：

```
interfaces/
→ 外部入口

application/
→ Feature / Use Case / Orchestration

domain/
→ 业务规则与稳定领域模型

infrastructure/
→ 外部技术实现

bootstrap/
→ 配置和装配
```

具体 Feature Package（功能包）、Module（模块）、File（文件）、Class（类）和 Function（函数）不由 Architecture 提前规定。

------

# 12. Documentation Organization（文档组织）

设计文档采用：

```
docs/
│
├── Business/
│   ├── PRODUCT.md
│   └── SALES_DOMAIN.md
│
├── Technical Design/
│   │
│   ├── ARCHITECTURE.md
│   │
│   ├── Platform Integration/
│   │   ├── SPEC.md
│   │   └── openapi.yaml
│   │
│   ├── Natural Language Query/
│   │   ├── SPEC.md
│   │   ├── Module 01 - ...
│   │   ├── Module 02 - ...
│   │   └── ...
│   │
│   └── Business Analysis/
│       ├── SPEC.md
│       ├── Module 01 - ...
│       └── ...
│
└── current_system_alignment.md
```

职责：

### `Business/PRODUCT.md`

定义：

> 产品需要什么。

### `Business/SALES_DOMAIN.md`

定义：

> 业务到底是什么意思。

### `Technical Design/ARCHITECTURE.md`

定义：

> 系统责任、边界、分层和依赖关系。

### `Technical Design/Platform Integration/SPEC.md`

定义：

> Platform 与 ChatBI 的集成语义。

### `Technical Design/Platform Integration/openapi.yaml`

定义：

> Platform ↔ ChatBI 的正式机器可读 API Contract。

### Feature `SPEC.md`

定义：

> 一个完整 Feature 如何工作，以及 Feature 的输入、输出、状态和错误契约。

### Module 文档

一份 Module 文档同时定义：

- Responsibility（职责）
- Boundary（边界）
- Input Contract（输入契约）
- Output Contract（输出契约）
- Failure Contract（失败契约）
- Processing Rules（处理规则）
- Test Cases（测试用例）

不再为每个 Module 重复创建多份文档。

------

# 13. Design and Development Flow（设计与开发流程）

完整层级：

```
Product Requirement
        ↓
Business Domain
        ↓
Architecture
        ↓
Platform Integration Spec + API Contract
        ↓
Feature Spec + Feature Contract
        ↓
Module Spec + Module Contract
        ↓
Test
        ↓
Implementation
        ↓
Integration Test
        ↓
Evaluation
        ↓
CI/CD
        ↓
Production
```

确定性模块采用：

> **TDD（测试驱动开发）**

```
Contract
    ↓
Test
    ↓
Red
    ↓
Implementation
    ↓
Green
    ↓
Refactor
```

LLM / RAG 等非确定性能力采用：

```
Spec
    ↓
Contract
    ↓
Evaluation Dataset
    ↓
Implementation
    ↓
Evaluation
```

最终统一经过：

- Integration Test（集成测试）
- End-to-End Evaluation（端到端评估）

------

# 14. Architecture Invariants（架构不变量）

长期保持以下规则：

### 14.1 Business First（业务优先）

技术服务于业务，不因某个框架或产品改变业务目标。

### 14.2 Domain Owns Business Truth（领域拥有业务事实）

业务含义由 Domain 定义，数据库和模型不能反向定义业务事实。

### 14.3 Authentication ≠ Domain Authorization

身份认证不等于业务数据授权。

### 14.4 Product Conversation ≠ Domain State

产品聊天记录不等于 ChatBI 领域状态。

### 14.5 Model Proposes, Program Decides

模型提出候选，确定性程序完成最终业务和安全裁决。

### 14.6 Trusted Data Before Analysis

经营分析必须建立在可信查询结果上。

### 14.7 Contract Alignment First

优先统一契约；只有存在真实边界差异时才增加 Adapter / Anti-Corruption Layer（适配器 / 防腐层）。

### 14.8 Stable Core, Replaceable Edge

```
Replace Platform
→ Keep ChatBI Core

Replace Model Provider
→ Keep Domain

Replace Database
→ Keep Business Semantics

Replace Retrieval
→ Keep Business Definition

Replace State Store
→ Keep Domain State Semantics
```

### 14.9 Do Not Overbuild（不过度建设）

Architecture 定义边界，不代表当前阶段必须把所有基础设施立即实现。

没有真实需求时，不提前建设：

- Microservice
- 大量空 Interface
- 大量空 Adapter
- Plugin Framework
- Distributed Runtime
- Enterprise IAM
- Complex State Platform

------

# 15. Architecture Change Rule（架构变更规则）

只有以下内容发生变化时，才需要评估修改 `ARCHITECTURE.md`：

- System Positioning（系统定位）
- Platform / ChatBI Responsibility Boundary
- 一级 Business Capability
- Technical Layering
- Dependency Direction
- 顶层 Code Organization
- Integration Boundary
- Architecture Invariant

以下变化通常不修改 Architecture：

- 新增指标
- 新增维度
- 修改 Prompt
- 修改 Retrieval
- 更换模型
- 更换数据库
- 调整 Feature Pipeline
- 新增 Module
- 修改 Module Algorithm
- 修复 Bad Case
- 新增测试

前提：

> 这些变化仍然遵守当前 Architecture 定义的边界。

------

# 16. Architecture Baseline（架构基线）

系统：

```
Enterprise AI Platform
        ↓
Integration Contract
        ↓
ChatBI Domain AI Engine
        │
        ├── Natural Language Query
        ├── Business Analysis
        │
        └── Shared Domain Capabilities
            ├── Business Semantics
            ├── Domain Authorization
            ├── Query Safety
            ├── Domain State
            ├── Result / Evidence
            └── Evaluation
        ↓
Certified Business Data
```

技术：

```
Interfaces
        ↓
Application
        ↓
Domain

Application
        ↓
Ports / Contracts
        ↑
Infrastructure

Bootstrap
        ↓
Assembly
```

设计：

```
Business
        ↓
Architecture
        ↓
Integration Contract
        ↓
Feature Contract
        ↓
Module Contract
        ↓
Test
        ↓
Implementation
```

最终原则：

> **上层定义目标和语义，边界定义契约，下层在契约内设计和实现。**

> **架构倒推，契约先定，测试先行，实施顺推。**

> **Business First, Boundary Aware.**

> **Model proposes, program decides.**

> **Stable Core, Replaceable Edge.**
>
> ```
> 
> ```
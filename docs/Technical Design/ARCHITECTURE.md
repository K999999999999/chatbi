------

# ChatBI Architecture

# ChatBI 系统架构

> **Status（状态）：** Design Baseline（设计基线）
> **Scope（范围）：** ChatBI System Architecture（ChatBI 系统级架构）
> **Architecture Style（架构形态）：** Modular Monolith（模块化单体）
> **Primary Capabilities（核心能力）：** Natural Language Query（自然语言查询）、Business Analysis（经营分析）
> **Engineering Reference（工程规范引用）：** `ENGINEERING.md`
> **Architecture Decision Reference（架构决策引用）：** `ARCHITECTURE_DECISIONS.md`

------

# 1. Purpose（目的）

本文档定义 ChatBI 的稳定 System Architecture（系统架构）。

主要定义：

- System Positioning（系统定位）；
- System Boundary（系统边界）；
- Responsibility Boundary（责任边界）；
- Capability Map（能力地图）；
- Integration Boundary（集成边界）；
- External Capability Boundary（外部能力边界）；
- Technical Layering（技术分层）；
- Dependency Rules（依赖规则）；
- Code Organization（代码组织）；
- Architecture Invariants（架构不变量）。

本文档回答：

> **ChatBI 是什么、负责什么、如何组织，以及系统级依赖方向是什么。**

本文档不定义：

- Platform API（平台接口）具体字段和协议；
- Feature Pipeline（功能内部流程）；
- Module Contract（模块契约）；
- Class / Function（类 / 函数）；
- Prompt（提示词）；
- Retrieval Algorithm（检索算法）；
- SQL Generation Algorithm（SQL 生成算法）；
- LangGraph Node（LangGraph 节点）；
- 具体模型、数据库、向量数据库和供应商；
- Test / Evaluation Case（测试 / 评估案例）。

这些内容分别由：

- Platform Integration Spec（平台集成规格）；
- Feature Architecture（功能架构）；
- Feature Spec（功能规格）；
- Module Spec（模块规格）；
- Acceptance & Evaluation（验收与评估）；
- Implementation（实现）

继续定义。

关键架构决策的 Why（原因）由：

> ```
> ARCHITECTURE_DECISIONS.md
> ```

记录。

------

# 2. System Positioning（系统定位）

ChatBI 定位为：

> **Domain AI Engine（领域 AI 引擎）。**

面向企业经营数据领域，提供领域 AI（人工智能）能力和领域正确性。

当前一级业务能力：

```
ChatBI Domain AI Engine
（ChatBI 领域 AI 引擎）

├── Natural Language Query
│   （自然语言查询）
│
└── Business Analysis
    （经营分析）
```

核心目标：

> **将自然语言经营问题转换为可信、可追溯的业务数据结果，并基于可信数据完成经营分析。**

ChatBI 不定位为：

> Enterprise AI Platform（企业 AI 平台）。

------

## 2.1 System Context（系统上下文）

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

> **Platform（平台）负责企业通用能力。**

> **ChatBI 负责领域能力和领域正确性。**

------

# 3. System Form（系统形态）

ChatBI 当前采用：

> **Modular Monolith（模块化单体）。**

保持：

```
Single Repository
（单代码仓库）

+

Single Application
（单应用）

+

Single Deployment Unit
（单部署单元）

+

Clear Internal Boundaries
（清晰内部边界）
```

当前不提前拆分 Microservice（微服务）。

只有出现真实：

- Independent Deployment（独立部署）；
- Independent Scaling（独立扩缩容）；
- Independent Team Boundary（独立团队边界）；
- Independent Failure Domain（独立故障域）；
- 明确 Performance Bottleneck（性能瓶颈）；
- 明确 Capacity Bottleneck（容量瓶颈）

时重新评估服务化。

原则：

> **先建立清晰模块边界，再根据真实需求决定是否拆分服务。**

------

# 4. Responsibility Boundary（责任边界）

系统级责任边界：

```
Enterprise AI Platform
（企业 AI 平台）

        ↓

Generic Platform Capabilities
（通用平台能力）

        ↓

Integration Boundary
（集成边界）

        ↓

ChatBI Domain AI Engine
（ChatBI 领域 AI 引擎）

        ↓

Domain Capabilities
（领域能力）
```

------

## 4.1 Platform Owned（平台负责）

Enterprise AI Platform（企业 AI 平台）或企业基础设施负责通用平台能力。

主要包括：

### Identity（身份）

- Authentication（身份认证）；
- User / Organization Directory（用户 / 组织目录）；
- SSO（单点登录）；
- Platform Permission（平台权限）。

### Product Conversation（产品会话）

- Chat UI（聊天界面）；
- Conversation（产品会话）；
- Message History（消息历史）；
- 产品级会话生命周期。

### Model Platform（模型平台）

- Model Gateway（模型网关）；
- 模型供应商接入；
- API Key / Secret（密钥）；
- 模型路由；
- 模型配额；
- 成本治理。

### Platform Governance（平台治理）

- API Gateway（接口网关）；
- Rate Limit / Quota（限流 / 配额）；
- Platform Observability（平台可观测性）；
- Deployment / Scaling（部署 / 扩缩容）；
- High Availability（高可用）；
- Secret Management（密钥管理）；
- Backup / Disaster Recovery（备份 / 灾难恢复）；
- CI/CD（持续集成 / 持续交付）。

这些能力：

> **不属于 ChatBI Core（ChatBI 核心）。**

------

## 4.2 ChatBI Owned（ChatBI 负责）

ChatBI 负责：

```
ChatBI

├── Natural Language Query
│   （自然语言查询）
│
├── Business Analysis
│   （经营分析）
│
└── Shared Domain Capabilities
    （共享领域能力）
```

ChatBI 对以下事项负责：

- Business Semantics（业务语义）；
- Domain Authorization（领域授权）；
- Query Safety（查询安全）；
- Domain State Semantics（领域状态语义）；
- Business Result / Evidence（业务结果 / 证据）；
- Business Evaluation（业务评估）。

------

# 5. Capability Map（能力地图）

```
ChatBI Domain AI Engine
（领域 AI 引擎）

├── Natural Language Query
│   （自然语言查询）
│
├── Business Analysis
│   （经营分析）
│
└── Shared Domain Capabilities
    （共享领域能力）

    ├── Business Semantics
    │   （业务语义）
    │
    ├── Domain Authorization
    │   （领域授权）
    │
    ├── Query Safety
    │   （查询安全）
    │
    ├── Domain State
    │   （领域状态）
    │
    ├── Result / Evidence
    │   （结果 / 证据）
    │
    └── Evaluation
        （评估）
```

------

## 5.1 Natural Language Query（自然语言查询）

职责：

> **将自然语言经营问题转换为可信、可追溯的数据查询结果。**

具体 Module（模块）、Processing Flow（处理链路）和 Contract（契约）：

> 由 `Technical Design/Natural Language Query/` 下的 Feature Architecture（功能架构）和 Feature Spec（功能规格）定义。

系统架构：

> 不展开 NLQ（自然语言查询）内部模块。

------

## 5.2 Business Analysis（经营分析）

职责：

> **基于可信经营数据完成分析、诊断和业务解释。**

稳定关系：

```
Trusted Business Data
（可信业务数据）

        ↓

Business Analysis
（经营分析）

        ↓

Analysis Result
（分析结果）
```

Business Analysis（经营分析）不得建立：

> 绕过 Trusted Query Capability（可信查询能力）的第二套独立数据访问体系。

原则：

> **Trusted Data Before Analysis（可信数据先于分析）。**

------

# 6. Shared Domain Capabilities（共享领域能力）

## 6.1 Business Semantics（业务语义）

负责正式：

- Business Domain（业务领域）；
- Business Object（业务对象）；
- Metric（指标）；
- Dimension（维度）；
- Business Rule（业务规则）；
- Business Meaning（业务含义）。

原则：

> **Domain Owns Business Truth（领域拥有业务事实）。**

稳定关系：

```
Business Meaning
（业务含义）
        ↓
Stable
（稳定）

Technical Mapping
（技术映射）
        ↓
Replaceable
（可替换）
```

Database Schema（数据库结构）、LLM Output（大语言模型输出）、Retrieval Result（检索结果）：

> 不得反向定义业务事实。

------

## 6.2 Domain Authorization（领域授权）

必须保持：

```
Authentication
（身份认证）

        ≠

Domain Authorization
（领域授权）
```

Platform（平台）负责：

> **用户是谁。**

ChatBI 负责确定：

> **用户在当前业务领域中可以访问什么。**

领域授权可以约束：

- Business Domain（业务领域）；
- Metric（指标）；
- Dimension（维度）；
- Data Scope（数据范围）；
- Detail Access（明细权限）；
- Sensitive Data Access（敏感数据权限）。

稳定关系：

```
Platform Authentication
（平台身份认证）

        ↓

Principal
（主体）

        ↓

ChatBI Domain Authorization
（ChatBI 领域授权）

        ↓

Authorized Data Scope
（授权数据范围）
```

Platform Role（平台角色）可以成为授权输入。

但：

> **Platform Role ≠ Final Data Scope（平台角色不等于最终数据范围）。**

------

## 6.3 Query Safety（查询安全）

LLM（大语言模型）可以：

> 提出 Candidate（候选）。

但不得最终决定：

- Domain Authorization（领域授权）；
- Data Scope（数据范围）；
- Query Safety（查询安全）；
- Data Execution Boundary（数据执行边界）。

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

Platform（平台）拥有：

- Conversation（产品会话）；
- Message History（消息历史）；
- 产品级会话生命周期。

ChatBI 拥有：

> 完成业务任务所需状态的业务语义。

具体保存什么 Domain State（领域状态）：

> 由各 Feature Spec（功能规格）定义。

System Architecture（系统架构）：

> 不绑定具体 State Store（状态存储）产品。

------

## 6.5 Result / Evidence（结果 / 证据）

稳定关系：

```
Natural Language Query
（自然语言查询）

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

ChatBI 负责：

- Business Meaning（业务含义）；
- Correctness（业务正确性）；
- Data Scope（数据范围）；
- Evidence（证据）；
- Traceability（可追溯性）。

Platform（平台）负责：

- Presentation（展示）；
- UI Interaction（界面交互）；
- 产品级消息呈现。

------

## 6.6 Evaluation（评估）

ChatBI 负责：

- Query Evaluation（查询评估）；
- Analysis Evaluation（分析评估）；
- Business Correctness（业务正确性）；
- Regression（回归）；
- Bad Case（失败案例）。

必须区分：

```
Observability
（可观测性）
=
系统运行得怎么样
```

与：

```
Evaluation
（评估）
=
业务结果做得对不对
```

Platform Observability（平台可观测性）：

> 不能替代 ChatBI Business Evaluation（业务评估）。

------

# 7. Integration Boundary（集成边界）

正常情况：

```
Enterprise AI Platform
（企业 AI 平台）

        ↓

ChatBI Public Contract
（ChatBI 公共契约）

        ↓

ChatBI Interfaces
（ChatBI 接口层）

        ↓

ChatBI Core
（ChatBI 核心）
```

如果外部 Platform（平台）与 ChatBI 存在真实：

- Protocol Difference（协议差异）；
- Semantic Difference（语义差异）；

才允许：

```
External Platform
（外部平台）

        ↓

Adapter / Anti-Corruption Layer
（适配器 / 防腐层）

        ↓

ChatBI Public Contract
（ChatBI 公共契约）

        ↓

ChatBI Core
（ChatBI 核心）
```

原则：

> **Contract Alignment First（契约对齐优先）。**

> **Adapter When Required（必要时才适配）。**

Platform Adapter（平台适配器）：

> 不是固定系统架构层。

具体 Integration Contract（集成契约）由：

> ```
> Technical Design/Platform Integration/
> ```

定义。

------

# 8. External Capability Boundary（外部能力边界）

ChatBI Core（ChatBI 核心）通过稳定：

> **Port / Contract（端口 / 契约）**

访问外部技术能力。

主要包括：

```
External Capabilities
（外部能力）

├── Platform Integration
│   （平台集成）
│
├── Model
│   （模型）
│
├── Business Data
│   （业务数据）
│
├── Retrieval
│   （检索）
│
├── State
│   （状态）
│
├── Telemetry
│   （遥测）
│
├── Audit
│   （审计）
│
└── Runtime
    （运行环境）
```

------

## 8.1 Model Boundary（模型边界）

ChatBI Core（ChatBI 核心）：

> 不绑定具体 Model Provider（模型供应商）、Model Gateway（模型网关）或供应商 SDK（软件开发工具包）。

具体模型接入：

> 由 Infrastructure（基础设施层）实现。

------

## 8.2 Retrieval Boundary（检索边界）

Domain / Application（领域 / 应用）逻辑：

> 不绑定具体 Embedding Model（向量模型）、Vector Database（向量数据库）或 Retrieval Framework（检索框架）。

必须保持：

```
Business Source of Truth
（业务事实源）

        ↓

Stable
（稳定）


Retrieval Asset / Index
（检索资产 / 索引）

        ↓

Derived / Replaceable
（派生 / 可替换）
```

具体 Retrieval Technology（检索技术）：

> 由 Infrastructure（基础设施层）实现。

------

## 8.3 Business Data Boundary（业务数据边界）

ChatBI 通过：

> **Data Access Contract（数据访问契约）**

访问：

> Certified Business Data（认证业务数据）。

ChatBI 不负责：

- ETL（数据抽取、转换、加载）；
- 企业数据仓库建设；
- 原始数据加工；
- 企业数据调度平台。

ChatBI 负责：

> 按照 Domain Rule（领域规则）正确、安全地使用认证业务数据。

------

## 8.4 State / Telemetry / Audit / Runtime（状态 / 遥测 / 审计 / 运行环境）

ChatBI 只定义：

> 自身所需 Capability / Semantics（能力 / 语义）。

具体：

- State Store（状态存储）；
- Observability Backend（可观测后端）；
- Audit Backend（审计后端）；
- Runtime Platform（运行平台）

保持：

> Replaceable（可替换）。

ChatBI Core（ChatBI 核心）不得直接依赖具体产品。

------

# 9. Technical Layering（技术分层）

ChatBI 内部采用：

```
Interfaces
（接口层）

Application
（应用层）

Domain
（领域层）

Infrastructure
（基础设施层）

Bootstrap
（装配层）
```

稳定关系：

```
Interfaces
（接口层）

        ↓

Application
（应用层）

        ↓

Domain
（领域层）
```

外部技术能力：

```
Application
（应用层）

        ↓

Ports / Contracts
（端口 / 契约）

        ↑ implements

Infrastructure
（基础设施层）
```

Bootstrap（装配层）：

> 集中完成依赖装配。

------

## 9.1 Interfaces（接口层）

负责：

- External Entry（外部入口）；
- Protocol Translation（协议转换）；
- 基础输入校验；
- 调用 Application（应用层）；
- 返回外部响应。

不负责：

- 核心业务规则；
- 完整 Feature Workflow（功能工作流）。

------

## 9.2 Application（应用层）

负责：

- Use Case（用例）；
- Feature Workflow（功能工作流）；
- Orchestration（编排）；
- Branch / State Transition（分支 / 状态流转）；
- 调用 Domain（领域层）；
- 调用外部 Port / Contract（端口 / 契约）。

Application（应用层）回答：

> **完成一个业务用例需要哪些能力，以及如何协作。**

不回答：

> **某个供应商具体如何实现这些能力。**

------

## 9.3 Domain（领域层）

负责稳定：

- Business Object（业务对象）；
- Metric（指标）；
- Dimension（维度）；
- Business Rule（业务规则）；
- Domain Authorization Semantics（领域授权语义）；
- Domain State Semantics（领域状态语义）；
- Result Semantics（结果语义）；
- Stable Domain Model（稳定领域模型）。

Domain（领域层）：

> 不依赖具体技术供应商、SDK（软件开发工具包）或应用框架。

原则：

> **Domain Owns Business Truth（领域拥有业务事实）。**

------

## 9.4 Infrastructure（基础设施层）

负责外部技术能力实现，例如：

- Model Adapter（模型适配器）；
- Retrieval Adapter（检索适配器）；
- Business Data Adapter（业务数据适配器）；
- State Adapter（状态适配器）；
- Database Access（数据库访问）；
- Telemetry（遥测）；
- Audit（审计）；
- 必要的 Platform Adapter（平台适配器）。

原则：

> **Infrastructure implements technology; it does not define business truth.**
> **基础设施实现技术能力，不定义业务事实。**

------

## 9.5 Bootstrap（装配层）

负责：

- Configuration（配置）；
- Dependency Injection（依赖注入）；
- Adapter Assembly（适配器装配）；
- Application Startup（应用启动）。

Bootstrap（装配层）：

> 不承载业务逻辑。

------

# 10. Dependency Rules（依赖规则）

必须长期保持以下 System-Level Dependency Rules（系统级依赖规则）：

1. Domain（领域层）不依赖 Infrastructure（基础设施层）。
2. Domain（领域层）不依赖具体 Framework / Vendor（框架 / 供应商）。
3. Application（应用层）不直接依赖供应商 SDK（软件开发工具包）。
4. Application（应用层）通过 Port / Contract（端口 / 契约）使用外部能力。
5. Infrastructure（基础设施层）实现外部技术能力。
6. Interfaces（接口层）不得绕过 Application（应用层）完成业务流程。
7. Infrastructure（基础设施层）不得定义 Metric / Business Rule（指标 / 业务规则）。
8. Bootstrap（装配层）只负责 Configuration / Assembly（配置 / 装配）。
9. Platform Private Model（平台私有对象）不得穿透系统边界进入 ChatBI Core（ChatBI 核心）。
10. Feature（功能）内部实现不得破坏系统级依赖方向。

核心依赖：

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
Ports / Contracts
        ↑
Infrastructure
```

------

# 11. Code Organization（代码组织）

运行代码顶层组织保持：

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
  （功能 / 用例 / 编排）

domain/
→ Business Rule / Stable Domain Model
  （业务规则 / 稳定领域模型）

infrastructure/
→ External Technology Implementation
  （外部技术实现）

bootstrap/
→ Configuration / Assembly
  （配置 / 装配）
```

System Architecture（系统架构）：

> 不提前定义具体 Feature Package（功能包）、Module（模块）、File（文件）、Class（类）和 Function（函数）。

这些由下级设计确定。

------

# 12. Architecture Invariants（架构不变量）

以下规则长期保持。

### 12.1 Business First（业务优先）

> 技术服务业务，技术产品不得反向改变业务目标。

------

### 12.2 Domain Owns Business Truth（领域拥有业务事实）

> 业务含义由 Domain（领域）定义。

Database（数据库）、Model（模型）、Vector Store（向量存储）和 Retrieval Result（检索结果）：

> 不得反向定义业务事实。

------

### 12.3 Authentication ≠ Domain Authorization（身份认证不等于领域授权）

Platform Authentication（平台身份认证）：

> 解决用户是谁。

Domain Authorization（领域授权）：

> 解决用户可以访问什么业务数据。

------

### 12.4 Product Conversation ≠ Domain State（产品会话不等于领域状态）

Product Conversation（产品会话）由 Platform（平台）拥有。

Domain State Semantics（领域状态语义）由 ChatBI 拥有。

------

### 12.5 Model Proposes, Program Decides（模型提出，程序裁决）

Model / LLM（模型 / 大语言模型）：

> 提出候选。

Deterministic Program（确定性程序）：

> 负责业务、安全与权限最终裁决。

------

### 12.6 Trusted Data Before Analysis（可信数据先于分析）

Business Analysis（经营分析）：

> 必须建立在 Trusted Business Data（可信业务数据）之上。

------

### 12.7 Contract Alignment First（契约对齐优先）

优先：

> 统一 Contract（契约）。

只有存在真实不可消除差异时：

> 增加 Adapter / Anti-Corruption Layer（适配器 / 防腐层）。

------

### 12.8 Stable Core, Replaceable Edge（稳定核心，可替换边缘）

必须允许：

```
Replace Platform
（替换平台）
→ Keep ChatBI Core
  （保持 ChatBI 核心）

Replace Model Provider
（替换模型供应商）
→ Keep Domain
  （保持领域）

Replace Database
（替换数据库）
→ Keep Business Semantics
  （保持业务语义）

Replace Retrieval
（替换检索）
→ Keep Business Definition
  （保持业务定义）

Replace State Store
（替换状态存储）
→ Keep Domain State Semantics
  （保持领域状态语义）
```

------

### 12.9 Do Not Overbuild（不过度建设）

没有真实需求时：

> 不提前建设未来可能使用的复杂平台能力。

包括但不限于：

- Microservice（微服务）；
- 大量空 Interface（接口）；
- 大量空 Adapter（适配器）；
- Plugin Framework（插件框架）；
- Distributed Runtime（分布式运行时）；
- Enterprise IAM（企业身份管理）；
- Complex State Platform（复杂状态平台）。

------

# 13. Architecture Change Rule（架构变更规则）

以下变化需要重新评估本文件：

- System Positioning（系统定位）；
- Platform / ChatBI Responsibility Boundary（平台 / ChatBI 责任边界）；
- 一级 Business Capability（业务能力）；
- Technical Layering（技术分层）；
- Dependency Direction（依赖方向）；
- Integration Boundary（集成边界）；
- Top-Level Code Organization（顶层代码组织）；
- Architecture Invariant（架构不变量）。

以下变化通常不修改系统架构：

- 新增 Metric（指标）；
- 新增 Dimension（维度）；
- 修改 Prompt（提示词）；
- 调整 Retrieval（检索）；
- 更换模型；
- 更换数据库；
- 调整 Feature Pipeline（功能流程）；
- 新增 Feature Internal Module（功能内部模块）；
- 修改 Module Algorithm（模块算法）；
- 修复 Bad Case（失败案例）；
- 新增 Test / Evaluation（测试 / 评估）。

前提：

> **这些变化仍然满足当前系统架构定义的稳定边界。**

如果关键 Architecture Decision（架构决策）发生变化：

> 使用新的 ADR（架构决策记录）替代旧决策，而不是在本文件长期保留历史讨论过程。

------

# 14. Architecture Baseline（架构基线）

当前 ChatBI 系统稳定结构：

```
Enterprise AI Platform
（企业 AI 平台）

        ↓
Platform Integration Contract
（平台集成契约）

        ↓

ChatBI Domain AI Engine
（ChatBI 领域 AI 引擎）

├── Natural Language Query
│   （自然语言查询）
│
├── Business Analysis
│   （经营分析）
│
└── Shared Domain Capabilities
    （共享领域能力）

        ↓

Certified Business Data
（认证业务数据）
```

内部技术结构：

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
（应用层）

        ↓

Ports / Contracts
（端口 / 契约）

        ↑

Infrastructure
（基础设施层）


Bootstrap
（装配层）

        ↓

Assembly
（装配）
```

系统稳定原则：

> **Business First（业务优先）。**

> **Domain Owns Business Truth（领域拥有业务事实）。**

> **Platform owns generic capabilities; ChatBI owns domain correctness.**
> **平台负责通用能力，ChatBI 负责领域正确性。**

> **Authentication ≠ Domain Authorization（身份认证不等于领域授权）。**

> **Product Conversation ≠ Domain State（产品会话不等于领域状态）。**

> **Model proposes, program decides（模型提出，程序裁决）。**

> **Trusted Data Before Analysis（可信数据先于分析）。**

> **Contract Alignment First（契约对齐优先）。**

> **Stable Core, Replaceable Edge（稳定核心，可替换边缘）。**

> **Do Not Overbuild（不过度建设）。**

------


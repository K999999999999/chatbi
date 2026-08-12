# ChatBI Architecture Decisions（架构决策记录）

> **Status（状态）**：Active（有效）  
> **Scope（范围）**：ChatBI 系统级关键架构决策  
> **Related Architecture（关联架构）**：`ARCHITECTURE.md`

---

# 1. Purpose（文档目的）

本文档记录 ChatBI 已经确认的重要 Architecture Decision（架构决策）。

`ARCHITECTURE.md` 回答：

> 系统现在是什么结构？

本文档回答：

> 为什么采用这种结构？

架构决策主要记录：

- Context（背景）
- Decision（决定）
- Rationale（原因）
- Consequences（影响）
- Revisit Conditions（重新评估条件）
- Status（状态）

普通代码实现决定不进入本文档。

---

# 2. Decision Status（决策状态）

统一使用：

### Proposed（提议）

尚未正式接受。

### Accepted（已接受）

当前正式架构基线。

### Superseded（已替代）

已经被新的 Architecture Decision（架构决策）替代。

### Deprecated（已废弃）

不再使用，但保留历史记录。

---

# 3. Decision Index（决策索引）

| ID      | Decision（决策）                                             | Status（状态） |
| ------- | ------------------------------------------------------------ | -------------- |
| ADR-001 | ChatBI 定位为 Domain AI Engine（领域 AI 引擎）               | Accepted       |
| ADR-002 | 采用 Modular Monolith（模块化单体）                          | Accepted       |
| ADR-003 | Platform（平台）与 ChatBI 按通用能力 / 领域能力分工          | Accepted       |
| ADR-004 | 采用 Interfaces / Application / Domain / Infrastructure / Bootstrap 分层 | Accepted       |
| ADR-005 | Domain（领域）拥有 Business Truth（业务事实）                | Accepted       |
| ADR-006 | Authentication（身份认证）与 Domain Authorization（领域授权）分离 | Accepted       |
| ADR-007 | Product Conversation（产品会话）与 Domain State（领域状态）分离 | Accepted       |
| ADR-008 | Model Proposes, Program Decides（模型提出，程序裁决）        | Accepted       |
| ADR-009 | Trusted Data Before Analysis（可信数据先于分析）             | Accepted       |
| ADR-010 | Contract Alignment First（契约统一优先）                     | Accepted       |
| ADR-011 | Stable Core, Replaceable Edge（稳定核心，可替换边缘）        | Accepted       |
| ADR-012 | Do Not Overbuild（不过度建设）                               | Accepted       |

---

# ADR-001 — Domain AI Engine（领域 AI 引擎）

## Status

Accepted（已接受）

## Context（背景）

企业 AI 系统中存在大量通用能力，例如：

- Authentication（身份认证）
- Model Gateway（模型网关）
- Conversation（会话）
- API Gateway（接口网关）
- Rate Limit（限流）
- Deployment（部署）
- Observability（可观测性）

如果 ChatBI 同时建设这些通用平台能力，会扩大系统边界并增加重复建设。

## Decision（决定）

ChatBI 定位为：

> **Domain AI Engine（领域 AI 引擎）**

而不是：

> Enterprise AI Platform（企业 AI 平台）。

ChatBI 聚焦经营数据领域能力和领域正确性。

## Consequences（影响）

ChatBI 可以：

- 专注 Natural Language Query（自然语言查询）
- 专注 Business Analysis（经营分析）
- 专注 Business Semantics（业务语义）
- 专注 Domain Authorization（领域授权）
- 专注 Business Correctness（业务正确性）

平台通用能力由外部 Enterprise AI Platform（企业 AI 平台）承担。

## Revisit When（重新评估条件）

只有当 ChatBI 产品定位发生变化，需要独立承担完整 AI Platform（AI 平台）职责时重新评估。

---

# ADR-002 — Modular Monolith（模块化单体）

## Status

Accepted（已接受）

## Context（背景）

当前 ChatBI 需要清晰的内部业务和技术边界。

但暂时没有明确需求证明必须：

- 独立部署多个服务
- 独立扩缩容
- 独立团队维护
- 独立故障隔离

提前拆分 Microservice（微服务）会增加：

- 网络通信
- 服务治理
- 部署复杂度
- 分布式状态
- 调试成本

## Decision（决定）

当前采用：

> **Modular Monolith（模块化单体）**

保持：

- Single Repository（单代码仓库）
- Single Application（单应用）
- Single Deployment Unit（单部署单元）
- Clear Internal Boundaries（清晰内部边界）

## Consequences（影响）

优点：

- 开发简单
- 调试简单
- 部署简单
- 事务边界简单
- Feature（功能）可以快速演进

要求：

> 模块边界必须明确。

模块化单体不等于：

> 所有代码随意互相调用。

## Revisit When（重新评估条件）

出现以下真实需求时重新评估：

- 独立部署
- 独立扩缩容
- 独立团队
- 独立故障域
- 明确性能瓶颈
- 明确容量瓶颈

---

# ADR-003 — Platform / ChatBI Responsibility Boundary（平台 / ChatBI 责任边界）

## Status

Accepted（已接受）

## Context（背景）

Enterprise AI Platform（企业 AI 平台）和 ChatBI 都会涉及用户、模型、会话和执行。

如果责任边界不明确，会产生：

- 重复能力
- 双重状态
- 双重权限系统
- API 语义冲突

## Decision（决定）

采用：

> **Platform owns generic platform capabilities.**

> **ChatBI owns domain capabilities and domain correctness.**

Platform（平台）负责：

- Authentication（身份认证）
- Product Conversation（产品会话）
- Model Gateway（模型网关）
- API Gateway（接口网关）
- Rate Limit（限流）
- Quota（配额）
- Deployment（部署）
- Platform Observability（平台可观测）

ChatBI 负责：

- Natural Language Query（自然语言查询）
- Business Analysis（经营分析）
- Business Semantics（业务语义）
- Domain Authorization（领域授权）
- Query Safety（查询安全）
- Domain State（领域状态）
- Business Evaluation（业务评估）

## Consequences（影响）

ChatBI 不重复建设企业通用平台。

平台也不能替代 ChatBI 的领域正确性判断。

---

# ADR-004 — Layered Architecture with Ports（分层架构与端口）

## Status

Accepted（已接受）

## Context（背景）

ChatBI 同时依赖：

- LLM（大语言模型）
- Database（数据库）
- Vector Database（向量数据库）
- Platform（平台）
- State Store（状态存储）

如果业务代码直接依赖具体供应商 SDK，将导致：

- 技术实现与业务语义耦合
- 更换供应商困难
- 测试困难
- Application（应用层）被基础设施污染

## Decision（决定）

采用：

```text
Interfaces
        ↓
Application
        ↓
Domain
```

外部技术能力使用：

```text
Application
        ↓
Ports / Contracts
        ↑
Infrastructure
```

Bootstrap（装配层）集中完成依赖装配。

## Consequences（影响）

Domain（领域层）保持纯净。

Application（应用层）关注 Use Case（用例）和 Orchestration（编排）。

Infrastructure（基础设施层）负责供应商和技术实现。

---

# ADR-005 — Domain Owns Business Truth（领域拥有业务事实）

## Status

Accepted（已接受）

## Context（背景）

数据库字段、LLM 输出、向量检索结果都属于技术表现。

这些技术对象可能变化。

但：

- Metric（指标）
- Dimension（维度）
- Business Rule（业务规则）
- Business Meaning（业务含义）

必须保持稳定。

## Decision（决定）

业务事实由：

> Domain（领域）

拥有和定义。

不得由：

- Database Schema（数据库结构）
- LLM Output（模型输出）
- Retrieval Result（检索结果）

反向定义业务事实。

## Consequences（影响）

可以替换技术实现而保持业务含义稳定。

例如：

```text
Replace Database
→ Keep Business Semantics

Replace Retrieval
→ Keep Metric Definition
```

---

# ADR-006 — Authentication ≠ Domain Authorization

## Status

Accepted（已接受）

## Context（背景）

用户完成 Authentication（身份认证）只说明：

> 用户是谁。

但不能说明：

> 用户可以访问哪些经营数据。

## Decision（决定）

Platform（平台）负责：

> Authentication（身份认证）

ChatBI 负责：

> Domain Authorization（领域授权）

Platform Role（平台角色）可以成为授权输入。

但：

> Platform Role ≠ Final Data Scope

## Consequences（影响）

ChatBI 可以根据业务领域规则确定：

- Business Domain（业务领域）
- Metric（指标）
- Dimension（维度）
- Data Scope（数据范围）
- Detail Access（明细权限）
- Sensitive Data（敏感数据）

---

# ADR-007 — Product Conversation ≠ Domain State

## Status

Accepted（已接受）

## Context（背景）

聊天产品需要保存完整 Message History（消息历史）。

但 ChatBI 完成领域任务并不一定需要全部聊天记录。

## Decision（决定）

Platform（平台）拥有：

> Product Conversation（产品会话）

ChatBI 拥有：

> Domain State（领域状态）

Domain State 只保存完成业务任务所需的信息。

例如：

- Previous Query Semantic（上一轮查询语义）
- Previous Result Reference（上一轮结果引用）
- Pending Clarification（待澄清）
- Analysis State（分析状态）

## Consequences（影响）

避免将聊天历史和领域状态混成一个状态系统。

---

# ADR-008 — Model Proposes, Program Decides

## Status

Accepted（已接受）

## Context（背景）

LLM（大语言模型）输出属于概率性结果。

它可以产生：

- Intent Candidate（意图候选）
- SQL Candidate（SQL 候选）
- Analysis Candidate（分析候选）

但安全和权限不能依赖模型概率判断。

## Decision（决定）

采用：

> **Model proposes, program decides.**

模型负责提出候选。

确定性程序负责最终判断：

- Authorization（授权）
- Query Safety（查询安全）
- Data Scope（数据范围）
- SQL 执行边界

## Consequences（影响）

安全关键路径必须存在确定性 Validation（校验）。

---

# ADR-009 — Trusted Data Before Analysis

## Status

Accepted（已接受）

## Context（背景）

Business Analysis（经营分析）需要多步骤推理。

如果分析模块能够直接自由访问数据库，会形成第二套数据查询逻辑。

这会导致：

- 指标口径不一致
- 权限逻辑重复
- SQL 安全逻辑重复
- 查询结果不可信

## Decision（决定）

Business Analysis 必须基于：

> Trusted Query（可信查询）

或：

> Trusted Business Data（可信业务数据）

完成分析。

稳定关系：

```text
Natural Language Query
        ↓
Trusted Query Result
        ↓
Business Analysis
        ↓
Analysis Result
```

## Consequences（影响）

Business Analysis 不建立绕过可信查询链路的独立数据访问系统。

---

# ADR-010 — Contract Alignment First（契约统一优先）

## Status

Accepted（已接受）

## Context（背景）

外部 Platform（平台）与 ChatBI 可能存在协议或数据模型差异。

一种做法是直接增加：

> Anti-Corruption Layer（防腐层）

但如果双方可以直接统一语义，额外 Adapter（适配器）只会增加复杂度。

## Decision（决定）

采用：

> **Contract Alignment First（契约统一优先）。**

只有存在真实无法消除的差异时：

> **Adapter When Required（必要时适配）。**

## Consequences（影响）

Platform Adapter（平台适配器）不是系统固定层。

避免为了架构模式而创建无意义 Adapter。

---

# ADR-011 — Stable Core, Replaceable Edge（稳定核心，可替换边缘）

## Status

Accepted（已接受）

## Context（背景）

ChatBI 使用的技术产品可能不断变化。

例如：

- Model Provider（模型供应商）
- Database（数据库）
- Vector Database（向量数据库）
- State Store（状态存储）
- Platform（平台）

如果业务核心绑定具体技术，系统将很难演进。

## Decision（决定）

保持：

> **Stable Core, Replaceable Edge（稳定核心，可替换边缘）。**

例如：

```text
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

## Consequences（影响）

技术 Adapter（适配器）应该可替换。

业务定义必须稳定。

---

# ADR-012 — Do Not Overbuild（不过度建设）

## Status

Accepted（已接受）

## Context（背景）

企业架构设计容易提前建设未来可能需要的能力。

例如：

- Microservice（微服务）
- Plugin Framework（插件框架）
- Distributed Runtime（分布式运行时）
- Complex State Platform（复杂状态平台）

如果没有真实需求，这些能力只会增加开发和维护成本。

## Decision（决定）

Architecture（架构）允许未来扩展。

但：

> 不因为未来“可能需要”就在当前阶段提前实现。

没有真实需求时，不建设：

- Microservice
- 大量空 Interface
- 大量空 Adapter
- Plugin Framework
- Distributed Runtime
- Enterprise IAM
- Complex State Platform

## Consequences（影响）

优先：

> 最小可运行闭环。

然后根据：

- Evaluation（评估）
- Bad Case（失败案例）
- 性能数据
- 业务需求

决定下一步演进。

---

# 4. Decision Change Rule（决策变更规则）

Accepted ADR（已接受架构决策）原则上不直接删除历史。

如果未来决定发生变化：

```text
Old ADR
Status = Superseded
        ↓
New ADR
Status = Accepted
```

新决策必须说明：

- 为什么旧决策不再适用
- 出现了什么新条件
- 新方案是什么
- 新方案的 Trade-off（权衡）是什么

---

# 5. What Requires an ADR（什么需要架构决策记录）

通常需要记录：

- System Positioning（系统定位）
- Architecture Style（架构形态）
- 系统边界
- 一级责任划分
- 技术分层
- 关键依赖方向
- 状态所有权
- 安全责任
- 很难撤销的技术战略

通常不需要记录：

- 修改函数
- 新增普通 Class（类）
- 修改 Prompt（提示词）
- 修改 Retrieval Top-K
- 新增普通 Metric（指标）
- 修改测试
- 修复 Bug
- 普通代码重构

---

# 6. Architecture Decision Baseline（架构决策基线）

当前 ChatBI 的核心架构选择可以压缩为：

> **Domain AI Engine（领域 AI 引擎），而不是 Enterprise AI Platform（企业 AI 平台）。**

> **Modular Monolith（模块化单体），而不是提前 Microservice（微服务）。**

> **Platform owns generic capabilities; ChatBI owns domain correctness.**

> **Domain Owns Business Truth（领域拥有业务事实）。**

> **Authentication ≠ Domain Authorization。**

> **Product Conversation ≠ Domain State。**

> **Model proposes, program decides.**

> **Trusted Data Before Analysis。**

> **Contract Alignment First。**

> **Stable Core, Replaceable Edge。**

> **Do Not Overbuild（不过度建设）。**
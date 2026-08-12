------

# ChatBI Architecture Decisions

# ChatBI 架构决策记录

> **Status（状态）：** Active（有效）
> **Scope（范围）：** ChatBI System-Level Architecture Decisions（ChatBI 系统级关键架构决策）
> **Related Architecture（关联架构）：** `ARCHITECTURE.md`

------

# 1. Purpose（目的）

本文档记录 ChatBI 已经确认的重要 Architecture Decision（架构决策）。

`ARCHITECTURE.md（系统架构）`回答：

> **系统现在是什么结构。**

本文件回答：

> **为什么采用当前结构，以及什么条件出现时需要重新评估。**

Architecture Decision Record（架构决策记录，ADR）主要记录：

- Context（背景）；
- Decision（决定）；
- Consequences（影响）；
- Revisit When（重新评估条件）；
- Status（状态）。

本文件不是：

> Future Architecture Roadmap（未来架构路线图）。

`Revisit When（重新评估条件）`表示：

> **未来出现什么真实条件时重新做决策。**

它不表示：

> **未来一定要实施某个目标架构。**

因此：

```
ADR
=
Current Decision
（当前决定）

+

Why
（为什么）

+

Consequences
（影响）

+

Revisit Trigger
（重新评估触发条件）
```

而不是：

```
Future Implementation Plan
（未来实施计划）
```

普通：

- 代码实现；
- Feature（功能）内部设计；
- Module（模块）内部算法；
- 参数调整；

不进入本文件。

------

# 2. Decision Status（决策状态）

统一使用以下状态。

## Proposed（提议）

尚未成为正式架构基线。

------

## Accepted（已接受）

当前正式 Architecture Baseline（架构基线）。

------

## Superseded（已替代）

旧决策已经被新的 Architecture Decision（架构决策）替代。

旧 ADR：

> 保留作为 Architecture History（架构历史）。

------

## Deprecated（已废弃）

该决策已经不再采用，但仍保留历史记录。

------

# 3. Decision Index（决策索引）

| ID      | Decision（决策）                                             | Status（状态） |
| ------- | ------------------------------------------------------------ | -------------- |
| ADR-001 | ChatBI 定位为 Domain AI Engine（领域 AI 引擎）               | Accepted       |
| ADR-002 | 采用 Modular Monolith（模块化单体）                          | Accepted       |
| ADR-003 | Platform（平台）与 ChatBI 按通用能力 / 领域能力分工          | Accepted       |
| ADR-004 | 采用 Layered Architecture with Ports（分层架构与端口）       | Accepted       |
| ADR-005 | Domain Owns Business Truth（领域拥有业务事实）               | Accepted       |
| ADR-006 | Authentication（身份认证）与 Domain Authorization（领域授权）分离 | Accepted       |
| ADR-007 | Product Conversation（产品会话）与 Domain State（领域状态）分离 | Accepted       |
| ADR-008 | Model Proposes, Program Decides（模型提出，程序裁决）        | Accepted       |
| ADR-009 | Trusted Data Before Analysis（可信数据先于分析）             | Accepted       |
| ADR-010 | Contract Alignment First（契约对齐优先）                     | Accepted       |
| ADR-011 | Stable Core, Replaceable Edge（稳定核心，可替换边缘）        | Accepted       |
| ADR-012 | Do Not Overbuild（不过度建设）                               | Accepted       |
| ADR-013 | Public Async API Deferred（对外异步接口延后）                | Accepted       |

------

# ADR-001 — Domain AI Engine（领域 AI 引擎）

## Status（状态）

Accepted（已接受）

## Context（背景）

企业 AI 系统中存在大量 Generic Platform Capability（通用平台能力），例如：

- Authentication（身份认证）；
- Model Gateway（模型网关）；
- Product Conversation（产品会话）；
- API Gateway（接口网关）；
- Rate Limit（限流）；
- Deployment（部署）；
- Observability（可观测性）。

如果 ChatBI 同时建设完整企业 AI 平台能力：

> 系统边界会快速扩大并产生重复建设。

## Decision（决定）

ChatBI 定位为：

> **Domain AI Engine（领域 AI 引擎）。**

而不是：

> Enterprise AI Platform（企业 AI 平台）。

ChatBI 聚焦：

- Natural Language Query（自然语言查询）；
- Business Analysis（经营分析）；
- Business Semantics（业务语义）；
- Domain Authorization（领域授权）；
- Business Correctness（业务正确性）。

通用平台能力：

> 由 Enterprise AI Platform（企业 AI 平台）承担。

## Consequences（影响）

ChatBI 可以：

- 聚焦经营数据领域；
- 避免重复建设企业 AI 平台；
- 保持领域边界清晰；
- 独立演进领域能力。

## Revisit When（重新评估条件）

只有当 ChatBI Product Positioning（产品定位）发生变化，需要独立承担完整 AI Platform（AI 平台）职责时重新评估。

------

# ADR-002 — Modular Monolith（模块化单体）

## Status（状态）

Accepted（已接受）

## Context（背景）

当前 ChatBI 需要：

> 清晰的业务边界和技术边界。

但当前没有真实需求证明必须：

- 独立部署多个服务；
- 独立扩缩容；
- 独立团队维护；
- 独立故障隔离。

提前拆分 Microservice（微服务）会增加：

- Network Communication（网络通信）；
- Service Governance（服务治理）；
- Deployment Complexity（部署复杂度）；
- Distributed State（分布式状态）；
- Debugging Cost（调试成本）。

## Decision（决定）

当前采用：

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

## Consequences（影响）

优点：

- 开发简单；
- 调试简单；
- 部署简单；
- 事务边界简单；
- Feature（功能）可以快速演进。

同时要求：

> **内部模块边界必须明确。**

Modular Monolith（模块化单体）不等于：

> 所有代码可以任意互相调用。

## Revisit When（重新评估条件）

出现以下真实需求时重新评估：

- Independent Deployment（独立部署）；
- Independent Scaling（独立扩缩容）；
- Independent Team（独立团队）；
- Independent Failure Domain（独立故障域）；
- 明确 Performance Bottleneck（性能瓶颈）；
- 明确 Capacity Bottleneck（容量瓶颈）。

------

# ADR-003 — Platform / ChatBI Responsibility Boundary

# 平台 / ChatBI 责任边界

## Status（状态）

Accepted（已接受）

## Context（背景）

Enterprise AI Platform（企业 AI 平台）和 ChatBI 都可能涉及：

- 用户；
- 模型；
- 会话；
- 状态；
- 执行；
- 权限。

如果责任边界不明确，会产生：

- Duplicate Capability（重复能力）；
- Double State（双重状态）；
- Double Authorization（双重权限体系）；
- Contract Conflict（契约冲突）。

## Decision（决定）

采用：

> **Platform owns generic platform capabilities.**

> **ChatBI owns domain capabilities and domain correctness.**

Platform（平台）负责：

- Authentication（身份认证）；
- Product Conversation（产品会话）；
- Model Gateway（模型网关）；
- API Gateway（接口网关）；
- Rate Limit / Quota（限流 / 配额）；
- Deployment（部署）；
- Platform Observability（平台可观测性）。

ChatBI 负责：

- Natural Language Query（自然语言查询）；
- Business Analysis（经营分析）；
- Business Semantics（业务语义）；
- Domain Authorization（领域授权）；
- Query Safety（查询安全）；
- Domain State Semantics（领域状态语义）；
- Business Evaluation（业务评估）。

## Consequences（影响）

ChatBI：

> 不重复建设企业通用 AI 平台。

Platform（平台）：

> 不替代 ChatBI 的领域正确性判断。

## Revisit When（重新评估条件）

当：

- Platform / ChatBI 产品边界发生变化；
- ChatBI 开始承担新的企业通用能力；
- 企业平台开始承担正式领域能力；

时重新评估。

------

# ADR-004 — Layered Architecture with Ports

# 分层架构与端口

## Status（状态）

Accepted（已接受）

## Context（背景）

ChatBI 依赖多种外部技术能力：

- LLM（大语言模型）；
- Database（数据库）；
- Vector Database（向量数据库）；
- Platform（平台）；
- State Store（状态存储）。

如果业务代码直接依赖具体供应商 SDK（软件开发工具包），将导致：

- Technology / Domain Coupling（技术 / 领域耦合）；
- Vendor Replacement Difficulty（供应商替换困难）；
- Testing Difficulty（测试困难）；
- Application Pollution（应用层被基础设施污染）。

## Decision（决定）

内部采用：

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

外部能力采用：

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

> 集中完成配置和依赖装配。

## Consequences（影响）

Domain（领域层）：

> 保持业务纯净。

Application（应用层）：

> 聚焦 Use Case / Orchestration（用例 / 编排）。

Infrastructure（基础设施层）：

> 负责供应商和具体技术实现。

## Revisit When（重新评估条件）

只有当当前 Layering（分层）已经无法满足：

- 系统边界；
- 依赖隔离；
- 模块演进；

并存在明确证据时重新评估。

------

# ADR-005 — Domain Owns Business Truth

# 领域拥有业务事实

## Status（状态）

Accepted（已接受）

## Context（背景）

Database Schema（数据库结构）、LLM Output（模型输出）、Retrieval Result（检索结果）：

> 都属于技术表现。

这些技术对象可以变化。

但是：

- Metric（指标）；
- Dimension（维度）；
- Business Rule（业务规则）；
- Business Meaning（业务含义）

必须保持稳定。

## Decision（决定）

业务事实由：

> **Domain（领域）**

拥有和定义。

不得由：

- Database Schema（数据库结构）；
- LLM Output（模型输出）；
- Retrieval Result（检索结果）

反向定义业务事实。

## Consequences（影响）

可以：

```
Replace Database
（替换数据库）

→ Keep Business Semantics
  （保持业务语义）


Replace Retrieval
（替换检索）

→ Keep Metric Definition
  （保持指标定义）
```

技术实现：

> 可替换。

业务定义：

> 保持稳定。

## Revisit When（重新评估条件）

只有当 Business Truth Ownership（业务事实所有权）本身发生领域建模变化时重新评估。

------

# ADR-006 — Authentication ≠ Domain Authorization

# 身份认证不等于领域授权

## Status（状态）

Accepted（已接受）

## Context（背景）

Authentication（身份认证）只能确认：

> **用户是谁。**

不能直接确认：

> **用户能够访问哪些经营数据。**

## Decision（决定）

Platform（平台）负责：

> Authentication（身份认证）。

ChatBI 负责：

> Domain Authorization（领域授权）。

Platform Role / Attribute（平台角色 / 属性）可以成为授权输入。

但：

> **Platform Role ≠ Final Data Scope（平台角色不等于最终数据范围）。**

## Consequences（影响）

ChatBI 可以根据领域规则决定：

- Business Domain（业务领域）；
- Metric（指标）；
- Dimension（维度）；
- Data Scope（数据范围）；
- Detail Access（明细权限）；
- Sensitive Data Access（敏感数据权限）。

## Revisit When（重新评估条件）

如果企业存在正式 Domain Authorization Service（领域授权服务），并明确承担当前 ChatBI 领域授权语义时：

> 重新评估授权责任边界。

------

# ADR-007 — Product Conversation ≠ Domain State

# 产品会话不等于领域状态

## Status（状态）

Accepted（已接受）

## Context（背景）

Chat Product（聊天产品）需要维护：

> Message History（消息历史）。

但 ChatBI 完成领域任务：

> 不一定需要完整聊天历史。

如果将两者混为一个状态系统：

- 状态边界不清；
- 平台和领域强耦合；
- 领域任务难以独立恢复；
- 会话内容容易污染业务状态。

## Decision（决定）

Platform（平台）拥有：

> **Product Conversation（产品会话）。**

ChatBI 拥有：

> **Domain State（领域状态）。**

Domain State（领域状态）只保存业务任务必要信息。

例如：

- Previous Query Semantic（上一轮查询语义）；
- Previous Result Reference（上一轮结果引用）；
- Pending Clarification（待澄清）；
- Analysis State（分析状态）。

## Consequences（影响）

避免：

> Product Conversation（产品会话）与 Domain State（领域状态）混成同一个状态模型。

ChatBI 可以独立控制：

> 领域状态的生命周期和语义。

## Revisit When（重新评估条件）

当平台正式提供可以完整表达 ChatBI Domain State Semantics（领域状态语义）的状态能力时：

> 可以重新评估状态所有权和存储边界。

------

# ADR-008 — Model Proposes, Program Decides

# 模型提出，程序裁决

## Status（状态）

Accepted（已接受）

## Context（背景）

LLM（大语言模型）输出具有概率性。

模型可以产生：

- Intent Candidate（意图候选）；
- SQL Candidate（SQL 候选）；
- Analysis Candidate（分析候选）。

但安全和权限不能依赖概率性判断。

## Decision（决定）

采用：

> **Model proposes, program decides.**
> **模型提出，程序裁决。**

模型负责：

> 提出 Candidate（候选）。

确定性程序负责最终判断：

- Authorization（授权）；
- Query Safety（查询安全）；
- Data Scope（数据范围）；
- SQL Execution Boundary（SQL 执行边界）；
- 其他安全关键规则。

## Consequences（影响）

安全关键路径必须存在：

> Deterministic Validation / Enforcement（确定性校验 / 强制执行）。

## Revisit When（重新评估条件）

除非底层安全模型和系统可信边界发生根本变化：

> 否则该原则长期保持。

------

# ADR-009 — Trusted Data Before Analysis

# 可信数据先于分析

## Status（状态）

Accepted（已接受）

## Context（背景）

Business Analysis（经营分析）需要多步骤分析和推理。

如果分析功能可以直接自由访问数据库：

> 会形成第二套数据查询体系。

可能导致：

- Metric Definition（指标口径）不一致；
- Authorization Logic（权限逻辑）重复；
- Query Safety（查询安全）重复；
- Business Result（业务结果）不可信。

## Decision（决定）

Business Analysis（经营分析）必须基于：

> **Trusted Query Result（可信查询结果）**

或：

> **Trusted Business Data（可信业务数据）**

完成。

稳定关系：

```
Natural Language Query
（自然语言查询）

        ↓

Trusted QueryResult
（可信查询结果）

        ↓

Business Analysis
（经营分析）

        ↓

AnalysisResult
（分析结果）
```

## Consequences（影响）

Business Analysis（经营分析）：

> 不建立绕过可信查询能力的第二套数据访问系统。

## Revisit When（重新评估条件）

如果未来出现其他同等可信、统一权限和统一业务语义的数据能力：

> 可以重新评估 Business Analysis（经营分析）的数据入口。

但必须继续满足：

> Trusted Data Before Analysis（可信数据先于分析）。

------

# ADR-010 — Contract Alignment First

# 契约对齐优先

## Status（状态）

Accepted（已接受）

## Context（背景）

External Platform（外部平台）与 ChatBI 可能存在：

- Protocol Difference（协议差异）；
- Data Model Difference（数据模型差异）；
- Semantic Difference（语义差异）。

可以直接增加 Adapter / Anti-Corruption Layer（适配器 / 防腐层）。

但如果双方可以统一 Contract（契约）：

> 额外适配层只会增加复杂度。

## Decision（决定）

采用：

> **Contract Alignment First（契约对齐优先）。**

只有存在真实不可消除差异时：

> **Adapter When Required（必要时才适配）。**

## Consequences（影响）

Platform Adapter（平台适配器）：

> 不是系统固定层。

避免：

> 为了架构模式本身创建没有实际价值的 Adapter（适配器）。

## Revisit When（重新评估条件）

当：

- 同时接入多个不同平台；
- 外部平台 Contract（契约）无法调整；
- 存在真实 Semantic Model Difference（语义模型差异）；
- 接入 Legacy System（遗留系统）；

时重新评估 Adapter / Anti-Corruption Layer（适配器 / 防腐层）。

------

# ADR-011 — Stable Core, Replaceable Edge

# 稳定核心，可替换边缘

## Status（状态）

Accepted（已接受）

## Context（背景）

ChatBI 使用的技术产品可能变化，例如：

- Model Provider（模型供应商）；
- Database（数据库）；
- Vector Database（向量数据库）；
- State Store（状态存储）；
- Platform（平台）。

如果 Domain Core（领域核心）绑定具体技术：

> 系统将难以演进。

## Decision（决定）

采用：

> **Stable Core, Replaceable Edge（稳定核心，可替换边缘）。**

保持：

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

## Consequences（影响）

技术 Adapter（适配器）：

> 应保持可替换。

稳定 Business Contract（业务契约）：

> 不依赖具体供应商。

## Revisit When（重新评估条件）

只有当某项基础设施能力成为不可替代的正式 Domain Capability（领域能力）时：

> 重新评估该边界。

------

# ADR-012 — Do Not Overbuild

# 不过度建设

## Status（状态）

Accepted（已接受）

## Context（背景）

企业系统设计容易提前建设：

> 未来“可能需要”的能力。

例如：

- Microservice（微服务）；
- Plugin Framework（插件框架）；
- Distributed Runtime（分布式运行时）；
- Complex State Platform（复杂状态平台）。

如果没有真实需求：

> 这些能力只会增加开发和维护成本。

## Decision（决定）

Architecture（架构）：

> 可以为未来演进保留边界。

但：

> **不因为未来可能需要，就在当前阶段提前实现。**

没有真实需求时，不提前建设：

- Microservice（微服务）；
- 大量空 Interface（接口）；
- 大量空 Adapter（适配器）；
- Plugin Framework（插件框架）；
- Distributed Runtime（分布式运行时）；
- Enterprise IAM（企业身份管理）；
- Complex State Platform（复杂状态平台）。

## Consequences（影响）

当前优先：

> **最小可运行业务闭环。**

然后根据：

- Feature Requirement（功能需求）；
- Evaluation（评估）；
- Bad Case（失败案例）；
- Performance Data（性能数据）；
- Production Requirement（生产需求）

决定下一步演进。

## Revisit When（重新评估条件）

当复杂能力已经由：

> **真实问题和证据证明需要**

时重新评估。

原则：

> Future Extensibility（未来可扩展性）不等于 Current Implementation（当前必须实现）。

------

# ADR-013 — Public Async API Deferred

# 对外异步接口延后

## Status（状态）

Accepted（已接受）

## Context（背景）

ChatBI 的 Natural Language Query（自然语言查询）和 Business Analysis（经营分析）可能涉及：

- LLM Call（大语言模型调用）；
- Retrieval（检索）；
- Database Query（数据库查询）；
- Multi-Step Processing（多步骤处理）。

这些操作具有大量 Network / I/O Waiting（网络 / 输入输出等待）。

因此内部实现可能需要：

> **Async I/O（异步输入输出）。**

例如：

```
await Model
（等待模型）

await Retrieval
（等待检索）

await Database
（等待数据库）
```

但：

```
Internal Async I/O
（内部异步输入输出）

        ≠

Public Async API
（对外异步任务接口）
```

Public Async API（对外异步接口）通常意味着：

```
Submit Run
（提交执行）

        ↓

Return Run ID
（返回执行编号）

        ↓

Background Execution
（后台执行）

        ↓

Status Query / Callback
（状态查询 / 回调）

        ↓

Result Retrieval
（结果获取）
```

这会额外引入：

- Persistent Run State（持久化执行状态）；
- Background Job（后台任务）；
- Run Status Query（执行状态查询）；
- Job Lifecycle（任务生命周期）；
- Retry / Recovery（重试 / 恢复）；
- Idempotency（幂等）；
- Queue / Worker（队列 / 工作进程）；
- Cancellation（取消）；
- Timeout / Expiration（超时 / 过期）；
- 更复杂的 State / Error Contract（状态 / 错误契约）。

当前 V1（第一版）的业务执行：

> 尚没有真实需求证明必须建设完整 Public Async Run（对外异步执行）体系。

当前典型任务仍可由：

- Blocking（阻塞）；
- SSE Streaming（服务器发送事件流式）

覆盖。

## Decision（决定）

ChatBI V1（第一版）：

> **不提供 Public Async API（对外异步任务接口）。**

Platform Integration V1（平台集成第一版）支持：

```
Blocking
（阻塞）

+

SSE Streaming
（服务器发送事件流式）
```

同时：

> **ChatBI 内部允许正常使用 Async I/O（异步输入输出）。**

因此：

```
Internal Async
（内部异步）
=
Implementation Concern
（实现问题）


Public Async API
（对外异步接口）
=
Integration / Architecture Concern
（集成 / 架构问题）
```

存在 LLM Call（大语言模型调用）：

> **本身不足以证明需要 Public Async API（对外异步接口）。**

## Consequences（影响）

V1（第一版）保持较简单的外部执行模型：

```
Platform
（平台）

        ↓

Run
（执行实例）

        ↓

Blocking / SSE
（阻塞 / 流式）

        ↓

Final Outcome
（最终结果）
```

当前不需要为了 Public Async API（对外异步接口）提前建设：

- Persistent Job Queue（持久化任务队列）；
- Public Run Status API（公开任务状态接口）；
- Background Job Lifecycle（后台任务生命周期）；
- Callback Completion（完成回调）；
- Distributed Worker（分布式工作进程）；
- Persistent Task Recovery（持久化任务恢复）。

Internal Async I/O（内部异步输入输出）：

> 仍然可以正常使用。

Blocking / SSE（阻塞 / 流式）：

> 不改变 Domain Authorization（领域授权）、Query Safety（查询安全）、Business Correctness（业务正确性）和 Result Semantics（结果语义）。

## Revisit When（重新评估条件）

出现以下任一真实需求时：

> 重新评估 Public Async API（对外异步接口）。

### Long-Running Task（长任务）

单次 Run（执行实例）经常达到：

> 不适合持续保持 HTTP / SSE Connection（HTTP / SSE 连接）的时长。

例如：

> 分钟级 Business Analysis（经营分析）。

------

### Disconnect-and-Continue（断线继续执行）

出现：

```
Client Disconnect
（客户端断开）

        ↓

Run Continues
（执行继续）

        ↓

User Returns Later
（用户稍后返回）

        ↓

Retrieve Result
（获取结果）
```

需求。

------

### Background Execution（后台执行）

用户需要：

> 提交任务后退出当前页面或客户端，业务执行继续完成。

------

### Run Status Query（执行状态查询）

Platform（平台）需要查询正式 Persistent Run State（持久化执行状态），例如：

```
queued
（排队）

running
（执行中）

completed
（完成）

failed
（失败）

cancelled
（取消）
```

------

### Recovery / Resume（恢复 / 继续）

业务执行需要：

- Process Restart Recovery（进程重启恢复）；
- Durable Checkpoint（持久化检查点）；
- Long-Running Workflow Resume（长工作流恢复）。

------

### Callback / Webhook（回调）

Platform（平台）需要：

> Run（执行实例）完成后由 ChatBI 主动通知，而不是持续保持连接。

------

当上述真实需求出现时：

> 通过新的 Platform Integration Contract Version（平台集成契约版本）设计 Public Async Run API（对外异步执行接口）。

不得通过：

> 临时修改当前 Blocking / SSE Contract（阻塞 / 流式契约）

隐式加入异步任务语义。

------

# 4. Decision Change Rule（决策变更规则）

Accepted ADR（已接受架构决策）：

> 原则上不直接删除。

未来决策发生变化时：

```
Old ADR
（旧决策）

Status = Superseded
（已替代）

        ↓

New ADR
（新决策）

Status = Accepted
（已接受）
```

新 ADR 必须说明：

- 为什么旧决策不再适用；
- 出现了什么新条件；
- 新 Decision（决定）是什么；
- 新方案的 Consequences / Trade-Off（影响 / 权衡）是什么。

原则：

> **ADR 保留 Architecture Evolution History（架构演进历史）。**

------

# 5. What Requires an ADR（什么需要架构决策记录）

通常需要 ADR（架构决策记录）的变化：

- System Positioning（系统定位）；
- Architecture Style（架构形态）；
- System Boundary（系统边界）；
- 一级 Responsibility Boundary（责任边界）；
- Technical Layering（技术分层）；
- Critical Dependency Direction（关键依赖方向）；
- State Ownership（状态所有权）；
- Security Responsibility（安全责任）；
- Integration Execution Model（集成执行模型）；
- 难以撤销或影响范围较大的技术战略。

例如：

```
Modular Monolith
→ Microservice
```

需要 ADR。

```
Blocking / SSE
→ Durable Public Async Run
```

通常也需要 ADR。

------

通常不需要 ADR 的变化：

- 修改 Function（函数）；
- 新增普通 Class（类）；
- 修改 Prompt（提示词）；
- 修改 Retrieval Top-K（检索前 K 个）；
- 更换局部 Algorithm（算法）；
- 新增普通 Metric（指标）；
- 修改 Test / Evaluation（测试 / 评估）；
- 修复 Bug；
- 普通 Code Refactor（代码重构）。

这些由对应：

- Feature Spec（功能规格）；
- Module Spec（模块规格）；
- Engineering（工程）；
- Implementation（实现）

处理。

------

# 6. ADR vs Roadmap（架构决策与路线图）

Architecture Decision Record（架构决策记录）：

> **记录当前已经做出的架构决定，以及重新评估条件。**

Roadmap / Evolution Plan（路线图 / 演进计划）：

> **描述未来准备实现什么以及实施顺序。**

两者不得混淆。

例如：

```
当前不使用 Microservice
出现独立扩缩容后重新评估
```

属于：

> ADR。

而：

```
下一阶段拆 User Service
再下一阶段拆 Query Service
```

属于：

> Roadmap。

同样：

```
V1 不提供 Public Async API
出现长任务后重新评估
```

属于：

> ADR。

而：

```
V2 一定开发 Public Async API
```

属于：

> Roadmap。

原则：

> **Revisit Condition（重新评估条件）不是 Future Commitment（未来承诺）。**

------

# 7. Architecture Decision Baseline（架构决策基线）

当前 ChatBI 系统级架构选择：

> **Domain AI Engine（领域 AI 引擎），而不是 Enterprise AI Platform（企业 AI 平台）。**

> **Modular Monolith（模块化单体），而不是提前 Microservice（微服务）。**

> **Platform owns generic capabilities; ChatBI owns domain correctness.**
> **平台负责通用能力，ChatBI 负责领域正确性。**

> **Layered Architecture with Ports（分层架构与端口）。**

> **Domain Owns Business Truth（领域拥有业务事实）。**

> **Authentication ≠ Domain Authorization（身份认证不等于领域授权）。**

> **Product Conversation ≠ Domain State（产品会话不等于领域状态）。**

> **Model proposes, program decides（模型提出，程序裁决）。**

> **Trusted Data Before Analysis（可信数据先于分析）。**

> **Contract Alignment First（契约对齐优先）。**

> **Stable Core, Replaceable Edge（稳定核心，可替换边缘）。**

> **Do Not Overbuild（不过度建设）。**

> **Internal Async I/O ≠ Public Async API（内部异步输入输出不等于对外异步任务接口）。**

> **Public Async API（对外异步接口）在 V1 延后，直到出现真实长任务、后台执行、断线继续、状态查询或任务恢复需求。**

最终原则：

> **Architecture（架构）描述当前稳定结构。**

> **ADR（架构决策记录）保存为什么这样设计，以及何时重新评估。**

> **ADR 保留演进可能性，但不提前承诺未来架构。**

------


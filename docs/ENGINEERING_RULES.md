# ChatBI Architecture

> Status: **Frozen Design Baseline**
>
> 本文档只定义 ChatBI 的稳定架构骨架：系统定位、核心业务链、核心对象、模块与分层、依赖方向、架构不变量，以及与外部模型、数据、身份、状态和平台的可替换边界。
>
> 本文档描述的是 ChatBI 必须长期保持的架构约束，不规定某个 Feature 的具体实现顺序、模型调用次数、检索算法、框架 API、部署产品或基础设施组合。
>
> 资料状态：当前资料证明的是业务与架构设计目标，不等同于已实现、已验证或生产就绪。

# 1. 系统定位与范围

```
ChatBI = Domain AI Engine Service（领域 AI 引擎服务）
内部 = Modular Monolith（模块化单体）
```

ChatBI 的核心职责是：

> 把自然语言业务问题转换为可验证的业务查询，并在业务语义、权限、安全和数据边界都通过后，返回具有业务含义和追溯信息的可信结果。

企业视角：

```
Enterprise AI Platform / Enterprise Infrastructure
                      ↓
          ChatBI Domain AI Engine Service
```

当前内部形态：

```
一个代码仓库
+
一个主要应用
+
一个主要部署单元
+
内部按稳定能力划分模块
```

当前不因“以后可能需要生产平台”而提前拆分微服务。

是否拆分，应由真实证据触发，例如：

```
独立扩缩容需求
独立部署需求
明确团队边界
运行压力
故障隔离需求
```

而不是因为理论上的未来可能性。

## 1.1 Owner 边界

| Owner              | ChatBI 负责的内容                                            |
| ------------------ | ------------------------------------------------------------ |
| **Engine Owned**   | Trusted Query、SemanticQuery、业务主题、业务校验、领域授权、Data Scope、SQL Guard、QueryResult、Evidence、Analysis、Engine State 不变量、Evaluation 与 Bad Case |
| **Contract Owned** | PrincipalContext、DomainAccessContext、ModelGateway、BusinessDataSource、State / Checkpoint / Conversation Store、ThreadRunGate、DurableRuntime、AuditSink、Telemetry Export、外部配置 |
| **Platform Owned** | 企业认证与用户目录、API 流量治理、模型密钥 / 预算 / 路由、Secret、部署与弹性、可观测性后端、高可用、备份和灾备 |

核心规则：

> **ChatBI 拥有领域正确性和必要合同；依赖合同，不依赖某个企业平台、基础设施产品或供应商的具体实现。**

换句话说：

```
业务核心稳定
+
外部实现可替换
```

即：

```
Stable Core
+
Replaceable Edge
```

# 2. 核心业务链

## 2.1 顶层能力路由

ChatBI 先判断请求属于哪种能力，再进入相应 Workflow：

```
User Question
    ↓
Capability Router
    ├── Trusted Query（P1）
    ├── Business Analysis（P2）
    └── Other / Out of Scope
```

Capability Router 只负责：

```
判断请求应该进入哪种业务能力
```

不负责：

```
生成完整 SemanticQuery
生成 SQL
生成 Analysis Plan
执行数据库查询
```

能力路由本身不能成为第二套业务逻辑。

# 2.2 P1 Trusted Query 主链

P1 的稳定业务链为：

```
Natural Language
        ↓
Semantic Resolution
    ├── Structured Intent
    ├── Semantic Context / Retrieval
    ├── Business Semantic Resolution
    └── Clarification when needed
        ↓
SemanticQuery
        ↓
Deterministic Business Validation
        ↓
Domain Authorization / Data Scope
        ↓
SQL Generation
        ↓
Deterministic SQL Guard
        ↓
Read-only BusinessDataSource
        ↓
Result Validation
        ↓
QueryResult
        ↓
Persist / Reference Result
and Update Engine Context
when required by Feature
```

其中：

> **Semantic Resolution 是逻辑阶段，不规定内部组件的严格运行顺序。**

因此以下实现都可以成立：

```
Intent
→ Retrieval
→ SemanticQuery
```

也可以：

```
Initial Retrieval
→ Intent
→ Additional Context
→ SemanticQuery
```

也可以：

```
Rule Resolution
+
Model Candidate
+
Semantic Context
→ SemanticQuery
```

还可以根据未来实现采用其他组合。

Architecture 只要求：

> **进入后续可信查询链之前，系统必须形成一个经过权威业务语义收敛、并能够进行确定性校验的 SemanticQuery。**

具体：

```
先 Intent 还是先 Retrieval
是否多阶段 Retrieval
是否 Query Rewrite
是否规则优先
是否使用模型
使用几次模型
使用哪种模型
```

均属于：

```
Feature Spec
POC
Implementation
Reference
ADR（必要时）
```

而不是核心架构不变量。

## 2.2.1 P1 关键状态

```
语义或必要信息不足
→ CLARIFY

超出当前业务能力范围
→ REJECT

业务存在但主体无权访问
或违反 Data Scope / Security
→ DENY

技术或不可恢复失败
→ FAILED

可信查询完整成功
→ SUCCESS
→ QueryResult
```

这些状态必须保持不同业务含义。

## 2.2.2 Semantic Resolution 原则

Semantic Resolution 可以使用：

```
确定性规则
指标别名匹配
业务目录
Semantic Resource
Retrieval
LLM
历史 Engine Context
已验证 Example
其他可替换实现
```

但任何实现都不能改变以下原则：

### StructuredIntent

StructuredIntent 表达：

```
用户原始查询意图
候选指标
候选维度
过滤表达
时间表达
查询动作
比较意图
上下文引用
```

它只是语义理解过程中的结构化表达。

它不是：

```
最终业务事实
最终权限决定
SQL
物理数据库结构
```

### SemanticContext

SemanticContext 提供与本次查询相关的权威业务信息，例如：

```
指标定义
业务规则
认证主题 Schema
允许维度
时间规则
已验证 Example
必要 Policy
```

Retrieval 只是获得 SemanticContext 的一种实现方式。

SemanticContext 不绑定：

```
Vector Database
BM25
Hybrid Search
Rerank
Embedding Model
具体检索产品
```

### SemanticQuery

SemanticQuery 是：

> **已经确认的业务查询含义。**

只有 SemanticQuery 达到当前 Feature 所要求的完整程度，并经过确定性业务校验后，才能进入后续执行阶段。

## 2.2.3 模型边界

模型可以参与：

```
自然语言理解
StructuredIntent 候选生成
语义候选生成
歧义识别
SQL 候选生成
有限修复
结果解释
```

但：

> **模型输出始终是不可信候选。**

模型不能最终决定：

```
企业业务口径
Metric 定义
权限
Data Scope
安全放行
SQL 是否允许执行
```

最终业务语义必须受：

```
Authoritative Semantic Context
+
Deterministic Business Validation
```

约束。

权限与 Data Scope 必须由：

```
Deterministic Domain Authorization
```

裁决。

SQL 是否能够执行必须由：

```
Deterministic SQL Guard
+
Read-only BusinessDataSource
```

裁决。

因此 Architecture 不规定：

```
第一次模型调用做什么
第二次模型调用做什么
模型调用几次
```

模型调用策略属于具体 Feature 和实现。

## 2.2.4 SQL Generation

P1 当前允许：

```
受约束模型生成 SQL Candidate
```

未来也可以演进为：

```
SemanticQuery
↓
Deterministic Compiler
↓
SQL
```

或者：

```
Compiler
+
LLM Assisted Generation
```

但无论具体 SQL Generation 如何变化：

```
SemanticQuery
```

不能因此消失。

SQL Generation 也不能绕过：

```
Business Validation
Domain Authorization
Data Scope
```

## 2.2.5 SQL Execution

任何 SQL Candidate 必须经过：

```
Deterministic SQL Guard
```

之后才允许进入：

```
Read-only BusinessDataSource
```

模型输出永远不能直接访问业务数据库。

# 2.3 P2 Analysis 关系

P2 Business Analysis 的稳定关系：

```
Analysis Goal / Plan
        ↓
构造或复用 SemanticQuery
        ↓
Trusted Query × N
        ↓
QueryResult / Evidence
        ↓
Analysis Result / Report
```

P2 负责：

```
趋势分析
拆解
贡献定位
原因验证
Evidence 组织
分析表达
```

但 P2 不允许：

```
Analysis
→ 自己生成 SQL
→ 直接访问 BusinessDataSource
```

因此：

> **P1 是可信事实获取能力。**

> **P2 是建立在可信事实之上的分析能力。**

P1 与 P2 不是两套独立的数据访问链。

# 2.4 运行模式关系

```
P1
=
交互式请求 / 响应
可以流式
外部 I/O 可异步

P2
=
当需要长时间、多次查询、
等待输入或中断恢复时，
可以采用异步或持久执行
```

运行模式可以演进。

但：

```
业务对象
SemanticQuery
QueryResult
权限边界
Trusted Query Contract
```

不能因为：

```
Queue
Worker
Temporal
LangGraph
Redis
Kubernetes
```

等具体运行实现发生变化而改变。

# 3. 核心对象

以下对象是跨入口、Workflow 和未来实现仍应保持稳定含义的最小集合。

字段细节由：

```
Domain
Feature Spec
Implementation Contract
```

决定。

| 对象                   | 稳定含义                                                     | 明确不包含                                          |
| ---------------------- | ------------------------------------------------------------ | --------------------------------------------------- |
| `StructuredIntent`     | Semantic Resolution 中对用户查询动作、指标 / 维度 / 过滤 / 时间等原始表达和上下文信息的结构化表示 | 物理表名、物理列名、最终权限决定、SQL               |
| `SemanticContext`      | 本次查询所需的权威业务语义、认证数据模型、业务规则和必要 Example | 某一种检索产品或向量数据库实现                      |
| `SemanticQuery`        | 已确认的企业业务查询含义：指标、维度、粒度、时间、过滤、比较、排序和查询方式 | 数据库连接、物理表 / 列、SQL 字符串                 |
| `PrincipalContext`     | 外部身份来源向 ChatBI 提供的主体、租户、组织 / 角色 / Claims 和追踪上下文 | ChatBI 最终业务授权结论                             |
| `DomainAccessContext`  | ChatBI 根据主体和领域规则形成的业务访问边界，例如可访问主题、指标、维度、区域、敏感等级和明细权限 | 外部平台 Role 的简单复制                            |
| `QueryResult`          | 一次成功可信查询产生的业务结果，包括 SemanticQuery、数据、业务元信息、警告、范围说明和必要追溯引用 | 澄清、拒绝、失败、完整会话、完整 Prompt、完整 Trace |
| `EngineExecutionState` | 当 Feature 需要跨步骤、跨轮、恢复或 Analysis State 时，ChatBI 必须维护的语义执行状态 | Product Conversation 的全部 UI 能力                 |
| `Evidence`             | P2 对 QueryResult 或其他被允许可信事实的引用和证据表达       | 绕过 Trusted Query 的原始 SQL 数据访问              |
| `AnalysisResult`       | 基于可信 Evidence 形成的业务分析结果                         | 绕过 Trusted Query 自行访问 BusinessDataSource      |

# 3.1 Semantic 资源边界

当前最小稳定 Semantic Resource 集合：

```
指标业务口径
认证主题 Schema 与主题规则
已验证查询 Example
```

业务口径由：

```
Domain
Semantic Resource
```

维护。

而：

```
文件读取
索引
Embedding
Retrieval
Storage
```

属于 Infrastructure。

资源版本应该能够被 QueryResult 或运行元数据追溯。

但以下内容不属于核心架构：

```
资源必须是 JSONL 还是 YAML
是否使用 Vector Database
是否使用 BM25
是否使用 Hybrid
是否使用 Rerank
使用什么 Embedding Model
```

# 3.2 QueryResult 语义

`QueryResult` 只表示：

> **一次成功完成的可信查询。**

至少满足：

```
SemanticQuery 已确定
↓
业务校验已通过
↓
领域授权已通过
↓
Data Scope 已落实
↓
SQL Guard 已通过
↓
只读 BusinessDataSource 执行成功
↓
Result Validation 已完成
```

才允许产生：

```
QueryResult
```

因此：

```
CLARIFY
REJECT
DENY
FAILED
```

不能伪装成 QueryResult。

外层响应负责表达：

```
SUCCESS
CLARIFY
REJECT
DENY
FAILED
```

成功业务数据和流程状态必须保持清晰边界。

# 4. 模块职责与分层

## 4.1 业务模块

| 模块                | 职责                                                         |
| ------------------- | ------------------------------------------------------------ |
| **Query**           | 统一 Trusted Query 能力，负责从确认的业务查询得到可信结果    |
| **Semantic**        | 指标口径、语义收敛、SemanticQuery 和相关上下文               |
| **Business Topics** | Sales 等业务主题的指标、维度、粒度和主题规则；Sales 是首个主题，不是系统结构的写死前提 |
| **Security**        | 功能权限、领域授权、敏感数据权限、Data Scope 和 SQL Guard Policy |
| **State / Result**  | EngineExecutionState、Checkpoint 业务语义、QueryResult、Result Reference 和跨轮上下文 |
| **Analysis**        | P2 分析编排，通过 Query 和 QueryResult 形成 Evidence / AnalysisResult |
| **Evaluation**      | Golden Dataset、分层 AI Evaluation、Bad Case 和质量反馈闭环  |

# 4.2 技术分层

```
Interfaces
    ↓
Application
    ↓
Domain


Application
    ↓
Ports / Contracts


Infrastructure
    ── implements ──>
Ports / Contracts


Bootstrap
    ↓
Assemble Concrete Implementations
```

| 层               | 责任                                                         | 不负责                                                |
| ---------------- | ------------------------------------------------------------ | ----------------------------------------------------- |
| `Interfaces`     | HTTP、CLI、UI 等入口的输入输出和协议转换                     | 业务规则、指标口径、SQL Generation、完整 Workflow     |
| `Application`    | Use Case、Workflow、路由、分支、状态编排、调用 Port、有限恢复 | 具体模型 / 数据库 SDK 的技术细节                      |
| `Domain`         | Metric、Dimension、TimeRange、Filter、Grain、SemanticQuery、主题规则、业务校验、领域授权 | LLM、数据库、Web Framework、文件系统、Vector Database |
| `Infrastructure` | Model、Retrieval、BusinessDataSource、State / Checkpoint、SQL AST、文件、Telemetry 等 Adapter | 销售额口径、毛利公式、领域分析规则                    |
| `Bootstrap`      | 创建 Adapter、注入依赖、组装应用                             | 业务逻辑                                              |

# 4.3 依赖规则

必须保持：

```
Interfaces
↓
Application
↓
Domain
```

并遵守：

1. Domain 不得依赖 Infrastructure。
2. Domain 不导入具体模型、数据库、Web Framework、检索产品或平台 SDK。
3. Interfaces 不得绕过 Application 直接执行完整业务链。
4. Application 通过 Port / Contract 使用外部能力。
5. Infrastructure 提供具体 Adapter 实现。
6. Bootstrap 负责具体对象装配。
7. Prompt 的任务编排属于 Application。
8. 业务知识属于 Domain / Semantic Resource。
9. 模型调用协议属于 Infrastructure / ModelGateway。
10. SQL 的业务语义校验与 SQL 技术安全校验必须分开。

前者属于：

```
Domain / Application
```

后者可以由：

```
Infrastructure
+
SQL AST
+
Database Policy
```

实现。

# 5. 必须保持的架构不变量

## 1. 可信结果的前置条件不变

没有：

```
确定的 SemanticQuery
确定性 Business Validation
Domain Authorization
Data Scope
SQL Guard
成功的只读执行
Result Validation
```

就不能产生正式：

```
QueryResult
```

## 2. 模型不是最终裁判

LLM 可以：

```
理解
提取
生成 Candidate
修复 Candidate
辅助解释
```

但不能最终决定：

```
业务口径
权限
Data Scope
安全放行
```

核心原则：

> **Model proposes, deterministic mechanisms decide.**

## 3. Analysis 不绕过 Query

P2 只能通过：

```
Trusted Query
```

获取业务事实。

禁止：

```
Analysis
→ Generate SQL
→ BusinessDataSource
```

形成第二条数据访问链。

## 4. 业务语义与物理结构分离

`SemanticQuery` 不保存：

```
数据库表
数据库列
数据库连接
SQL 字符串
```

数据库物理映射变化不应该迫使：

```
业务语义
Workflow
Application
```

重写。

## 5. 业务数据默认只读且受认证模型约束

BusinessDataSource 默认：

```
Read-only
+
Certified Business Model Only
```

具体硬限制由：

```
DataSource Adapter
Database Account
Database Policy
```

落实。

## 6. 权限必须确定性执行

以下内容不能只存在 Prompt：

```
功能权限
敏感数据权限
Metric 权限
Dimension 权限
Data Scope
Detail Access
```

越权必须：

```
DENY
```

禁止为了让查询成功而：

```
静默修改用户问题
缩小数据范围
换 SQL 绕过权限
```

## 7. 成功状态与失败状态分离

```
CLARIFY
REJECT
DENY
FAILED
```

不得污染：

```
last_successful_semantic_query
last_result_id
其他成功上下文
```

只有成功完成的可信查询才能更新成功状态。

## 8. Engine State 规则按 Feature 需要启用

`EngineExecutionState` 是稳定的架构概念。

但：

> **并非所有 Feature 都必须立即实现跨请求状态、Checkpoint 或持久化。**

当 Feature 只需要：

```
一次请求
一次响应
无跨请求语义状态
```

时：

```
局部运行状态
```

即可满足当前 Feature。

不因此要求提前建设：

```
Persistent StateStore
Checkpoint
ThreadRunGate
Distributed Lock
Redis
Durable Runtime
```

当 Feature 开始引入：

```
跨请求 Thread State
连续追问
Clarification Resume
Checkpoint
中断恢复
Analysis Durable State
```

时，必须遵守：

```
同一 Thread 的可修改状态
按业务顺序执行

不同 Thread
能够独立并发
```

当权威状态需要：

```
跨进程
重启恢复
多实例共享
```

时：

> **不得仅保存在单个进程内存中。**

## 9. Product Conversation 不等于 Engine State

外部平台可以拥有：

```
聊天 UI
聊天标题
聊天列表
收藏
分享
完整消息历史
```

但这些不能替代 ChatBI 所需要的：

```
SemanticQuery
QueryResult
pending clarification
checkpoint semantics
analysis state
必要 result reference
```

完整 Product Conversation 可以由外部 AI Platform 管理。

ChatBI 仍必须掌握完成 Trusted Query 所需的最小 Engine Context。

## 10. 外部实现可替换

以下能力必须只能通过边界进入核心：

```
入口
模型供应商
Retrieval 实现
数据库产品
State Store
Checkpoint
Durable Runtime
Audit
Telemetry
企业平台
```

不得因为替换某个产品而重写：

```
Domain
SemanticQuery
Trusted Query
QueryResult
业务规则
```

# 6. 必要的外部边界

# 6.1 Identity：Authentication 与 Domain Authorization 分离

稳定关系：

```
External Authentication
        ↓
PrincipalContext
        ↓
ChatBI Domain Authorization
        ↓
DomainAccessContext
```

外部平台负责：

```
你是谁？
```

例如未来可能提供：

```
subject_id
tenant_id
organization
roles
groups
claims
trace context
```

ChatBI 负责：

```
你能使用什么 BI 能力？
你能访问哪些 Topic？
你能访问哪些 Metric？
你能访问哪些 Dimension？
你能访问哪些区域？
你能否访问敏感指标？
你能否查看 Detail？
```

因此：

```
Authentication
≠
Domain Authorization
```

ChatBI 不在核心内部建设：

```
账号密码
SSO
MFA
企业用户目录
```

## 6.1.1 MVP Authorization

P1 MVP 不需要企业 IAM。

当前可以使用：

```
最小 PrincipalContext
+
最小 DomainAccessContext
```

甚至：

```
单用户 Local Development Principal
```

但：

> **Domain Authorization 这个逻辑阶段不能从 Trusted Query 主链消失。**

当前最小 DomainAccessContext 只需要表达：

```
当前允许的 Business Topic
当前允许的 Metric
当前允许的 Dimension
当前数据范围
当前 Detail Access
```

即可。

不需要提前建设：

```
RBAC Platform
Permission Database
Keycloak
Enterprise IAM
SSO
Policy Server
```

未来接 AI Platform / IAM 时，只替换：

```
External Identity Adapter
```

以及必要映射。

ChatBI 内部的 Domain Authorization 语义保持不变。

## 6.1.2 REJECT 与 DENY

两者必须区分。

例如：

```
用户查询 HR 工资
但 ChatBI 当前不存在 HR Topic
```

属于：

```
REJECT
```

因为：

```
业务能力不支持
```

如果：

```
Sales Topic 存在
Sales Cost Metric 存在
但当前主体无权查看 Sales Cost
```

属于：

```
DENY
```

因为：

```
业务存在
但当前主体没有访问权限
```

# 6.2 Model：模型调用可替换

Application 依赖：

```
ModelGateway
```

所表达的能力，例如：

```
结构化输出
普通生成
超时
取消
可重试错误
Usage Metadata
```

Application 不依赖：

```
DeepSeek
OpenAI
Qwen
Higress
Provider URL
API Key
Provider Header
供应商 SDK
```

具体实现：

```
Direct Provider
Higress AI Gateway
LiteLLM
Company Model Platform
Other Model Gateway
```

均属于 Adapter。

模型输出始终视为：

```
Untrusted Candidate
```

不能因为使用“更强模型”而跳过后续确定性验证。

# 6.3 Data：状态数据与业务数据分离

稳定关系：

```
ChatBI-owned State Store
    ├── Engine State
    ├── QueryResult
    ├── AuditEvent
    └── optional Product Conversation


BusinessDataSource
    └── Certified Business Data
        ChatBI Read-only
```

ChatBI 拥有：

```
Engine State 的业务语义
QueryResult 的业务语义
Evidence 的业务语义
```

ChatBI 不拥有企业数据平台的：

```
ETL
原始数据加工
企业级 Data Quality Platform
数据调度
底层 Raw Table 生命周期
```

业务数据接入未来应能够提供：

```
Certified Model
Data Version / Data As Of
Freshness
Quality Status
```

具体形式由 Integration / Data Platform 决定。

# 6.4 State：状态能力可替换并按 Feature 启用

ChatBI 规定：

> **当某个 Feature 需要状态时，必须保存什么业务语义。**

例如可能包括：

```
last_successful_semantic_query
last_result_id
pending_clarification
current_workflow_state
checkpoint semantics
analysis state
```

具体底层：

```
StateStore
CheckpointStore
ConversationContextStore
```

可以由：

```
Standalone Implementation
Database
Framework Adapter
Enterprise AI Platform
其他平台服务
```

实现。

引擎不得依赖：

```
某个 Workflow Framework 的私有表结构
某个 State 产品的内部 Schema
```

完整聊天历史可以由外部产品拥有。

但 Trusted Query 所需的：

```
最小 Engine Context
```

必须能够获得。

当前不需要跨请求 State 的 Feature：

> **不要求为了满足架构而提前建设 StateStore、Checkpoint 或 ThreadRunGate。**

当 Feature 或运行环境真正要求：

```
跨请求恢复
重启恢复
多实例共享
并发修改控制
```

时，再落实相应 Contract 和 Adapter。

# 6.5 Runtime / Platform：核心只依赖合同

运行环境最终应能够提供：

```
外部配置
Timeout
Cancellation
Bounded Retry
Health
State Externalization
必要的 Durable Execution
```

但具体：

```
API Gateway
Queue
Worker
Redis
Cache
Kubernetes
HPA
Service Mesh
Observability Backend
Deployment Topology
Release Platform
```

不属于核心 Architecture。

只有 Feature 或真实运行需求证明需要以后，再实现。

# 6.6 Telemetry / Audit

ChatBI 应能够产生必要的结构化运行信息，例如：

```
request_id
run_id
thread_id
model
prompt_version
semantic_version
status
latency
error_type
result_id
```

以及必要 Audit Event。

ChatBI 通过：

```
Telemetry Export
AuditSink
```

等 Contract 输出。

未来可以接：

```
OpenTelemetry
Langfuse
Phoenix
Grafana
Company Observability
Enterprise AI Platform
```

但 ChatBI 不依赖某个具体 Monitoring Backend。

# 7. 质量与证据边界

Architecture 规定质量证据类型，但不在这里锁定具体工具、框架和阈值。

```
Software Tests
    ↓
证明代码按照 Contract 运行


AI Evaluation
    ↓
证明状态、语义、Retrieval、
SQL、安全和结果行为正确


Business Acceptance
    ↓
证明真实业务问题和 Domain Rule
得到正确满足
```

错误处理使用稳定顶层状态：

```
SUCCESS
CLARIFY
REJECT
DENY
FAILED
```

外部调用必须具备：

```
Timeout
```

只有明确可判定的临时错误才允许：

```
Bounded Retry
```

模型生成错误可以根据 Feature Spec：

```
有限修复
```

但真正：

```
权限拒绝
Data Scope 拒绝
SQL Safety 拒绝
```

不得通过：

```
换一条 SQL
重新 Prompt
换模型
```

进行规避。

# 7.1 Evaluation 原则

Evaluation 必须从 MVP 开始存在。

开发循环：

```
Baseline
↓
Change
↓
Evaluation
↓
Compare
↓
Regression
↓
Bad Case
↓
Fix
```

最低应能够验证：

```
Expected Status
Expected Semantic Behavior
Expected Business Result
SQL Safety
Business Correctness
```

核心原则：

> **ChatBI 最核心的生产能力首先是正确性，而不是基础设施复杂度。**

# 8. P1 / P2 与文档边界

```
Architecture
    ↓
定义稳定骨架、边界和不变量


Domain / Topic
    ↓
定义业务事实、口径和规则


Feature Spec
    ↓
定义当前阶段支持什么、
拒绝什么以及如何验收


Code
    ↓
实现 Feature Spec


Test / Evaluation
    ↓
证明实现正确


Integration / Reference
    ↓
定义如何接入具体环境、
产品或技术组合


ADR
    ↓
记录稳定的跨模块取舍及理由
```

当前 P1 / P2 关系只在架构层保持：

### P1

```
完成可验证的 Trusted Query 闭环
```

具体：

```
支持哪些指标
支持哪些维度
时间行为
Clarification 行为
Comparison 行为
Detail 行为
```

由：

```
P1 Feature Spec
+
Domain
```

定义。

### P2

```
在 P1 QueryResult / Evidence 之上
构建 Business Analysis
```

不重新发明数据访问链。

### POC

POC 用于验证高风险实现选择，例如：

```
Retrieval
SQL Generation
Runtime
State
```

POC 结果不会自动升级为：

```
Architecture Commitment
```

需要稳定成为跨 Feature 不变量时，再通过 Architecture / ADR 收口。

# 9. 本文档明确不包含的内容

以下内容不进入核心 `ARCHITECTURE.md`：

## Platform Integration Implementation

```
HiMarket
Higress
Company AI Platform
具体 Northbound API 字段全集
具体企业 IAM 配置
API Gateway 配置
Model Gateway 配置
```

## Deployment / Scale Implementation

```
Kubernetes
Helm
HPA
RabbitMQ
Kafka
Temporal
Redis / Redis HA
Worker Lease
Heartbeat
Transactional Outbox
Canary Traffic Control
CI/CD
HA
Backup
Disaster Recovery
```

## Observability Implementation

```
OTel Collector
Trace Backend
Metric Backend
Log Backend
Dashboard
Alert Platform
Grafana Deployment
```

## Retrieval Implementation

```
Vector
BM25
Hybrid
Rerank
Embedding
Vector Database
Index Product
具体 Retrieval POC
```

## Database Implementation

```
具体数据库产品
Connection Pool 参数
Migration Script
Checkpoint Table Schema
Database Account 配置
底层 Data Platform 部署
```

## Workflow Framework Implementation

```
LangGraph 私有 API
节点拆分
框架内部 State Schema
RetryPolicy 参数
Checkpoint 私有表结构
部署组合
```

## Feature 级业务细节

例如：

```
P1 具体指标公式
销售字段名
销售主题事实
Acceptance Cases
Golden Dataset
Prompt 内容
实现代码
```

这些内容不是删除。

而是：

> **按照变化原因放到正确的 Source of Truth。**

核心 Architecture 只保留它们必须遵守的 Contract 和不变量。

# 10. 相关 Source of Truth

| 内容                                       | 维护位置                                             |
| ------------------------------------------ | ---------------------------------------------------- |
| 产品目标与阶段路线                         | `10-product/*`                                       |
| 业务建模与销售业务真相                     | `20-domain/*`                                        |
| Trusted Query 详细 Workflow                | `30-engine/02-trusted-query-engine.md`               |
| Semantic / Data Contract 与资源细节        | `30-engine/03-semantic-and-data-contracts.md`        |
| Engine State 与持久化细节                  | `30-engine/04-state-context-and-persistence.md`      |
| Domain Security 与 SQL Guard 细节          | `30-engine/05-domain-security.md`                    |
| Quality、Evaluation、Bad Case、Error Model | `30-engine/06-quality-and-reliability.md`            |
| Runtime Contract                           | `30-engine/07-engine-runtime-contract.md`            |
| 外部平台接入 Contract                      | `40-integration/01-platform-integration-contract.md` |
| 当前阶段行为与 Acceptance                  | `50-specs/*`                                         |
| 本地 / OSS / 企业技术组合                  | `80-reference/*`                                     |
| 稳定跨模块决策                             | `90-adr/*`                                           |

这些路径是资料职责边界。

不要求新项目第一天创建全部文件。

> **只有当真实内容出现时，再创建相应 Source of Truth。**

禁止为了目录完整而提前生成大量空文档。

# 10.1 新内容放置规则

只有当新增内容改变以下至少一项时，才修改：

```
ARCHITECTURE.md
```

包括：

```
系统 Owner 边界

核心业务链

核心对象稳定含义

模块职责

技术分层

依赖方向

不可破坏的业务正确性不变量

不可破坏的安全不变量

不可破坏的状态不变量

外部能力 Contract 边界
```

否则优先进入：

```
Domain
Feature Spec
Engine Detail
Integration
Reference
ADR
Code
Test
Evaluation
```

避免实现细节重新进入核心 Architecture。

# 11. 当前阶段的实现原则

Architecture 描述最终必须长期保持的边界。

但：

> **Architecture 中存在某个 Contract，不等于 MVP 第一阶段必须把它完整实现。**

当前开发遵循：

```
Business First
+
Boundary Aware
```

即：

```
先完成业务闭环
↓
保持关键边界
↓
通过 Evaluation 证明正确
↓
发现稳定模式
↓
必要时重构
↓
Production Readiness
↓
Platform Integration
↓
Scale when proven necessary
```

## 11.1 当前可以实现

```
Sales Domain
Trusted Query
Semantic Resource
SemanticQuery
Business Validation
Minimal Domain Authorization
SQL Generation
SQL Guard
Read-only BusinessDataSource
QueryResult
Clarification
Continuous Follow-up
Evaluation
Bad Case
```

具体是否进入当前 Feature：

由 Feature Spec 决定。

## 11.2 当前明确不因为 Architecture 而提前实现

```
Enterprise IAM
SSO
Keycloak
HiMarket Integration
Higress Integration
Kubernetes
HPA
Service Mesh
RabbitMQ
Kafka
Temporal
Transactional Outbox
Redis Cluster
Redis HA
OTel Collector
Grafana Platform
CI/CD Platform
Canary Platform
Database HA
Backup / DR
Distributed ThreadRunGate
Durable Runtime
```

除非：

> **当前 Feature 或真实运行证据明确需要。**

# 12. 抽象建立原则

不要为了：

```
以后可能有多个实现
```

就提前创建：

```
大量 Interface
大量 Adapter
Plugin Manager
Provider Registry
Abstract Factory
```

建立抽象至少满足以下之一：

### 条件 A

已经存在多个真实实现。

### 条件 B

当前外部依赖已经明确即将替换。

### 条件 C

不建立边界会让：

```
Provider SDK
Database SDK
Platform SDK
```

污染核心业务。

否则：

> **先保持简单。**

Architecture 定义的 Contract 是系统边界。

它不意味着每个 Contract 都必须立即变成：

```
Python ABC
Protocol
Interface Class
```

具体代码抽象以当前 Feature 实际需要为准。

# 13. 最终架构原则

ChatBI 的最终稳定关系可以压缩为：

```
User
↓
Business Semantic Resolution
↓
SemanticQuery
↓
Trusted Query
↓
QueryResult
↓
Business Analysis
```

其中：

```
Business Semantics
保持稳定

External Technology
允许替换
```

最终应做到：

```
换模型
→ 不改 Trusted Query

换模型 Gateway
→ 不改 SemanticQuery

换数据库接入
→ 不改业务语义

换企业 IAM
→ 不改 Domain Authorization

换 AI Platform
→ 不改 ChatBI Core

换 State Store
→ 不改 Engine State 语义

换 Observability
→ 不改 Evaluation

换部署方式
→ 不改 Domain

换 Retrieval
→ 不改 SemanticQuery Contract
```

整个架构最终遵循：

> **Business First, Boundary Aware.**

以及：

> **Model proposes, program decides.**

以及：

> **Stable Core, Replaceable Edge.**

最终目标：

```
Architecture
    ↓
约束系统不能怎么乱长

Domain
    ↓
定义业务到底是什么

Feature Spec
    ↓
定义这一次具体做什么

Code
    ↓
实现 Feature

Test / Evaluation
    ↓
证明 Feature 正确

Bad Case
    ↓
驱动下一次 Spec
```

# 14. Architecture Freeze Rule

本版本完成后，`ARCHITECTURE.md` 进入稳定基线状态。

日常 Feature 开发：

> **默认不修改 Architecture。**

只有真实变化涉及：

```
系统定位
Owner 边界
核心业务链
核心对象语义
模块职责
分层
依赖方向
安全 / 正确性 / 状态不变量
外部 Contract 边界
```

才重新打开 Architecture Discussion。

以下变化默认不需要修改 Architecture：

```
增加指标
增加维度
增加 Golden Case
修复 Bad Case
修改 Prompt
更换模型
修改 Retrieval
增加 SQL Rule
局部代码重构
新增 Feature
增加测试
页面变化
配置变化
数据库物理字段变化
```

只要这些变化仍然遵守已有 Architecture Contract。

# Final Baseline

```
ChatBI
=
Domain AI Engine Service

Internal Architecture
=
Modular Monolith
```

核心可信查询链：

```
Natural Language
↓
Semantic Resolution
↓
SemanticQuery
↓
Deterministic Business Validation
↓
Domain Authorization / Data Scope
↓
SQL Generation
↓
Deterministic SQL Guard
↓
Read-only BusinessDataSource
↓
Result Validation
↓
QueryResult
```

核心边界：

```
Enterprise AI Platform
        ↓
Contracts / Adapters
        ↓
ChatBI Stable Core
        ↓
BusinessDataSource
```

核心开发原则：

```
先业务正确
↓
再完整闭环
↓
再 Evaluation
↓
再可维护
↓
再工程化
↓
再 Production
↓
再 Platform Integration
↓
最后根据真实需求 Scale
```

> **Architecture 到此冻结。后续开发由 Domain 与 Feature Spec 驱动。**

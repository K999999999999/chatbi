# ChatBI Architecture

> Status: Design baseline
>
> 本文档只定义 ChatBI 的稳定架构骨架：系统定位、核心业务链、核心对象、模块与分层、依赖方向、架构不变量，以及与外部模型、数据、身份、状态和平台的可替换边界。
>
> 资料状态：当前资料证明的是业务与架构设计目标，不等同于已实现、已验证或生产就绪。

## 1. 系统定位与范围

```text
ChatBI = Domain AI Engine Service（领域 AI 引擎服务）
内部 = Modular Monolith（模块化单体）
```

ChatBI 的核心职责是把自然语言问题转换为可验证的业务查询，并在业务语义、权限、安全和数据边界都通过后，返回具有业务含义和追溯信息的可信结果。

企业视角如下：

```text
Enterprise AI Platform / Enterprise Infrastructure
                      ↓
          ChatBI Domain AI Engine Service
```

当前内部形态为：

```text
一个代码仓库
+
一个主要应用
+
一个主要部署单元
+
内部按稳定能力划分模块
```

当前不因“以后可能需要生产平台”而提前拆分微服务。是否拆分，应由真实的独立扩缩容、独立部署、团队边界或运行压力证据触发新的决策。

### 1.1 Owner 边界

| Owner | ChatBI 负责的内容 |
|---|---|
| Engine Owned | Trusted Query、SemanticQuery、业务主题、业务校验、领域授权、Data Scope、SQL Guard、QueryResult、Evidence、Analysis、Engine State 不变量、Evaluation 与 Bad Case |
| Contract Owned | PrincipalContext、DomainAccessContext、ModelGateway、BusinessDataSource、State/Checkpoint/Conversation Store、ThreadRunGate、DurableRuntime、AuditSink、Telemetry Export、外部配置 |
| Platform Owned | 企业认证与用户目录、API 流量治理、模型密钥/预算/路由、Secret、部署与弹性、可观测性后端、高可用、备份和灾备 |

核心规则：

> ChatBI 拥有领域正确性和必要合同；依赖合同，不依赖某个企业平台或供应商的具体实现。

## 2. 核心业务链

### 2.1 顶层能力路由

ChatBI 先判断请求属于哪种能力，再进入相应 Workflow：

```text
User Question
    ↓
Capability Router
    ├── Trusted Query（P1）
    ├── Business Analysis（P2）
    └── Other / Out of Scope
```

路由器只负责选择能力，不负责生成完整 SemanticQuery、SQL 或分析计划。

### 2.2 P1 Trusted Query 主链

```text
Natural Language
    ↓
Structured Intent
    ↓
Semantic Context / Retrieval
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
Persist / Reference Result and Update Engine Context
```

关键分支：

```text
语义或信息不足       → CLARIFY → 等待补充 → 恢复原 Workflow
超出当前业务范围     → REJECT
权限、数据范围或安全拒绝 → DENY
技术或不可恢复失败   → FAILED
成功                 → SUCCESS → 产生 QueryResult
```

其中：

- 第一次模型调用负责理解自然语言并生成结构化意图，不负责最终权限判断、业务口径决定或直接生成 SQL。
- Semantic Context 负责提供与本次问题相关的指标口径、认证主题 Schema、业务规则和已验证示例；具体检索算法由 POC/实现决定。
- SemanticQuery 是业务查询含义的确认结果；只有通过确定性业务校验后才进入 SQL 生成。
- P1 可以使用受约束的模型生成 SQL；未来可替换为确定性 Compiler，但不改变上游业务链。
- SQL 生成结果必须经过确定性 Guard 和只读数据源约束，模型输出不能直接访问数据库。

### 2.3 P2 Analysis 关系

```text
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

P2 负责基于可信事实进行趋势、拆解、贡献定位、原因验证和分析表达；它不能绕过 Trusted Query 自己生成 SQL 或直接访问 BusinessDataSource。P1 是面向用户的可信查询闭环，P2 是建立在该闭环之上的分析能力，不是两套独立的数据访问链。

### 2.4 运行模式关系

```text
P1 = 交互式请求/响应（可以流式），外部 I/O 使用异步调用
P2 = 需要长时间、多次查询或等待输入时，可采用异步/持久执行
```

运行模式可以演进，但业务对象、权限边界和 Trusted Query 合同不随队列、Worker 或具体运行时改变。

## 3. 核心对象

这些对象是跨入口、Workflow 和未来实现仍应保持稳定含义的最小集合。字段细节由当前 Feature Spec、Domain 文档和实现合同决定。

| 对象 | 稳定含义 | 明确不包含 |
|---|---|---|
| `StructuredIntent` | 从自然语言中提取的查询动作、指标/维度/过滤/时间等原始表达及上下文信息 | 物理表名、物理列名、最终权限决定、SQL |
| `SemanticContext` | 本次查询所需的权威业务语义、认证数据模型和示例上下文 | 某一种检索产品或向量数据库实现 |
| `SemanticQuery` | 已确认的企业业务查询含义：指标、维度、粒度、时间、过滤、比较、排序和查询方式 | 数据库连接、物理表/列、SQL 字符串 |
| `PrincipalContext` | 外部身份系统传入的主体、租户、组织/角色/声明和追踪上下文 | ChatBI 的业务授权结论 |
| `DomainAccessContext` | ChatBI 根据主体和领域规则形成的业务访问边界，如可访问主题、指标、维度、区域、敏感等级和明细权限 | 外部平台角色的简单复制 |
| `QueryResult` | 一次成功可信查询得到的业务结果，包含 `SemanticQuery`、数据、业务元信息、警告、范围说明和必要追溯引用 | 澄清、拒绝、失败、完整会话、完整 Prompt 或完整 Trace |
| `EngineExecutionState` | Thread 相关的跨轮语义状态、当前运行状态、澄清状态、Checkpoint、结果引用和 Analysis 状态 | Product Conversation 的全部 UI 能力 |
| `Evidence` / `AnalysisResult` | P2 分析引用的 QueryResult 及由可信事实形成的分析结果 | 绕过 Trusted Query 的原始 SQL 访问 |

### 3.1 Semantic 资源边界

当前最小稳定资源集合为：

```text
指标业务口径
认证主题表 Schema 与主题规则
已验证查询示例
```

业务口径由 Domain/Semantic 资料维护，文件读取、索引和检索由 Infrastructure 提供。资源版本应可追溯到查询结果，但资源存储格式和 Retrieval 实现不属于本核心架构。

### 3.2 QueryResult 语义

`QueryResult` 只表示成功完成的可信查询：

```text
SemanticQuery 已确定
业务校验已通过
领域授权已通过
SQL Guard 已通过
只读数据源执行成功
结果已完成基础校验
```

外层响应另行表达 `SUCCESS / CLARIFY / REJECT / DENY / FAILED`，避免把流程状态与成功业务数据混为一个对象。

## 4. 模块职责与分层

### 4.1 业务模块

| 模块 | 职责 |
|---|---|
| Query | 统一的 Trusted Query 能力，负责从确认的业务查询得到可信结果 |
| Semantic | 指标口径、语义收敛、SemanticQuery 和相关上下文 |
| Business Topics | 销售等业务主题的指标、维度、粒度和主题规则；销售是首个主题，不是系统结构的写死前提 |
| Security | 功能权限、领域授权、敏感数据权限、Data Scope 和 SQL Guard 策略 |
| State / Result | Engine Execution State、Checkpoint 语义、QueryResult、结果引用和跨轮上下文 |
| Analysis | P2 分析编排，复用 Query 和 QueryResult 形成 Evidence/AnalysisResult |
| Evaluation | Golden Dataset、分层 AI 评估、Bad Case 和质量反馈闭环 |

### 4.2 技术分层

```text
Interfaces
    ↓
Application
    ↓
Domain

Application ── depends on ──> Ports / Contracts
Infrastructure ── implements ──> Ports / Contracts

Bootstrap ── assembles all concrete implementations
```

| 层 | 责任 | 不负责 |
|---|---|---|
| Interfaces | HTTP、CLI、UI 等入口的输入输出和协议转换 | 业务规则、指标口径、SQL 生成、Workflow |
| Application | Use Case、Workflow、路由、分支、状态编排、调用端口和有限恢复 | 具体模型/数据库 SDK 的细节 |
| Domain | Metric、Dimension、TimeRange、Filter、Grain、SemanticQuery、主题规则、业务校验和领域授权 | LLM、数据库、Web 框架、文件系统、向量库 |
| Infrastructure | Model、Retrieval、BusinessDataSource、State/Checkpoint、SQL AST、文件和遥测等适配器 | 销售额口径、毛利公式、领域分析规则 |
| Bootstrap | 创建适配器、注入依赖、组装应用 | 业务逻辑 |

### 4.3 依赖规则

- Domain 不得依赖 Infrastructure；领域代码不导入具体模型、数据库、Web 框架或检索产品。
- Interfaces 不得绕过 Application 直接执行完整业务链。
- Application 通过 Port/Contract 使用外部能力，具体 Adapter 在 Bootstrap 中装配。
- Prompt 的任务编排属于 Application，业务知识属于 Domain/Semantic Resources，模型调用协议属于 Infrastructure/ModelGateway。
- SQL 业务语义校验与 SQL 技术安全校验分开：前者属于 Domain/Application，后者可由 Infrastructure 使用 AST 等技术实现。

## 5. 必须保持的架构不变量

1. **可信结果的前置条件不变**：没有确定的 `SemanticQuery`、确定性业务校验、领域授权、SQL Guard 和成功的只读执行，就不能产生正式 `QueryResult`。
2. **模型不是最终裁判**：LLM 可以理解、生成候选和辅助解释，但不能最终决定业务口径、权限、Data Scope 或安全放行。
3. **Analysis 不绕过 Query**：P2 只能通过 Trusted Query 获取事实；不得自行生成 SQL 或直连 BusinessDataSource。
4. **语义与物理结构分离**：`SemanticQuery` 不保存数据库表、列、连接或 SQL；物理映射变化不应迫使业务语义和上层 Workflow 重写。
5. **业务数据默认只读且受认证模型约束**：BusinessDataSource 只允许访问认证的数据模型/主题，具体硬权限由数据源和 Adapter 落实。
6. **权限必须确定性执行**：功能权限、敏感数据权限和 Data Scope 不能只靠 Prompt；越权应拒绝，不得静默改写用户问题为更窄查询。
7. **成功状态与失败状态分离**：澄清、拒绝和失败不得污染 `last_successful_semantic_query`、`last_result_id` 等跨轮成功状态。
8. **同一 Thread 有序，不同 Thread 可并发**：同一 Thread 的可修改 Engine Run 按业务顺序执行；不同 Thread 可以并发；权威状态不能只保存在单个进程内存。
9. **Product Conversation 不等于 Engine State**：外部平台可以拥有聊天 UI、标题、分享和完整消息，但不能替代 ChatBI 的 SemanticQuery、Checkpoint、QueryResult 和 ThreadRunGate 不变量。
10. **外部实现可替换**：入口、模型供应商、检索算法、数据库产品、状态存储、Checkpoint、Durable Runtime、审计和遥测后端只能通过合同进入核心。

## 6. 必要的外部边界

### 6.1 Identity：认证与领域授权分离

```text
External Authentication
    ↓
PrincipalContext
    ↓
ChatBI Domain Authorization
    ↓
DomainAccessContext
```

外部平台负责“你是谁”；ChatBI 负责“你能否使用某项 BI 能力、能看哪些主题/指标/维度/数据范围、能否访问敏感数据”。ChatBI 不在核心内建设企业账号密码、SSO 或用户目录。

### 6.2 Model：模型调用可替换

Application 只依赖 `ModelGateway` 能力，例如结构化输出、超时、取消、可重试错误和使用量元数据；不依赖某个模型品牌、URL、API Key、供应商 Header 或专属 SDK。模型输出一律视为不可信候选，必须进入后续确定性校验。

### 6.3 Data：状态数据与业务数据分离

```text
ChatBI-owned State Store
    ├── Engine State
    ├── QueryResult
    ├── AuditEvent
    └── optional Product Conversation

BusinessDataSource
    └── Certified Business Data（ChatBI 只读）
```

ChatBI 拥有运行状态的业务语义，但不拥有企业数据平台的 ETL、刷新、质量平台和底层原始表。业务数据接入应能提供认证模型、数据版本/时点以及新鲜度和质量状态。

### 6.4 State：状态存储可替换

ChatBI 规定必须保存和恢复的 Engine State 语义；具体 State Store、CheckpointStore 和 ConversationContextStore 可以由 Standalone 实现或外部平台实现。引擎不得依赖某个框架的私有表结构。完整聊天历史可以由外部产品拥有，但 Trusted Query 所需的最小上下文必须可获得。

### 6.5 Runtime / Platform：只依赖合同

运行环境应能提供外部配置、超时、取消、有限重试、健康状态、状态外置和必要的持久执行能力；具体 API Gateway、队列、Worker、缓存、弹性平台、部署拓扑、可观测性后端和发布系统不属于本文件的核心架构。

## 7. 质量与证据边界

架构只规定证据类型，不在此文档锁定具体工具和阈值：

```text
Software Tests
    → 证明代码按合同运行

AI Evaluation
    → 证明状态、语义、检索、SQL、安全和结果行为正确

Business Acceptance
    → 证明原始业务问题和领域规则真正得到满足
```

错误处理采用稳定的顶层语义：`SUCCESS / CLARIFY / REJECT / DENY / FAILED`。外部调用必须有超时；只有可判定的临时失败才允许有界重试；模型生成错误可以进入有限修复，真正的权限或安全拒绝不得通过换一条 SQL 规避。

## 8. P1 / P2 与文档边界

```text
Architecture
    → 定稳定骨架、边界和不变量

Feature Spec
    → 定当前阶段支持什么、拒绝什么以及如何验收

Domain / Topic
    → 定业务事实、口径和规则

Integration / Reference
    → 定如何接入某个环境或具体技术组合

ADR
    → 记录某个稳定跨模块取舍及其理由
```

当前 P1/P2 的关系只在架构层保留为：

- P1 先完成可验证的 Trusted Query 闭环，业务主题和具体支持范围由 P1 Spec 与 Domain 文档维护。
- P2 在 P1 可信结果之上构建 Analysis，不重新发明数据访问链。
- POC 用于验证高风险实现选择，例如 Retrieval 或 Runtime，不自动升级为架构承诺。

## 9. 本文档明确不包含的内容

以下内容不进入核心 `ARCHITECTURE.md`，继续由 V2 文档中的专门文档、ADR 或 Reference 维护：

- 具体平台集成、Northbound 字段全集和某个企业 IAM/API Gateway/Model Gateway 的配置。
- Kubernetes、HPA、RabbitMQ、Temporal、Redis/Redis HA、Worker Lease、Canary Traffic Control、CI/CD 和具体部署拓扑。
- OTel Collector、Trace/Metric/Log 后端、Dashboard、告警平台和具体观测部署。
- Vector、BM25、Hybrid、Rerank 等 Retrieval 算法，向量库/索引产品和具体 POC 对比结论。
- 具体数据库产品、连接池参数、迁移脚本、Checkpoint 表结构、账号/角色配置和数据平台部署。
- LangGraph 等 Workflow 框架的私有 API、内部表结构、节点拆分、RetryPolicy 参数和部署组合。
- P1 的具体指标公式、字段名、销售主题事实、验收案例、Golden Dataset 和实现代码。

这些内容不是删除，而是按变化原因降级到正确的 Source of Truth；核心架构只保留它们必须遵守的合同和不变量。

## 10. 相关 Source of Truth

| 内容 | 继续维护的位置 |
|---|---|
| 产品目标与阶段路线 | `10-product/*` |
| 业务建模与销售业务真相 | `20-domain/*` |
| Trusted Query 详细 Workflow | `30-engine/02-trusted-query-engine.md` |
| Semantic/Data Contract 与资源细节 | `30-engine/03-semantic-and-data-contracts.md` |
| Engine State 与持久化细节 | `30-engine/04-state-context-and-persistence.md` |
| Domain Security 与 SQL Guard 细节 | `30-engine/05-domain-security.md` |
| Quality、Evaluation、Bad Case 与 Error Model | `30-engine/06-quality-and-reliability.md` |
| Runtime Contract | `30-engine/07-engine-runtime-contract.md` |
| 外部接入合同 | `40-integration/01-platform-integration-contract.md` |
| 当前阶段行为与验收 | `50-specs/*` |
| 本地/OSS/企业技术组合 | `80-reference/*` |
| 稳定跨模块决策 | `90-adr/*` |

### 10.1 新内容放置规则

只有当新增内容改变以下至少一项时，才应修改本文档：

```text
系统 Owner 边界
核心业务链
核心对象的稳定含义
模块/分层/依赖方向
不可破坏的安全、正确性或状态不变量
外部能力的 Contract 边界
```

否则优先放入相应的 Domain、Feature Spec、Integration、Reference 或 ADR，避免把实现细节重新塞回核心架构。

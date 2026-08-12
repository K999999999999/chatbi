

------

# Natural Language Query Architecture

# 自然语言查询功能架构

> **Status（状态）：** Frozen V1（V1 已冻结）
> **Feature（功能）：** Natural Language Query（自然语言查询）
> **Document Level（文档层级）：** Feature Architecture（功能架构）
> **System Architecture Reference（系统架构引用）：** `../ARCHITECTURE.md`
> **Feature Architecture Standard Reference（功能架构标准引用）：** `../FEATURE_ARCHITECTURE_STANDARD.md`
> **Feature Spec Reference（功能规格引用）：** `FEATURE_SPEC.md`

------

# 1. Purpose（目的）

本文档定义 ChatBI Engine（ChatBI 引擎）中 Natural Language Query（自然语言查询，NLQ）的 Feature Architecture（功能架构）。

本文档只定义：

- Feature Responsibility（功能职责）；
- Feature Boundary（功能边界）；
- Module Map（模块地图）；
- Module Responsibility（模块职责）；
- Main Processing Flow（主要处理链路）；
- Major Information Flow（主要信息流）；
- Module Collaboration（模块协作）；
- Online / Offline Boundary（在线 / 离线边界）；
- External Capability Boundary（外部能力边界）；
- Cross-Cutting Constraints（横切约束）；
- Outcome Boundary（结果边界）；
- Architecture Invariants（架构不变量）。

本文档不定义：

- Typed Schema（类型化结构）具体字段；
- Class / Function（类 / 函数）；
- File Layout（文件布局）；
- Prompt（提示词）；
- Retrieval Algorithm（检索算法）；
- Top-K（前 K 个）；
- Threshold（阈值）；
- Retry Count（重试次数）；
- SDK / Framework API（软件开发工具包 / 框架接口）；
- Test Case（测试用例）；
- Evaluation Case（评估案例）；
- 具体 Infrastructure Implementation（基础设施实现）。

这些内容分别由：

- Feature Spec（功能规格）；
- Module Spec（模块规格）；
- Acceptance & Evaluation（验收与评估）；
- Implementation（实现）

继续定义。

核心原则：

> **Feature Architecture defines structure and collaboration, not module implementation.**
> **功能架构定义结构和协作，不定义模块实现。**

------

# 2. Feature Responsibility & Boundary（功能职责与边界）

## 2.1 Responsibility（职责）

Natural Language Query（自然语言查询）负责：

> **将用户自然语言业务查询转换为可信、受控、可执行的数据查询，并返回稳定的业务 QueryResult（查询结果）。**

核心闭环：

```
Natural Language Query
（自然语言查询）
        ↓
Semantic Understanding
（语义理解）
        ↓
Schema / Metric Resolution
（结构 / 指标解析）
        ↓
Generation Context
（生成上下文）
        ↓
SQL Generation
（SQL 生成）
        ↓
Validation & Guard
（校验与防护）
        ↓
Authorization Enforcement
（权限强制校验）
        ↓
Query Execution
（查询执行）
        ↓
Query Result
（查询结果）
```

NLQ（自然语言查询）的核心目标是：

> **获得可信业务事实。**

------

## 2.2 Responsible For（负责）

NLQ（自然语言查询）负责：

- Current Query Understanding（当前查询理解）；
- Conversation Semantic Context（会话语义上下文）使用；
- Clarification Detection（澄清判断）；
- Schema Linking（结构关联）；
- Relationship / Join Resolution（关系 / 连接解析）；
- Metric Resolution（指标解析）；
- Generation Context Assembly（生成上下文组装）；
- SQL Generation（SQL 生成）；
- SQL Validation & Guard（SQL 校验与防护）；
- Domain Authorization Enforcement（领域权限强制校验）；
- Read-Only Query Execution（只读查询执行）；
- Query Result Assembly（查询结果组装）。

------

## 2.3 Not Responsible For（不负责）

NLQ（自然语言查询）不负责：

- Business Analysis（经营分析）；
- Root Cause Analysis（根因分析）；
- Recommendation（经营建议）；
- Visualization Rendering（可视化渲染）；
- UI Rendering（界面渲染）；
- Product Conversation Management（产品会话管理）；
- Authentication（身份认证）；
- Enterprise Identity Management（企业身份管理）；
- API Gateway（接口网关）；
- Platform Rate Limit / Quota（平台限流 / 配额）；
- 通用 Logging / Tracing / Metrics（日志 / 链路追踪 / 监控）；
- Secret Management（密钥管理）；
- Deployment / CI/CD（部署 / 持续集成与持续交付）。

业务支持范围与 Unsupported Boundary（不支持边界）由：

> ```
> FEATURE_SPEC.md
> ```

定义。

------

# 3. Architecture Overview（架构总览）

NLQ（自然语言查询）由两个主要运行维度组成：

```
Natural Language Query
（自然语言查询）

├── Online Runtime
│   （在线运行）
│
└── Offline Preparation
    （离线准备）
```

其中：

### Online Runtime（在线运行）

负责：

> 实时处理用户 Natural Language Query（自然语言查询）。

### Offline Preparation（离线准备）

负责：

> 将 Authoritative Semantic Sources（权威语义源）准备为 Online Runtime（在线运行）可消费的 Retrieval Assets（检索资产）。

Online / Offline（在线 / 离线）描述：

> **什么时候运行。**

它不等于：

> Application / Domain / Infrastructure（应用 / 领域 / 基础设施）的职责分层。

------

# 4. V1 Module Map（第一版模块地图）

NLQ V1（自然语言查询第一版）Online Runtime（在线运行）的核心 Module（模块）为：

```
1. Query Semantic Parser
   （查询语义解析器）

2. Schema Linking
   （结构关联）

3. Metric Resolution
   （指标解析）

4. Generation Context Assembly
   （生成上下文组装）

5. SQL Generation
   （SQL 生成）

6. SQL Validation & Guard
   （SQL 校验与防护）

7. Query Execution
   （查询执行）

8. Query Result Assembly
   （查询结果组装）
```

此外存在：

```
Domain Authorization
（领域权限）
```

作为：

> Cross-Cutting Capability（横切能力）。

以及：

```
Conversation Context Resolution
（会话上下文解析）
```

作为：

> Application-Level Capability（应用级能力）。

Feature Entry Validation（功能入口基础校验）属于入口责任：

> 不作为独立 Module（模块）。

Final Authorization Enforcement（最终权限强制校验）属于：

> Domain Authorization（领域权限）的最终执行点。

不作为第九个核心 Module（模块）。

------

# 5. Module Responsibilities（模块职责）

## 5.1 Query Semantic Parser（查询语义解析器）

### Responsibility（职责）

负责：

> 根据 Current Query（当前查询）和 Conversation Semantic Context（会话语义上下文），确定用户真正希望查询的业务语义。

### Major Input（主要输入）

- Current Query（当前查询）；
- Conversation Semantic Context（会话语义上下文）。

### Major Output（主要输出）

- Semantic Query Intent（语义查询意图）；
- 或 Clarification（澄清）。

### Boundary（边界）

负责：

- Semantic Understanding（语义理解）；
- Semantic Extraction（语义提取）；
- Context Carry-Forward（上下文继承）；
- Missing / Ambiguous Semantic Detection（缺失 / 歧义语义判断）。

不负责：

- Schema（结构）；
- Join（连接）；
- Metric Formula（指标公式）；
- SQL（结构化查询语言）；
- Authorization Decision（权限裁决）；
- Query Execution（查询执行）。

核心边界：

> **用户业务语义澄清发生在这里。**

一旦用户语义已经完整：

> 后续 Module（模块）不得因为系统内部解析失败重新要求用户澄清。

------

## 5.2 Schema Linking（结构关联）

### Responsibility（职责）

负责：

> 将已经明确的业务语义映射为合法数据结构，并确定完成查询所需的合法结构关系。

### Major Input（主要输入）

- Semantic Query Intent（语义查询意图）；
- Authorization Context（权限上下文）。

### Major Output（主要输出）

- Resolved Schema Context（已解析结构上下文）。

### Major Responsibility（主要责任）

包括：

- Schema Grounding（结构语义映射）；
- Anchor Selection（锚点选择）；
- Relationship Resolution（关系解析）；
- Join Resolution（连接解析）；
- Resolution Validation（解析结果校验）。

核心规则：

> **SQL Generation（SQL 生成）不得自行发明 Join（连接）关系。**

Retrieval（检索）可以发现 Candidate Table / Column（候选表 / 字段）。

但：

> 数据结构合法性必须由 Authoritative Schema Metadata（权威结构元数据）决定。

Schema Linking（结构关联）不负责：

- 用户自然语言理解；
- 正式指标定义；
- SQL Generation（SQL 生成）；
- Query Execution（查询执行）；
- 用户业务语义澄清。

------

## 5.3 Metric Resolution（指标解析）

### Responsibility（职责）

负责：

> 将已经明确的 Metric Intent（指标意图）绑定到 Authoritative Metric Catalog（权威指标目录）中的正式指标定义。

### Major Input（主要输入）

- Semantic Query Intent（语义查询意图）；
- Authorization Context（权限上下文）。

### Major Output（主要输出）

- Resolved Metric Context（已解析指标上下文）。

### Major Responsibility（主要责任）

包括：

- Metric Matching（指标匹配）；
- Authoritative Metric Resolution（权威指标解析）；
- Resolution Validation（解析结果校验）。

核心规则：

> **Metric Resolution（指标解析）消费指标事实，不创造指标事实。**

Metric Catalog（指标目录）拥有正式指标定义。

Retrieval Index（检索索引）可以保存 Derived Metric Asset（派生指标资产），但：

> 其业务内容必须来源于 Authoritative Metric Catalog（权威指标目录）。

Metric Resolution（指标解析）不负责：

- 完整自然语言理解；
- Schema Linking（结构关联）；
- Join Resolution（连接解析）；
- 创建 Metric Formula（指标公式）；
- SQL Generation（SQL 生成）；
- Query Execution（查询执行）。

------

## 5.4 Generation Context Assembly（生成上下文组装）

### Responsibility（职责）

负责：

> 将 Semantic Query Intent（语义查询意图）、Resolved Schema Context（已解析结构上下文）和 Resolved Metric Context（已解析指标上下文）汇合为 SQL Generation（SQL 生成）可以直接消费的 Generation Context（生成上下文）。

### Major Input（主要输入）

- Semantic Query Intent（语义查询意图）；
- Resolved Schema Context（已解析结构上下文）；
- Resolved Metric Context（已解析指标上下文）。

### Major Output（主要输出）

- Generation Context（生成上下文）。

### Core Rule（核心规则）

该模块负责：

- Context Merge（上下文汇合）；
- Context Reconciliation（上下文协调）；
- Context Completeness Validation（上下文完整性校验）。

必须确认：

```
Semantic Query Intent
（用户想查什么）

        ↕

Resolved Schema Context
（数据在哪里）

        ↕

Resolved Metric Context
（指标如何定义）
```

不存在无法接受的冲突。

不得通过：

- 静默修改上游结果；
- 凭空补充业务事实；
- 再次调用模型猜测事实；

修复 Contract Conflict（契约冲突）。

无法协调时：

> 明确 Failure（失败）。

------

## 5.5 SQL Generation（SQL 生成）

### Responsibility（职责）

负责：

> 根据 Generation Context（生成上下文）生成 Candidate SQL（候选 SQL）。

### Major Input（主要输入）

- Generation Context（生成上下文）。

### Major Output（主要输出）

- Candidate SQL（候选 SQL）。

### Architecture Boundary（架构边界）

SQL Generation（SQL 生成）定义：

> **生成责任。**

不绑定具体 Generation Strategy（生成策略）。

实现可以演进为：

- LLM Generation（大语言模型生成）；
- Deterministic Generation（确定性生成）；
- Hybrid Generation（混合生成）。

但 SQL Generation（SQL 生成）不得：

- 重新解析用户业务语义；
- 重新搜索数据库结构；
- 修改指标定义；
- 发明新的 Join（连接）；
- 绕过 Resolved Schema Context（已解析结构上下文）；
- 绕过 Resolved Metric Context（已解析指标上下文）。

Candidate SQL（候选 SQL）：

> **始终是不可信执行对象。**

必须继续进入：

> SQL Validation & Guard（SQL 校验与防护）。

------

## 5.6 SQL Validation & Guard（SQL 校验与防护）

### Responsibility（职责）

负责：

> 对 Candidate SQL（候选 SQL）进行确定性的结构、范围和安全校验。

### Major Input（主要输入）

- Candidate SQL（候选 SQL）；
- 必要的 Resolved Query Context（已解析查询上下文）。

### Major Output（主要输出）

成功：

- Validated SQL（已校验 SQL）。

失败：

- SQL Validation Failure（SQL 校验失败）。

### Major Responsibility（主要责任）

包括：

- SQL Structure Validation（SQL 结构校验）；
- Query Scope Validation（查询范围校验）；
- Read-Only Safety（只读安全）；
- SQL Safety Guard（SQL 安全防护）。

核心边界：

> **SQL Safety（SQL 安全） ≠ Domain Authorization（领域权限）。**

SQL Validation & Guard（SQL 校验与防护）负责：

> 查询本身是否结构合法、安全、允许执行。

不负责：

> 当前用户是否有权访问这些业务数据。

------

## 5.7 Query Execution（查询执行）

### Responsibility（职责）

负责：

> 执行已经通过 SQL Validation & Guard（SQL 校验与防护）和 Final Authorization Enforcement（最终权限强制校验）的查询。

### Major Input（主要输入）

- Authorized Query（已授权查询）。

### Major Output（主要输出）

- Raw Query Result（原始查询结果）。

核心规则：

> Query Execution（查询执行）只接收已经完成安全与权限裁决的查询。

Query Execution（查询执行）不负责：

- 重新理解用户意图；
- 修改 SQL（结构化查询语言）；
- 修改指标；
- 修改查询范围；
- 绕过权限约束。

------

## 5.8 Query Result Assembly（查询结果组装）

### Responsibility（职责）

负责：

> 将 Raw Query Result（原始查询结果）转换为稳定的业务 QueryResult（查询结果）。

### Major Input（主要输入）

- Raw Query Result（原始查询结果）；
- 必要的 Resolved Query Context（已解析查询上下文）。

### Major Output（主要输出）

- QueryResult（查询结果）。

核心边界：

```
Raw Query Result
（数据库原始查询结果）

        ≠

QueryResult
（业务查询结果）
```

并且：

```
QueryResult
（业务查询结果）

        ≠

API Response
（接口响应）

        ≠

UI View Model
（界面展示模型）
```

QueryResult（查询结果）应使用稳定：

> Business Semantic Identity（业务语义身份）。

不应让 Physical Database Field（物理数据库字段）成为上层长期业务契约。

------

# 6. Main Processing Flow（主要处理链路）

NLQ V1（自然语言查询第一版）的 Online Runtime（在线运行）主链为：

```
Current Query
（当前查询）

+

Conversation Semantic Context
（会话语义上下文）

+

Authorization Context
（权限上下文）

        ↓

Feature Entry Validation
（功能入口基础校验）

        ↓

Query Semantic Parser
（查询语义解析器）

        ↓

Semantic Query Intent
（语义查询意图）

        ↓

┌────────────────────────────────────┐
│                                    │
↓                                    ↓

Schema Linking                 Metric Resolution
（结构关联）                    （指标解析）

↓                                    ↓

Resolved Schema Context       Resolved Metric Context
（已解析结构上下文）            （已解析指标上下文）

│                                    │
└──────────────────┬─────────────────┘
                   ↓

Generation Context Assembly
（生成上下文组装）

                   ↓

Generation Context
（生成上下文）

                   ↓

SQL Generation
（SQL 生成）

                   ↓

Candidate SQL
（候选 SQL）

                   ↓

SQL Validation & Guard
（SQL 校验与防护）

                   ↓

Validated SQL
（已校验 SQL）

                   ↓

Final Authorization Enforcement
（最终权限强制校验）

                   ↓

Authorized Query
（已授权查询）

                   ↓

Query Execution
（查询执行）

                   ↓

Raw Query Result
（原始查询结果）

                   ↓

Query Result Assembly
（查询结果组装）

                   ↓

QueryResult
（查询结果）
```

------

# 7. Module Collaboration & Information Flow（模块协作与信息流）

## 7.1 Logical Parallelism（逻辑并行）

Schema Linking（结构关联）与 Metric Resolution（指标解析）在当前 V1 Architecture（第一版架构）中表示为两个：

> Parallel Capability Paths（并行能力路径）。

```
Semantic Query Intent
（语义查询意图）

        ↓

┌─────────────────────┐
↓                     ↓

Schema Linking        Metric Resolution
（结构关联）           （指标解析）
```

其中：

```
Schema Linking
→ Where
  （数据在哪里）

Metric Resolution
→ Metric Definition
  （指标如何正式定义）
```

这里的 Parallel（并行）表示：

> **逻辑职责可以独立解析。**

不表示 Implementation（实现）必须采用：

- Thread（线程）；
- Async Task（异步任务）；
- Concurrent Execution（并发执行）。

实际执行方式属于 Implementation（实现）。

------

## 7.2 Merge Point（汇合点）

两条解析路径统一在：

> Generation Context Assembly（生成上下文组装）

汇合。

Generation Context Assembly（生成上下文组装）是：

> **Context Merge / Consistency Boundary（上下文汇合 / 一致性边界）。**

它不重新承担：

- Semantic Parsing（语义解析）；
- Schema Linking（结构关联）；
- Metric Resolution（指标解析）。

------

## 7.3 Information Flow（信息流）

主要 Conceptual Data Object（概念数据对象）：

```
Current Query
（当前查询）

        ↓

Semantic Query Intent
（语义查询意图）

        ↓

Resolved Schema Context
（已解析结构上下文）

+

Resolved Metric Context
（已解析指标上下文）

        ↓

Generation Context
（生成上下文）

        ↓

Candidate SQL
（候选 SQL）

        ↓

Validated SQL
（已校验 SQL）

        ↓

Authorized Query
（已授权查询）

        ↓

Raw Query Result
（原始查询结果）

        ↓

QueryResult
（查询结果）
```

这些对象的具体字段：

> 不在 Feature Architecture（功能架构）定义。

由对应 Module Spec（模块规格）定义。

------

# 8. Online / Offline Boundary（在线 / 离线边界）

## 8.1 Offline Preparation（离线准备）

Offline Preparation（离线准备）负责将正式语义资源转换为 Online Runtime（在线运行）可使用的 Retrieval Asset（检索资产）。

主链：

```
Authoritative Semantic Sources
（权威语义源）

        ↓

Resource Validation
（资源校验）

        ↓

Semantic Asset Preparation
（语义资产准备）

        ↓

Embedding
（向量化）

        ↓

Index Build / Update
（索引构建 / 更新）

        ↓

Validated Retrieval Assets
（已验证检索资产）

────────────────────────────
Online / Offline Boundary
（在线 / 离线边界）
────────────────────────────

        ↓

Semantic Retrieval
（语义检索）

        ↓

Schema Linking / Metric Resolution
（结构关联 / 指标解析）
```

------

## 8.2 Authoritative Semantic Sources（权威语义源）

Offline Preparation（离线准备）消费正式：

- Schema Metadata（结构元数据）；
- Metric Catalog（指标目录）；
- Relationship Metadata（关系元数据）；
- 其他 Authoritative Semantic Resource（权威语义资源）。

这些资源定义：

> **Business Truth（业务事实）。**

------

## 8.3 Retrieval Asset（检索资产）

Retrieval Asset（检索资产）属于：

> **Derived / Materialized Asset（派生 / 物化资产）。**

可以包含：

```
Embedding
（向量）

+

Semantic Payload
（语义载荷）

+

Metadata
（元数据）
```

Online Runtime（在线运行）可以直接消费已验证 Retrieval Asset（检索资产）中的完整 Semantic Payload（语义载荷）。

不要求每次 Retrieval（检索）后重新读取原始 Catalog（目录）。

但必须保持：

```
Authoritative Source
（权威源）

        ↓

Offline Build
（离线构建）

        ↓

Runtime Projection
（运行时投影）

        ↓

Retrieval Asset
（检索资产）
```

因此：

> **Retrieval Asset（检索资产）不是 Business Source of Truth（业务事实源）。**

业务定义只能首先修改：

> Authoritative Semantic Source（权威语义源）。

然后重新：

```
Validate
（验证）
↓
Build
（构建）
↓
Publish
（发布）
```

Retrieval Asset（检索资产）。

------

## 8.4 Retrieval Responsibility（检索职责）

Retrieval（检索）负责：

> **发现最相关 Candidate（候选）。**

不负责：

> **定义业务事实。**

稳定关系：

```
Retrieval
（检索）
→ Candidate
  （候选）

Authoritative Metadata / Catalog
（权威元数据 / 目录）
→ Formal Definition
  （正式定义）
```

------

## 8.5 Build vs Serve（构建与服务）

Architecture（架构）只要求：

> **Online Runtime（在线运行）开始提供服务之前，必须存在有效 Retrieval Assets（检索资产）。**

不规定具体使用：

- Application Startup Build（应用启动构建）；
- Manual Build（手动构建）；
- CI/CD Build（持续集成 / 持续交付构建）；
- Independent Offline Job（独立离线任务）；
- Incremental Refresh（增量刷新）。

因此：

> **Build（构建）与 Serve（服务）在架构上保持可分离。**

------

# 9. External Capability Boundary（外部能力边界）

NLQ（自然语言查询）业务模块优先依赖：

> **Capability / Port（能力 / 端口）。**

不直接依赖：

> Concrete Vendor / Product（具体供应商 / 产品）。

稳定关系：

```
Feature / Application
（功能 / 应用）

        ↓

Capability / Port
（能力 / 端口）

        ↓

Infrastructure Adapter
（基础设施适配器）

        ↓

Concrete Technology
（具体技术）
```

------

## 9.1 Online Capabilities（在线能力）

### Conversation Context Capability（会话上下文能力）

主要服务：

- Query Semantic Parser（查询语义解析器）。

提供：

- Conversation Semantic Context（会话语义上下文）。

------

### Authorization Capability（权限能力）

主要服务：

- Schema Linking（结构关联）；
- Metric Resolution（指标解析）；
- Final Authorization Enforcement（最终权限强制校验）。

提供：

- Authorization Context（权限上下文）；
- Deterministic Authorization Decision（确定性权限裁决）。

------

### Model Capability（模型能力）

明确可能服务：

- Query Semantic Parser（查询语义解析器）；
- SQL Generation（SQL 生成，如 Generation Strategy 需要）。

Feature Architecture（功能架构）不绑定：

- Model Provider（模型供应商）；
- Model Name（模型名称）；
- Model SDK（模型软件开发工具包）。

------

### Semantic Retrieval Capability（语义检索能力）

主要服务：

- Schema Linking（结构关联）；
- Metric Resolution（指标解析）。

不绑定：

- Vector Database（向量数据库）；
- Embedding Model（向量模型）；
- Retrieval Framework（检索框架）。

------

### Database Query Capability（数据库查询能力）

主要服务：

- Query Execution（查询执行）。

负责：

> 提供受控的 Read-Only Database Query（只读数据库查询）能力。

------

## 9.2 Offline Capabilities（离线能力）

### Semantic Resource Access Capability（语义资源访问能力）

负责读取：

- Schema Metadata（结构元数据）；
- Metric Catalog（指标目录）；
- Relationship Metadata（关系元数据）；
- 其他 Authoritative Semantic Resource（权威语义资源）。

------

### Embedding Capability（向量化能力）

负责：

```
Semantic Content
（语义内容）

        ↓

Embedding
（向量化）

        ↓

Vector Representation
（向量表示）
```

不绑定具体 Embedding Model（向量模型）。

------

### Vector Index Capability（向量索引能力）

负责：

- Build（构建）；
- Update（更新）；
- Store（存储）；
- Publish（发布）

Retrieval Asset（检索资产）。

不绑定具体 Vector Database（向量数据库）。

------

# 10. Cross-Cutting Constraints（横切约束）

## 10.1 Conversation Context（会话上下文）

Platform（平台）拥有：

> Product Conversation（产品会话）。

ChatBI（ChatBI 引擎）消费：

> Conversation Semantic Context（会话语义上下文）。

NLQ（自然语言查询）不依赖完整 Raw Chat History（原始聊天历史）作为业务状态。

具体继承、覆盖、删除和重置行为由：

> Feature Spec / Module Spec（功能规格 / 模块规格）

定义。

------

## 10.2 Domain Authorization（领域权限）

Authorization（权限）是 Cross-Cutting Capability（横切能力）。

架构模式：

```
Platform Identity
（平台身份）

        ↓

Authorization Context
（权限上下文）

        ├──→ Schema Linking
        │    （结构关联）
        │
        ├──→ Metric Resolution
        │    （指标解析）
        │
        └──→ Final Authorization Enforcement
             （最终权限强制校验）
```

不得每经过一个 Module（模块）就重新建立一套权限体系。

稳定模式：

```
Establish Authorization Context
（建立权限上下文）

        ↓

Constrain Resolution
（约束解析）

        ↓

Final Enforcement
（最终强制校验）
```

LLM（大语言模型）：

> 不得承担最终 Authorization Decision（权限裁决）。

------

## 10.3 Final Authorization Enforcement（最终权限强制校验）

数据库执行前必须存在：

> **不可绕过的 Final Authorization Enforcement（最终权限强制校验）。**

稳定关系：

```
Candidate SQL
（候选 SQL）

        ↓

SQL Validation & Guard
（SQL 校验与防护）

        ↓

Validated SQL
（已校验 SQL）

        ↓

Final Authorization Enforcement
（最终权限强制校验）

        ↓

Authorized Query
（已授权查询）
```

只有：

> Authorized Query（已授权查询）

可以进入 Query Execution（查询执行）。

------

## 10.4 Clarification Boundary（澄清边界）

Clarification（澄清）只用于：

> **用户业务语义缺失或存在真实歧义。**

一旦 Query Semantic Parser（查询语义解析器）已经产生完整 Semantic Query Intent（语义查询意图）：

后续：

- Schema Resolution Failure（结构解析失败）；
- Metric Resolution Failure（指标解析失败）；
- Relationship Failure（关系失败）；
- Generation Failure（生成失败）；
- Dependency Failure（依赖失败）

不得重新转换成：

> 用户 Clarification（澄清）。

------

## 10.5 Trust Boundary（信任边界）

NLQ（自然语言查询）的信任逐步收敛：

```
Natural Language
（自然语言）
低确定性

        ↓

Semantic Query Intent
（语义查询意图）

        ↓

Resolved Context
（已解析上下文）

        ↓

Generation Context
（生成上下文）

        ↓

Candidate SQL
（候选 SQL）
仍不可信

        ↓

SQL Validation & Guard
（SQL 校验与防护）

        ↓

Validated SQL
（已校验 SQL）

        ↓

Authorization Enforcement
（权限强制校验）

        ↓

Authorized Query
（已授权查询）

        ↓

Read-Only Execution
（只读执行）

        ↓

Trusted QueryResult
（可信查询结果）
```

原则：

> **链路越接近执行，不确定性越少，确定性约束越强。**

------

## 10.6 Failure Boundary（失败边界）

所有 Module（模块）遵循：

> **No Silent Degradation（禁止静默降级）。**

模块无法满足自身 Contract（契约）时：

> 明确失败。

不得：

```
Contract Failure
（契约失败）

        ↓

Guess
（猜测）

        ↓

Continue
（继续）

        ↓

Fake Success
（伪装成功）
```

Bad Case（失败案例）、Evaluation（评估）和 Regression（回归）的详细工程闭环：

> 不属于 Online Runtime Architecture（在线运行架构）。

由：

> ```
> ACCEPTANCE_AND_EVALUATION.md
> ```

和 Engineering Workflow（工程流程）定义。

------

# 11. Outcome Boundary（结果边界）

NLQ（自然语言查询）的正常 Business Outcome（业务结果）包括：

```
Business Outcome
（业务结果）

├── QueryResult
│   （查询结果）
│
├── Clarification
│   （澄清）
│
└── UnsupportedRequest
    （不支持请求）
```

------

## 11.1 QueryResult（查询结果）

表示：

> 查询成功完成并产生可信业务结果。

包括：

> Empty Result（空结果）。

------

## 11.2 Clarification（澄清）

表示：

> 用户业务意图仍缺失或存在无法唯一确定的真实歧义。

------

## 11.3 UnsupportedRequest（不支持请求）

表示：

> 请求已经明确，但超出当前 NLQ（自然语言查询）正式能力范围。

------

## 11.4 System Failure（系统失败）

System Failure（系统失败）表示：

> 系统设计上应该完成当前请求，但此次执行失败。

它属于：

> **Error Path（错误路径）。**

不是：

> Business Outcome（业务结果）。

------

# 12. Cross-Feature Boundary（跨功能边界）

Business Analysis（经营分析）未来需要可信业务数据时：

> 应复用 NLQ（自然语言查询）的可信查询能力。

概念关系：

```
Business Analysis
（经营分析）

        ↓

Internal Query Capability
（内部查询能力）

        ↓

Trusted QueryResult
（可信查询结果）

        ↓

Diagnosis / Analysis
（诊断 / 分析）
```

Business Analysis（经营分析）不应重新建立第二套：

- Schema Linking（结构关联）；
- Metric Resolution（指标解析）；
- SQL Generation（SQL 生成）；
- Authorization（权限）；
- Query Execution（查询执行）。

NLQ（自然语言查询）本身不承担：

> System-Level Intent Router（系统级意图路由器）。

如果未来同时存在多个 Feature（功能）入口：

> Intent Routing（意图路由）应在更高系统层设计。

------

# 13. Architecture Invariants（架构不变量）

NLQ V1（自然语言查询第一版）长期保持以下架构规则。

### Invariant 1 — Domain Owns Business Truth（领域拥有业务事实）

Metric（指标）、Schema Semantic（结构语义）、Relationship（关系）等正式业务事实：

> 不由 LLM（大语言模型）或 Retrieval（检索）创造。

------

### Invariant 2 — Model Proposes, Program Decides（模型提出，程序裁决）

模型可以处理自然语言不确定性。

确定性程序负责：

- Query Safety（查询安全）；
- Authorization（权限）；
- Business Rule Enforcement（业务规则执行）。

------

### Invariant 3 — Retrieval Proposes, Authoritative Source Decides（检索提出，权威源裁决）

Retrieval（检索）：

> 寻找 Candidate（候选）。

Authoritative Semantic Source（权威语义源）：

> 定义正式业务事实。

------

### Invariant 4 — No Invented Join（禁止创造连接）

SQL Generation（SQL 生成）不得创造未被 Schema Linking（结构关联）正式解析的 Relationship / Join（关系 / 连接）。

------

### Invariant 5 — Candidate SQL Is Untrusted（候选 SQL 不可信）

Candidate SQL（候选 SQL）：

> 不得直接执行。

必须经过：

```
SQL Validation & Guard
（SQL 校验与防护）

+

Final Authorization Enforcement
（最终权限强制校验）
```

------

### Invariant 6 — SQL Safety ≠ Authorization（SQL 安全不等于权限）

查询安全与用户数据权限：

> 保持独立责任。

------

### Invariant 7 — Authorization Is Deterministic（权限必须确定性）

LLM（大语言模型）：

> 不得成为最终权限裁决者。

------

### Invariant 8 — Clarification Is for User Ambiguity（澄清只解决用户歧义）

系统内部失败：

> 不得转嫁给用户澄清。

------

### Invariant 9 — QueryResult ≠ Raw Query Result（查询结果不等于数据库原始结果）

数据库结果必须经过：

> Query Result Assembly（查询结果组装）。

------

### Invariant 10 — QueryResult ≠ API / UI Model（查询结果不等于接口 / 界面模型）

Feature Result（功能结果）、API Response（接口响应）和 UI View Model（界面展示模型）：

> 保持边界分离。

------

### Invariant 11 — Source of Truth Is Authoritative（事实源必须权威）

Retrieval Index（检索索引）：

> 是 Derived Runtime Asset（派生运行资产）。

不是：

> Business Source of Truth（业务事实源）。

------

### Invariant 12 — Stable Core, Replaceable Edge（稳定核心，可替换边缘）

NLQ（自然语言查询）核心不得绑定：

- Model Provider（模型供应商）；
- Vector Database（向量数据库）；
- Embedding Model（向量模型）；
- Database Driver（数据库驱动）；
- Retrieval Framework（检索框架）。

------

### Invariant 13 — No Silent Degradation（禁止静默降级）

任何 Module（模块）：

> 不得通过修改业务语义换取技术成功。

------

### Invariant 14 — Trusted Data Before Analysis（可信数据先于分析）

Business Analysis（经营分析）：

> 必须建立在 Trusted QueryResult（可信查询结果）之上。

------

# 14. V1 Architecture Non-Goals（第一版架构非目标）

NLQ V1（自然语言查询第一版）不因为未来可能需要而提前建设：

- General Query Planner（通用查询规划器）；
- SQL Repair Agent（SQL 修复智能体）；
- Agentic Retry Loop（智能体重试循环）；
- LangGraph Workflow（LangGraph 工作流）；
- Multi-Agent System（多智能体系统）；
- 通用 Enterprise Semantic Platform（企业语义平台）；
- 完整 Metadata Platform（元数据平台）；
- Complex Authorization Platform（复杂权限平台）；
- Full Real-Time Index Synchronization Platform（全量实时索引同步平台）。

这些能力只有在出现真实：

- Feature Requirement（功能需求）；
- Evaluation Evidence（评估证据）；
- Performance Evidence（性能证据）

时重新评估。

原则：

> **Do Not Overbuild（不过度建设）。**

------

# 15. Deferred Architecture Decisions（延后架构决定）

当前仍允许以下设计在不改变 Feature Architecture（功能架构）主体的情况下继续演进。

## 15.1 SQL Generation Strategy（SQL 生成策略）

Architecture（架构）只固定：

> Generation Context → Candidate SQL（生成上下文 → 候选 SQL）。

不固定最终使用：

- LLM Generation（大语言模型生成）；
- Deterministic Generation（确定性生成）；
- Hybrid Generation（混合生成）。

具体选择根据：

- Evaluation（评估）；
- Maintainability（可维护性）；
- Complexity（复杂度）；
- Latency（延迟）；
- Cost（成本）

决定。

------

## 15.2 Offline Build Trigger（离线构建触发方式）

Architecture（架构）只要求：

> Online Runtime（在线运行）开始服务前存在有效 Retrieval Asset（检索资产）。

具体 Build Trigger（构建触发方式）：

> 属于后续 Implementation / Operation Design（实现 / 运行设计）。

------

## 15.3 Retrieval Asset Versioning（检索资产版本）

后续生产化可以进一步定义：

- Source Version（源版本）；
- Index Version（索引版本）；
- Content Hash（内容哈希）；
- Asset Validity（资产有效性）；
- Rebuild / Publish（重建 / 发布）。

具体机制：

> 不属于当前 Feature Architecture（功能架构）。

------

# 16. Architecture Baseline（架构基线）

NLQ V1（自然语言查询第一版）的稳定结构为：

```
Natural Language Query
（自然语言查询）

├── Online Runtime
│
│   Current Query
│       ↓
│   Query Semantic Parser
│       ↓
│   Semantic Query Intent
│       ↓
│   ┌────────────────────────────┐
│   ↓                            ↓
│   Schema Linking        Metric Resolution
│   ↓                            ↓
│   Resolved Schema       Resolved Metric
│   Context               Context
│   └────────────┬───────────────┘
│                ↓
│   Generation Context Assembly
│                ↓
│   SQL Generation
│                ↓
│   SQL Validation & Guard
│                ↓
│   Final Authorization Enforcement
│                ↓
│   Query Execution
│                ↓
│   Query Result Assembly
│                ↓
│   QueryResult
│
└── Offline Preparation

    Authoritative Semantic Sources
                ↓
    Resource Validation
                ↓
    Semantic Asset Preparation
                ↓
    Embedding / Index Build
                ↓
    Validated Retrieval Assets
                ↓
    Online Semantic Retrieval
```

横切能力：

```
Domain Authorization
（领域权限）

Conversation Context Resolution
（会话上下文解析）
```

最终结构原则：

> **Query Semantic Parser（查询语义解析器）确定用户想查什么。**

> **Schema Linking（结构关联）确定数据在哪里以及结构如何合法连接。**

> **Metric Resolution（指标解析）确定正式指标是什么。**

> **Generation Context Assembly（生成上下文组装）汇合并校验可信上下文。**

> **SQL Generation（SQL 生成）表达查询，但不能重新定义业务事实。**

> **SQL Validation & Guard（SQL 校验与防护）确保候选查询结构和安全合法。**

> **Domain Authorization（领域权限）确定用户是否允许访问对应业务数据。**

> **Query Execution（查询执行）只执行安全且已授权的查询。**

> **Query Result Assembly（查询结果组装）把数据库原始结果转换为稳定业务结果。**

> **Offline Preparation（离线准备）负责产生运行资产，Authoritative Semantic Source（权威语义源）始终拥有业务事实。**

------


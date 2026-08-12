# Natural Language Query Architecture
# 自然语言查询功能架构

> Status（状态）：Frozen V1（V1 已冻结）  
> Feature（功能）：Natural Language Query（自然语言查询）  
> Architecture Style（架构风格）：Modular Monolith（模块化单体）  
> Document Level（文档层级）：Feature Architecture（功能架构）  
> Scope（范围）：ChatBI Engine（ChatBI 引擎）

---

# 1. Purpose（目的）

本文档定义 ChatBI Engine（ChatBI 引擎）中 Natural Language Query（自然语言查询，以下简称 NLQ）的 Feature Architecture（功能架构）。

本文档用于明确：

- NLQ（自然语言查询）的 Feature Responsibility（功能职责）
- NLQ（自然语言查询）的 Feature Boundary（功能边界）
- Online Runtime（在线运行链路）
- Offline Preparation（离线准备链路）
- Module Map（模块地图）
- Module Responsibility（模块职责）
- Major Input / Output（主要输入 / 输出）
- Module Collaboration（模块协作）
- Cross-Cutting Constraints（横切约束）
- Online / Offline Boundary（在线 / 离线边界）
- External Capability Map（外部能力地图）
- Outcome Boundary（结果边界）
- Architecture Decisions（架构决策）
- Deferred Decisions（延后决策）

本文档不定义：

- 具体 Class（类）
- 具体 Function（函数）
- 具体文件结构
- Pydantic Model（Pydantic 数据模型）
- 字段级 Schema（结构模式）
- Prompt（提示词）
- LLM Model（大语言模型型号）
- Retrieval Algorithm（检索算法）
- Top-K（前 K 个结果）
- Threshold（阈值）
- Retry（重试）策略
- SDK（软件开发工具包）
- Framework API（框架接口）
- Exception Code（异常码）
- Test Case（测试用例）
- 数据库连接参数
- 具体基础设施实现细节

上述内容由后续 Feature Spec（功能规格）、Module Spec（模块规格）、Test / Evaluation（测试 / 评估）和 Implementation（实现）阶段定义。

---

# 2. Feature Responsibility（功能职责）

Natural Language Query（自然语言查询）的核心职责是：

> 将用户的自然语言业务查询解析为可信、受控、可执行的数据查询，并返回结构化、可追溯、与底层物理数据库实现解耦的 Query Result（查询结果）。

NLQ（自然语言查询）主要完成以下业务闭环：

```text
用户自然语言问题
        ↓
理解用户查询意图
        ↓
定位正确的数据结构
        ↓
解析正确的指标定义
        ↓
形成可信查询上下文
        ↓
生成查询
        ↓
确定性校验与安全防护
        ↓
权限强制约束
        ↓
执行数据库查询
        ↓
构造结构化业务查询结果
```

NLQ（自然语言查询）的核心原则：

> Trusted Data Before Analysis（可信数据先于分析）

> Domain Owns Business Truth（领域拥有业务事实）

> Model Proposes, Program Decides（模型提出，程序裁决）

> Stable Core, Replaceable Edge（稳定核心，可替换边缘）

> Do Not Overbuild（不过度建设）

---

# 3. Feature Boundary（功能边界）

## 3.1 NLQ（自然语言查询）负责

NLQ（自然语言查询）负责：

- 理解当前用户的业务查询语义
- 结合必要的 Conversation Semantic Context（会话语义上下文）恢复连续查询意图
- 识别用户查询中真正缺失或存在歧义的业务语义
- 将业务语义映射到合法数据库结构
- 确定合法的表、字段、锚表和连接关系
- 将用户指标表达绑定到正式 Metric Catalog（指标目录）
- 组装 SQL Generation（SQL 生成）所需的可信上下文
- 生成 Candidate SQL（候选 SQL）
- 对 Candidate SQL（候选 SQL）进行确定性校验与安全防护
- 执行最终领域权限约束
- 受控执行只读数据库查询
- 将数据库原始结果转换为稳定的 Query Result（查询结果）

---

## 3.2 NLQ（自然语言查询）不负责

NLQ（自然语言查询）不负责：

- Business Analysis（经营分析）
- Root Cause Analysis（根因分析）
- Query Planning for Business Analysis（经营分析查询规划）
- Visualization（可视化）
- Chart Recommendation（图表推荐）
- UI Rendering（界面渲染）
- Frontend View Model（前端展示模型）
- Platform Conversation Management（平台会话管理）
- Authentication（身份认证）
- 企业级 Identity Management（身份管理）
- 平台级 API Gateway（接口网关）
- 通用 Logging（日志）
- 通用 Tracing（链路追踪）
- 通用 Metrics（监控指标）
- 通用 Secret Management（密钥管理）

这些能力由系统其他 Layer（层）、Feature（功能）或 Platform（平台）承担。

---

# 4. Architecture Overview（架构总览）

NLQ（自然语言查询）由两条主要处理路径组成：

```text
Natural Language Query
（自然语言查询）

├── Offline Preparation
│   （离线准备链路）
│
└── Online Runtime
    （在线运行链路）
```

其中：

- Offline Preparation（离线准备）负责准备在线检索所需的语义资产
- Online Runtime（在线运行）负责处理用户实时自然语言查询

---

# 5. Online Runtime（在线运行链路）

## 5.1 Main Flow（主链路）

```text
Current Query
（当前查询）

+

Conversation Semantic Context
（会话语义上下文）

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

┌─────────────────────────────────┐
│                                 │
↓                                 ↓

Schema Linking              Metric Resolution
（结构关联）                 （指标解析）

↓                                 ↓

Resolved Schema Context     Resolved Metric Context
（已解析结构上下文）          （已解析指标上下文）

│                                 │
└──────────────┬──────────────────┘
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

Query Result
（查询功能结果）
```

---

# 6. Feature Entry（功能入口）

Feature Entry（功能入口）负责接收已经通过外部接口契约校验的 NLQ（自然语言查询）请求。

Feature Entry（功能入口）仅承担基础入口责任，不作为独立 Module（模块）。

主要职责：

- 确认请求满足进入 NLQ（自然语言查询）的最低条件
- 确保当前查询内容存在
- 将当前查询与必要上下文交给 Query Semantic Parser（查询语义解析器）

Feature Entry（功能入口）不负责：

- 外部 API Contract Validation（接口契约校验）
- 用户身份认证
- 用户业务语义理解
- Schema Linking（结构关联）
- Metric Resolution（指标解析）

外部 API Contract Validation（接口契约校验）属于 Interfaces / Platform Boundary（接口层 / 平台边界）。

---

# 7. Query Semantic Parser（查询语义解析器）

## 7.1 Responsibility（职责）

Query Semantic Parser（查询语义解析器）负责：

> 结合当前用户查询与 Conversation Semantic Context（会话语义上下文），理解并提取用户真正的业务查询语义，形成 Semantic Query Intent（语义查询意图）。

---

## 7.2 Major Input（主要输入）

- Current Query（当前查询）
- Conversation Semantic Context（会话语义上下文，可选）

---

## 7.3 Major Output（主要输出）

正常：

- Semantic Query Intent（语义查询意图）

业务意图仍然缺失或存在真实歧义：

- Clarification（澄清）

---

## 7.4 Major Capabilities（主要能力）

- Query Preparation（查询准备）
- Semantic Understanding（语义理解）
- Semantic Extraction（语义提取）
- Context Carry-Forward（上下文继承）
- Semantic Completeness Detection（语义完整性判断）
- Semantic Ambiguity Detection（语义歧义判断）

---

## 7.5 Clarification Boundary（澄清边界）

Clarification（澄清）仅允许处理：

> 用户业务意图本身仍然缺失或存在无法唯一确定的歧义。

例如：

```text
用户：
“销售情况怎么样？”
```

如果无法确定用户真正希望查询的指标或范围，可以产生 Clarification（澄清）。

但是一旦 Query Semantic Parser（查询语义解析器）已经声明：

> 用户语义完整。

后续模块不得因为系统内部问题重新要求用户澄清。

---

## 7.6 Not Responsible For（不负责）

Query Semantic Parser（查询语义解析器）不负责：

- 决定实际数据库表
- 决定实际数据库字段
- 决定 Join（连接）关系
- 定义指标公式
- 生成 SQL（结构化查询语言）
- 判断最终权限
- 执行数据库查询

---

# 8. Schema Linking（结构关联）

## 8.1 Responsibility（职责）

Schema Linking（结构关联）负责：

> 将已经明确的业务查询语义映射到查询所需的合法数据库结构，并确定这些结构之间应该如何连接。

---

## 8.2 Major Input（主要输入）

- Semantic Query Intent（语义查询意图）
- Authorization Context（权限上下文）

---

## 8.3 Major Output（主要输出）

- Resolved Schema Context（已解析结构上下文）

---

## 8.4 Major Capabilities（主要能力）

### Schema Grounding（结构语义映射）

将业务概念映射到实际可查询的数据结构。

### Anchor Selection（锚表选择）

确定查询的主要业务数据主体。

### Relationship Resolution（关系解析）

确定查询可以使用哪些权威数据关系。

### Join Resolution（连接解析）

确定查询所需数据结构之间合法的 Join Path（连接路径）。

### Resolution Validation（解析结果校验）

确认结构解析结果在概念层面完整、一致并具有合法连接关系。

具体规则由 Module Spec（模块规格）定义。

---

## 8.5 Core Rule（核心规则）

> SQL Generation（SQL 生成）不得自行发明 Join（连接）关系。

合法的表关联关系必须由 Schema Linking（结构关联）基于权威 Schema Metadata（结构元数据）确定。

Retrieval（检索）可以帮助发现 Candidate Table / Column（候选表 / 字段），但不能决定结构是否合法。

合法性必须由 Authoritative Schema Metadata（权威结构元数据）裁决。

---

## 8.6 Not Responsible For（不负责）

Schema Linking（结构关联）不负责：

- 用户业务意图解析
- 正式指标定义
- SQL Generation（SQL 生成）
- SQL Execution（SQL 执行）
- 用户业务语义澄清
- 凭空创造数据库关系

---

# 9. Metric Resolution（指标解析）

## 9.1 Responsibility（职责）

Metric Resolution（指标解析）负责：

> 将用户已经明确的指标表达解析并绑定到正式 Metric Catalog（指标目录）定义的权威指标语义。

---

## 9.2 Major Input（主要输入）

- Semantic Query Intent（语义查询意图）
- Authorization Context（权限上下文）

---

## 9.3 Major Output（主要输出）

- Resolved Metric Context（已解析指标上下文）

---

## 9.4 Major Capabilities（主要能力）

- Metric Matching（指标匹配）
- Authoritative Metric Resolution（权威指标解析）
- Resolution Validation（解析结果校验）

---

## 9.5 Core Rule（核心规则）

> Metric Resolution（指标解析）消费指标事实，不创造指标事实。

Metric Catalog（指标目录）是指标业务定义的 Authoritative Source（权威源）。

Retrieval Index（检索索引）可以携带完整 Metric Card（指标卡）并直接供在线链路使用，但其中内容必须来源于 Metric Catalog（指标目录）。

---

## 9.6 Not Responsible For（不负责）

Metric Resolution（指标解析）不负责：

- 理解用户完整自然语言
- Schema Linking（结构关联）
- Join Resolution（连接解析）
- 创建新的指标公式
- SQL Generation（SQL 生成）
- Query Execution（查询执行）

---

# 10. Parallel Resolution（并行解析关系）

Schema Linking（结构关联）与 Metric Resolution（指标解析）在逻辑上是两个相对独立的解析方向。

```text
Semantic Query Intent
（语义查询意图）

        ↓

┌────────────────────┐
↓                    ↓

Schema Linking       Metric Resolution
（结构关联）          （指标解析）

解决：
Where（数据在哪里）  How（业务指标怎么算）
```

Feature Architecture（功能架构）允许将二者表达为 Parallel Capability Paths（并行能力路径）。

但：

> 架构上的并行，不等于实现必须使用多线程、异步任务或并发执行。

具体执行方式属于 Implementation（实现）阶段。

---

# 11. Generation Context Assembly（生成上下文组装）

## 11.1 Responsibility（职责）

Generation Context Assembly（生成上下文组装）负责：

> 将用户查询语义、已解析结构上下文和已解析指标上下文汇合为 SQL Generation（SQL 生成）可直接消费的统一可信 Generation Context（生成上下文）。

---

## 11.2 Major Input（主要输入）

- Semantic Query Intent（语义查询意图）
- Resolved Schema Context（已解析结构上下文）
- Resolved Metric Context（已解析指标上下文）

---

## 11.3 Major Output（主要输出）

- Generation Context（生成上下文）

---

## 11.4 Major Capabilities（主要能力）

- Context Merge（上下文汇合）
- Context Reconciliation（上下文协调）
- Context Completeness Validation（上下文完整性校验）

---

## 11.5 Core Rule（核心规则）

Generation Context Assembly（生成上下文组装）必须确认：

```text
Semantic Query Intent
（用户想查什么）

         ↕

Resolved Schema Context
（数据在哪里）

         ↕

Resolved Metric Context
（指标怎么定义）
```

三者不存在明显冲突。

该模块不得在发现冲突后：

- 静默修改上游结果
- 凭空补充业务信息
- 再次调用模型猜测缺失业务事实

如果上下文无法协调：

> 应产生明确 Failure（失败），并进入 Bad Case Loop（失败案例闭环）。

---

# 12. SQL Generation（SQL 生成）

## 12.1 Responsibility（职责）

SQL Generation（SQL 生成）负责：

> 根据可信 Generation Context（生成上下文），生成表达当前业务查询意图的 Candidate SQL（候选 SQL）。

---

## 12.2 Major Input（主要输入）

- Generation Context（生成上下文）

---

## 12.3 Major Output（主要输出）

- Candidate SQL（候选 SQL）

---

## 12.4 Major Capability（主要能力）

- Query Synthesis（查询合成）
- Generation Result Production（生成结果产出）

---

## 12.5 Generation Strategy（生成策略）

Feature Architecture（功能架构）不将 SQL Generation（SQL 生成）绑定到特定生成技术。

允许的 Generation Strategy（生成策略）包括：

### LLM Generation（大模型生成）

由 LLM（大语言模型）基于 Generation Context（生成上下文）生成 SQL。

### Deterministic Generation（确定性生成）

由确定性程序或 SQL Compiler（SQL 编译器）根据结构化查询计划生成 SQL。

### Hybrid Generation（混合生成）

由 LLM（大语言模型）承担部分理解或规划，再由确定性程序生成最终 SQL。

当前 V1（第一版）可以优先采用 LLM Generation（大模型生成）以降低初始工程复杂度。

是否引入 Deterministic SQL Compiler（确定性 SQL 编译器）由后续 Evaluation（评估）结果和维护成本决定。

---

## 12.6 Core Rule（核心规则）

SQL Generation（SQL 生成）不得：

- 重新搜索数据库 Schema（结构）
- 自行决定新的指标定义
- 自行发明 Join（连接）关系
- 越过 Resolved Schema Context（已解析结构上下文）
- 越过 Resolved Metric Context（已解析指标上下文）

Candidate SQL（候选 SQL）不是可信执行结果。

它必须进入后续 SQL Validation & Guard（SQL 校验与防护）。

---

# 13. SQL Validation & Guard（SQL 校验与防护）

## 13.1 Responsibility（职责）

SQL Validation & Guard（SQL 校验与防护）负责：

> 对 Candidate SQL（候选 SQL）进行确定性的结构、范围和安全校验，只有满足执行约束的查询才能进入后续权限裁决阶段。

---

## 13.2 Major Input（主要输入）

- Candidate SQL（候选 SQL）
- 必要的 Resolved Schema Context（已解析结构上下文）

---

## 13.3 Major Output（主要输出）

正常：

- Validated SQL（已校验 SQL）

失败：

- SQL Validation Failure（SQL 校验失败）

---

## 13.4 Major Capabilities（主要能力）

### SQL Structure Validation（SQL 结构校验）

判断 SQL 是否满足合法查询结构。

### Query Scope Validation（查询范围校验）

判断 Candidate SQL（候选 SQL）是否越过当前已解析的数据结构范围。

### Safety Guard（安全防护）

判断 SQL 是否满足 ChatBI Engine（ChatBI 引擎）的安全查询约束。

### Validation Result Decision（校验结果裁决）

对 Candidate SQL（候选 SQL）做明确 PASS / FAIL（通过 / 失败）裁决。

---

## 13.5 Core Rule（核心规则）

> Model Proposes, Program Decides（模型提出，程序裁决）。

SQL Generation（SQL 生成）可以使用模型。

SQL Validation & Guard（SQL 校验与防护）必须以 Deterministic Rule（确定性规则）完成最终安全裁决。

---

## 13.6 No Silent Degradation（禁止静默降级）

如果 Candidate SQL（候选 SQL）不符合约束：

```text
Candidate SQL
        ↓
Validation Failure
（校验失败）
        ↓
Feature Failure
（功能失败）
        ↓
Bad Case Loop
（失败案例闭环）
```

不得：

```text
发现问题
↓
忽略
↓
继续执行
```

---

## 13.7 SQL Repair（SQL 修复）

V1（第一版）不要求 SQL Validation & Guard（SQL 校验与防护）自动修改 SQL。

即：

```text
Validation
≠
Repair
```

未来只有 Evaluation（评估）证明自动修复具有明确价值时，才考虑 SQL Repair / Retry（SQL 修复 / 重试）。

---

## 13.8 Not Responsible For（不负责）

SQL Validation & Guard（SQL 校验与防护）不负责：

- SQL Generation（SQL 生成）
- Schema Linking（结构关联）
- Metric Resolution（指标解析）
- Domain Authorization（领域权限）
- Query Execution（查询执行）
- 用户业务语义澄清

---

# 14. Authorization（权限）

Authorization（权限）不是单纯位于主链某一个位置的普通 Module（模块）。

它属于：

> Cross-Cutting Capability（横切能力）

并且在查询执行前存在：

> Final Enforcement Point（最终强制执行点）

---

# 15. Authorization Context（权限上下文）

## 15.1 Responsibility（职责）

Authorization Capability（权限能力）负责：

> 根据当前用户身份建立其在 ChatBI 业务领域中的权限范围，并将权限约束提供给真正需要的业务模块。

---

## 15.2 Architecture Pattern（架构模式）

```text
Platform Identity
（平台身份）

        ↓

Authorization Context
（权限上下文）

        │
        ├────────→ Schema Linking
        │          （结构关联）
        │
        ├────────→ Metric Resolution
        │          （指标解析）
        │
        └────────→ Final Authorization Enforcement
                   （最终权限强制校验）
```

---

## 15.3 Core Rule（核心规则）

不是：

```text
每经过一个 Module
↓
重新远程查询一次权限
```

而是：

```text
解析权限上下文
        ↓
建立 Authorization Context
（权限上下文）
        ↓
必要模块消费
        ↓
执行前最终强制校验
```

---

## 15.4 LLM Boundary（大模型边界）

LLM（大语言模型）不得作为最终 Authorization Decision Maker（权限裁决者）。

LLM（大语言模型）可以理解：

> 用户想查询什么。

但权限系统必须确定性判断：

> 用户是否允许查询这些数据。

即：

```text
LLM
→ 理解请求

Program / Policy
（程序 / 权限策略）
→ 做权限裁决
```

---

# 16. Final Authorization Enforcement（最终权限强制校验）

## 16.1 Responsibility（职责）

Final Authorization Enforcement（最终权限强制校验）负责：

> 在数据库执行之前，对最终查询进行不可绕过的权限裁决。

---

## 16.2 Major Input（主要输入）

- Validated SQL（已校验 SQL）
- Authorization Context（权限上下文）
- 必要的 Resolved Query Context（已解析查询上下文）

---

## 16.3 Major Output（主要输出）

成功：

- Authorized Query（已授权查询）

拒绝：

- Authorization Denied（权限拒绝）

---

## 16.4 Core Rule（核心规则）

SQL Safety（SQL 安全）与 Authorization（权限）必须分离。

一条查询可以同时满足：

```text
SQL 语法正确
+
SQL 只读
+
SQL 结构安全
```

但用户仍然可能：

```text
没有权限访问对应业务数据
```

因此：

```text
SQL Validation & Guard
（SQL 校验与防护）

≠

Domain Authorization
（领域权限校验）
```

---

# 17. Query Execution（查询执行）

## 17.1 Responsibility（职责）

Query Execution（查询执行）负责：

> 执行已经通过 SQL 安全校验和领域权限校验的查询，并返回数据库真实查询结果。

---

## 17.2 Major Input（主要输入）

- Authorized Query（已授权查询）

---

## 17.3 Major Output（主要输出）

- Raw Query Result（原始查询结果）

---

## 17.4 Major Capabilities（主要能力）

- Query Submission（查询提交）
- Execution Control（执行控制）
- Result Retrieval（结果获取）

---

## 17.5 Database Boundary（数据库边界）

数据库本身应作为最后一道安全边界。

整体原则：

```text
Application Guard
（应用层防护）

        ↓

Authorization Enforcement
（权限强制校验）

        ↓

Read-Only Database Access
（数据库只读访问）
```

形成 Defense in Depth（纵深防御）。

具体数据库账号、权限语句和连接方式由 Implementation（实现）阶段定义。

---

## 17.6 Not Responsible For（不负责）

Query Execution（查询执行）不负责：

- 理解用户问题
- 修改用户查询意图
- Schema Linking（结构关联）
- Metric Resolution（指标解析）
- SQL Generation（SQL 生成）
- SQL Repair（SQL 修复）
- 权限策略定义
- 业务结果解释

---

# 18. Query Result Assembly（查询结果组装）

## 18.1 Responsibility（职责）

Query Result Assembly（查询结果组装）负责：

> 将数据库 Raw Query Result（原始查询结果）转换为稳定、结构化、与底层物理数据库实现解耦的业务 Query Result（查询结果）。

---

## 18.2 Major Input（主要输入）

- Raw Query Result（原始查询结果）
- 必要的 Semantic Query Context（语义查询上下文）
- 必要的 Resolved Metric Context（已解析指标上下文）
- 必要的 Result Evidence Context（结果证据上下文）

---

## 18.3 Major Output（主要输出）

- Query Result（查询结果）

---

# 19. Query Result Model Principle（查询结果模型原则）

数据库通常返回：

```text
Columns
（列）

+

Rows
（行）
```

NLQ（自然语言查询）应保留结构化表格模型作为结果核心。

概念上：

```text
Query Result
（查询结果）

├── Columns
│   （结果列）
│
├── Rows
│   （结果行）
│
├── Business Semantics
│   （业务语义）
│
├── Query Context Summary
│   （查询上下文摘要）
│
└── Evidence
    （必要证据）
```

具体字段定义由 Feature Spec（功能规格）和 Module Spec（模块规格）完成。

---

# 20. Semantic Identity vs Display Label（语义标识与展示名称）

Query Result（查询结果）不应该把物理数据库字段名称直接作为稳定的上层业务契约。

推荐逻辑：

```text
Physical Database Field
（物理数据库字段）

        ↓

Business Semantic Identity
（业务语义标识）

        ↓

Display Label
（展示名称）
```

例如概念上：

```text
数据库字段
        ↓
gross_profit
（毛利业务语义标识）
        ↓
“毛利”
（中文展示名称）
```

稳定契约依赖：

> Business Semantic Identity（业务语义标识）

而不是：

- 数据库物理字段名
- 当前中文展示文案

---

# 21. Query Result Boundary（查询结果边界）

必须区分三个层次：

```text
Feature Result
（功能结果）

≠

API Response
（接口响应）

≠

UI View Model
（界面展示模型）
```

NLQ（自然语言查询）只负责：

> Query Result（查询功能结果）。

其后由 Interfaces Layer（接口层）完成：

```text
Query Result
（查询结果）

        ↓

Platform Contract Mapping
（平台契约映射）

        ↓

Run Outcome
（执行结果）

        ↓

API Response / SSE Event
（接口响应 / 服务器发送事件）

        ↓

Frontend / Other Client
（前端 / 其他客户端）
```

---

# 22. Visualization Boundary（可视化边界）

NLQ（自然语言查询）不负责：

- Chart（图表）生成
- Chart Recommendation（图表推荐）
- Table Rendering（表格渲染）
- 数字显示格式
- 前端颜色
- 前端布局

未来可以由其他能力消费 Query Result（查询结果）：

```text
Query Result
（查询结果）

├──→ Table Renderer
│    （表格渲染）
│
├──→ Chart Generator
│    （图表生成）
│
├──→ Export
│    （导出）
│
└──→ Business Analysis
     （经营分析）
```

---

# 23. Conversation Context（会话上下文）

Conversation（会话）不作为 NLQ（自然语言查询）内部独立 Module（模块）。

Product Conversation（产品会话）由 Platform（平台）拥有。

ChatBI Engine（ChatBI 引擎）只消费与当前业务查询有关的：

> Conversation Semantic Context（会话语义上下文）

---

## 23.1 Context Flow（上下文流）

```text
Platform Conversation
（平台会话）

        ↓

Conversation Context Resolution
（会话上下文解析）

        ↓

Conversation Semantic Context
（会话语义上下文）

        ↓

Query Semantic Parser
（查询语义解析器）
```

---

## 23.2 Conversation History vs Domain State（会话历史与领域状态）

必须区分：

### Conversation History（会话历史）

原始用户 / 系统聊天内容。

由 Platform（平台）拥有。

### Domain State（领域状态）

ChatBI 当前真正需要继承的业务查询语义状态。

例如概念上：

- Previous Query Intent（上一轮查询意图）
- Previous Metric Context（上一轮指标上下文）
- Previous Time Context（上一轮时间上下文）
- Previous Dimension Context（上一轮维度上下文）
- Previous Query Result Reference（上一轮查询结果引用）

具体状态结构后续定义。

---

## 23.3 Context Carry-Forward（上下文继承）

Query Semantic Parser（查询语义解析器）允许：

> 根据当前查询和 Conversation Semantic Context（会话语义上下文）恢复当前完整查询意图。

例如：

```text
上一轮：
“2025 年华东销售额是多少？”

下一轮：
“那毛利呢？”
```

系统可以继承：

```text
时间：
2025

区域：
华东
```

并替换：

```text
指标：
销售额 → 毛利
```

具体继承规则由后续 Module Spec（模块规格）定义。

---

# 24. Clarification / Unsupported / Failure Boundary
# 澄清 / 不支持 / 失败边界

NLQ（自然语言查询）必须明确区分三种结果。

---

## 24.1 Clarification（澄清）

仅表示：

> 用户业务意图仍然缺失或存在真实歧义。

例如：

```text
“帮我看看销售情况”
```

如果当前上下文不足以唯一确定业务请求，可以产生 Clarification（澄清）。

---

## 24.2 Unsupported（不支持）

表示：

> 用户请求已经明确，但当前系统没有设计支持该能力。

例如未来用户请求某种系统当前明确未支持的复杂分析。

---

## 24.3 Failure（失败）

表示：

> 系统按照现有能力设计本应完成，但本次执行失败。

例如：

- Schema Resolution Failure（结构解析失败）
- Metric Resolution Failure（指标解析失败）
- SQL Generation Failure（SQL 生成失败）
- SQL Validation Failure（SQL 校验失败）
- Dependency Failure（依赖失败）
- Query Execution Failure（查询执行失败）

---

## 24.4 Core Principle（核心原则）

```text
用户意图本身不清楚
        ↓
Clarification
（澄清）


系统根本没有这个能力
        ↓
Unsupported
（不支持）


系统应该能做但这次失败
        ↓
Failure
（失败）
        ↓
Bad Case Loop
（失败案例闭环）
```

原则：

> User Clarifies Intent; System Resolves Structure  
> 用户澄清意图，系统解决结构。

不得要求业务用户帮助系统选择：

- 数据库字段
- 数据库表
- Join（连接）路径
- SQL（结构化查询语言）
- 内部技术实现

---

# 25. Offline Preparation（离线准备）

NLQ（自然语言查询）不仅包含 Online Runtime（在线运行链路），还存在一个为在线查询准备检索资产的 Offline Preparation（离线准备链路）。

---

# 26. Offline Preparation Main Flow（离线准备主链路）

```text
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

Schema Linking
（结构关联）

/

Metric Resolution
（指标解析）
```

---

# 27. Authoritative Semantic Sources（权威语义源）

Offline Preparation（离线准备）从正式业务语义资源构建检索资产。

主要包括：

- Schema Metadata（结构元数据）
- Metric Catalog（指标目录）
- Relationship Metadata（关系元数据）
- 其他正式 Semantic Resources（语义资源）

这些资源负责定义 Business Truth（业务事实）。

---

# 28. Retrieval Index（检索索引）

Retrieval Index（检索索引）是：

> 由 Authoritative Semantic Sources（权威语义源）生成的 Derived / Materialized Asset（派生 / 物化资产）。

Retrieval Index（检索索引）可以包含：

```text
Embedding
（向量）

+

完整 Semantic Payload
（完整语义载荷）

+

Metadata
（元数据）
```

因此 Online Runtime（在线运行时）检索得到结果以后：

> 可以直接使用检索索引携带的完整业务内容。

不要求每一次：

```text
Vector Retrieval
（向量检索）
        ↓
取得 ID
        ↓
再次读取原始 Catalog
（原始目录）
```

---

# 29. Source of Truth Principle（事实源原则）

即使 Retrieval Index（检索索引）保存完整业务内容：

> 它仍然不是 Business Source of Truth（业务事实源）。

正确关系：

```text
Authoritative Source
（权威源）

        ↓

Offline Build
（离线构建）

        ↓

Runtime Projection
（运行时投影）

        ↓

Retrieval Index
（检索索引）
```

业务定义修改必须发生在 Authoritative Source（权威源）。

然后：

```text
修改权威资源
        ↓
重新验证
        ↓
重新构建 / 更新索引
        ↓
发布新的 Retrieval Asset
（检索资产）
```

不得绕过权威源直接修改向量索引中的业务定义。

---

# 30. Retrieval Responsibility（检索职责）

Retrieval（检索）的主要职责是：

> 找到最相关的候选业务语义资产。

但是：

> Retrieval Similarity（检索相似度）不等于 Business Truth（业务事实）。

Schema（结构）侧：

```text
Retrieval
（检索）
        ↓
Candidate Tables / Columns
（候选表 / 字段）

        ↓
Authoritative Metadata
（权威元数据）

        ↓
合法结构裁决
```

Metric（指标）侧：

```text
Retrieval
（检索）
        ↓
Candidate Metric
（候选指标）

        ↓
Authoritative Metric Definition
（权威指标定义）

        ↓
正式指标解析结果
```

---

# 31. Offline Does Not Equal Infrastructure
# 离线不等于基础设施

必须明确：

```text
Online / Offline
（在线 / 离线）
```

描述的是：

> 能力在什么时候运行。

而：

```text
Application / Domain / Infrastructure
（应用 / 领域 / 基础设施）
```

描述的是：

> 职责属于哪一层。

这是两个不同维度。

---

## 31.1 Conceptual Matrix（概念矩阵）

```text
                         Online              Offline
                        （在线）             （离线）

Application
（应用层）              在线用例编排          离线构建用例

Domain
（领域层）              在线业务规则          离线业务规则

Infrastructure
（基础设施层）          在线技术适配          离线技术适配
```

---

## 31.2 Offline Application Responsibility（离线应用职责）

例如：

```text
读取正式资源
↓
验证资源
↓
准备检索文档
↓
调用向量化能力
↓
写入检索索引
↓
验证资产
↓
发布
```

整个流程的编排属于 Application Responsibility（应用职责）。

---

## 31.3 Offline Domain Responsibility（离线领域职责）

例如：

- Metric Catalog Validation（指标目录校验）
- Relationship Validation（关系校验）
- Semantic Consistency Validation（语义一致性校验）

这些属于 Domain Rule（领域规则）。

---

## 31.4 Offline Infrastructure Responsibility（离线基础设施职责）

例如：

- Resource Loader（资源加载器）
- Embedding Adapter（向量化适配器）
- Vector Store Adapter（向量存储适配器）
- Index Writer（索引写入器）

这些才属于 Infrastructure（基础设施）。

---

# 32. Build vs Serve（构建与服务）

Architecture（架构）只要求：

> Online Runtime（在线运行时）开始接受用户查询之前，必须存在有效的 Retrieval Assets（检索资产）。

不要求具体采用：

```text
应用启动时构建
```

还是：

```text
独立 Offline Job
（离线任务）构建
```

V1（第一版）可以采用简单方式。

Production（生产环境）未来可以演进为：

```text
Semantic Resource Update
（语义资源更新）

        ↓

Offline Build Job
（离线构建任务）

        ↓

Validation
（验证）

        ↓

Publish
（发布）

        ↓

Online Runtime
（在线运行）
```

因此：

> Build（构建）与 Serve（服务）在架构上保持可分离。

---

# 33. External Capability Map（外部能力地图）

NLQ（自然语言查询）模块不应直接绑定具体基础设施产品。

业务模块依赖：

> Capability / Port（能力 / 端口）

Infrastructure（基础设施）提供：

> Adapter（适配器）

整体原则：

```text
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

---

# 34. Online External Capabilities（在线外部能力）

V1（第一版）定义以下主要 Online Capability（在线能力）。

---

## 34.1 Conversation Context Capability（会话上下文能力）

主要使用者：

- Query Semantic Parser（查询语义解析器）

负责提供：

- 当前查询需要的 Conversation Semantic Context（会话语义上下文）

底层实现不进入 Feature Architecture（功能架构）。

---

## 34.2 Authorization Capability（权限能力）

主要使用者：

- Schema Linking（结构关联）
- Metric Resolution（指标解析）
- Final Authorization Enforcement（最终权限强制校验）

负责提供：

- Authorization Context（权限上下文）
- 最终确定性权限裁决

---

## 34.3 Model Capability（模型能力）

明确使用者：

- Query Semantic Parser（查询语义解析器）

可能使用者：

- SQL Generation（SQL 生成）

SQL Generation（SQL 生成）是否使用模型由 Generation Strategy（生成策略）决定。

Model Capability（模型能力）不绑定：

- 特定 Model Provider（模型供应商）
- 特定模型名称
- 特定 Framework（框架）

---

## 34.4 Semantic Retrieval Capability（语义检索能力）

提供统一 Semantic Retrieval Capability（语义检索能力）。

逻辑上支持：

```text
Semantic Retrieval
（语义检索）

├── Schema Retrieval
│   （结构检索）
│
└── Metric Retrieval
    （指标检索）
```

主要使用者：

- Schema Linking（结构关联）
- Metric Resolution（指标解析）

Feature Architecture（功能架构）不绑定：

- Qdrant（向量数据库）
- PostgreSQL pgvector（PostgreSQL 向量扩展）
- Elasticsearch（搜索引擎）
- 内存索引
- 具体 Embedding Model（向量模型）

---

## 34.5 Database Query Capability（数据库查询能力）

主要使用者：

- Query Execution（查询执行）

负责：

> 提供受控的数据库查询执行能力。

NLQ（自然语言查询）不直接依赖具体数据库驱动。

---

# 35. Offline External Capabilities（离线外部能力）

Offline Preparation（离线准备）主要需要以下能力。

---

## 35.1 Semantic Resource Access Capability（语义资源访问能力）

负责读取：

- Schema Metadata（结构元数据）
- Metric Catalog（指标目录）
- Relationship Metadata（关系元数据）
- 其他权威 Semantic Resources（语义资源）

底层可以是：

- JSON（结构化文本）
- JSONL（逐行结构化文本）
- Metadata Service（元数据服务）
- Semantic Layer（语义层）
- Database Catalog（数据库目录）

Feature Architecture（功能架构）不绑定具体形式。

---

## 35.2 Embedding Capability（向量化能力）

负责：

```text
Semantic Content
（语义内容）

        ↓

Embedding
（向量化）

        ↓

Vector Representation
（向量表示）
```

当前实现可以采用 BGE-M3（向量模型），但 Feature Architecture（功能架构）不绑定该模型。

---

## 35.3 Vector Index Capability（向量索引能力）

负责：

- Build（构建）
- Update（更新）
- Store（存储）
- Publish（发布）

Retrieval Asset（检索资产）。

当前实现可以采用 Qdrant（向量数据库），但 Feature Architecture（功能架构）不绑定该产品。

---

# 36. External Capability Relationship（外部能力关系）

完整能力关系：

```text
                     ONLINE
                     （在线）

Conversation Context Capability
（会话上下文能力）
        ↓
Query Semantic Parser
（查询语义解析器）
        ↓
Model Capability
（模型能力）


Semantic Retrieval Capability
（语义检索能力）
        │
        ├──────────────→ Schema Linking
        │                （结构关联）
        │
        └──────────────→ Metric Resolution
                         （指标解析）


Authorization Capability
（权限能力）
        │
        ├──────────────→ Schema Linking
        ├──────────────→ Metric Resolution
        └──────────────→ Final Authorization Enforcement
                         （最终权限强制校验）


Model Capability
（模型能力）
        ↓
SQL Generation
（SQL 生成，可选依赖）


Database Query Capability
（数据库查询能力）
        ↓
Query Execution
（查询执行）
```

离线：

```text
                     OFFLINE
                     （离线）

Authoritative Semantic Sources
（权威语义源）

        ↓

Semantic Resource Access Capability
（语义资源访问能力）

        ↓

Offline Preparation
（离线准备）

        ├────────→ Embedding Capability
        │          （向量化能力）
        │
        └────────→ Vector Index Capability
                   （向量索引能力）

        ↓

Validated Retrieval Assets
（已验证检索资产）

        ↓

Online Semantic Retrieval
（在线语义检索）
```

---

# 37. Cross-Cutting Engineering Capabilities
# 横切工程能力

以下能力属于系统级 Engineering Capability（工程能力），但不进入 NLQ（自然语言查询）的核心业务 Module Map（模块地图）：

- Logging（日志）
- Tracing（链路追踪）
- Metrics（监控指标）
- Configuration（配置）
- Secret Management（密钥管理）
- Health Check（健康检查）
- Deployment（部署）
- CI/CD（持续集成 / 持续交付）

这些能力可以横切 NLQ（自然语言查询），但不属于其业务模块。

---

# 38. Outcome Boundary（结果边界）

NLQ（自然语言查询）最终可能产生以下 Feature Outcome（功能结果）。

---

## 38.1 QueryResult（查询结果）

表示：

> 查询成功完成，并形成稳定结构化业务结果。

---

## 38.2 Clarification（澄清）

表示：

> 用户业务意图本身仍存在缺失或歧义，需要用户补充业务信息。

---

## 38.3 UnsupportedRequest（不支持请求）

表示：

> 请求本身已经明确，但当前系统没有设计支持该能力。

---

## 38.4 Failure（失败）

表示：

> 系统本应完成当前能力，但此次运行失败。

Failure（失败）属于系统执行问题，不属于正常业务 Outcome（业务结果）。

---

# 39. Platform Result Mapping（平台结果映射）

NLQ（自然语言查询）的 Query Result（查询结果）不是新的外部 API（接口）。

系统继续使用统一 Platform Run Contract（平台执行契约）。

概念上：

```text
ChatBI Run
（ChatBI 执行）

        ↓

Future Intent Router
（未来意图路由器）

        ↓

┌────────────────────────────┐
↓                            ↓

Natural Language Query       Business Analysis
（自然语言查询）             （经营分析）

↓                            ↓

QueryResult                  AnalysisResult
（查询结果）                 （分析结果）

└──────────────┬─────────────┘
               ↓

Run Outcome
（执行结果）

               ↓

Platform Contract
（平台契约）

               ↓

Frontend / Other Client
（前端 / 其他客户端）
```

当前 V1（第一版）只有 NLQ（自然语言查询），因此暂不需要 Intent Router（意图路由器）。

未来 Business Analysis（经营分析）加入以后，再增加系统级 Intent Router（意图路由器）。

---

# 40. Business Analysis Integration Boundary
# 经营分析集成边界

未来 Business Analysis（经营分析）可能需要查询可信业务数据。

Business Analysis（经营分析）不应：

```text
调用自己的外部 HTTP API
（超文本传输协议接口）

↓
解析面向前端的 JSON
（结构化数据）
```

更合理的是通过：

> Internal Query Capability（内部查询能力）

获得：

> Trusted Query Result（可信查询结果）

概念关系：

```text
Business Analysis
（经营分析）

        ↓

Internal Query Capability
（内部查询能力）

        ↓

Trusted Query Result
（可信查询结果）

        ↓

Analysis
（分析）
```

具体 Business Analysis Architecture（经营分析架构）在对应 Feature Architecture（功能架构）中定义。

---

# 41. Architecture Decisions（架构决策）

## AD-01：NLQ（自然语言查询）采用独立 Feature Architecture（功能架构）

NLQ（自然语言查询）作为 ChatBI Engine（ChatBI 引擎）的核心 Feature（功能）独立设计。

Business Analysis（经营分析）不混入 NLQ（自然语言查询）的主链。

---

## AD-02：Query Semantic Parser（查询语义解析器）只理解业务语义

Parser（解析器）不负责：

- Schema（结构）
- Join（连接）
- Metric Formula（指标公式）
- SQL（结构化查询语言）
- Authorization（权限）

避免形成 God Module（万能模块）。

---

## AD-03：Schema Linking（结构关联）拥有结构解析与连接责任

表、字段、锚表、关系和 Join Path（连接路径）由 Schema Linking（结构关联）确定。

SQL Generation（SQL 生成）不得重新发明数据结构。

---

## AD-04：Metric Resolution（指标解析）消费权威指标事实

正式指标定义来自 Metric Catalog（指标目录）。

模型或 Retrieval（检索）不得创造新的业务指标定义。

---

## AD-05：Schema Linking（结构关联）与 Metric Resolution（指标解析）逻辑并行

二者分别解决：

- Where（数据在哪里）
- How（指标怎么算）

但不要求实现层实际并发运行。

---

## AD-06：Generation Context Assembly（生成上下文组装）保持确定性

该模块只负责汇合、协调和校验上游上下文。

不得偷偷重新调用模型或检索来修复上游。

---

## AD-07：SQL Generation（SQL 生成）不绑定 LLM（大语言模型）

SQL Generation（SQL 生成）定义的是责任，而不是具体技术。

允许未来在：

- LLM Generation（大模型生成）
- Deterministic Generation（确定性生成）
- Hybrid Generation（混合生成）

之间演进。

---

## AD-08：Candidate SQL（候选 SQL）永远不是可信执行对象

Candidate SQL（候选 SQL）必须经过：

```text
SQL Validation & Guard
（SQL 校验与防护）

        ↓

Authorization Enforcement
（权限强制校验）
```

之后才能执行。

---

## AD-09：SQL Validation（SQL 校验）与 SQL Safety（SQL 安全）合并

V1（第一版）将二者作为同一个：

> SQL Validation & Guard（SQL 校验与防护）

Module（模块）。

避免过度拆分。

---

## AD-10：Authorization（权限）独立于 SQL Safety（SQL 安全）

SQL 合法、安全，并不代表当前用户有权访问对应数据。

因此 Domain Authorization（领域权限）保持独立责任。

---

## AD-11：Authorization（权限）作为 Cross-Cutting Capability（横切能力）

权限不是每个模块重复查询。

采用：

```text
Authorization Context
（权限上下文）

+

Final Enforcement
（最终强制校验）
```

模式。

---

## AD-12：LLM（大语言模型）不得做最终权限裁决

模型负责理解。

程序 / Policy（策略）负责最终安全和权限裁决。

---

## AD-13：Clarification（澄清）不是独立 Module（模块）

Clarification（澄清）属于 Feature Outcome（功能结果）。

只用于真实用户业务语义缺失或歧义。

---

## AD-14：系统内部失败不得转嫁为用户澄清

一旦用户意图完整，后续：

- Schema（结构）问题
- Metric（指标）问题
- SQL（结构化查询语言）问题
- Dependency（依赖）问题

均进入：

- Failure（失败）
- Unsupported（不支持）
- Bad Case Loop（失败案例闭环）

---

## AD-15：Request Validation（请求校验）不单独建立 Module（模块）

外部 Contract Validation（契约校验）属于接口边界。

Feature Entry Validation（功能入口校验）属于 NLQ（自然语言查询）入口。

Query Normalization（查询规范化）属于 Query Semantic Parser（查询语义解析器）内部责任。

---

## AD-16：Conversation（会话）不属于 NLQ（自然语言查询）内部模块

Platform（平台）拥有 Product Conversation（产品会话）。

Application Layer（应用层）向 NLQ（自然语言查询）提供 Conversation Semantic Context（会话语义上下文）。

---

## AD-17：Online Runtime（在线运行）与 Offline Preparation（离线准备）分离

Offline Preparation（离线准备）构建运行时资产。

Online Runtime（在线运行）消费运行时资产。

---

## AD-18：Retrieval Index（检索索引）可以携带完整业务内容

Online Runtime（在线运行）可以直接消费 Retrieval Index（检索索引）中保存的完整 Semantic Payload（语义载荷）。

不要求每次检索后重新读取原始 Catalog（目录）。

---

## AD-19：Retrieval Index（检索索引）不是业务事实源

Retrieval Index（检索索引）是：

> Derived / Materialized Asset（派生 / 物化资产）。

正式业务事实只能由 Authoritative Semantic Source（权威语义源）修改。

---

## AD-20：Retrieval（检索）负责寻找候选，不负责创造真相

Retrieval（检索）回答：

> 什么最可能相关？

Authoritative Metadata / Catalog（权威元数据 / 目录）回答：

> 什么才是合法正式定义？

---

## AD-21：Offline（离线）不等于 Infrastructure（基础设施）

Online / Offline（在线 / 离线）描述运行时机。

Application / Domain / Infrastructure（应用 / 领域 / 基础设施）描述职责分层。

二者不能混为同一维度。

---

## AD-22：Query Result（查询结果）不是数据库原始结果

Raw Query Result（原始查询结果）必须通过 Query Result Assembly（查询结果组装）转换成稳定业务结果。

---

## AD-23：Query Result（查询结果）不是前端模型

Feature Result（功能结果）、API Response（接口响应）和 UI View Model（界面展示模型）保持分离。

---

## AD-24：Rows / Columns（行 / 列）是查询结果的稳定核心

NLQ（自然语言查询）以结构化表格结果作为核心数据表达。

Visualization（可视化）和 Natural Language Summary（自然语言总结）不属于当前 NLQ（自然语言查询）的核心职责。

---

## AD-25：业务语义标识与数据库字段解耦

Query Result（查询结果）优先使用稳定 Business Semantic Identity（业务语义标识）。

不将物理数据库字段名直接作为上层长期业务契约。

---

# 42. Deferred Decisions（延后决策）

以下问题已经识别，但不阻塞 Feature Architecture V1（功能架构 V1）冻结。

---

## 42.1 SQL Generation Strategy（SQL 生成策略）

待 Feature Spec（功能规格）和 Evaluation（评估）阶段决定：

- V1（第一版）是否继续采用 LLM Generation（大模型生成）
- 什么情况下值得采用 Deterministic SQL Compiler（确定性 SQL 编译器）
- 是否需要 Hybrid Generation（混合生成）

决策依据：

- 查询准确率
- 可维护性
- 系统复杂度
- 延迟
- 成本
- Bad Case（失败案例）分布

---

## 42.2 Offline Build Trigger（离线构建触发方式）

后续决定：

- Application Startup Build（应用启动构建）
- Manual Build（手动构建）
- CI/CD Build（持续集成 / 持续交付构建）
- Independent Offline Job（独立离线任务）
- Incremental Refresh（增量刷新）

Feature Architecture（功能架构）只要求：

> Online Runtime（在线运行）开始服务前必须存在有效 Retrieval Assets（检索资产）。

---

## 42.3 Query Result Contract（查询结果契约）

后续 Feature Spec（功能规格）需要明确：

- Columns（列）具体结构
- Rows（行）具体结构
- Business Semantic Metadata（业务语义元数据）
- Query Context Summary（查询上下文摘要）
- Evidence（证据）
- SQL（结构化查询语言）是否作为证据返回
- 数据类型表达
- Display Label（展示名称）
- 数据来源追溯

---

## 42.4 Conversation Semantic Context Contract
## 会话语义上下文契约

后续需要明确：

- 哪些上一轮语义可以继承
- 哪些语义由当前轮覆盖
- 如何处理冲突
- 如何引用 Previous Query Result（上一轮查询结果）
- Domain State（领域状态）生命周期

---

## 42.5 Authorization Contract（权限契约）

后续需要明确：

- Authorization Context（权限上下文）的概念结构
- 指标权限
- 数据范围权限
- 行级权限
- 维度级权限
- 最终权限强制规则

---

## 42.6 Retrieval Asset Versioning（检索资产版本管理）

后续需要考虑：

- Source Version（源版本）
- Index Version（索引版本）
- Content Hash（内容哈希）
- Asset Validity（资产有效性）
- Rebuild / Publish（重建 / 发布）

具体机制不属于当前 Feature Architecture（功能架构）。

---

# 43. V1 Module Map（V1 模块地图）

NLQ（自然语言查询）V1 Online Runtime（在线运行）的核心 Module（模块）最终冻结为：

```text
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

同时存在一个 Cross-Cutting Capability（横切能力）：

```text
Domain Authorization
（领域权限）
```

以及一个 Application-Level Capability（应用层能力）：

```text
Conversation Context Resolution
（会话上下文解析）
```

---

# 44. Responsibility Summary（职责总表）

```text
Query Semantic Parser
（查询语义解析器）
→ 用户到底想查什么


Schema Linking
（结构关联）
→ 数据在哪里、哪些结构合法、应该怎么连接


Metric Resolution
（指标解析）
→ 用户说的指标对应什么正式指标定义


Generation Context Assembly
（生成上下文组装）
→ 把语义、结构和指标汇合成可信生成上下文


SQL Generation
（SQL 生成）
→ 将生成上下文转换成候选 SQL


SQL Validation & Guard
（SQL 校验与防护）
→ 判断候选 SQL 是否结构合法、范围合法、安全可控


Domain Authorization
（领域权限）
→ 判断当前用户能否访问相应业务数据


Query Execution
（查询执行）
→ 执行已经安全且已授权的查询


Query Result Assembly
（查询结果组装）
→ 将数据库原始结果转换成稳定业务查询结果
```

---

# 45. Information Flow（信息流）

NLQ（自然语言查询）的主要 Conceptual Data Object（概念数据对象）：

```text
Natural Language Query Request
（自然语言查询请求）

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

Query Result
（查询结果）
```

具体字段结构不在 Feature Architecture（功能架构）定义。

---

# 46. Trust Boundary（信任边界）

NLQ（自然语言查询）的信任逐步收敛过程：

```text
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

Trusted Query Result
（可信查询结果）
```

核心思想：

> 随着链路向后推进，不确定性应该越来越少，确定性约束应该越来越强。

---

# 47. Failure Principle（失败原则）

所有模块必须遵循：

> No Silent Degradation（禁止静默降级）。

如果当前模块无法满足其 Contract（契约）：

```text
明确失败
↓
暴露正确失败类型
↓
记录 Bad Case（失败案例）
↓
进入 Evaluation / Regression
（评估 / 回归）
```

不得：

```text
猜一个结果
↓
继续执行
↓
假装成功
```

---

# 48. Bad Case Loop（失败案例闭环）

NLQ（自然语言查询）运行失败应进入：

```text
Runtime Failure
（运行失败）

        ↓

Bad Case Capture
（失败案例记录）

        ↓

Classification
（分类）

        ↓

Root Cause
（根因）

        ↓

Fix
（修复）

        ↓

Evaluation
（评估）

        ↓

Regression
（回归）

        ↓

Release
（发布）
```

Evaluation Loop（评估循环）属于开发与演进流程，而不是正常 Online Runtime（在线运行）主链。

---

# 49. Evolution Principle（演进原则）

NLQ（自然语言查询）遵循：

> Architecture-Guided Evolutionary Development（架构指导下的演进式开发）

即：

```text
Feature Architecture
（功能架构）

        ↓

Feature Spec
（功能规格）

        ↓

Module Spec
（模块规格）

        ↓

Test / Evaluation
（测试 / 评估）

        ↓

Implementation
（实现）

        ↓

Bad Case
（失败案例）

        ↓

Evidence-Based Evolution
（基于证据的演进）
```

不因为“未来可能需要”提前建设复杂能力。

---

# 50. V1 Non-Goals（V1 非目标）

NLQ（自然语言查询）V1 不主动引入：

- General Query Planner（通用查询规划器）
- SQL Repair Agent（SQL 修复智能体）
- Agentic Retry Loop（智能体重试循环）
- LangGraph Workflow（LangGraph 工作流）
- Multi-Agent System（多智能体系统）
- 自动 Root Cause Analysis（根因分析）
- Chart Generation（图表生成）
- 自然语言经营分析
- 通用企业 Semantic Platform（语义平台）
- 完整 Metadata Platform（元数据平台）
- 复杂权限平台
- 全量实时索引同步平台

只有真实 Feature Requirement（功能需求）或 Evaluation Evidence（评估证据）出现时才演进。

---

# 51. Architecture Freeze Checklist（架构冻结检查）

## Feature Boundary（功能边界）

- [x] 功能目标明确
- [x] 功能负责范围明确
- [x] 功能非职责明确
- [x] 与 Business Analysis（经营分析）边界明确
- [x] 与 Platform（平台）边界明确

## Module Map（模块地图）

- [x] Query Semantic Parser（查询语义解析器）
- [x] Schema Linking（结构关联）
- [x] Metric Resolution（指标解析）
- [x] Generation Context Assembly（生成上下文组装）
- [x] SQL Generation（SQL 生成）
- [x] SQL Validation & Guard（SQL 校验与防护）
- [x] Query Execution（查询执行）
- [x] Query Result Assembly（查询结果组装）

## Main Flow（主链路）

- [x] 入口明确
- [x] 模块顺序明确
- [x] 主要信息流明确
- [x] 分支 / 汇合关系明确
- [x] Feature Outcome（功能结果）明确

## Cross-Cutting Constraints（横切约束）

- [x] Conversation Context（会话上下文）
- [x] Authorization（权限）
- [x] Clarification Boundary（澄清边界）
- [x] Failure Boundary（失败边界）

## Offline Preparation（离线准备）

- [x] 权威源明确
- [x] 派生检索资产明确
- [x] 在线 / 离线边界明确
- [x] Source of Truth（事实源）原则明确

## External Capability（外部能力）

- [x] Conversation Context Capability（会话上下文能力）
- [x] Authorization Capability（权限能力）
- [x] Model Capability（模型能力）
- [x] Semantic Retrieval Capability（语义检索能力）
- [x] Database Query Capability（数据库查询能力）
- [x] Semantic Resource Access Capability（语义资源访问能力）
- [x] Embedding Capability（向量化能力）
- [x] Vector Index Capability（向量索引能力）

## Architecture Boundary（架构深度）

- [x] 未进入具体 Class（类）
- [x] 未进入具体 Function（函数）
- [x] 未进入具体字段 Schema（结构模式）
- [x] 未绑定具体 Prompt（提示词）
- [x] 未绑定具体模型
- [x] 未绑定具体 Retrieval Algorithm（检索算法）
- [x] 未绑定具体 SDK（软件开发工具包）
- [x] 未定义 Test Case（测试用例）

---

# 52. Architecture Freeze（架构冻结）

Natural Language Query Feature Architecture V1（自然语言查询功能架构 V1）：

> **FROZEN（已冻结）**

当前架构已经完成：

```text
Feature Responsibility
（功能职责）

        ↓

Feature Boundary
（功能边界）

        ↓

Module Map
（模块地图）

        ↓

Online Runtime
（在线运行链路）

        ↓

Offline Preparation
（离线准备链路）

        ↓

Cross-Cutting Constraints
（横切约束）

        ↓

External Capability Map
（外部能力地图）

        ↓

Outcome Boundary
（结果边界）

        ↓

Architecture Decisions
（架构决策）
```

没有发现阻塞 Feature Architecture V1（功能架构 V1）冻结的结构性缺口。

---

# 53. Next Stage（下一阶段）

下一阶段进入：

> Feature Spec（功能规格）

Feature Spec（功能规格）将开始回答：

```text
Natural Language Query
（自然语言查询）

到底向外承诺什么行为？

支持哪些业务场景？

输入是什么？

输出是什么？

什么情况下成功？

什么情况下澄清？

什么情况下不支持？

什么情况下失败？

哪些行为必须保持一致？

如何验收这个 Feature？
```

Feature Spec（功能规格）完成以后，再进入：

```text
Module Spec
（模块规格）

        ↓

Test / Evaluation
（测试 / 评估）

        ↓

Implementation
（实现）
```

---

# 54. Final Principle（最终原则）

Natural Language Query（自然语言查询）的总体设计原则：

> 用户负责表达业务问题，系统负责解决内部结构问题。

> 模型负责处理不确定的自然语言，程序负责执行确定性的安全与业务约束。

> Retrieval（检索）负责发现候选，Domain Truth（领域事实）负责裁决真相。

> 在线链路负责实时查询，离线链路负责准备可信运行资产。

> Feature Result（功能结果）保持稳定，Infrastructure（基础设施）保持可替换。

> 先定义职责和边界，再定义契约；先证明契约，再进入实现。
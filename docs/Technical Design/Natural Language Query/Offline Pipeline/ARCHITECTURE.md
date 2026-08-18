# Offline Pipeline Architecture

# 离线链路功能架构

> **Feature（功能）：** Offline Pipeline（离线链路）
> **Version（版本）：** V1
> **Status（状态）：** Frozen V1
> **Document Level（文档层级）：** Feature Architecture（功能架构）
> **Parent Feature（上级功能）：** Natural Language Query（自然语言查询）
> **Parent Architecture（上级架构）：** `../ARCHITECTURE.md`
> **Architecture Standard（架构标准）：** `../../FEATURE_ARCHITECTURE_STANDARD.md`

---

# 1. Purpose（目的）

Offline Pipeline（离线链路）负责：

> **将已经确认的 Schema Metadata（结构元数据）和 Semantic Resources（语义资源），构建为 Online Runtime（在线运行）可直接消费、可验证、可重新生成的 Retrieval Assets（检索资产）。**

本文档定义：

- Feature Responsibility（功能职责）
- Feature Boundary（功能边界）
- Source / Derived Asset Boundary（事实源 / 派生产物边界）
- Module Map（模块地图）
- Module Responsibility（模块职责）
- Major Input / Output（主要输入 / 输出）
- Main Processing Flow（主处理链路）
- Module Collaboration（模块协作）
- Online / Offline Boundary（在线 / 离线边界）
- External Capability Boundary（外部能力边界）
- Architecture Invariants（架构不变量）

本文档不定义：

- Retrieval Record 具体字段
- Payload 具体字段
- Dense / Sparse / Hybrid 算法
- Embedding Model
- Vector Database 产品
- Physical Collection 数量与名称
- Point ID 算法
- Top-K / Threshold
- Ranking Algorithm
- Evaluation Dataset
- Class / Function / File Layout

这些由后续 Feature Spec、Module Spec、Acceptance & Evaluation 和 Implementation 定义。

核心原则：

> **Architecture defines build structure, not retrieval implementation.**
> **架构定义构建结构，不定义具体检索实现。**

---

# 2. Feature Responsibility & Boundary（功能职责与边界）

## 2.1 Responsibility（职责）

Offline Pipeline 的核心职责：

> **把权威结构和业务语义资源，确定性地投影为可信的运行时检索资产。**

核心闭环：

```text
Authoritative Build Inputs
（权威构建输入）
        ↓
Validate
（校验）
        ↓
Retrieval Projection
（检索投影）
        ↓
Embedding
（向量化）
        ↓
Index Build
（索引构建）
        ↓
Asset Validation
（资产验证）
        ↓
Validated Retrieval Assets
（已验证检索资产）
```



Offline Retrieval Assets（离线检索资产）只包含：

- TABLE；
- COLUMN；
- METRIC。

Deterministic Join Capability（确定性连接能力）独立于 Retrieval Asset：

- Relationship Catalog；
- Relationship Graph；
- Join Resolution。

## 2.2 Entry Boundary（入口边界）

Offline Pipeline 从已经建立好的正式资源开始：

```
Schema Metadata
├── tables.json
├── columns.json
└── relationships.json

Semantic Resources
└── metrics.json
```

这些资源：

> **保持各自独立，不合并为新的权威大文件。**

Offline Pipeline 可以在构建过程中形成统一 Logical View（逻辑视图），但：

> **不得产生新的 Business Source of Truth（业务事实源）。**

------

## 2.3 Exit Boundary（出口边界）

Offline Pipeline 最终产生：

> **Validated Retrieval Assets（已验证检索资产）。**

供 Online Retrieval（在线检索）消费。

概念上包括：

```
Retrieval Records
+
Retrieval Representation
+
Semantic Payload
+
Index Metadata
```

------

## 2.4 Out of Scope（范围外）

Offline Pipeline 不负责：

- PostgreSQL Schema 设计或修改
- Schema Metadata 数据库抽取
- Domain Modeling（领域建模）
- Analytical Modeling（分析模型）
- 创建或修改 Metric Definition
- 创建或修改 Dimension Definition
- 创建 Relationship
- Online Retrieval
- Schema Linking
- Metric Resolution
- SQL Generation
- Query Execution

原则：

> **Offline Pipeline consumes truth; it does not create truth.**
> **离线链路消费事实，不创造事实。**

------

# 3. Source & Derived Asset Model（事实源与派生产物模型）

必须保持两条事实链。

## 3.1 Physical Structure（物理结构）

```
PostgreSQL
        ↓
Schema Metadata
        ↓
Physical Structure Fact
（物理结构事实）
```

包括：

- Table
- Column
- PK / FK
- Relationship
- Constraint

------

## 3.2 Business Semantics（业务语义）

```
Domain Spec
+
Analytical Model
        ↓
Semantic Resources
        ↓
Business Semantic Fact
（业务语义事实）
```

包括：

- Metric
- Dimension
- Alias
- Business Definition
- Physical Mapping

------

## 3.3 Retrieval Asset（检索资产）

```
Schema Metadata
+
Semantic Resources
        ↓
Offline Pipeline
        ↓
Retrieval Assets
```

Retrieval Asset 属于：

> **Derived / Materialized Asset（派生 / 物化资产）。**

因此：

> **Retrieval Asset ≠ Source of Truth**

不得直接修改 Vector Index 中的业务定义来代替修改上游正式资源。

------

# 4. Retrieval Projection Model（检索投影模型）

Offline Pipeline 不把全部资源拼接成一个大 Document。

而是将不同 Source Object（源对象）投影为多条独立 Retrieval Record（检索记录）。

V1 可检索对象：

```
Table
→ Table Retrieval Record

Column
→ Column Retrieval Record

Metric
→ Metric Retrieval Record
```

概念上：

```
tables.json ───────────→ Table Records
columns.json ──────────→ Column Records
metrics.json ──────────→ Metric Records
```

每个 Record：

> **代表一个独立可检索语义对象。**

不是：

```
All Resources
        ↓
One Huge Document
        ↓
One Embedding
```

------

# 5. Relationship Boundary（关系边界）

`relationships.json` 属于：

> **Authoritative Physical Relationship Catalog（权威物理关系目录）。**

V1 不将 Relationship 作为 Retrieval Record（检索记录）或向量检索对象。

正确关系：

```
Retrieval
        ↓
Candidate Table / Column
        ↓
Schema Linking
        ↓
relationships.json
        ↓
Validated Relationship Catalog
（已校验关系目录）
        ↓
Deterministic In-Memory Relationship Graph
（确定性内存关系图）
        ↓
BFS / Join Resolution
（广度优先搜索 / 连接解析）
```

即：

> **Retrieval 发现候选，Relationship Catalog 决定合法关系。**

不得通过 Vector Retrieval（向量检索）猜测正式 Join Relationship（连接关系）。

------

# 6. Module Map（模块地图）

Offline Pipeline V1 包含五个核心 Logical Module（逻辑模块）：

```
1. Resource Loading & Validation
   （资源加载与校验）

2. Retrieval Projection
   （检索投影）

3. Embedding Generation
   （向量表示生成）

4. Retrieval Index Building
   （检索索引构建）

5. Retrieval Asset Validation
   （检索资产验证）
```

整体关系：

```
Schema Metadata ───────┐
                       │
Semantic Resources ────┘
          ↓
Resource Loading & Validation
          ↓
Validated Catalogs
          ↓
Retrieval Projection
          ↓
Retrieval Records
          ↓
Embedding Generation
          ↓
Embedded Retrieval Records
          ↓
Retrieval Index Building
          ↓
Built Retrieval Assets
          ↓
Retrieval Asset Validation
          ↓
Validated Retrieval Assets
```

这些 Module 表示：

> **Responsibility Boundary（职责边界）。**

M1～M5 只构建三类 Offline Retrieval Asset（离线检索资产）：

```text
TABLE / COLUMN / METRIC
```

`relationships.json` 由 M1 校验后继续作为独立 Relationship Catalog（关系目录）传递；它不进入 Retrieval Record、Embedding 或 Vector Index。后续 Online Join Resolver 使用已校验的 Relationship Catalog 构建确定性内存 Relationship Graph，并执行 BFS / Join Resolution。

不等同于具体 Python 文件、Class 或 Process。

------

# 7. Module Responsibilities（模块职责）

## 7.1 Resource Loading & Validation（资源加载与校验）

### Responsibility

负责：

> 加载并验证正式 Schema Metadata 与 Semantic Resources。

### Major Input

- Schema Metadata
- Semantic Resources

### Major Output

- Validated Catalogs（已验证目录集合）

`Validated Catalogs` 是：

> **构建过程中的逻辑集合。**

不是：

> 新生成的 `merged.json` 或新的权威资源文件。

### Boundary

负责：

- 格式有效性
- 资源完整性
- 唯一性
- 跨资源引用一致性
- Semantic → Physical Mapping 存在性

不负责：

- 修改业务定义
- 自动补写缺失事实
- 猜测 Relationship

------

## 7.2 Retrieval Projection（检索投影）

### Responsibility

负责：

> 将已验证的 Source Object 确定性投影为独立 Retrieval Record。

### Major Input

- Validated Catalogs

### Major Output

- Retrieval Records

主要类型：

- Table Record
- Column Record
- Metric Record

### Boundary

可以：

- 重组用于检索的文本
- 带入 Alias
- 带入必要 Metadata
- 带入 Semantic Payload
- 保留 Source Trace

不得：

- 创造新的 Business Fact
- 修改 Metric Formula
- 修改 Column / Field Meaning
- 创建新的 Relationship

核心原则：

> **Projection may reorganize truth, but must not invent truth.**

------

## 7.3 Embedding Generation（向量表示生成）

### Responsibility

负责：

> 将 Retrieval Record 转换为可检索 Representation（表示）。

### Major Input

- Retrieval Records

### Major Output

- Embedded Retrieval Records

### Boundary

负责检索表示生成。

不负责：

- 修改业务语义
- 决定业务事实
- Online Ranking
- Schema Linking
- Metric Resolution

Dense / Sparse / Hybrid 属于后续规格和实现决策。

------

## 7.4 Retrieval Index Building（检索索引构建）

### Responsibility

负责：

> 将 Retrieval Record、Retrieval Representation 和 Payload 构建为 Online Retrieval 可以消费的索引资产。

### Major Input

- Embedded Retrieval Records

### Major Output

- Built Retrieval Assets

逻辑上形成：

```
Unified Retrieval Index
（统一逻辑检索索引）

├── Table Record
├── Column Record
└── Metric Record
```

这里的：

> **Unified Retrieval Index（统一逻辑检索索引）**

不等于已经冻结：

> 一个物理 Vector Collection。

具体使用一个还是多个 Physical Collection：

> 留给后续 Module Spec / Implementation 决定。

------

## 7.5 Retrieval Asset Validation（检索资产验证）

### Responsibility

负责：

> 在资产进入 Online Runtime 前验证构建结果是否完整、可追踪、可消费。

### Major Input

- Built Retrieval Assets
- Validated Catalogs

### Major Output

成功：

- Validated Retrieval Assets

失败：

- Offline Build Failure

### Boundary

验证：

- Source / Asset 对齐
- Record 完整性
- Payload 完整性
- Index 完整性
- Source Trace
- 基础 Retrieval 可用性

详细 Evaluation Metric、Dataset 和 Threshold：

> 由 Acceptance & Evaluation 定义。

------

# 8. Main Processing Flow（主要处理链路）

```
tables.json
columns.json
relationships.json
metrics.json
        ↓
Resource Loading & Validation
        ↓
Validated Catalogs
        ↓
Retrieval Projection
        ↓
┌─────────────────────────┐
│ Table Records           │
│ Column Records          │
│ Metric Records          │
└─────────────────────────┘
        ↓
Embedding Generation
        ↓
Embedded Retrieval Records
        ↓
Retrieval Index Building
        ↓
Built Retrieval Assets
        ↓
Retrieval Asset Validation
        ↓
Validated Retrieval Assets
```

`relationships.json` 同时保留为：

```
Authoritative Relationship Catalog
        ↓
M1 Validation
        ↓
Online Join Resolver
        ↓
Deterministic Relationship Graph
        ↓
BFS / Join Resolution
```

它不需要为了进入 Vector Retrieval 而被重新解释。

------

# 9. Module Collaboration（模块协作）

核心信息流：

```
Validated Catalogs
        ↓
Retrieval Records
        ↓
Embedded Retrieval Records
        ↓
Built Retrieval Assets
        ↓
Validated Retrieval Assets
```

Module 之间必须通过显式信息边界协作。

禁止依赖：

- Hidden Global State（隐藏全局状态）
- 未声明旧资源
- Legacy Index
- 其他 Module 内部实现
- 静默共享临时数据

下游发现上游 Contract Violation：

> **返回 Failure，不得自行猜测或修改事实。**

------

# 10. Online / Offline Boundary（在线 / 离线边界）

```
Schema Metadata
+
Semantic Resources
        ↓
Offline Pipeline
        ↓
Validated Retrieval Assets

══════════════════════════════
      Online / Offline
══════════════════════════════

        ↓
Online Retrieval
        ↓
Candidate
        ↓
┌──────────────────┐
│ Schema Linking   │
│ Metric Resolution│
└──────────────────┘
        ↓
Authoritative Validation
```

Offline Pipeline：

> **负责 Build（构建）。**

Online Runtime：

> **负责 Retrieve / Resolve（检索 / 解析）。**

在线模块不得依赖 Offline Build 内部实现。

Offline Build 也不得承担 Runtime Query Logic（在线查询逻辑）。

------

# 11. Retrieval Responsibility Boundary（检索责任边界）

Retrieval 负责：

> **Find Candidate（发现候选）。**

不负责：

> **Define Truth（定义事实）。**

因此：

```
Vector Retrieval
        ↓
Candidate
```

之后必须继续：

```
Schema Linking / Metric Resolution
        ↓
Authoritative Metadata / Semantic Catalog
        ↓
Formal Resolution
```

即使 Retrieval Asset 携带完整 Semantic Payload：

> 它仍然只是 Authoritative Resource 的 Runtime Projection（运行时投影）。

------

# 12. External Capability Boundary（外部能力边界）

Offline Pipeline 依赖三个外部 Capability（能力）。

## Resource Access Capability（资源访问能力）

读取正式：

- Schema Metadata
- Semantic Resources

## Embedding Capability（向量化能力）

将 Retrieval Record 转换为 Retrieval Representation。

## Retrieval Index Capability（检索索引能力）

保存并发布 Retrieval Asset。

Feature Architecture 只依赖：

> **Capability / Contract**

不绑定：

- Qdrant
- Azure AI Search
- BGE-M3
- OpenAI Embedding
- 其他 Vendor / SDK

------

# 13. Architecture Invariants（架构不变量）

Offline Pipeline V1 必须保持：

### 1. Source Separation（事实源分离）

> Schema Metadata 与 Semantic Resources 保持独立事实源，不合并成新的权威文件。

### 2. Record Independence（记录独立）

> 每个 Table / Column / Metric 独立形成 Retrieval Record，不构造全局超级文档。

### 3. Source Fidelity（事实忠实）

> Retrieval Projection 不得创造或修改业务事实。

### 4. Derived Asset Rule（派生产物规则）

> Retrieval Asset 必须能够从正式 Source Resource 重新生成。

### 5. Relationship Authority（关系权威）

> 正式 Relationship 由 Authoritative Relationship Metadata 决定，不由向量检索猜测。

### 6. Traceability（可追踪）

> Retrieval Record 必须能够追踪到 Source Resource。

### 7. Validation Before Use（使用前验证）

> 未通过验证的 Retrieval Asset 不得进入 Online Runtime。

### 8. Candidate Boundary（候选边界）

> Retrieval 发现候选，正式解析由 Schema Linking / Metric Resolution 与权威资源完成。

### 9. Build / Serve Separation（构建 / 服务分离）

> Offline Build 与 Online Retrieval 在架构上保持独立。

------

# 14. Deferred Decisions（延后决策）

以下不在 Feature Architecture 冻结：

- Retrieval Record 具体字段
- Search Text 构造规则
- Payload 具体结构
- Dense / Sparse / Hybrid
- Embedding Model
- Vector Database
- Physical Collection Strategy
- Point ID Algorithm
- Version Strategy
- Full Rebuild / Incremental Refresh
- Atomic Publish Strategy
- Top-K
- Threshold
- Ranking Strategy
- Evaluation Metric / Dataset

这些分别进入：

- Feature Spec
- Module Spec
- Acceptance & Evaluation
- Implementation

------

# 15. Architecture Completion Check（架构完整性检查）

Freeze（冻结）前确认：

- [x] Feature Responsibility 明确
- [x] Entry / Exit / Out of Scope 明确
- [x] Source 与 Derived Asset 边界明确
- [x] Source Resource 保持分离
- [x] Retrieval Record 独立投影
- [x] 五个核心 Module 职责明确
- [x] Main Flow 完整
- [x] Relationship Authority 明确
- [x] Online / Offline Boundary 明确
- [x] External Capability 明确
- [x] 未进入算法、参数和供应商实现细节

全部满足后：

> **Offline Pipeline Feature Architecture V1 可以 Freeze（冻结）。**

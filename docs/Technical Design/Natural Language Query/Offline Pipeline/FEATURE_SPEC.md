# Offline Pipeline Feature Spec

# 离线链路功能规格

> **Feature（功能）：** Offline Pipeline（离线链路）
> **Version（版本）：** V1
> **Status（状态）：** Feature Specification Baseline（功能规格基线）
> **Architecture Reference（架构引用）：** `ARCHITECTURE.md`
>
> **Feature Spec Standard（功能规格标准）：** `../../FEATURE_SPEC_STANDARD.md`

---

# 1. Purpose（目的）

本文档定义 Offline Pipeline V1（离线链路第一版）必须满足的正式行为契约。

核心目标：

> **基于当前有效的 Schema Metadata（结构元数据）和 Semantic Resources（语义资源），稳定构建可供 Online Retrieval（在线检索）使用的可信 Retrieval Assets（检索资产）。**

原则：

> **Feature Spec defines required behavior, not implementation.**
> **功能规格定义必须做到什么，不定义具体怎么实现。**

---

# 2. Feature Goal（功能目标）

Offline Pipeline 必须完成：

```text
Authoritative Build Inputs
（权威构建输入）
        ↓
Validate
        ↓
Retrieval Projection
        ↓
Retrieval Representation Generation
        ↓
Index Build
        ↓
Post-build Validation / Online Ready Gate
        ↓
Validated Retrieval Assets
```



成功意味着：

1. 输入资源合法；
2. Retrieval Record（检索记录）正确；
3. Retrieval Representation（检索表示）完整；
4. Index（索引）构建完整；
5. Source → Asset 可追踪；
6. 最终资产通过正式验证；
7. Online Runtime 可以消费该资产。

------

# 3. Feature Input（功能输入）

V1 输入为当前正式：

## Schema Metadata（结构元数据）

```
tables.json
columns.json
relationships.json
```

## Semantic Resources（语义资源）

```
metrics.json
```

本 Feature 的正式机器可读输入由四份资源组成：`tables.json`、`columns.json`、`metrics.json` 和 `relationships.json`。其中 `relationships.json` 是独立的 Relationship Catalog，不是 Retrieval Source Object。

这些资源必须保持：

> **独立 Source Resource（源资源）。**

Offline Pipeline：

> 不得为了构建索引创建新的权威合并资源。

构建过程中的 Logical Catalog（逻辑目录）：

> 仅属于运行时构建状态，不成为新的 Source of Truth（事实源）。

------

# 4. Feature Output（功能输出）

成功输出：

> **Validated Retrieval Assets（已验证检索资产）。**

概念上包含：

```
Retrieval Records
+
Retrieval Representation
+
Semantic Payload
+
Index Metadata
```

失败输出：

> **Offline Build Failure（离线构建失败）。**

只有通过完整验证的资产：

> 才能被视为有效 Retrieval Asset。

------

# 5. Retrieval Record Contract（检索记录契约）

V1 正式支持三类可检索对象：

```
Table
Column
Metric
```

每个 Source Object：

> **独立投影为一个 Retrieval Record。**

保持：

```
One Source Object
→ One Logical Retrieval Record
```

禁止：

```
All Resources
→ One Huge Document
→ One Embedding
```

不同 Record 可以共享统一逻辑结构，但：

> 不要求不同 Source Resource 合并存储。

模块职责和模块间边界由 `PIPELINE_CONTRACT.md` 定义；具体字段留给 Implementation。

------

# 6. Relationship Rule（关系规则）

`relationships.json` 是：

> **Authoritative Physical Relationship Catalog（权威物理关系目录）。**

V1：

> V1 不将 Relationship 作为 Retrieval Record（检索记录）或向量检索对象。

Resource Loading & Validation 负责校验 `relationships.json`；后续 Join Resolver 使用已校验的 Relationship Catalog 构建确定性内存 Relationship Graph，并执行 BFS / Join Resolution。该过程不将 Relationship 转换为 Retrieval Representation，也不创建 Relationship Retrieval Record。

正确流程：

```
Retrieval
↓
Candidate Table / Column
↓
Schema Linking
↓
Authoritative Relationship Catalog
↓
Legal Relationship / Join
```

禁止：

> 使用 Embedding / Vector Similarity（向量相似度）创造或裁决正式 Join Relationship。

------

# 7. Resource Validation Rule（资源校验规则）

进入 Retrieval Projection 前必须验证输入资源。

至少保证：

- Resource 可解析；
- 必需 Catalog 存在；
- Object Identity 唯一；
- 引用对象存在；
- Semantic → Physical Mapping 合法；
- Metric Dependency 合法；
- Relationship 引用合法；
- 不引用已退出 Current Source of Truth 的 Legacy Resource。

出现 Contract Violation：

> **Build 必须失败。**

禁止：

- 猜测缺失业务定义；
- 自动创造不存在的字段；
- 自动创造 Relationship；
- 静默修改 Metric 或 Column / Field Meaning；
- 使用 Legacy Resource 补齐当前资源。

------

# 8. Retrieval Projection Rule（检索投影规则）

Retrieval Projection 可以：

- 重组 Source 内容；
- 形成可检索文本；
- 使用 Alias；
- 携带必要 Metadata；
- 携带完整或必要 Semantic Payload；
- 添加 Source Trace（来源追踪信息）。

不得：

- 创造 Business Truth；
- 修改 Metric Formula；
- 修改 Column / Field Meaning；
- 修改 Physical Mapping；
- 创建 Relationship。

原则：

> **Projection may reorganize truth, but must not invent truth.**

------

# 9. Retrieval Representation Rule（检索表示规则）

每个 Retrieval Record：

> 独立生成 Retrieval Representation（检索表示）。

Retrieval Representation Generation 不得改变：

- Source Identity；
- Business Definition；
- Physical Mapping；
- Semantic Payload。

具体：

```
Dense
Sparse
Hybrid
Embedding Model
```

由后续 Implementation 决定。

Feature Contract 只要求：

> 每类 Retrieval Record 必须通过明确、稳定、可重复的 Retrieval Representation Contract（检索表示契约）生成检索表示。
>
> 不同 Record Type 是否共享同一 Representation Strategy，由后续 Implementation 决定。

------

# 10. Retrieval Index Rule（检索索引规则）

Index 必须保持：

```
Retrieval Record
+
Retrieval Representation
+
Payload
+
Identity
+
Source Trace
```

之间的一致关联。

逻辑上支持：

```
Table Record
Column Record
Metric Record
```

共同组成：

> **Unified Retrieval Space（统一逻辑检索空间）。**

V1 不在 Feature Spec 强制：

- 一个 Physical Collection；
- 多个 Physical Collection。

具体 Physical Collection Strategy（物理集合策略）由后续 Implementation 决定。

------

# 11. Build Strategy（构建策略）

V1 正式采用：

> **Full Rebuild（全量重建）。**

即：

```
Current Authoritative Resources
        ↓
Build Complete Asset Set
        ↓
Validate
        ↓
Publish / Activate
```

V1 不要求：

> Incremental Refresh（增量刷新）。

原因不进入正式 Contract；增量能力留待真实规模需要时演进。

------

# 12. Publish Safety（发布安全）

新 Retrieval Asset：

> **必须先完成构建和验证，再成为有效资产。**

必须保持：

```
Build
↓
Validate
↓
Activate
```

不得：

```
Build Partially
↓
Immediately Serve
```

如果构建或验证失败：

> 未完成资产不得被标记为 Validated Retrieval Asset。

如果已经存在上一版有效资产：

> 失败的新 Build 不得使上一版有效资产自动失效。

具体 Atomic Publish（原子发布）实现由后续 Implementation 决定。

------

# 13. Reproducibility & Traceability（可重复构建与可追踪）

Retrieval Asset 必须能够识别其构建依据。

至少必须能够追踪：

```
Source Resource
+
Build Configuration
+
Retrieval Representation Version
```

具体 Fingerprint（指纹）、Version Field（版本字段）和 ID Algorithm（标识算法）：

> 由后续 Implementation 定义。

在相同：

```
Source
+
Build Contract
+
Relevant Build Configuration
```

条件下重复构建：

> 应产生语义等价的 Retrieval Asset Set。

------

# 14. Failure Rule（失败规则）

以下情况必须 Build Failure：

- Source Resource 缺失；
- Source Resource 非法；
- Cross-Resource Reference 非法；
- Semantic → Physical Mapping 不存在；
- Retrieval Projection 失败；
- Retrieval Representation Generation 失败且无法完成完整资产；
- Index Build 不完整；
- Post-build Validation / Online Ready Gate 未通过；
- Source Trace 无法建立；
- 发现无法接受的 Legacy / Current 混用。

失败不得被：

> 静默降级为成功。

------

# 15. Online Boundary（在线边界）

Offline Pipeline 的结束点：

> **Validated Retrieval Assets。**

Online Runtime 从：

> Validated Retrieval Assets

开始消费。

Offline Pipeline 不负责：

```
User Query
Online Retrieval
Ranking Decision
Schema Linking
Metric Resolution
SQL Generation
Query Execution
```

保持：

```
Offline
Build Asset

──────────────

Online
Retrieve Candidate
→ Resolve
→ Validate
```

------

# 16. Source of Truth Rule（事实源规则）

必须保持：

```
PostgreSQL
→ Schema Metadata
→ Physical Structure Fact
Domain / Analytical Model
→ Semantic Resources
→ Business Semantic Fact
```

然后：

```
Schema Metadata
+
Semantic Resources
→ Offline Pipeline
→ Retrieval Assets
```

因此：

> **Retrieval Asset 永远不是 Business Source of Truth。**

业务事实或物理结构变化：

> 必须先修改对应上游事实链，再重新构建 Retrieval Asset。

------

# 17. V1 Supported Scope（V1 支持范围）

V1 正式支持：

- Table Retrieval Record；
- Column Retrieval Record；
- Metric Retrieval Record；
- Source Validation；
- Retrieval Projection；
- Retrieval Representation Generation；
- Full Index Build；
- Post-build Validation / Online Ready Gate；
- Full Rebuild；
- Source Trace；
- Build / Serve Separation。

------

# 18. V1 Deferred Scope（V1 延后范围）

V1 不要求：

- Relationship Vector Retrieval；
- Incremental Refresh；
- Partial Update；
- Distributed Build；
- Background Scheduler；
- Automatic Change Detection；
- Multi-Version Online Serving；
- Rollback Platform；
- Complex Collection Routing；
- Online Re-Embedding；
- Generic ETL Platform。

这些能力只有出现真实需求时再扩展。

------

# 19. Feature Invariants（功能不变量）

Offline Pipeline V1 必须始终保持：

1. **Source Separation**
   Schema Metadata 与 Semantic Resources 不合并成新的权威事实源。
2. **One Object, One Logical Record**
   一个正式可检索 TABLE、COLUMN 或 METRIC Source Object 对应一个独立逻辑 Retrieval Record。
3. **No Invented Truth**
   Offline Pipeline 不创造业务或结构事实。
4. **Relationship Authority**
   Relationship 由 Authoritative Relationship Metadata 裁决。
5. **Derived Asset**
   Retrieval Asset 必须可以重新生成。
6. **Traceability**
   Retrieval Asset 必须能够追踪到构建来源。
7. **Validation Before Activation**
   未验证资产不得成为有效在线资产。
8. **Fail Closed**
   无法确认正确性时构建失败，不猜测修复。
9. **Build / Serve Separation**
   Offline Build 与 Online Retrieval 保持职责分离。

------

# 20. Feature Done When（功能完成条件）

Offline Pipeline V1 完成必须满足：

- 输入资源 Contract 已验证；
- 三类 Retrieval Record 可以稳定构建；
- 每条 Record 可追踪到 Source；
- Retrieval Representation 可以完整生成；
- Retrieval Index 可以完整重建；
- Relationship 未被错误向量化裁决；
- Post-build Validation / Online Ready Gate 通过；
- Full Rebuild 可重复执行；
- Build Failure 不产生有效资产；
- Online Runtime 可以消费最终 Validated Retrieval Assets；
- Acceptance & Evaluation Gate 全部通过。

满足以上条件：

> **Offline Pipeline V1 Feature Contract 完成。

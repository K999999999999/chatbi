# Offline Pipeline Acceptance & Evaluation Spec

# 离线链路验收与评估规格

> **Feature（功能）：** Offline Pipeline（离线链路）
> **Version（版本）：** V1
> **Status（状态）：** Acceptance & Evaluation Baseline（验收与评估基线）
> **Architecture Reference（架构引用）：** `ARCHITECTURE.md`
> **Feature Spec Reference（功能规格引用）：** `FEATURE_SPEC.md`

---

# 1. Purpose（目的）

本文档定义 Offline Pipeline V1（离线链路第一版）的：

- Verification（验证）
- Acceptance（验收）
- Retrieval Evaluation（检索评估）
- Release / Activation Gate（发布 / 激活门禁）

本文档回答：

- 哪些行为必须通过 Deterministic Test（确定性测试）证明；
- 哪些能力必须通过 Retrieval Evaluation（检索评估）证明；
- 哪些错误属于 Hard Failure（硬失败）；
- 如何验证 Retrieval Asset（检索资产）完整性；
- 如何验证 Full Rebuild（全量重建）；
- 如何验证 Build → Validate → Activate；
- 如何验证最终资产能够支持 Online Retrieval（在线检索）；
- 什么条件下 Offline Pipeline V1 才算通过验收。

本文档不定义：

- 具体 Test Code（测试代码）
- 具体 Evaluation Dataset 内容
- Embedding Model
- Vector Database
- Physical Collection Strategy
- Top-K 具体值
- Evaluation Threshold 具体数值
- Retrieval Algorithm
- Module Implementation

原则：

> **Specification defines what must be true; Test and Evaluation prove it.**

> **规格定义什么必须成立，测试与评估负责证明。**

---

# 2. Verification Model（验证模型）

Offline Pipeline V1 使用三层验证：

```text
Offline Pipeline Verification
（离线链路验证）

├── Deterministic Contract Test
│   （确定性契约测试）
│
├── Retrieval Evaluation
│   （检索评估）
│
└── Build-to-Retrieve Integration Evaluation
    （构建到检索集成评估）
```



三层职责不同，不互相替代。

------

# 3. Deterministic Contract Test（确定性契约测试）

Deterministic Contract Test 验证：

> **可以通过明确程序规则判断正确与错误的 Offline Pipeline 行为。**

主要覆盖：

- Source Resource Validation（源资源校验）
- Object Identity Uniqueness（对象标识唯一性）
- Cross-Resource Reference Validation（跨资源引用校验）
- Semantic → Physical Mapping Validation（语义到物理映射校验）
- Relationship Reference Validation（关系引用校验）
- Retrieval Record Coverage（检索记录覆盖）
- Source Trace（来源追踪）
- Payload Integrity（载荷完整性）
- Index Completeness（索引完整性）
- Full Rebuild（全量重建）
- Build Failure Behavior（构建失败行为）
- Validation Before Activation（激活前验证）
- Previous Valid Asset Protection（上一版有效资产保护）
- Relationship Vectorization Prohibition（关系向量化禁止）
- Legacy Resource Isolation（旧资源隔离）

原则：

> **能够确定性证明的行为，不使用 Retrieval Evaluation 替代。**

------

# 4. Retrieval Evaluation（检索评估）

Retrieval Evaluation 验证：

> **构建后的 Retrieval Asset 是否真的能够把正确业务对象作为高相关候选召回。**

主要评估三类 Retrieval Record：

```
Table
Column
Metric
```

不评估：

```
Relationship
```

因为 V1 中 Relationship：

> 不属于 Retrieval Record，也不属于向量检索对象。

正式 Relationship 由 Authoritative Relationship Catalog（权威关系目录）裁决。

------

# 5. Build-to-Retrieve Integration Evaluation（构建到检索集成评估）

该层验证完整 Feature 闭环：

```
Schema Metadata
+
Semantic Resources
        ↓
Offline Build
        ↓
Retrieval Records
        ↓
Retrieval Representation
        ↓
Retrieval Index
        ↓
Asset Validation
        ↓
Activate
        ↓
Retrieval Query
        ↓
Expected Candidate
```

最终验证的不是：

> Embedding 是否成功生成。

也不是：

> Vector Database 是否写入成功。

而是：

> **从正式 Source Resource 构建出的有效资产，是否能够被 Online Retrieval Capability 正确消费并返回预期候选。**

------

# 6. Acceptance Gates（验收门禁）

Offline Pipeline V1 使用四类 Gate（门禁）：

```
Offline Pipeline Acceptance

├── Hard Contract Gate
│   （硬契约门禁）
│
├── Retrieval Quality Gate
│   （检索质量门禁）
│
├── Build & Activation Gate
│   （构建与激活门禁）
│
└── Critical Bad Case Gate
    （严重失败案例门禁）
```

四类 Gate 全部满足：

> 才能通过 Offline Pipeline V1 Acceptance。

------

# 7. Hard Contract Gate（硬契约门禁）

Hard Contract Gate 验证：

> **已经明确的确定性 Contract 绝对不能违反。**

以下必须 100% Pass。

## 7.1 Source Integrity（源完整性）

必须保证：

- 必需 Source Resource 存在；
- Resource 可解析；
- Identity 唯一；
- Cross-Resource Reference 合法；
- Semantic → Physical Mapping 存在；
- Metric Dependency 合法；
- Relationship Reference 合法。

任何违反：

> Build Failure。

------

## 7.2 Record Coverage（记录覆盖）

当前正式可检索 Source Object：

```
Table
Column
Metric
```

必须全部产生对应 Retrieval Record。

即：

```
Expected Retrieval Record
=
Current Supported Source Object
```

要求：

> **Record Coverage = 100%。**

不得：

- 丢失正式对象；
- 无理由重复对象；
- 创建不存在的业务对象。

------

## 7.3 One Object, One Logical Record（一个对象一个逻辑记录）

必须保持：

```
One Source Object
→ One Logical Retrieval Record
```

不得：

```
Multiple Source Objects
→ One Huge Retrieval Record
```

也不得因为重复构建：

> 产生逻辑重复 Record。

------

## 7.4 Source Trace（来源追踪）

每个 Retrieval Record：

> 必须能够追踪到正式 Source Resource。

要求：

> **Traceability Coverage = 100%。**

任何无法确认来源的 Record：

> 不得进入有效 Retrieval Asset。

------

## 7.5 Relationship Boundary（关系边界）

V1：

> Relationship 不得形成 Retrieval Record 或向量检索对象。

必须验证：

- Relationship Catalog 正常存在；
- Relationship Catalog 已通过 M1 校验；
- Relationship 可以被 Online Schema Linking 消费；
- Join Resolver 可以基于该 Catalog 构建确定性内存 Relationship Graph，并执行 BFS / Join Resolution；
- Vector Index 中不存在 Relationship Retrieval Record；
- Retrieval 不负责创造正式 Join。

------

## 7.6 No Invented Truth（禁止创造事实）

Retrieval Projection 不得：

- 修改 Metric Formula；
- 修改 Column / Field Meaning；
- 修改 Physical Mapping；
- 创建 Table / Column；
- 创建 Relationship；
- 使用 Legacy Resource 补齐当前业务事实。

发现上述行为：

> Hard Gate Fail。

------

# 8. Retrieval Quality Gate（检索质量门禁）

Retrieval Quality Gate 验证：

> **正确对象能否稳定进入候选结果，并获得合理 Ranking（排序）。**

V1 正式使用两个主要 Retrieval Metric（检索指标）：

1. Recall@K（前 K 召回率）
2. MRR（平均倒数排名）

不使用大量指标作为正式 Gate。

------

# 9. Recall@K（前 K 召回率）

Recall@K 衡量：

> 预期正确对象是否出现在前 K 个 Retrieval Candidate（检索候选）中。

对于单一目标对象的 Evaluation Case：

```
Expected Object
是否出现在 Top-K
```

出现：

> Case Recall@K Pass。

未出现：

> Case Recall@K Fail。



对于存在 Multiple Acceptable Objects（多个等价可接受对象）的 Evaluation Case：

> 任一正式 Expected Object 出现在 Top-K 中，即视为该 Case 命中。

具体多目标评分规则：

> 由 Evaluation Asset（评估资产）定义。

Feature-Level Recall@K：

```
命中 Expected Object 的 Case 数
/
总 Evaluation Case 数
```

K 的正式数值：

> 在 Evaluation Baseline（评估基线）阶段确定。

Feature Spec / Architecture：

> 不提前冻结具体 K。

------

# 10. MRR（平均倒数排名）

MRR 用于判断：

> 正确对象虽然被召回，但排名是否足够靠前。

单 Case：

```
Reciprocal Rank
=
1 / Expected Object Rank
```

例如：

```
Rank 1 → 1.0
Rank 2 → 0.5
Rank 3 → 0.333...
```

全部 Evaluation Case 求平均：

> 得到 MRR。

Recall@K 主要判断：

> **有没有找到。**

MRR 主要判断：

> **找到以后排得够不够前。**

------

# 11. Evaluation Dataset（评估数据集）

Evaluation Dataset 必须覆盖三类 Retrieval Object：

```
Table
Column
Metric
```

每个 Case 至少包含概念上的：

```
Query
（检索表达）

Expected Asset Type
（预期对象类型）

Expected Object Identity
（预期对象标识）
```

必要时允许：

```
Multiple Acceptable Objects
（多个等价可接受对象）
```

但必须明确为什么存在多个正确结果。

------

# 12. Evaluation Scenario Coverage（评估场景覆盖）

Evaluation Dataset 至少覆盖以下场景。

## 12.1 Canonical Name（标准名称）

例如：

```
销售额
```

应找到正式 Sales Revenue Metric。

------

## 12.2 Alias（别名）

例如不同业务叫法：

```
销售收入
净销售额
销售金额
```

应能够命中正确正式对象。

------

## 12.3 Natural Language Expression（自然语言表达）

不是直接使用 Catalog 名称，而是：

> 通过业务表达描述目标对象。

用于验证 Semantic Retrieval（语义检索）能力。

------

## 12.4 Similar Object Disambiguation（相似对象区分）

验证相似对象之间不会严重混淆。

例如：

```
销售区域
vs
客户区域
订单日期
vs
确认日期
vs
完成日期
```

------

## 12.5 Metric Similarity（相似指标）

例如：

```
销售额
销售成本
毛利
毛利率
```

必须具有合理区分能力。

------

## 12.6 Physical / Semantic Mapping（物理 / 语义映射）

验证：

> 用户业务表达能够找到正确 Semantic Object 或 Physical Structure Candidate。

但最终业务裁决：

> 不属于 Retrieval Evaluation。

------

# 13. Evaluation by Asset Type（按资产类型评估）

Retrieval Quality 不只计算一个总体平均值。

必须能够分别观察：

```
Table Recall@K / MRR
Column / Field Recall@K / MRR
Metric Recall@K / MRR
```

原因：

> 总体平均值可能掩盖某一种资产类型质量严重不足。

正式 Release Gate 是否使用全部分类型阈值：

> 在 Baseline 后确定。

但 Diagnostic Report（诊断报告）必须能够分类型查看。

------

# 14. Build & Activation Gate（构建与激活门禁）

## 14.1 Full Rebuild（全量重建）

必须验证：

```
Current Authoritative Build Inputs
        ↓
Full Rebuild
        ↓
Complete Retrieval Asset Set
```

要求：

- 不依赖已有 Index 才能完成；
- 删除派生索引后可以重新建立；
- 不需要手工修改 Vector Database 中的业务内容。

------

## 14.2 Reproducibility（可重复构建）

相同：

```
Source
+
Build Contract
+
Relevant Configuration
```

重复构建：

> 必须产生语义等价的 Retrieval Asset Set。

不要求：

> 所有基础设施内部 Binary Representation（字节表示）完全一致。

要求：

- Logical Identity 一致；
- Source Trace 一致；
- Semantic Payload 等价；
- Retrieval Behavior 不出现不可解释变化。

------

## 14.3 Validation Before Activation（验证后激活）

必须证明：

```
Build
↓
Validate
↓
Activate
```

而不是：

```
Build
↓
Immediately Serve
```

未完成 Validation：

> 不得成为有效 Online Retrieval Asset。

------

## 14.4 Failed Build Protection（失败构建保护）

如果已有：

```
Valid Asset V1
```

同时新 Build：

```
Build V2
↓
Failure
```

必须保持：

```
Valid Asset V1
→ 仍然有效
```

失败构建：

> 不得自动破坏上一版有效资产。

------

# 15. Critical Bad Case Gate（严重失败案例门禁）

以下属于 Critical Bad Case：

- 检索资产包含不存在的业务事实；
- Metric Formula 被 Offline Pipeline 修改；
- Column / Field Meaning 被修改；
- Relationship 被向量结果错误裁决；
- Semantic → Physical Mapping 被静默改变；
- Legacy Resource 覆盖 Current Resource；
- 无 Source Trace 的资产被激活；
- 不完整 Build 被激活；
- Build Failure 被报告为成功；
- 新失败 Build 破坏上一版有效资产；
- 大量正式 Source Object 未被构建但 Pipeline 返回成功。

原则：

> **Critical failure cannot be hidden by average retrieval quality.**

> **严重错误不能被总体 Recall / MRR 掩盖。**

任何未解决 Critical Bad Case：

> Offline Pipeline 不得通过验收。

------

# 16. Threshold Strategy（阈值策略）

Hard Contract Gate：

> **100% Pass。**

例如：

- Source Validation
- Record Coverage
- Traceability
- Relationship Boundary
- Build Safety
- Activation Safety

这些不存在：

> “95% 差不多可以”。

------

Retrieval Quality：

> 不预先拍脑袋写死数值。

正式流程：

```
Build Evaluation Dataset
        ↓
Run Baseline
        ↓
Measure Recall@K / MRR
        ↓
Analyze Bad Cases
        ↓
Assess Online Retrieval Requirement
        ↓
Freeze Release Threshold
```

一旦形成 Release Baseline：

> Threshold 必须明确记录并版本化。

------

# 17. Bad Case Regression（失败案例回归）

任何确认属于系统问题的 Retrieval Bad Case：

```
Bad Case
↓
Root Cause Analysis
↓
Fix
↓
Add to Evaluation Dataset
↓
Regression Evaluation
```

Bad Case 不允许：

> 修完代码以后直接丢弃。

必须成为：

> Regression Asset（回归资产）。

------

# 18. Test / Evaluation Ownership（测试 / 评估职责）

## Deterministic Test

负责证明：

```
Contract Correctness
Build Correctness
Asset Integrity
Publish Safety
```

主要适用于：

> TDD — Test-Driven Development（测试驱动开发）。

------

## Retrieval Evaluation

负责证明：

```
Candidate Retrieval Quality
Ranking Quality
Semantic Matching Quality
```

主要适用于：

> EDD — Evaluation-Driven Development（评估驱动开发）。

------

两者不能互相替代。

例如：

> ```
> 所有预期 Retrieval Record 都已经成功写入 Index
> ```

不能证明：

> “销售额”一定能找到正确 Metric。

同样：

> Recall@K 很高

也不能证明：

> Source Trace 和 Build Safety 正确。

------

# 19. Feature Acceptance（功能验收）

Offline Pipeline V1 通过验收必须同时满足：

## Hard Contract

- 所有冻结 Deterministic Contract Test 100% Pass；
- Record Coverage 100%；
- Traceability Coverage 100%；
- Relationship Boundary 100% 满足；
- 无 Source Truth Violation。

## Retrieval Quality

- Evaluation Dataset 已建立；
- Baseline 已运行；
- Recall@K 已测量；
- MRR 已测量；
- 正式 Release Threshold 已达到。

## Build Safety

- Full Rebuild PASS；
- Reproducibility PASS；
- Validation Before Activation PASS；
- Failed Build Protection PASS。

## Critical Bad Case

- 无未解决 Critical Bad Case。

全部满足：

> **Offline Pipeline V1 Acceptance PASS。**

------

# 20. Done When（完成条件）

本 Acceptance & Evaluation Baseline 完成意味着：

- Verification Layer 已定义；
- Hard Gate 已定义；
- Retrieval Quality Gate 已定义；
- Build & Activation Gate 已定义；
- Critical Bad Case Gate 已定义；
- Recall@K / MRR 指标已确定；
- Evaluation Dataset Contract 已确定；
- Threshold Strategy 已确定；
- Bad Case Regression 机制已确定；
- Feature Acceptance 条件已确定。

具体：

- Test Case
- Evaluation Case
- Evaluation Dataset 内容
- Threshold 数值

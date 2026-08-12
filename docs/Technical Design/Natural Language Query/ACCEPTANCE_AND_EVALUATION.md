# Natural Language Query Acceptance & Evaluation Spec

# 自然语言查询验收与评估规格

> **Document（文档）：** `docs/Technical Design/Natural Language Query/ACCEPTANCE_AND_EVALUATION.md`
> **Feature（功能）：** Natural Language Query（自然语言查询）
> **Version（版本）：** V1
> **Status（状态）：** Acceptance & Evaluation Baseline（验收与评估基线）
> **Feature Spec Reference（功能规格引用）：** `FEATURE_SPEC.md`
> **Architecture Reference（架构引用）：** `ARCHITECTURE.md`

# 1. Purpose（目的）

本文档定义 Natural Language Query（自然语言查询，NLQ）V1（第一版）的：

- Verification（验证）；
- Acceptance（验收）；
- Evaluation（评估）；
- Release Gate（发布门禁）。

本文档回答：

- NLQ V1（自然语言查询第一版）需要证明什么；
- 哪些能力使用 Test（测试）验证；
- 哪些能力使用 Evaluation（评估）验证；
- 哪些规则属于 Hard Gate（硬性门禁）；
- AI Capability（人工智能能力）使用哪些正式质量指标；
- Test / Evaluation Case（测试 / 评估案例）如何组织；
- Bad Case（失败案例）如何进入回归；
- 满足什么条件才能通过发布验收。

本文档不定义：

- 具体 Test Case（测试用例）；
- 具体 Evaluation Case（评估案例）；
- Evaluation Dataset（评估数据集）具体内容；
- Test Code（测试代码）；
- Mock（模拟对象）；
- Prompt（提示词）；
- 具体 Module Implementation（模块实现）；
- 尚未经过 Baseline（基线）确定的数值阈值。

具体 Test / Evaluation Case（测试 / 评估案例）直接维护在对应 Test / Evaluation Asset（测试 / 评估资产）中。

不额外维护独立：

> Scenario Catalog（场景目录）。

核心原则：

> **Specification defines what must be true; Test and Evaluation prove it.**
> **规格定义什么必须成立，测试与评估负责证明它。**

# 2. Verification Layers（验证层）

NLQ V1（自然语言查询第一版）采用三个 Verification Layer（验证层）：

```
NLQ Verification
（自然语言查询验证）

├── Deterministic Test
│   （确定性测试）
│
├── AI Evaluation
│   （人工智能评估）
│
└── End-to-End Evaluation
    （端到端评估）
```

三层承担不同责任，不互相替代。

# 2.1 Deterministic Test（确定性测试）

Deterministic Test（确定性测试）验证：

> **能够通过明确程序规则判断正确与错误的行为。**

主要包括：

- Authorization Enforcement（权限强制校验）；
- SQL Safety（SQL 安全）；
- Read-Only Rule（只读规则）；
- Metric Formula（指标公式）；
- Business Time Rule（业务时间规则）；
- Comparison Formula（比较公式）；
- Result Contract（结果契约）；
- Unsupported Boundary Enforcement（不支持边界执行）；
- No Silent Change Rule（禁止静默修改规则）；
- Critical Feature Boundary Enforcement（关键功能边界执行）；
- 其他 Deterministic Business Rule（确定性业务规则）。

原则：

> **能够通过确定性 Test（测试）证明的规则，不使用 LLM Evaluation（大语言模型评估）代替。**

Deterministic Capability（确定性能力）主要采用：

> **TDD — Test-Driven Development（测试驱动开发）。**

# 2.2 AI Evaluation（人工智能评估）

AI Evaluation（人工智能评估）验证具有模型或检索不确定性的能力。

主要包括：

- Intent Understanding（意图理解）；
- Metric Resolution（指标解析）；
- Schema Linking（结构关联）；
- SQL Generation（SQL 生成）；
- Context Understanding（上下文理解）；
- Continuous Follow-up Understanding（连续追问理解）；
- Feature / Outcome Classification（功能 / 结果分类）。

这些能力不能只通过传统 Unit Test（单元测试）判断实际质量。

主要采用：

> **EDD — Evaluation-Driven Development（评估驱动开发）。**

基本过程：

```
Evaluation Dataset
（评估数据集）
        ↓
Run Evaluation
（运行评估）
        ↓
Measure Metrics
（计算指标）
        ↓
Analyze Bad Cases
（分析失败案例）
        ↓
Improve
（优化）
        ↓
Regression Evaluation
（回归评估）
```

# 2.3 End-to-End Evaluation（端到端评估）

End-to-End Evaluation（端到端评估）验证完整 NLQ（自然语言查询）业务链路。

```
Natural Language Query
（自然语言问题）
        ↓
Semantic Understanding
（语义理解）
        ↓
Schema / Metric Resolution
（结构 / 指标解析）
        ↓
SQL Generation
（SQL 生成）
        ↓
Validation
（校验）
        ↓
Authorization Enforcement
（权限强制校验）
        ↓
Query Execution
（查询执行）
        ↓
QueryResult
（查询结果）
```

最终判断标准不是：

> SQL（结构化查询语言）是否成功生成。

而是：

> **用户问题最终是否获得正确、可信、受权限约束的业务结果。**

End-to-End Evaluation（端到端评估）是 NLQ V1（自然语言查询第一版）最终质量判断的核心验证层。

# 3. Acceptance Model（验收模型）

NLQ V1（自然语言查询第一版）的验收使用四类 Gate（门禁）：

```
Acceptance
（验收）

├── Hard Gate
│   （硬性门禁）
│
├── Quality Gate
│   （质量门禁）
│
├── End-to-End Gate
│   （端到端门禁）
│
└── Critical Bad Case Gate
    （严重失败案例门禁）
```

四个 Gate（门禁）全部满足：

> 才能通过 Release Acceptance（发布验收）。

# 3.1 Hard Gate（硬性门禁）

Hard Gate（硬性门禁）约束：

> **系统已经明确规则后绝对不能违反的确定性行为。**

主要包括：

- Authorization Enforcement（权限强制校验）；
- SQL Safety（SQL 安全）；
- Read-Only Rule（只读规则）；
- Authoritative Metric Rule（权威指标规则）；
- Authoritative Business Rule（权威业务规则）；
- No Silent Change（禁止静默修改）；
- Result Contract（结果契约）；
- Data Write Prohibition（禁止数据写入）；
- Critical Feature Boundary Enforcement（关键功能边界执行）。

Hard Gate（硬性门禁）要求：

> **所有已冻结 Hard Gate Acceptance Case（硬性门禁验收案例）必须 100% Pass（100%通过）。**

任何已知 Critical Violation（严重违规）：

> 阻止发布。

## 3.1.1 Critical Feature Boundary Enforcement（关键功能边界执行）

Feature Boundary（功能边界）包含两部分。

### AI Classification Quality（人工智能分类质量）

例如：

> 用户自然语言是否被正确理解为 NLQ（自然语言查询）或 Business Analysis（经营分析）。

这类模型判断质量：

> 进入 Quality Gate（质量门禁）与 Outcome Accuracy（结果类型准确率）。

不要求理论上的 100%。

### Deterministic Boundary Enforcement（确定性边界执行）

一旦系统已经明确识别：

> 某请求不属于 NLQ（自然语言查询）能力，

则后续执行链：

> 不得继续绕过边界生成一个看似成功的 QueryResult（查询结果）。

这属于 Hard Gate（硬性门禁）。

即：

```
AI Classification
（人工智能分类）
→ Quality Gate
（质量门禁）

Deterministic Boundary Enforcement
（确定性边界执行）
→ Hard Gate
（硬性门禁）
```

# 3.2 Quality Gate（质量门禁）

Quality Gate（质量门禁）用于衡量 AI / Retrieval Capability（人工智能 / 检索能力）的质量。

主要包括：

- Intent Understanding（意图理解）；
- Metric Resolution（指标解析）；
- Schema Linking（结构关联）；
- SQL Generation（SQL 生成）；
- Context Understanding（上下文理解）；
- Outcome Classification（结果分类）。

Quality Gate（质量门禁）：

> 不要求理论上的 100%。

使用正式：

> Evaluation Threshold（评估阈值）

进行验收。

当前阶段不预先写死：

- 95%；
- 98%；
- 99%；

等任意数值。

阈值确定流程：

```
Build Evaluation Dataset
（建立评估数据集）
        ↓
Run Baseline
（运行基线）
        ↓
Observe Actual Quality
（观察真实质量）
        ↓
Assess Business Risk
（评估业务风险）
        ↓
Freeze Release Threshold
（冻结发布阈值）
```

Release Threshold（发布阈值）一旦用于正式 Release Baseline（发布基线）：

> 应明确记录并版本化。

# 3.3 End-to-End Gate（端到端门禁）

End-to-End Gate（端到端门禁）用于验证：

> **最终用户业务结果是否正确。**

核心指标：

> End-to-End Business Correctness（端到端业务正确率）。

即使所有中间 Module（模块）分别表现良好：

> 只要最终业务结果错误，Feature（功能）仍然不能视为正确。

# 3.4 Critical Bad Case Gate（严重失败案例门禁）

即使整体 Evaluation Metric（评估指标）已经达到正式阈值：

> 只要存在未解决 Critical Bad Case（严重失败案例），仍然不得发布。

Critical Bad Case（严重失败案例）主要包括：

- Authorization Violation（权限违规）；
- Data Write Risk（数据写入风险）；
- Silent Semantic Change（静默语义修改）；
- 明显错误的业务结果却被标记为成功；
- 违反 Authoritative Business Rule（权威业务规则）的结果；
- 其他可能造成严重错误业务决策的问题。

原则：

> **Critical failure cannot be hidden by average accuracy.**
> **严重错误不能被总体平均准确率掩盖。**

# 4. Feature-Level Evaluation Metrics（功能级评估指标）

正式 Feature-Level Evaluation Metric（功能级评估指标）只保留四个：

1. Semantic Intent Accuracy（语义意图准确率）；
2. Query Execution Correctness（查询执行正确率）；
3. Outcome Accuracy（结果类型准确率）；
4. End-to-End Business Correctness（端到端业务正确率）。

正式指标保持：

> **少而稳定。**

细粒度问题使用 Diagnostic Metric（诊断指标）分析。

# 4.1 Semantic Intent Accuracy（语义意图准确率）

用于衡量：

> 系统是否正确理解了用户真正需要查询的业务语义。

主要检查：

- Metric（指标）；
- Dimension（维度）；
- Time（时间）；
- Filter（筛选）；
- Grouping（分组）；
- Aggregate Filter（聚合筛选）；
- Sorting / Top N（排序 / 前 N）；
- Comparison（比较）；
- Detail Requirement（明细要求）。

只有所有影响业务结果的必要语义正确：

> Evaluation Case（评估案例）才算 Semantic Intent Correct（语义意图正确）。

不要求比较模型内部自由文本。

优先比较：

> Structured Semantic Intent（结构化语义意图）。

# 4.2 Query Execution Correctness（查询执行正确率）

用于衡量：

> 系统生成并执行的查询是否产生正确业务数据结果。

不以：

> SQL Exact Match（SQL 完全匹配）

作为主要判断标准。

原因：

> 同一个正确业务查询可以存在多个合法 SQL（结构化查询语言）表达方式。

优先使用：

> **Execution Equivalence（执行等价）。**

基本判断：

```
Generated Query
（生成查询）
        ↓
Execute
（执行）
        ↓
Actual Result
（实际结果）

       VS

Reference Query / Result
（参考查询 / 参考结果）
```

只要业务结果等价：

> Case Pass（案例通过）。

如果 SQL（结构化查询语言）写法不同但结果业务等价：

> 不应因为 SQL 文本不同判为失败。

# 4.3 Outcome Accuracy（结果类型准确率）

Outcome Accuracy（结果类型准确率）用于衡量：

> **系统是否正确判断当前请求应该进入哪一种 Business Outcome / Error Path（业务结果 / 错误路径）。**

可能路径包括：

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


Error Path
（错误路径）

└── System Failure
    （系统失败）
```

System Failure（系统失败）：

> 不是正常 Business Outcome（业务结果）。

但 Outcome Accuracy（结果类型准确率）必须能够验证：

> 系统是否正确进入了 System Failure Path（系统失败路径）。

例如存在真实 Metric Ambiguity（指标歧义）时：

> 应进入 Clarification（澄清）。

如果系统直接猜测指标并返回 QueryResult（查询结果）：

> Case Fail（案例失败）。

如果请求本来受支持，但系统内部处理失败：

> 应进入 System Failure Path（系统失败路径）。

不能伪装成：

> UnsupportedRequest（不支持请求）。

# 4.4 End-to-End Business Correctness（端到端业务正确率）

这是 NLQ V1（自然语言查询第一版）最重要的总体质量指标。

衡量：

> **从用户自然语言开始，到最终 Business Outcome / Error Path（业务结果 / 错误路径）为止，整个 Feature（功能）行为是否正确。**

成功 QueryResult（查询结果）场景主要验证：

```
Natural Language
（自然语言）
        ↓
Semantic Understanding
（语义理解）
        ↓
Metric / Schema Resolution
（指标 / 结构解析）
        ↓
SQL Generation
（SQL 生成）
        ↓
Validation
（校验）
        ↓
Authorization
（权限）
        ↓
Execution
（执行）
        ↓
QueryResult
（查询结果）
```

Clarification（澄清）、UnsupportedRequest（不支持请求）和 System Failure Path（系统失败路径）：

> 同样必须验证最终行为是否符合 Feature Spec（功能规格）。

任何阶段只要最终导致业务行为或业务结果错误：

> 整个 Evaluation Case（评估案例）失败。

原则：

> **End-to-End Business Correctness（端到端业务正确率）是 NLQ（自然语言查询）是否真正可用的最终质量指标。**

# 5. Diagnostic Metrics（诊断指标）

以下指标可用于开发、定位问题和 Bad Case Analysis（失败案例分析）：

- Schema Linking Accuracy（结构关联准确率）；
- Metric Resolution Accuracy（指标解析准确率）；
- SQL Generation Accuracy（SQL 生成准确率）；
- Context Resolution Accuracy（上下文解析准确率）；
- 其他真实问题驱动产生的 Module-Level Diagnostic Metric（模块级诊断指标）。

Diagnostic Metric（诊断指标）：

> 不默认升级为正式 Feature-Level Acceptance Metric（功能级验收指标）。

原则：

> **正式验收指标保持少而稳定，诊断指标根据真实问题增加。**

# 6. Test & Evaluation Case Organization（测试与评估案例组织）

不单独维护 Scenario Catalog（场景目录）。

Feature Spec（功能规格）中的 Capability / Rule / Boundary / Invariant（能力 / 规则 / 边界 / 不变量）直接转化为：

- Test Case（测试用例）；
- Evaluation Case（评估案例）。

基本链路：

```
FEATURE_SPEC.md
（功能规格）
        ↓
Test / Evaluation Case
（测试 / 评估案例）
        ↓
Test / Evaluation Run
（测试 / 评估运行）
        ↓
Report
（报告）
        ↓
Bad Case
（失败案例）
```

原则：

> **每个重要 Test / Evaluation Case（测试 / 评估案例）应能够追溯到它正在证明的 Source Rule（来源规则）。**

# 6.1 Test Case（测试用例）

Deterministic Rule（确定性规则）直接形成 Test Case（测试用例）。

Test Case（测试用例）至少应能够表达：

```
Case ID
（案例编号）

Source Rule
（来源规则）

Input / Setup
（输入 / 前置环境）

Expected Result
（预期结果）
```

例如：

```
Source Rule
（来源规则）
=
FEATURE_SPEC.md
→ Read-Only Rule
（只读规则）

Expected
（预期）
=
INSERT / UPDATE / DELETE
（插入 / 更新 / 删除）
全部拒绝
```

具体测试资产结构：

> 由 Test Implementation（测试实现）阶段确定。

# 6.2 Evaluation Case（评估案例）

AI / Retrieval Capability（人工智能 / 检索能力）直接形成 Evaluation Case（评估案例）。

一个 Evaluation Case（评估案例）至少表达：

```
Case ID
（案例编号）

Source Rule
（来源规则）

Input
（输入）

Expected Semantic Intent
（预期语义意图，如适用）

Expected Outcome / Path
（预期业务结果 / 路径）

Reference Query / Result
（参考查询 / 结果，如适用）
```

`Source Rule（来源规则）` 用于建立：

```
Feature Spec Rule
（功能规格规则）
        ↓
Test / Evaluation Case
（测试 / 评估案例）
        ↓
Run
（运行）
        ↓
Report
（报告）
```

例如：

```
Source Rule
（来源规则）

FEATURE_SPEC.md
→ Metric Query
  （指标查询）
```

或者：

```
FEATURE_SPEC.md
→ No Silent Change
  （禁止静默修改）
```

本文档不保存具体 Evaluation Case（评估案例）。

# 6.3 Natural Language Variation（自然语言表达变化）

同一种 Business Scenario（业务场景）可以存在多种自然语言表达。

这些不同表达：

> 不需要形成独立 Feature Scenario Document（功能场景文档）。

可以作为同一个业务规则下面的多个：

> Evaluation Case（评估案例）。

用于验证：

> Natural Language Robustness（自然语言鲁棒性）。

# 6.4 Case Coverage（案例覆盖）

Test / Evaluation Asset（测试 / 评估资产）应覆盖 Feature Spec（功能规格）中重要：

- Supported Capability（支持能力）；
- Business Rule（业务规则）；
- Authorization Rule（权限规则）；
- Result Rule（结果规则）；
- Clarification Rule（澄清规则）；
- Unsupported Boundary（不支持边界）；
- Feature Invariant（功能不变量）。

不要求：

> 每一句文档文字对应一个独立 Case（案例）。

原则：

> **测试关键 Contract（契约），不要机械测试文档句子。**

# 7. Bad Case Regression（失败案例回归）

Evaluation（评估）或真实 Runtime（运行时）中发现的有价值失败：

> 应进入 Bad Case（失败案例）管理。

典型包括：

- Intent Understanding Error（意图理解错误）；
- Metric Resolution Error（指标解析错误）；
- Schema Linking Error（结构关联错误）；
- SQL Generation Error（SQL 生成错误）；
- Context Resolution Error（上下文解析错误）；
- Outcome Classification Error（结果分类错误）；
- 最终 Business Result Error（业务结果错误）；
- Silent Semantic Change（静默语义修改）。

基本流程：

```
Bad Case
（失败案例）
        ↓
Root Cause Analysis
（根因分析）
        ↓
Fix
（修复）
        ↓
Add Regression Case
（加入回归案例）
        ↓
Re-Evaluation
（重新评估）
```

# 7.1 Bad Case Admission Rule（失败案例准入规则）

不是所有 Runtime Failure（运行时失败）都必须进入正式 Evaluation Dataset（评估数据集）。

例如偶发：

> Database Timeout（数据库超时）

通常主要属于：

- Reliability（可靠性）；
- Observability（可观测）；
- Infrastructure（基础设施）

问题。

只有具有以下至少一种价值的 Failure（失败）：

- 可复现价值；
- 质量改进价值；
- 回归价值；

才进入正式 Bad Case Regression（失败案例回归）。

# 7.2 Regression Rule（回归规则）

任何已经修复的重要 Bad Case（失败案例）：

> 应增加对应 Regression Case（回归案例）。

后续模型、Prompt（提示词）、Retriever（检索器）、Semantic Asset（语义资产）或代码发生变化时：

> 必须重新验证这些回归案例。

原则：

> **A fixed Bad Case becomes a Regression Case.**
> **修复后的失败案例应成为回归案例。**

# 8. Release Gate（发布门禁）

NLQ V1（自然语言查询第一版）只有同时满足以下四个条件：

1. Hard Gate Pass（硬性门禁通过）；
2. Quality Gate Pass（质量门禁通过）；
3. End-to-End Gate Pass（端到端门禁通过）；
4. Critical Bad Case Gate Pass（严重失败案例门禁通过）；

才能通过 Release Acceptance（发布验收）。

# 8.1 Hard Gate Pass（硬性门禁通过）

所有已经冻结的：

> Hard Gate Acceptance Case（硬性门禁验收案例）

必须：

> **100% Pass（100%通过）。**

任何已知 Critical Violation（严重违规）都阻止发布。

包括但不限于：

- Authorization Violation（权限违规）；
- SQL Write Operation（SQL 写操作）；
- 静默修改 Metric（指标）；
- 静默修改 Time Scope（时间范围）；
- 静默删除 Filter（筛选）；
- 静默改变 Result Grain（结果粒度）；
- 明确越权请求被静默缩窄；
- 已确定超出 NLQ（自然语言查询）边界却继续返回 QueryResult（查询结果）。

这里的：

> **100% Pass（100%通过）**

指的是：

> 当前冻结的 Hard Gate Acceptance Suite（硬性门禁验收集）100% 通过。

# 8.2 Quality Gate Pass（质量门禁通过）

以下正式质量指标必须达到冻结的 Release Threshold（发布阈值）：

- Semantic Intent Accuracy（语义意图准确率）；
- Query Execution Correctness（查询执行正确率）；
- Outcome Accuracy（结果类型准确率）。

具体 Threshold（阈值）：

> 根据 Evaluation Dataset（评估数据集）、Baseline（基线）和 Business Risk（业务风险）确定。

未冻结正式 Threshold（阈值）前：

> 不使用任意经验数字代替。

# 8.3 End-to-End Gate Pass（端到端门禁通过）

End-to-End Business Correctness（端到端业务正确率）必须达到：

> 正式冻结的 Release Threshold（发布阈值）。

最终 Release Decision（发布决策）必须以：

> **最终用户业务行为和业务结果是否正确**

作为核心依据。

# 8.4 Critical Bad Case Gate Pass（严重失败案例门禁通过）

发布前必须满足：

> **No Unresolved Critical Bad Case（不存在未解决严重失败案例）。**

即使总体 Evaluation Metric（评估指标）达到阈值：

> 仍不能用平均准确率抵消 Critical Bad Case（严重失败案例）。

# 9. Release Threshold Rule（发布阈值规则）

Quality Gate（质量门禁）和 End-to-End Gate（端到端门禁）的具体 Threshold（阈值）：

> 不在 Feature Specification Stage（功能规格阶段）随意确定。

流程：

```
Evaluation Dataset
（评估数据集）
        ↓
Baseline Evaluation
（基线评估）
        ↓
Quality Distribution
（质量分布）
        ↓
Business Risk Assessment
（业务风险评估）
        ↓
Release Threshold
（发布阈值）
        ↓
Freeze
（冻结）
```

Threshold（阈值）冻结后：

- 应有明确版本；
- 应明确使用的数据集版本；
- 应明确模型 / 系统 Baseline（基线）；
- 变更阈值应有原因。

不得为了让某次 Release（发布）通过：

> 临时降低 Threshold（阈值）。

# 10. Release Decision（发布判断）

最终 Release Decision（发布判断）保持简单：

```
Hard Gate
（硬性门禁）
=
Frozen Hard Gate Suite
（冻结硬性门禁测试集）
100% Pass
（100%通过）

AND

Quality Gate
（质量门禁）
>=
Frozen Release Threshold
（冻结发布阈值）

AND

End-to-End Business Correctness
（端到端业务正确率）
>=
Frozen Release Threshold
（冻结发布阈值）

AND

No Unresolved Critical Bad Case
（不存在未解决严重失败案例）

↓

NLQ V1 Accepted
（自然语言查询第一版验收通过）
```

任何一个条件不满足：

> NLQ V1（自然语言查询第一版）不得通过正式 Release Acceptance（发布验收）。

# 11. Verification Traceability（验证可追溯性）

正式验证应形成以下链路：

```
FEATURE_SPEC.md
（功能规格）
        ↓
Source Rule
（来源规则）
        ↓
Test / Evaluation Case
（测试 / 评估案例）
        ↓
Test / Evaluation Run
（测试 / 评估运行）
        ↓
Report
（报告）
        ↓
Bad Case
（失败案例，如存在）
        ↓
Regression
（回归）
```

目标不是建立复杂 Traceability Platform（可追溯平台）。

V1（第一版）只要求：

> **重要测试和评估案例能够明确知道自己正在证明哪条 Feature / Module Contract（功能 / 模块契约）。**

# 12. Core Principles（核心原则）

本 Acceptance & Evaluation（验收与评估）体系长期遵守：

> **Deterministic rules are proven by Test.**
> **确定性规则使用 Test（测试）证明。**

> **AI and Retrieval quality are measured by Evaluation.**
> **人工智能和检索质量使用 Evaluation（评估）衡量。**

> **Final business correctness is judged End-to-End.**
> **最终业务正确性通过 End-to-End Evaluation（端到端评估）判断。**

> **Hard Gate cannot be offset by average accuracy.**
> **硬性门禁不能由总体平均准确率抵消。**

> **Different correct SQL expressions are allowed; business Execution Equivalence matters.**
> **允许不同的正确 SQL（结构化查询语言）表达，重点验证业务执行等价。**

> **Feature-Level Metrics stay few and stable.**
> **功能级正式指标保持少而稳定。**

> **Diagnostic Metrics grow from real problems.**
> **诊断指标从真实问题中生长。**

> **Critical failures cannot be hidden by aggregate metrics.**
> **严重失败不能被总体指标掩盖。**

> **Bad Cases feed Regression.**
> **失败案例进入回归闭环。**

> **Tests and Evaluations trace back to Contracts.**
> **测试和评估应能够追溯到规格与契约。**

最终原则：

> **验收证明的不是“系统能运行”，而是“系统能够稳定产生正确、可信、受权限约束的业务行为和业务结果”。**

# 13. Acceptance Baseline（验收基线）

NLQ V1（自然语言查询第一版）的验证体系：

```
Verification
（验证）

├── Deterministic Test
│   （确定性测试）
│
├── AI Evaluation
│   （人工智能评估）
│
└── End-to-End Evaluation
    （端到端评估）
```

正式 Feature-Level Metric（功能级指标）：

```
1. Semantic Intent Accuracy
   （语义意图准确率）

2. Query Execution Correctness
   （查询执行正确率）

3. Outcome Accuracy
   （结果类型准确率）

4. End-to-End Business Correctness
   （端到端业务正确率）
```

正式 Release Gate（发布门禁）：

```
1. Hard Gate
   （硬性门禁）
   → 冻结验收集 100% Pass

2. Quality Gate
   （质量门禁）
   → 达到冻结发布阈值

3. End-to-End Gate
   （端到端门禁）
   → 达到冻结业务正确率阈值

4. Critical Bad Case Gate
   （严重失败案例门禁）
   → 不存在未解决严重失败案例
```

最终目标：

> **使用最少但有效的 Test（测试）与 Evaluation（评估），证明 NLQ V1（自然语言查询第一版）满足** `**FEATURE_SPEC.md**` **定义的业务能力、规则、边界与不变量。**
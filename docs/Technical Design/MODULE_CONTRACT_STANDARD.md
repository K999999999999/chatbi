# ChatBI Module Contract Standard

# ChatBI 模块契约标准

> **Status（状态）：** Engineering Baseline（工程基线）
> **Scope（范围）：** ChatBI 所有 Feature Module（功能模块）与 Technical Module（技术模块）
> **Engineering Reference（工程依据）：** `ENGINEERING.md`
> **Architecture Reference（架构依据）：** `ARCHITECTURE.md`
> **Feature Architecture Standard Reference（功能架构标准依据）：** `FEATURE_ARCHITECTURE_STANDARD.md`

# 1. Purpose（目的）

本文档定义 ChatBI 统一的 Module Contract Standard（模块契约标准）。

Module Contract（模块契约）回答：

> **一个 Module（模块）在进入 Test / Evaluation（测试 / 评估）和 Implementation（实现）之前，必须承诺什么。**

目标是让每个 Module（模块）具有：

- Clear Responsibility（清晰职责）；
- Explicit Input / Output Contract（明确输入 / 输出契约）；
- Explicit Boundary（明确边界）；
- Explicit Failure（明确失败）；
- Verifiable Behavior（可验证行为）；
- Replaceable Implementation（可替换实现）。

核心原则：

> **Every Module has a Contract; Implementation must satisfy the Contract.**
> **每个模块都有契约，实现必须满足契约。**

# 2. Module Positioning（模块定位）

Module（模块）是 Feature（功能）内部承担一组高度相关责任的设计单元。

Module（模块）必须满足：

> **High Cohesion, Clear Boundary（高内聚，清晰边界）。**

一个 Module（模块）必须能够明确回答：

```
我负责什么？
我不负责什么？

我接收什么？
我保证输出什么？

执行前必须满足什么条件？
什么结果才算成功？

什么时候失败？
依赖哪些外部能力？

如何证明契约成立？
```

Module Contract（模块契约）描述：

> **模块承诺什么。**

不描述：

> **模块必须使用什么具体代码、类、函数、框架或算法实现。**

# 3. Required Module Contract（必须定义的模块契约）

所有正式 Module Spec（模块规格）必须定义以下九项：

```
1. Responsibility
   （职责）

2. Input Contract
   （输入契约）

3. Preconditions
   （前置条件）

4. Processing Responsibilities
   （处理职责）

5. Output Contract
   （输出契约）

6. Postconditions / Invariants
   （后置条件 / 不变量）

7. Failure Contract
   （失败契约）

8. Dependencies
   （依赖）

9. Test / Evaluation
   （测试 / 评估）
```

影响 Contract（契约）的核心内容不得省略。

不适用的子项可以省略。

不得为了满足 Template（模板）制造无意义内容。

# 4. Responsibility（职责）

Responsibility（职责）必须说明：

- Module（模块）为什么存在；
- Module（模块）负责解决什么问题；
- Module（模块）的责任边界；
- Module（模块）明确不负责什么。

原则：

> **One Module owns one coherent responsibility.**
> **一个模块承担一组高度相关的责任。**

不得因为：

- 实现方便；
- 代码短；
- 共用某个 Framework（框架）；

把不相关责任合并进一个 Module（模块）。

# 5. Input Contract（输入契约）

每个 Module（模块）必须拥有明确的 Input Contract（输入契约）。

Input Contract（输入契约）根据实际需要定义：

```
Input Object
（输入对象）

Field
（字段）

Type
（类型）

Required / Optional
（必需 / 可选）

Semantic Meaning
（语义）

Allowed Value / Constraint
（允许值 / 约束）
```

原则：

> **输入必须可描述、可验证、可依赖。**

禁止把以下形式作为稳定 Module Contract（模块契约）：

- 未定义结构的自由 `dict（字典）`；
- 未定义结构的自由 JSON（JSON 数据）；
- 隐式字段约定；
- 依赖调用方“自己知道怎么传”的数据。

# 6. Typed Contract（类型化契约）

Input Contract（输入契约）和 Output Contract（输出契约）应优先使用：

> **Typed Contract（类型化契约）。**

常见类型包括：

- `string（字符串）`
- `integer（整数）`
- `float（浮点数）`
- `boolean（布尔值）`
- `enum（枚举）`
- `list（列表）`
- `structured object（结构化对象）`
- `nullable（可为空）`

固定语义集合应优先使用：

> **Enum（枚举）**

而不是任意 String（字符串）。

用户原始自然语言可以保留 Business Text（业务文本）；

系统控制字段应优先使用稳定：

> **Machine Value（机器值）。**

设计层定义的是：

> **Schema / Typed Contract（结构 / 类型化契约）。**

Pydantic（Python 数据校验模型库）等属于 Implementation Technology（实现技术），不是 Contract（契约）本身。

# 7. Preconditions（前置条件）

Preconditions（前置条件）定义：

> **Module（模块）开始处理以前，上游必须已经保证什么。**

可以包括：

- Input Contract（输入契约）已经满足；
- 必需业务语义已经存在；
- 上游 Module（模块）已经成功完成；
- Authorization Context（授权上下文）已经建立；
- 必要 Resource（资源）已经可用；
- 必需 Domain Rule（领域规则）已经加载。

原则：

> **Upstream guarantees become downstream assumptions.**
> **上游已经保证的事实，可以成为下游明确的前置条件。**

Precondition（前置条件）未满足时：

> 按 Failure Contract（失败契约）处理。

不得由下游：

- 静默猜测；
- 自动改变业务语义；
- 无限补偿上游错误。

# 8. Processing Responsibilities（处理职责）

Processing Responsibilities（处理职责）定义：

> **为了满足 Output Contract（输出契约），Module（模块）必须完成哪些行为和决策。**

可以定义：

- Required Capability（必需能力）；
- Processing Rule（处理规则）；
- Decision Rule（决策规则）；
- Validation Responsibility（校验责任）。

不得定义：

- Class（类）；
- Function（函数）；
- Package（包）；
- File Layout（文件组织）；
- SDK Call（软件开发工具包调用）；
- Framework API（框架接口）；
- 具体算法代码。

原则：

> **Describe behavior, not implementation.**
> **描述行为，不规定实现。**

# 9. Output Contract（输出契约）

每个 Module（模块）必须拥有明确 Output Contract（输出契约）。

根据实际需要定义：

```
Output Object
（输出对象）

Typed Schema
（类型化结构）

Field Meaning
（字段语义）

Required / Optional
（必需 / 可选）

Success Semantics
（成功语义）
```

原则：

> **成功输出必须是完整 Contract Result（契约结果）。**

禁止：

- 返回半完成对象；
- 缺失关键字段却继续进入下游；
- 使用隐藏字段表达未声明状态；
- 用自由文本代替应该结构化的正式结果。

# 10. Postconditions / Invariants（后置条件 / 不变量）

Postconditions / Invariants（后置条件 / 不变量）定义：

> **Module（模块）成功返回时必须始终成立的条件。**

根据模块职责，可以包括：

### Completeness（完整性）

该 Module（模块）负责解决的信息已经完整解决。

### Consistency（一致性）

结果内部不存在冲突。

### Validity（合法性）

结果满足 Business Rule / System Rule（业务规则 / 系统规则）。

### Connectivity（连通性）

涉及结构关系时，结果具有合法 Relationship（关系）。

### Authorization（授权）

结果没有超出当前允许的数据或业务范围。

### Determinism（确定性）

需要确定性保证的规则没有交给非确定性组件最终裁决。

原则：

> **Success means all required Invariants hold.**
> **只有所有必要不变量成立，才能视为成功。**

# 11. Validation Rule（校验规则）

Contract（契约）和 Runtime Validation（运行时校验）不是同一概念。

所有 Module（模块）：

> **必须拥有明确 Contract（契约）。**

但不是所有内部边界都必须重复进行完整 Runtime Schema Validation（运行时结构校验）。

## 11.1 Untrusted Boundary（不可信边界）

以下边界必须进行严格 Validation（校验）：

- External API（外部接口）；
- User Input（用户输入）；
- LLM Output（大语言模型输出）；
- File / JSON Resource（文件 / JSON 资源）；
- External Service（外部服务）；
- 其他当前进程无法直接控制的数据。

基本规则：

```
Raw / Untrusted Data
（原始 / 不可信数据）
        ↓
Runtime Validation
（运行时校验）
        ↓
Typed Object
（类型化对象）
```

## 11.2 Internal Trusted Boundary（内部可信边界）

已经满足 Typed Contract（类型化契约）的内部 Module（模块）之间：

```
Typed Output
（类型化输出）
        ↓
Typed Input
（类型化输入）
```

不要求每层重复完整：

- Serialization / Deserialization（序列化 / 反序列化）；
- Schema Validation（结构校验）。

但必须保持：

- Preconditions（前置条件）；
- Postconditions（后置条件）；
- Invariants（不变量）。

原则：

> **Validate strongly at trust boundaries; preserve Contracts internally.**
> **不可信边界严格校验，内部边界依靠明确契约。**

# 12. Failure Contract（失败契约）

每个 Module（模块）必须明确：

> **什么情况下无法产生合法 Output（输出）。**

通用 Failure Category（失败类别）包括：

### Invalid Input（非法输入）

Input Contract（输入契约）或 Preconditions（前置条件）未满足。

### Resolution Failure（解析失败）

Module（模块）设计上应该能够完成任务，但没有得到唯一、完整或合法结果。

### Dependency Failure（依赖失败）

外部 Capability（能力）：

- 不可用；
- 超时；
- 返回非法结果。

### Unsupported（不支持）

请求本身明确超出当前设计能力范围。

### Authorization Violation（权限违规）

仅在 Module（模块）职责涉及 Authorization（授权）时使用。

### Internal Failure（内部失败）

模块出现违反自身 Contract / Invariant（契约 / 不变量）的系统错误。

Module（模块）可以根据实际职责增加必要 Failure Category（失败类别）。

不得为了统一格式制造无实际意义的 Failure（失败）。

# 13. No Silent Degradation（禁止静默降级）

如果关键 Contract（契约）无法满足：

> **Fail Explicitly（明确失败）。**

禁止：

```
发现关键问题
        ↓
忽略 / 猜测 / 偷换语义
        ↓
生成看似成功的结果
```

尤其禁止静默修改：

- Business Meaning（业务含义）；
- Metric（指标）；
- Time（时间）；
- Filter（筛选）；
- Authorization Scope（权限范围）；
- Relationship（关系）；
- Result Granularity（结果粒度）。

原则：

> **Incorrect success is worse than explicit failure.**
> **错误的成功比明确失败更危险。**

# 14. Clarification Boundary（澄清边界）

Clarification（澄清）属于：

> **Feature Outcome（功能结果）。**

普通 Module（模块）不得直接与用户进行 Clarification（澄清）。

只有负责：

> **User Semantic Understanding（用户语义理解）**

的 Module（模块），可以报告：

- Missing Required Semantics（缺少必要语义）；
- Semantic Ambiguity（语义歧义）；
- Context Reference Ambiguity（上下文引用歧义）。

再由 Feature（功能）决定是否生成：

> Clarification（澄清）。

一旦上游已经确认用户业务语义完整：

后续 Module（模块）出现：

- Schema Mapping Failure（结构映射失败）；
- Metric Resolution Failure（指标解析失败）；
- Relationship Failure（关系失败）；
- SQL Generation Failure（SQL 生成失败）；
- Dependency Failure（依赖失败）；

不得重新要求用户解决系统内部问题。

原则：

> **User clarifies business intent; system resolves internal structure.**
> **用户澄清业务意图，系统解决内部结构。**

# 15. Failure vs Unsupported（失败与不支持）

必须严格区分：

### Unsupported（不支持）

> 当前系统设计上就没有能力完成该请求。

### Failure（失败）

> 当前系统设计上应该能够完成，但本次没有正确完成。

Failure（失败）应优先进入：

```
Failure
（失败）
   ↓
Bad Case Capture
（失败案例记录）
   ↓
Root Cause Analysis
（根因分析）
   ↓
Fix
（修复）
   ↓
Regression
（回归）
```

不得把 Failure（失败）伪装成 Unsupported（不支持）。

也不得把 Unsupported（不支持）伪装成系统故障。

# 16. Dependencies（依赖）

每个 Module（模块）必须明确自己依赖哪些外部能力。

依赖应优先表达为：

> **Capability / Port（能力 / 端口）**

例如：

- Model Capability（模型能力）；
- Semantic Retrieval Capability（语义检索能力）；
- Database Query Capability（数据库查询能力）；
- Schema Metadata Capability（结构元数据能力）；
- Metric Catalog Capability（指标目录能力）；
- Relationship Metadata Capability（关系元数据能力）；
- State Capability（状态能力）。

Domain / Application Module（领域 / 应用模块）原则上不直接绑定：

- LLM Provider（大语言模型供应商）；
- Vector Database Vendor（向量数据库供应商）；
- Database SDK（数据库软件开发工具包）；
- Framework SDK（框架软件开发工具包）。

原则：

> **Depend on capability, not vendor.**
> **依赖能力，不依赖供应商。**

具体 Adapter（适配器）由 Infrastructure（基础设施）实现。

# 17. Infrastructure Growth Rule（基础设施生长规则）

Infrastructure（基础设施）应从真实 Module Contract（模块契约）需求中生长。

正确顺序：

```
Feature Requirement
（功能需求）
        ↓
Module Contract
（模块契约）
        ↓
Required Capability
（所需能力）
        ↓
Port
（端口）
        ↓
Infrastructure Adapter
（基础设施适配器）
```

不采用：

```
先建设大量通用 Infrastructure
（基础设施）
        ↓
再寻找业务使用场景
```

原则：

> **Infrastructure grows from real Feature / Module needs.**
> **基础设施从真实功能 / 模块需求中生长。**

# 18. Test / Evaluation Rule（测试 / 评估规则）

每个 Module Contract（模块契约）都必须能够被证明。

## 18.1 Deterministic Module（确定性模块）

优先使用：

> **TDD — Test-Driven Development（测试驱动开发）。**

重点验证：

- Input Contract（输入契约）；
- Preconditions（前置条件）；
- Processing Rule（处理规则）；
- Output Contract（输出契约）；
- Boundary Condition（边界条件）；
- Failure Contract（失败契约）；
- Invariants（不变量）。

## 18.2 AI / LLM / Retrieval Module（人工智能 / 大语言模型 / 检索模块）

优先使用：

> **EDD — Evaluation-Driven Development（评估驱动开发）。**

重点验证：

- Semantic Accuracy（语义准确性）；
- Retrieval Quality（检索质量）；
- Required Context Coverage（必要上下文覆盖）；
- Outcome Correctness（结果类型正确性）；
- Bad Case（失败案例）；
- Regression（回归）。

## 18.3 Hybrid Module（混合模块）

同时包含确定性逻辑与 AI / Retrieval（人工智能 / 检索）能力时：

> **TDD（测试驱动开发） + EDD（评估驱动开发）同时使用。**

原则：

> **Test / Evaluation proves the Contract.**
> **测试 / 评估负责证明契约成立。**

不是只验证：

> “代码可以运行。”

# 19. Detail Boundary（设计深度边界）

Module Spec（模块规格）可以定义：

- Responsibility（职责）；
- Typed Input / Output Contract（类型化输入 / 输出契约）；
- Preconditions（前置条件）；
- Processing Rule（处理规则）；
- Decision Rule（决策规则）；
- Invariants（不变量）；
- Failure Category（失败类别）；
- Capability Dependency（能力依赖）；
- Test / Evaluation Requirement（测试 / 评估要求）。

Module Spec（模块规格）原则上不定义：

- Concrete Class（具体类）；
- Concrete Function（具体函数）；
- File Layout（文件布局）；
- SDK Call（软件开发工具包调用）；
- Framework API（框架接口）；
- Prompt Text（具体提示词文本）；
- Concrete Algorithm Code（具体算法代码）；
- Concrete Retry Count（具体重试次数）；
- Arbitrary Threshold（任意阈值）；
- Concrete Infrastructure Adapter（具体基础设施适配器）。

如果某个实现决定会改变 Module Contract（模块契约）：

> 在 Module Spec（模块规格）中定义。

如果只是实现方式：

> 留到 Implementation Task Spec（实现任务规格）或 Implementation（实现）。

# 20. Change Rule（变更规则）

设计变化时，修改事实所属的最高正确层级。

```
Business Meaning Changed?
（业务含义变化？）
        ↓ Yes
Business Domain
（业务领域）


Feature Behavior / Boundary Changed?
（功能行为 / 边界变化？）
        ↓ Yes
Feature Architecture / Feature Spec
（功能架构 / 功能规格）


Module Contract Changed?
（模块契约变化？）
        ↓ Yes
Module Spec
（模块规格）


Implementation Only?
（只是实现变化？）
        ↓
Code / Test / Evaluation
（代码 / 测试 / 评估）
```

Module Implementation（模块实现）不得自行反向修改：

- Business Meaning（业务含义）；
- Feature Contract（功能契约）；
- Feature Architecture（功能架构）；
- System Architecture（系统架构）。

如果必须改变上层事实：

> **先修改上层设计，再修改 Module Contract（模块契约）和 Implementation（实现）。**

# 21. Module Spec Template（模块规格模板）

所有正式 Module Spec（模块规格）推荐采用以下模板：

```
# <Module Name> Module Spec
# <模块名称> 模块规格

> Status（状态）
> Version（版本）
> Feature（所属功能）
> Feature Architecture Reference（功能架构引用）
> Feature Spec Reference（功能规格引用）
> Module Standard Reference（模块标准引用）

## 1. Responsibility（职责）

负责什么。

明确不负责什么。

---

## 2. Input Contract（输入契约）

输入对象。

Typed Schema（类型化结构）。

Required / Optional（必需 / 可选）。

字段语义和值约束。

---

## 3. Preconditions（前置条件）

进入 Module（模块）前必须成立的条件。

---

## 4. Processing Responsibilities（处理职责）

Module（模块）为了满足 Output Contract（输出契约）
必须完成的行为、规则和决策。

不描述具体代码实现。

---

## 5. Output Contract（输出契约）

输出对象。

Typed Schema（类型化结构）。

Success Semantics（成功语义）。

---

## 6. Postconditions / Invariants（后置条件 / 不变量）

成功返回时必须始终成立的条件。

---

## 7. Failure Contract（失败契约）

根据实际职责选择：

- Invalid Input（非法输入）
- Resolution Failure（解析失败）
- Dependency Failure（依赖失败）
- Authorization Violation（权限违规，如适用）
- Unsupported（不支持）
- Internal Failure（内部失败）

明确 Clarification（澄清）边界。

---

## 8. Dependencies（依赖）

需要哪些：

Domain / Application / Infrastructure Capability
（领域 / 应用 / 基础设施能力）。

优先依赖 Capability / Port（能力 / 端口），
不绑定 Vendor / Framework（供应商 / 框架）。

---

## 9. Test / Evaluation（测试 / 评估）

确定性逻辑：
TDD（测试驱动开发）。

AI / LLM / Retrieval（人工智能 / 大语言模型 / 检索）：
EDD（评估驱动开发）。

明确证明 Contract（契约）成立所需要的核心测试或评估。
```

Module（模块）可以根据真实需要增加少量章节。

但：

> **不得重复上层已经定义的事实。**

> **不得为了模板完整而制造内容。**

# 22. Module Design Baseline（模块设计基线）

ChatBI 所有 Module（模块）长期遵循：

> **Clear Responsibility（职责清晰）。**

> **Typed Input / Output Contract（类型化输入 / 输出契约）。**

> **Explicit Preconditions（明确前置条件）。**

> **Explicit Postconditions / Invariants（明确后置条件 / 不变量）。**

> **Explicit Failure（明确失败）。**

> **No Silent Degradation（禁止静默降级）。**

> **User Clarifies Intent, System Resolves Structure（用户澄清意图，系统解决结构）。**

> **Depend on Capability, Not Vendor（依赖能力，不依赖供应商）。**

> **Infrastructure Grows from Real Needs（基础设施从真实需求中生长）。**

> **Contract First, Implementation Second（契约先行，实现随后）。**

最终原则：

> **模块先定职责和契约，再证明契约，最后实现契约。**

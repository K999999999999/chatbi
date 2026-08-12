# ChatBI Module Contract Standard（模块契约标准）

> **Status（状态）**：Engineering Baseline（工程基线）  
> **Scope（范围）**：ChatBI 所有 Feature Module（功能模块）与技术模块  
> **Engineering Reference（工程依据）**：`ENGINEERING.md`  
> **Architecture Reference（架构依据）**：`ARCHITECTURE.md`

---

# 1. Purpose（目的）

本文档定义 ChatBI 的统一 Module Contract Standard（模块契约标准）。

回答：

> 一个 Module（模块）在进入实现之前，必须明确哪些内容？

目标是让所有模块具有统一、稳定、可验证的设计边界，使：

- 上下游能够依赖明确 Contract（契约）协作
- Module 可以独立 Test / Evaluation（测试 / 评估）
- Implementation（实现）可以替换而不破坏上层行为
- Failure（失败）可以被定位、记录和回归
- Infrastructure（基础设施）由真实模块需求驱动产生

原则：

> **Every module has a contract; implementation must satisfy the contract.**

即：

> **每个模块都有契约，实现必须满足契约。**

---

# 2. Module Positioning（模块定位）

Module（模块）是 Feature（功能）内部承担单一明确责任的设计单元。

Module 应满足：

> **High Cohesion, Clear Boundary（高内聚，清晰边界）。**

一个 Module 应能够回答：

```text
我负责什么？
我不负责什么？

我接收什么？
我保证输出什么？

什么条件下可以执行？
什么结果才算成功？

什么情况下失败？
依赖哪些外部能力？
```





Module Contract（模块契约）描述：

> **模块承诺什么。**

不描述：

> **模块必须使用什么具体代码、类、函数或算法实现。**

------

# 3. Standard Module Contract（标准模块契约）

每个 Module Spec（模块规格）至少必须定义以下八部分：

```
Responsibility
（职责）
        ↓
Input Contract
（输入契约）
        ↓
Preconditions
（前置条件）
        ↓
Processing Responsibilities
（处理职责）
        ↓
Output Contract
（输出契约）
        ↓
Postconditions / Invariants
（后置条件 / 不变量）
        ↓
Failure Contract
（失败契约）
        ↓
Dependencies
（依赖）
```

------

# 4. Responsibility（职责）

Responsibility 定义：

> **这个模块为什么存在。**

必须说明：

- 模块负责的核心问题
- 模块职责边界
- 明确不属于该模块的责任

原则：

> **One module owns one coherent responsibility.**

即：

> **一个模块承担一组高度相关的责任。**

不得因为实现方便，把无关业务职责堆入同一个 Module。

------

# 5. Input Contract（输入契约）

每个 Module 必须拥有明确的 Input Contract（输入契约）。

Input Contract 至少定义：

- Input Object（输入对象）
- Typed Schema（类型结构）
- Required Field（必需字段）
- Optional Field（可选字段）
- Field Meaning（字段语义）
- Value Constraint（值约束）

原则：

> **输入必须是可描述、可验证、可依赖的。**

禁止以未定义结构的自由 `dict`、自由 JSON 或隐式约定作为稳定模块契约。

------

# 6. Typed Contract（类型化契约）

模块输入与输出应优先采用：

> **Typed Contract（类型化契约）**

例如概念上：

```
Field
├── Name
├── Type
├── Required / Optional
├── Allowed Value
└── Semantic Meaning
```

类型可以包括：

```
string
integer
float
boolean
enum
list
structured object
nullable
```

对于固定语义集合应优先使用：

> Enum（枚举）

而不是任意字符串。

用户自然语言表达可以保留原始业务文本；

系统控制字段应使用稳定 Machine Value（机器值）。

设计层定义：

> Schema / Typed Contract（结构 / 类型化契约）

具体实现可以使用 Pydantic 等技术，但具体库不属于 Module Contract 本身。

------

# 7. Preconditions（前置条件）

Preconditions 定义：

> **模块开始处理之前，上游必须已经保证什么。**

例如可能包括：

- 输入结构合法
- 必需业务语义已经存在
- Authorization Context（授权上下文）已经建立
- 必要资源已经加载
- 上游解析阶段已经成功完成

Precondition 不应该由下游模块无限重复补偿。

原则：

> **Upstream guarantees become downstream assumptions.**

即：

> **上游已经承诺的事实，可以成为下游明确的前置条件。**

如果前置条件未满足，应按照 Failure Contract（失败契约）处理，而不是静默猜测或修复。

------

# 8. Processing Responsibilities（处理职责）

Processing Responsibilities 描述：

> **为了满足 Output Contract，模块必须完成哪些处理能力。**

描述：

- Required Capability（必需能力）
- Processing Rule（处理规则）
- Decision Rule（决策规则）
- Validation Responsibility（校验责任）

不描述：

- Class（类）
- Function（函数）
- 文件组织
- SDK 调用
- 具体算法代码

原则：

> **Describe behavior, not implementation.**

即：

> **描述行为，不规定实现。**

------

# 9. Output Contract（输出契约）

每个 Module 必须拥有明确的 Output Contract（输出契约）。

Output Contract 至少定义：

- Output Object（输出对象）
- Typed Schema（类型结构）
- Field Meaning（字段语义）
- Required / Optional（必需 / 可选）
- Success Semantics（成功语义）

原则：

> **模块只允许输出满足 Contract 的完整结果。**

禁止：

- 返回半完成对象
- 使用缺失关键字段的对象继续下游处理
- 使用未定义字段表达隐藏状态
- 通过自由文本代替正式结构结果

------

# 10. Postconditions / Invariants（后置条件 / 不变量）

Postconditions 定义：

> **模块成功返回时，哪些条件必须成立。**

可以包括：

### Completeness（完整性）

需要解决的信息已经完整解决。

### Consistency（一致性）

结果内部不存在冲突。

### Validity（合法性）

结果满足业务和系统规则。

### Connectivity（连通性）

涉及结构关系的结果具有合法连接关系。

### Authorization（授权）

结果没有超出允许的数据和业务范围。

具体 Module 根据自身职责选择需要保证的不变量。

原则：

> **Success means all required invariants hold.**

即：

> **只有所有必要不变量成立，才能视为模块成功。**

------

# 11. Validation Standard（校验标准）

Contract（契约）和 Runtime Validation（运行时校验）不是同一概念。

所有 Module：

> **必须拥有明确 Contract。**

但不要求所有内部边界重复执行完整 Runtime Schema Validation（运行时结构校验）。

------

## 11.1 Untrusted Boundary（不可信边界）

以下边界应进行严格 Validation（校验）：

- External API（外部接口）
- User Input（用户输入）
- LLM Output（大模型输出）
- File / JSON Resource（文件 / JSON 资源）
- External Service（外部服务）
- 其他不受当前进程直接控制的数据源

通常包括：

```
Raw Input
        ↓
Schema Validation
        ↓
Typed Object
```

------

## 11.2 Internal Trusted Boundary（内部受控边界）

已经满足 Typed Contract 的内部 Module 之间：

```
Typed Output
        ↓
Typed Input
```

不要求每层重复完整反序列化和 Schema Validation。

但仍必须保证：

- Preconditions
- Postconditions
- Invariants

并通过 Test / Evaluation 证明 Contract 成立。

原则：

> **Validate strongly at trust boundaries; preserve contracts internally.**

即：

> **不可信边界严格校验，内部边界依靠明确契约。**

------

# 12. Failure Contract（失败契约）

每个 Module 必须明确：

> **什么情况下不能产生合法 Output。**

典型 Failure Category（失败类别）包括：

### Invalid Input（非法输入）

Input Contract 或 Preconditions 未满足。

### Resolution Failure（解析失败）

模块应该能够完成任务，但无法唯一、完整或合法地解析结果。

### Dependency Failure（依赖失败）

外部依赖不可用、超时或返回非法结果。

### Unsupported（不支持）

请求本身超出当前系统明确支持的能力范围。

### Internal Failure（内部失败）

出现违反模块不变量的系统错误。

------

# 13. No Silent Degradation（禁止静默降级）

Module 不得：

```
发现关键问题
        ↓
忽略问题
        ↓
生成看似成功的结果
```

如果关键 Contract 无法满足：

> **Fail Explicitly（明确失败）。**

不得为了“让链路继续运行”产生不可靠结果。

原则：

> **Incorrect success is worse than explicit failure.**

即：

> **错误的成功比明确失败更危险。**

------

# 14. Clarification Boundary（澄清边界）

Clarification（用户澄清）属于 Feature Outcome（功能结果），不是普通 Module 自己直接与用户交互的行为。

只有负责 User Semantic Understanding（用户语义理解）的模块，可以报告：

- Missing Required Semantics（缺少必要语义）
- Semantic Ambiguity（语义歧义）

由 Feature 决定是否生成：

> Clarification（澄清）

一旦上游已经声明业务语义完整，后续 Module 原则上不得重新要求用户解决系统内部问题。

例如后续出现：

- Schema Mapping Failure（结构映射失败）
- Metric Resolution Failure（指标解析失败）
- Relationship Failure（关系失败）
- Join Resolution Failure（连接解析失败）

应进入：

```
Module Failure
        ↓
Feature Failure / Unsupported
        ↓
Bad Case Capture
        ↓
Root Cause Analysis
        ↓
Fix
        ↓
Regression
```

原则：

> **User clarifies business intent; the system resolves internal structure.**

即：

> **用户负责说明业务意图，系统负责解决内部结构。**

------

# 15. Failure vs Unsupported（失败与不支持）

必须区分：

### Unsupported（不支持）

系统设计上当前就没有能力完成该请求。

### Failure（失败）

系统设计上应该能够完成，但本次处理没有正确完成。

二者不得混淆。

Failure 应优先进入：

> Bad Case Loop（失败案例闭环）

用于后续修复和 Regression（回归）。

------

# 16. Dependencies（依赖）

每个 Module 必须声明自己依赖哪些能力。

依赖应优先表达为：

> **Capability / Port（能力 / 端口）**

而不是直接绑定具体技术产品。

例如概念上：

```
Model Capability
Retrieval Capability
Database Query Capability
Schema Catalog
Metric Catalog
Relationship Catalog
State Capability
```

Feature / Domain Module 不应因为需要某项能力直接绑定：

- 具体 LLM Provider
- Vector Database Vendor
- Database SDK
- Framework SDK

原则：

> **Depend on capability, not vendor.**

即：

> **依赖能力，不依赖供应商。**

具体 Adapter（适配器）由 Infrastructure（基础设施层）实现。

------

# 17. Infrastructure Growth Rule（基础设施生长规则）

Infrastructure（基础设施）由真实 Module Contract（模块契约）驱动。

采用：

```
Feature Requirement
        ↓
Module Contract
        ↓
Required Capability
        ↓
Port
        ↓
Infrastructure Adapter
```

不采用：

```
先建设大量通用基础设施
        ↓
再寻找业务使用场景
```

原则：

> **Infrastructure grows from real feature needs.**

即：

> **基础设施从真实功能需求中生长。**

------

# 18. Test / Evaluation Responsibility（测试与评估责任）

每个 Module Contract 必须能够被证明。

### Deterministic Module（确定性模块）

优先使用：

> TDD — Test-Driven Development（测试驱动开发）

验证：

- Input Contract
- Processing Rule
- Output Contract
- Boundary Condition
- Failure Contract
- Invariants

### AI / LLM / RAG Module（非确定性模块）

优先使用：

> Evaluation-Driven Development（评估驱动开发）

验证：

- Semantic Accuracy（语义准确性）
- Retrieval Quality（检索质量）
- Required Context Coverage（必要上下文覆盖）
- Failure / Bad Case
- Regression（回归）

Module 的 Test / Evaluation 必须围绕 Contract，而不是只验证代码可以运行。

------

# 19. Module Spec Template（模块规格模板）

所有正式 Module Spec 推荐统一采用以下结构：

```
# <Module Name>

## 1. Responsibility
模块负责什么。
模块明确不负责什么。

## 2. Input Contract
输入对象。
Typed Schema。
字段语义。
Required / Optional。

## 3. Preconditions
进入模块前必须成立的条件。

## 4. Processing Responsibilities
模块必须完成的处理能力和规则。

## 5. Output Contract
输出对象。
Typed Schema。
成功语义。

## 6. Postconditions / Invariants
成功结果必须满足的条件。

## 7. Failure Contract
Invalid Input。
Resolution Failure。
Dependency Failure。
Unsupported。
Internal Failure。

## 8. Dependencies
需要的 Domain / Application / Infrastructure Capability。

## 9. Test / Evaluation
证明 Contract 成立所需要的测试或评估。
```

Module 可以根据实际需要增加章节，但不得省略影响 Contract 的核心内容。

------

# 20. Change Rule（变更规则）

Module Contract 发生变化时，首先判断：

```
Business Meaning changed?
        ↓ Yes
Business Domain

Feature behavior changed?
        ↓ Yes
Feature Architecture / Spec

Only Module Contract changed?
        ↓ Yes
Module Spec

Implementation only?
        ↓
Code / Test
```

Module 实现不得自行反向修改：

- Business Meaning（业务含义）
- Feature Contract（功能契约）
- System Architecture（系统架构）

如果确实需要改变上层事实：

> **先修改上层设计，再修改 Module Contract 和实现。**

------

# 21. Module Design Baseline（模块设计基线）

ChatBI 所有 Module 长期遵循：

> **Clear Responsibility（职责清晰）。**

> **Typed Input / Output Contract（类型化输入输出契约）。**

> **Explicit Preconditions（明确前置条件）。**

> **Explicit Postconditions / Invariants（明确后置条件与不变量）。**

> **Explicit Failure（明确失败）。**

> **No Silent Degradation（禁止静默降级）。**

> **User Clarifies Intent, System Resolves Structure（用户澄清意图，系统解决结构）。**

> **Depend on Capability, Not Vendor（依赖能力，不依赖供应商）。**

> **Infrastructure Grows from Feature Needs（基础设施从功能需求中生长）。**

> **Contract First, Implementation Second（契约先行，实现随后）。**

最终原则：

> **模块先定职责和契约，再证明契约，最后实现契约。**


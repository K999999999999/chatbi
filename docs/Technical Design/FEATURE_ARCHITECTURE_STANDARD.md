# ChatBI Feature Architecture Standard（功能架构设计标准）

> **Status（状态）**：Engineering Baseline（工程基线）  
> **Scope（范围）**：ChatBI 所有 Feature（功能）的功能架构设计  
> **Engineering Reference（工程依据）**：`ENGINEERING.md`  
> **System Architecture Reference（系统架构依据）**：`ARCHITECTURE.md`  
> **Module Standard Reference（模块标准依据）**：`MODULE_CONTRACT_STANDARD.md`

---

# 1. Purpose（目的）

本文档定义 ChatBI 的统一 Feature Architecture Standard（功能架构设计标准）。

回答：

> 一个 Feature（功能）在进入 Feature Spec（功能规格）和 Module Spec（模块规格）之前，应该设计到什么程度？

Feature Architecture 的目标是建立：

> **Feature 的完整结构地图。**

使开发者能够明确：

- Feature 为什么存在
- Feature 从哪里开始、在哪里结束
- Feature 由哪些主要 Module（模块）组成
- 每个 Module 负责什么
- Module 之间如何协作
- Feature 的主要运行链路是什么
- Feature 依赖哪些外部能力
- 哪些内容明确不属于当前 Feature

原则：

> **Feature Architecture defines the structure of a feature, not the implementation of its modules.**

即：

> **功能架构定义功能结构，不定义模块实现。**

---

# 2. Design Position（设计位置）

ChatBI 的设计层级为：

```text
Product Requirement
（产品需求）
        ↓
Business Domain
（业务领域）
        ↓
System Architecture
（系统架构）
        ↓
Platform Integration
（平台集成）
        ↓
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
```

Feature Architecture 位于：

> **系统架构与详细功能规格之间。**

它负责把 System Capability（系统能力）进一步拆解为可以协作的 Feature Modules（功能模块）。

---

# 3. Core Question（核心问题）

Feature Architecture 必须能够回答：

```text
这个 Feature 为什么存在？
        ↓
它负责什么？
        ↓
它从哪里开始？
        ↓
它到哪里结束？
        ↓
需要哪些主要 Module？
        ↓
每个 Module 负责什么？
        ↓
Module 怎么协作？
        ↓
依赖哪些外部能力？
```

Feature Architecture 不回答：

```text
具体字段是什么？
类型是什么？
Class 怎么写？
Function 怎么写？
Prompt 怎么写？
算法怎么实现？
SDK 怎么调用？
```

---

# 4. Standard Feature Architecture（标准功能架构）

每个 Feature Architecture 至少定义以下七部分：

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
Module Responsibility
（模块职责）
        ↓
Major Input / Output
（主要输入 / 输出）
        ↓
Module Collaboration
（模块协作）
        ↓
External Capability Boundary
（外部能力边界）
```

必要时可以增加：

```text
Main Flow
（主流程）

Branch / Merge
（分支 / 汇合）

Online / Offline Boundary
（在线 / 离线边界）

Cross-Cutting Constraint
（横切约束）
```

但不得因为增加章节而进入 Module Spec 或 Implementation 级别。

---

# 5. Feature Responsibility（功能职责）

Feature Responsibility 定义：

> **这个 Feature 为什么存在。**

必须明确：

- Feature 解决什么业务问题
- Feature 提供什么核心能力
- Feature 最终产生什么类型的业务结果
- Feature 明确不负责什么

原则：

> **One feature owns one coherent business capability.**

即：

> **一个 Feature 承担一组完整且高度相关的业务能力。**

Feature 不应因为技术实现方便而承担其他 Feature 的职责。

---

# 6. Feature Boundary（功能边界）

Feature Boundary 定义：

> **这个 Feature 从哪里开始，到哪里结束。**

必须说明：

### Entry Boundary（入口边界）

Feature 接收什么概念级输入。

例如只需要描述：

```text
Natural Language Query Request
```

而不是立即定义具体字段。

---

### Exit Boundary（出口边界）

Feature 最终产生什么类型的结果。

例如：

```text
Query Result
Clarification
Unsupported
Failure
```

这里只定义结果类型和边界。

具体 Result Schema（结果结构）由 Feature Spec / Contract 定义。

---

### Out of Scope（不负责范围）

明确哪些能力：

> **不是当前 Feature 的责任。**

避免 Feature Boundary 随实现不断扩张。

---

# 7. Module Map（模块地图）

Feature Architecture 必须识别完成该 Feature 所需要的主要 Module。

Module Map 回答：

> **这个功能由哪些主要责任单元组成？**

例如概念结构：

```text
Feature
│
├── Module A
├── Module B
├── Module C
└── Module D
```

此阶段识别的是：

> **Logical Module（逻辑模块）。**

不是：

- Python Package
- 文件
- Class
- Function
- Service Instance

原则：

> **Architecture modules are responsibility boundaries before they are code boundaries.**

即：

> **架构中的模块首先是职责边界，然后才可能成为代码边界。**

---

# 8. Module Identification Rule（模块识别规则）

只有存在清晰独立责任时，才识别为 Module。

适合作为独立 Module 的能力通常满足至少一个条件：

- 拥有明确独立责任
- 拥有独立输入与输出概念
- 可以独立 Test / Evaluation
- 可以被替换而不改变整个 Feature
- 依赖独立的 Domain / Infrastructure Capability
- 内部复杂度值得建立清晰边界

不要因为：

> “以后可能有用”

提前拆 Module。

也不要因为：

> “现在代码很短”

把不同责任强行放进一个 Module。

原则：

> **Split by responsibility, not by code size.**

即：

> **按职责拆模块，不按代码长度拆模块。**

---

# 9. Module Responsibility（模块职责）

Feature Architecture 中，每个 Module 只需要定义：

```text
Module Name
        ↓
Responsibility
        ↓
Major Input
        ↓
Major Output
```

必要时增加：

```text
Not Responsible For
```

Module Responsibility 应能够用一句话说明：

> **这个 Module 负责解决什么问题。**

此阶段不定义详细：

- Typed Schema
- Required / Optional Field
- Preconditions
- Postconditions
- Failure Code
- Validation Rule
- Test Case

这些属于：

> `MODULE_CONTRACT_STANDARD.md`

约束的 Module Spec 阶段。

---

# 10. Major Input / Output（主要输入 / 输出）

Feature Architecture 应描述 Module 之间传递的：

> **Conceptual Data Object（概念数据对象）。**

例如：

```text
Semantic Query Intent
Resolved Schema Context
Resolved Metric Context
Generation Context
Candidate SQL
Query Result
```

此阶段回答：

> **传递的是什么信息。**

不回答：

> **这个对象里面具体有多少字段。**

因此可以写：

```text
Query Semantic Parser
        ↓
SemanticQueryIntent
```

但不需要在 Feature Architecture 中展开：

```text
metric_mentions: list[str]
time_range: ...
filters: ...
```

具体结构属于 Module Contract。

原则：

> **Architecture defines information flow; contracts define data shape.**

即：

> **架构定义信息如何流动，契约定义信息具体长什么样。**

---

# 11. Main Processing Flow（主要处理链路）

Feature Architecture 必须描述 Feature 的主要运行链路。

例如：

```text
Input
        ↓
Module A
        ↓
Module B
        ↓
Module C
        ↓
Result
```

如果存在独立能力，可以表达：

```text
             ┌→ Module B
Module A ────┤
             └→ Module C
                   ↓
                 Merge
```

Main Flow 用于说明：

- Processing Order（处理顺序）
- Dependency Order（依赖顺序）
- Parallel Capability（可并行能力）
- Branch（分支）
- Merge（汇合）

但：

> Feature Architecture 描述逻辑协作关系，不承诺具体并发实现。

例如架构上两项能力独立：

```text
A
├→ B
└→ C
```

不代表实现必须创建两个线程或两个进程。

---

# 12. Module Collaboration（模块协作）

Module Collaboration 定义：

> **模块为什么以及如何连接。**

必须明确：

- 上游 Module 产出什么概念结果
- 下游 Module 为什么需要该结果
- 哪些 Module 相互独立
- 哪些 Module 必须先后执行
- 哪些结果需要汇合
- 哪些 Module 之间禁止直接依赖

原则：

> **Modules collaborate through explicit information boundaries.**

即：

> **模块通过明确的信息边界协作。**

禁止依赖：

- 隐藏全局变量
- 隐式共享状态
- 未声明的内部数据
- 上一个 Module 的内部实现细节

---

# 13. Branch and Decision Boundary（分支与决策边界）

如果 Feature 存在重要业务分支，应在 Feature Architecture 中表达。

例如：

```text
Processing
        ↓
Decision
   ┌────┴────┐
   ↓         ↓
Path A     Path B
```

Feature Architecture 只定义：

> **为什么存在这个分支以及分支的业务意义。**

不定义：

- if / else 代码
- LangGraph Node
- Condition Function
- Prompt 分类实现
- Threshold 具体数值

这些属于后续设计和实现。

---

# 14. Clarification Boundary（澄清边界）

Clarification（澄清）属于：

> **Feature Outcome（功能结果）。**

Feature Architecture 可以表达：

```text
Semantic Understanding
        ↓
Missing / Ambiguous Business Intent
        ↓
Clarification
```

但不在此阶段定义：

- Clarification Schema
- 问句模板
- 提示词
- Failure Code
- UI 表现形式

原则：

> **User clarification exists only for unresolved user intent.**

即：

> **只有用户业务意图本身不完整或存在歧义时，才进入用户澄清。**

一旦用户业务意图已经被确认完整：

> 后续模块内部解析问题不应重新要求用户解决系统内部问题。

应进入 Failure / Unsupported / Bad Case 流程。

---

# 15. Failure Boundary（失败边界）

Feature Architecture 可以识别主要 Failure Boundary（失败边界）。

例如：

```text
Semantic Resolution Failure

Schema Resolution Failure

Metric Resolution Failure

External Dependency Failure

Execution Failure
```

但 Feature Architecture 不定义：

- Error Code
- Exception Class
- Retry Count
- HTTP Status
- 详细错误对象

这些属于 Feature Spec、Module Spec 或 Integration Contract。

Feature Architecture 只需要说明：

> **失败可能发生在哪个责任边界，以及失败不能被错误地当作成功继续传播。**

---

# 16. External Capability Boundary（外部能力边界）

Feature Architecture 必须识别当前 Feature 需要哪些外部 Capability（能力）。

例如概念上：

```text
Model Capability
Retrieval Capability
Schema Catalog
Metric Catalog
Relationship Catalog
Database Query Capability
State Capability
```

Feature Architecture 描述的是：

> **需要什么能力。**

不直接规定：

```text
DeepSeek
OpenAI
LangChain
Qdrant
BGE-M3
psycopg
Redis
```

具体技术由相应 Feature / Module / Infrastructure 决策确定。

原则：

> **Depend on capability before choosing implementation.**

即：

> **先确定需要什么能力，再选择怎么实现。**

---

# 17. Infrastructure Growth Rule（基础设施生长规则）

Feature Architecture 可以暴露 Infrastructure Requirement（基础设施需求），但不提前建设完整基础设施。

演进顺序：

```text
Feature Architecture
        ↓
Module Requirement
        ↓
Required Capability
        ↓
Module Contract
        ↓
Port / Adapter
        ↓
Infrastructure Implementation
```

原则：

> **Infrastructure grows from real feature requirements.**

即：

> **基础设施从真实功能需求中生长。**

禁止：

```text
先设计大量通用基础设施
        ↓
再寻找 Feature 使用方式
```

---

# 18. Online / Offline Boundary（在线 / 离线边界）

如果 Feature 同时依赖 Runtime Capability（运行时能力）和 Offline Preparation（离线准备），Feature Architecture 应明确两者边界。

例如：

```text
Offline
───────
Resource
↓
Index Build
↓
Derived Index


Online
──────
Request
↓
Retrieval
↓
Feature Processing
```

必须明确：

> Offline Artifact（离线产物）是 Derived Data（派生数据）还是 Source of Truth（事实源）。

避免运行时系统把索引、缓存或生成产物错误地当作业务事实来源。

---

# 19. Cross-Cutting Constraints（横切约束）

如果以下能力会直接影响 Feature Architecture，可以在架构级说明其边界：

- Authorization（授权）
- State（状态）
- Evidence（证据）
- Security（安全）
- Observability（可观测）
- Audit（审计）

Feature Architecture 只说明：

> **它们在哪些关键边界影响 Feature。**

不重新定义系统级规则。

系统级事实仍由：

```text
ARCHITECTURE.md
Platform Integration Spec
Business Domain Spec
```

负责。

---

# 20. Feature Architecture vs Feature Spec（功能架构与功能规格）

两者必须明确区分。

## Feature Architecture

回答：

> **这个功能由什么组成，以及这些部分怎样协作。**

主要关注：

```text
Boundary
Modules
Responsibilities
Flow
Collaboration
External Capabilities
```

---

## Feature Spec

回答：

> **这个功能对外到底必须做到什么。**

主要关注：

```text
Input
Output
Business Outcome
Clarification
Unsupported
Failure
State
Authorization
Evidence
Acceptance Criteria
```

原则：

> **Architecture defines structure; Spec defines behavior and acceptance.**

即：

> **架构定义结构，规格定义行为和验收。**

---

# 21. Feature Architecture vs Module Spec（功能架构与模块规格）

Feature Architecture 只需要知道：

```text
Module A
        ↓
Responsible for X
        ↓
Produces Y
```

Module Spec 才继续展开：

```text
Responsibility
Input Contract
Typed Schema
Preconditions
Processing Responsibilities
Output Contract
Postconditions / Invariants
Failure Contract
Dependencies
Test / Evaluation
```

原则：

> **Feature Architecture discovers modules; Module Spec constructs modules.**

即：

> **功能架构识别模块，模块规格施工模块。**

---

# 22. Detail Boundary（设计深度边界）

Feature Architecture 可以定义：

```text
Feature Responsibility

Feature Boundary

Module Name

Module Responsibility

Major Input

Major Output

Processing Order

Branch / Merge

External Capability

Online / Offline Boundary
```

Feature Architecture 不进入：

```text
Typed Schema 具体字段

Pydantic Model

Enum 具体值

Required / Optional 字段

Class

Function

File Structure

Prompt

SQL Algorithm

Retrieval Algorithm

Top-K

Threshold

Retry Count

SDK

Framework API

Exception Class

具体 Test Case
```

一旦讨论开始进入这些内容：

> **停止继续下钻，记录为后续 Feature Spec / Module Spec / Implementation Decision。**

---

# 23. Architecture Completeness Check（架构完整性检查）

Feature Architecture 在冻结之前，应确认：

### Responsibility

Feature 职责是否明确？

### Boundary

入口、出口和 Out of Scope 是否明确？

### Module Map

完成 Feature 所需要的主要 Module 是否已经识别？

### Responsibility Separation

Module 之间是否存在职责重复或职责空洞？

### Information Flow

主要输入输出和信息流是否完整？

### Collaboration

顺序、分支、并行、汇合关系是否明确？

### External Capability

需要的外部能力是否已经识别？

### Architecture Alignment

是否符合系统分层与 Dependency Rule（依赖规则）？

如果以上问题均能够清晰回答：

> Feature Architecture 可以进入 Freeze（冻结）。

---

# 24. Architecture Freeze Rule（功能架构冻结规则）

Feature Architecture Freeze（功能架构冻结）意味着：

> **Feature 的主要结构已经足够稳定，可以进入 Feature Spec 与 Module Spec。**

Freeze 不意味着：

- Module 已实现
- 数据结构已经最终定义
- 算法已经确定
- 技术栈已经全部选择
- 后续永远不能修改

Freeze 表示：

> **当前 Feature 的责任边界、主要模块和协作方式已经形成稳定基线。**

后续如果 Module Spec 发现局部实现问题：

> 优先在 Module 内解决。

只有当发现：

- Feature Boundary 错误
- Module Responsibility 错误
- 主要协作关系错误
- Feature Main Flow 本身错误

才返回修改 Feature Architecture。

---

# 25. Feature Architecture Template（功能架构模板）

所有正式 Feature `ARCHITECTURE.md` 推荐采用以下结构：

```markdown
# <Feature Name> Architecture

## 1. Purpose
这个 Feature 为什么存在。

## 2. Responsibility
负责什么。
明确不负责什么。

## 3. Feature Boundary
入口。
出口。
Out of Scope。

## 4. Module Map
主要 Module。
整体模块关系图。

## 5. Module Responsibilities
每个 Module：
- Responsibility
- Major Input
- Major Output
- Not Responsible For（必要时）

## 6. Main Processing Flow
Feature 主链路。
顺序。
分支。
并行。
汇合。

## 7. Module Collaboration
Module 之间如何协作。
主要信息如何传递。

## 8. External Capability Boundary
依赖哪些外部 Capability。
不绑定具体供应商实现。

## 9. Online / Offline Boundary
如存在离线准备和在线运行，明确两者边界。

## 10. Cross-Cutting Constraints
只记录真正影响 Feature Architecture 的授权、状态、安全等系统约束。

## 11. Failure / Clarification Boundary
说明主要责任边界。
不定义详细 Failure Contract。

## 12. Architecture Invariants
该 Feature 长期必须保持的关键结构规则。

## 13. Out of Scope
明确当前版本不处理的能力。

## 14. Open Questions
尚未冻结、需要后续决定的问题。
```

Feature 可以根据实际复杂度减少不必要章节。

不得为了满足模板而制造没有实际意义的内容。

---

# 26. Documentation Rule（文档规则）

Feature Architecture 文件统一放在对应 Feature 目录。

例如：

```text
Technical Design/
└── <Feature Name>/
    ├── ARCHITECTURE.md
    ├── SPEC.md
    └── Modules/
```

其中：

```text
ARCHITECTURE.md
→ Feature Structure（功能结构）

SPEC.md
→ Feature Contract / Acceptance（功能契约 / 验收）

Modules/
→ Module Specs（模块规格）
```

不同文档不得重复维护同一层级事实。

---

# 27. Change Rule（变更规则）

设计变化首先判断影响层级：

```text
Business Meaning changed?
        ↓ Yes
Business Domain

System Boundary changed?
        ↓ Yes
System Architecture

Feature Structure changed?
        ↓ Yes
Feature Architecture

Feature Behavior / Acceptance changed?
        ↓ Yes
Feature Spec

Module Contract changed?
        ↓ Yes
Module Spec

Implementation only?
        ↓
Code / Test / Evaluation
```

原则：

> **修改事实所属的最高正确层级。**

不得因为实现细节变化就修改 Feature Architecture。

---

# 28. Feature Architecture Baseline（功能架构基线）

ChatBI 所有 Feature Architecture 长期遵循：

> **Business Capability First（业务能力优先）。**

> **Clear Feature Boundary（功能边界清晰）。**

> **Module by Responsibility（按职责识别模块）。**

> **Architecture Before Contract Detail（先架构，后详细契约）。**

> **Explicit Information Flow（信息流明确）。**

> **Explicit Module Collaboration（模块协作明确）。**

> **Depend on Capability, Not Vendor（依赖能力，不依赖供应商）。**

> **Infrastructure Grows from Feature Needs（基础设施从功能需求生长）。**

> **Do Not Overdesign（不过度设计）。**

> **Do Not Enter Implementation Too Early（不过早进入实现）。**

最终原则：

> **先把整个 Feature 的模块地图和协作关系理清，再逐个模块进入规格与实现。**
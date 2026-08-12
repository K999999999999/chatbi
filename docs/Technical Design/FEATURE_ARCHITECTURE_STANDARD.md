# ChatBI Feature Architecture Standard

# ChatBI 功能架构设计标准

> **Status（状态）：** Engineering Baseline（工程基线）
> **Scope（范围）：** ChatBI 所有 Feature（功能）的 Feature Architecture（功能架构）设计
> **Engineering Reference（工程依据）：** `ENGINEERING.md`
> **System Architecture Reference（系统架构依据）：** `ARCHITECTURE.md`
> **Feature Spec Standard Reference（功能规格标准依据）：** `FEATURE_SPEC_STANDARD.md`
> **Module Standard Reference（模块标准依据）：** `MODULE_CONTRACT_STANDARD.md`

# 1. Purpose（目的）

本文档定义 ChatBI 统一的 Feature Architecture Standard（功能架构设计标准）。

Feature Architecture（功能架构）回答：

> **一个 Feature（功能）由什么组成，以及这些部分如何协作。**

目标是形成 Feature（功能）的稳定结构地图，使后续：

- Feature Spec（功能规格）；
- Module Spec（模块规格）；
- Test / Evaluation（测试 / 评估）；
- Implementation（实现）

能够在明确边界下继续展开。

核心原则：

> **Architecture defines structure, not implementation.**
> **架构定义结构，不定义实现。**

# 2. Design Position（设计位置）

ChatBI 设计层级：

```
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

Feature Architecture（功能架构）位于：

> **System Architecture（系统架构）之后，Feature Spec（功能规格）和 Module Spec（模块规格）之前。**

它负责把系统级 Capability（能力）拆解为：

> **职责清晰、可以协作的 Feature Module（功能模块）。**

# 3. Required Architecture Content（必须定义的架构内容）

每个正式 Feature Architecture（功能架构）必须至少定义以下七项。

```
1. Feature Responsibility
   （功能职责）

2. Feature Boundary
   （功能边界）

3. Module Map
   （模块地图）

4. Module Responsibility
   （模块职责）

5. Major Input / Output
   （主要输入 / 输出）

6. Module Collaboration
   （模块协作）

7. External Capability Boundary
   （外部能力边界）
```

如果这七项无法明确：

> Feature Architecture（功能架构）不得进入 Freeze（冻结）。

# 4. Feature Responsibility（功能职责）

必须明确：

- Feature（功能）解决什么业务问题；
- Feature（功能）提供什么核心业务能力；
- Feature（功能）最终产生什么类型的业务结果；
- Feature（功能）明确不负责什么。

原则：

> **One Feature owns one coherent business capability.**
> **一个 Feature（功能）承担一组完整且高度相关的业务能力。**

不得因为技术实现方便，把其他 Feature（功能）的职责合并进来。

# 5. Feature Boundary（功能边界）

Feature Boundary（功能边界）必须明确：

### Entry Boundary（入口边界）

Feature（功能）从什么概念级输入开始。

### Exit Boundary（出口边界）

Feature（功能）最终产生什么类型的结果。

### Out of Scope（范围外）

哪些能力明确不属于当前 Feature（功能）。

Feature Architecture（功能架构）只定义：

> **边界和概念级结果。**

不定义具体：

- API Field（接口字段）；
- Typed Schema（类型化结构）；
- HTTP Status（超文本传输协议状态码）；
- UI Model（界面模型）。

# 6. Module Map（模块地图）

Feature Architecture（功能架构）必须识别完成该 Feature（功能）所需要的主要 Logical Module（逻辑模块）。

Module（模块）首先是：

> **Responsibility Boundary（职责边界）。**

不是：

- Python Package（Python 包）；
- File（文件）；
- Class（类）；
- Function（函数）；
- Service Instance（服务实例）。

模块拆分原则：

> **Split by responsibility, not by code size.**
> **按职责拆模块，不按代码长度拆模块。**

只有存在独立责任时才建立 Module（模块）。

不得因为：

> “以后可能有用”

提前增加 Module（模块）。

# 7. Module Responsibility（模块职责）

Feature Architecture（功能架构）中，每个 Module（模块）只需要定义：

```
Module Name
（模块名称）

Responsibility
（职责）

Major Input
（主要输入）

Major Output
（主要输出）
```

必要时增加：

```
Not Responsible For
（明确不负责）
```

此阶段不定义：

- Typed Schema（类型化结构）；
- Required / Optional Field（必需 / 可选字段）；
- Preconditions（前置条件）；
- Failure Contract（失败契约）；
- Validation Rule（校验规则）；
- Test Case（测试用例）。

这些属于 Module Spec（模块规格）。

# 8. Major Input / Output（主要输入 / 输出）

Feature Architecture（功能架构）描述 Module（模块）之间传递的：

> **Conceptual Data Object（概念数据对象）。**

例如：

```
Semantic Query Intent
（语义查询意图）

Resolved Schema Context
（已解析结构上下文）

Resolved Metric Context
（已解析指标上下文）

Generation Context
（生成上下文）

Candidate SQL
（候选 SQL）

Query Result
（查询结果）
```

此阶段回答：

> **传递什么信息。**

不回答：

> **对象内部有哪些具体字段。**

原则：

> **Architecture defines information flow; contracts define data shape.**
> **架构定义信息流，契约定义数据结构。**

# 9. Module Collaboration（模块协作）

Feature Architecture（功能架构）必须明确主要 Module（模块）之间：

- Processing Order（处理顺序）；
- Dependency Order（依赖顺序）；
- Branch（分支）；
- Merge（汇合）；
- Logical Parallelism（逻辑并行）；
- 主要信息传递；
- 禁止的直接依赖。

模块之间必须通过：

> **Explicit Information Boundary（明确的信息边界）**

协作。

禁止依赖：

- Hidden Global State（隐藏全局状态）；
- Implicit Shared State（隐式共享状态）；
- 未声明的数据；
- 其他 Module（模块）的内部实现细节。

# 10. Main Processing Flow（主要处理链路）

每个复杂 Feature（功能）应提供一条主要处理链路。

例如概念上：

```
Input
（输入）
   ↓
Module A
（模块 A）
   ↓
Module B
（模块 B）
   ↓
Module C
（模块 C）
   ↓
Result
（结果）
```

如果存在逻辑并行：

```
             ┌→ Module B（模块 B）
Module A ────┤
             └→ Module C（模块 C）
                    ↓
                  Merge
                 （汇合）
```

Feature Architecture（功能架构）表达的是：

> **逻辑协作关系。**

不承诺具体：

- Thread（线程）；
- Process（进程）；
- Async Task（异步任务）；
- LangGraph Node（LangGraph 节点）。

# 11. External Capability Boundary（外部能力边界）

Feature Architecture（功能架构）必须声明需要哪些 External Capability（外部能力）。

例如：

- Model Capability（模型能力）；
- Semantic Retrieval Capability（语义检索能力）；
- Database Query Capability（数据库查询能力）；
- Authorization Capability（权限能力）；
- State Capability（状态能力）；
- Semantic Resource Capability（语义资源能力）。

Feature Architecture（功能架构）优先依赖：

> **Capability（能力）**

而不是：

> **Vendor / Framework（供应商 / 框架）。**

例如应写：

```
Semantic Retrieval Capability
（语义检索能力）
```

而不是直接要求：

```
Qdrant
BGE-M3
```

原则：

> **Depend on capability before choosing implementation.**
> **先确定需要什么能力，再决定如何实现。**

# 12. Optional Architecture Content（可选架构内容）

只有确实影响 Feature Structure（功能结构）时，才增加以下内容。

### Branch / Merge（分支 / 汇合）

存在重要业务分支或结果汇合时定义。

### Online / Offline Boundary（在线 / 离线边界）

Feature（功能）同时存在 Online Runtime（在线运行）与 Offline Preparation（离线准备）时定义。

必须区分：

- Source of Truth（事实源）；
- Derived Asset（派生资产）。

### Cross-Cutting Constraints（横切约束）

只有直接影响 Feature Structure（功能结构）时才记录：

- Authorization（权限）；
- State（状态）；
- Security（安全）；
- Evidence（证据）；
- Observability（可观测）；
- Audit（审计）。

不得重新定义已有系统级规则。

### Failure / Clarification Boundary（失败 / 澄清边界）

只定义主要责任边界。

不定义详细 Error Code（错误码）、Exception（异常）或 Retry（重试）。

### Architecture Invariants（架构不变量）

只记录少量长期必须保持的结构规则。

# 13. Clarification Boundary（澄清边界）

Clarification（澄清）属于：

> **Feature Outcome（功能结果）。**

只有：

> **用户业务意图本身缺失或存在歧义**

时，才允许进入 Clarification（澄清）。

一旦业务意图已经完整：

> 后续 Module（模块）内部的 Schema Resolution Failure（结构解析失败）、Metric Resolution Failure（指标解析失败）、Relationship Failure（关系失败）等，不得重新要求用户解决系统内部问题。

原则：

> **User clarifies business intent; system resolves internal structure.**
> **用户澄清业务意图，系统解决内部结构。**

# 14. Failure Boundary（失败边界）

Feature Architecture（功能架构）可以识别主要 Failure Boundary（失败边界），例如：

- Semantic Resolution Failure（语义解析失败）；
- Schema Resolution Failure（结构解析失败）；
- Metric Resolution Failure（指标解析失败）；
- Dependency Failure（依赖失败）；
- Execution Failure（执行失败）。

但不定义：

- Error Code（错误码）；
- Exception Class（异常类）；
- Retry Count（重试次数）；
- HTTP Status（超文本传输协议状态码）；
- 详细 Failure Object（失败对象）。

原则：

> **架构只定义失败发生在哪个职责边界，以及失败不能被当作成功继续传播。**

# 15. Online / Offline Boundary（在线 / 离线边界）

如果 Feature（功能）同时存在 Online Runtime（在线运行）和 Offline Preparation（离线准备），必须明确：

```
Authoritative Source
（权威来源）
        ↓
Offline Preparation
（离线准备）
        ↓
Derived Runtime Asset
（派生运行资产）
        ↓
Online Runtime
（在线运行）
```

必须明确：

> Derived Asset（派生资产）是否只是 Source of Truth（事实源）的 Materialized Copy（物化副本）。

不得让：

- Vector Index（向量索引）；
- Cache（缓存）；
- Generated Artifact（生成产物）

在架构中错误取代 Authoritative Source（权威来源）。

# 16. Detail Boundary（设计深度边界）

Feature Architecture（功能架构）可以定义：

```
Feature Responsibility
（功能职责）

Feature Boundary
（功能边界）

Module Map
（模块地图）

Module Responsibility
（模块职责）

Major Input / Output
（主要输入 / 输出）

Processing Order
（处理顺序）

Branch / Merge
（分支 / 汇合）

External Capability
（外部能力）

Online / Offline Boundary
（在线 / 离线边界）

Cross-Cutting Constraint
（横切约束）
```

Feature Architecture（功能架构）不得进入：

```
Typed Schema Fields
（类型化结构具体字段）

Pydantic Model
（Pydantic 数据模型）

Enum Value
（枚举具体值）

Required / Optional Field
（必需 / 可选字段）

Class
（类）

Function
（函数）

File Structure
（文件结构）

Prompt
（提示词）

SQL Algorithm
（SQL 算法）

Retrieval Algorithm
（检索算法）

Top-K
（前 K 个）

Threshold
（阈值）

Retry Count
（重试次数）

SDK API
（软件开发工具包接口）

Framework API
（框架接口）

Exception Class
（异常类）

Concrete Test Case
（具体测试用例）
```

出现以上内容时：

> **停止在 Feature Architecture（功能架构）继续下钻。**

将内容移动到正确层级：

- Feature Spec（功能规格）；
- Module Spec（模块规格）；
- Test / Evaluation（测试 / 评估）；
- Implementation（实现）。

# 17. Architecture Completeness Check（架构完整性检查）

Feature Architecture（功能架构）进入 Freeze（冻结）前，只检查以下核心项目。

### Responsibility（职责）

Feature（功能）负责什么、不负责什么是否明确？

### Boundary（边界）

Entry（入口）、Exit（出口）和 Out of Scope（范围外）是否明确？

### Module Map（模块地图）

主要 Module（模块）是否已经识别？

### Responsibility Separation（职责分离）

Module（模块）之间是否存在明显职责重复或职责空洞？

### Information Flow（信息流）

主要 Input / Output（输入 / 输出）是否明确？

### Collaboration（协作）

主要顺序、分支、并行和汇合是否明确？

### External Capability（外部能力）

需要的外部 Capability（能力）是否明确？

### Architecture Alignment（架构一致性）

是否符合 System Architecture（系统架构）和 Dependency Rule（依赖规则）？

以上均明确时：

> Feature Architecture（功能架构）可以 Freeze（冻结）。

# 18. Freeze Rule（冻结规则）

Feature Architecture Freeze（功能架构冻结）表示：

> **Feature（功能）的责任边界、主要模块和协作关系已经形成稳定设计基线。**

Freeze（冻结）不表示：

- Module（模块）已经实现；
- Typed Contract（类型化契约）已经最终完成；
- 算法已经确定；
- 技术栈已经全部选择；
- 后续永远不能修改。

后续 Module Spec（模块规格）发现局部问题：

> 优先在 Module（模块）内部解决。

只有发现以下问题时才返回修改 Feature Architecture（功能架构）：

- Feature Boundary（功能边界）错误；
- Module Responsibility（模块职责）错误；
- Module Map（模块地图）错误；
- Main Flow（主流程）错误；
- Module Collaboration（模块协作关系）错误。

# 19. Change Rule（变更规则）

发生设计变化时，修改事实所属的最高正确层级。

```
Business Meaning Changed?
（业务含义变化？）
        ↓ Yes
Business Domain
（业务领域）


System Boundary Changed?
（系统边界变化？）
        ↓ Yes
System Architecture
（系统架构）


Feature Structure Changed?
（功能结构变化？）
        ↓ Yes
Feature Architecture
（功能架构）


Feature Behavior Changed?
（功能行为变化？）
        ↓ Yes
Feature Spec
（功能规格）


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

原则：

> **修改事实所属的最高正确层级。**

不得因为 Implementation Detail（实现细节）变化就修改 Feature Architecture（功能架构）。

# 20. Documentation Rule（文档规则）

正式 Feature（功能）推荐目录：

```
Technical Design/
└── <Feature Name>/
    │
    ├── ARCHITECTURE.md
    │   （功能架构）
    │
    ├── FEATURE_SPEC.md
    │   （功能规格）
    │
    ├── ACCEPTANCE_AND_EVALUATION.md
    │   （验收与评估，如需要）
    │
    └── Modules/
        （模块规格）
```

职责：

```
ARCHITECTURE.md
→ Feature Structure
  （功能结构）

FEATURE_SPEC.md
→ Feature Behavior / Rules
  （功能行为 / 规则）

ACCEPTANCE_AND_EVALUATION.md
→ Verification / Acceptance
  （验证 / 验收）

Modules/
→ Module Contract
  （模块契约）
```

原则：

> **同一个设计事实只在最高正确层级维护一次。**

不得在多个文档重复维护同一事实。

# 21. Standard Feature Architecture Template（标准功能架构模板）

正式 Feature `ARCHITECTURE.md（功能架构）` 推荐使用以下模板。

```
# <Feature Name> Architecture
# <功能名称> 功能架构

> Status（状态）
> Version（版本）
> System Architecture Reference（系统架构引用）

## 1. Purpose（目的）
这个 Feature（功能）为什么存在。

## 2. Responsibility（职责）
负责什么。
明确不负责什么。

## 3. Feature Boundary（功能边界）
Entry Boundary（入口边界）。
Exit Boundary（出口边界）。
Out of Scope（范围外）。

## 4. Module Map（模块地图）
主要 Module（模块）。
整体关系图。

## 5. Module Responsibilities（模块职责）
每个 Module（模块）：
- Responsibility（职责）
- Major Input（主要输入）
- Major Output（主要输出）
- Not Responsible For（不负责，可选）

## 6. Main Processing Flow（主要处理链路）
主要顺序。
分支。
逻辑并行。
汇合。

## 7. Module Collaboration（模块协作）
主要信息如何传递。
模块之间主要依赖关系。
禁止的直接依赖。

## 8. External Capability Boundary（外部能力边界）
依赖哪些 Capability（能力）。
不绑定具体 Vendor / Framework（供应商 / 框架）。

## 9. Online / Offline Boundary（在线 / 离线边界）
仅在存在离线准备时定义。
明确 Source of Truth（事实源）与 Derived Asset（派生资产）。

## 10. Cross-Cutting Constraints（横切约束）
只记录真正影响架构的：
Authorization（权限）、
State（状态）、
Security（安全）等。

## 11. Failure / Clarification Boundary（失败 / 澄清边界）
定义主要责任边界。
不定义详细 Failure Contract（失败契约）。

## 12. Architecture Invariants（架构不变量）
少量长期必须保持的结构规则。

## 13. Open Questions（开放问题）
只记录尚未冻结且真正影响架构的问题。
```

不适用章节：

> **可以删除。**

不得为了 Template（模板）完整而制造无意义内容。

# 22. Standard Baseline（标准基线）

所有 ChatBI Feature Architecture（功能架构）长期遵循：

> **Business Capability First（业务能力优先）。**

> **Clear Feature Boundary（功能边界清晰）。**

> **Module by Responsibility（按职责拆模块）。**

> **Architecture Defines Structure（架构定义结构）。**

> **Contract Defines Data Shape（契约定义数据结构）。**

> **Explicit Information Flow（信息流明确）。**

> **Explicit Module Collaboration（模块协作明确）。**

> **Depend on Capability, Not Vendor（依赖能力，不依赖供应商）。**

> **Infrastructure Grows from Real Feature Needs（基础设施从真实功能需求中生长）。**

> **Do Not Overdesign（不过度设计）。**

> **Do Not Enter Implementation Too Early（不过早进入实现）。**

最终原则：

> **先把 Feature（功能）的责任边界、模块地图和协作关系设计清楚，再进入 Feature Spec（功能规格）、Module Spec（模块规格）和 Implementation（实现）。**
------

# ChatBI Engineering Guide

# ChatBI 工程设计与开发规范

> **Status（状态）：** Engineering Baseline（工程基线）
> **Scope（范围）：** ChatBI 设计、开发、测试、评估、集成与演进
> **Architecture Reference（架构引用）：** `ARCHITECTURE.md`
> **Architecture Decision Reference（架构决策引用）：** `ARCHITECTURE_DECISIONS.md`
> **Feature Architecture Standard（功能架构标准）：** `FEATURE_ARCHITECTURE_STANDARD.md`
> **Feature Spec Standard（功能规格标准）：** `FEATURE_SPEC_STANDARD.md`
> **Module Contract Standard（模块契约标准）：** `MODULE_CONTRACT_STANDARD.md`

------

# 1. Purpose（目的）

本文档定义 ChatBI 的 Engineering Method（工程方法）。

它回答：

> **一个业务需求如何从目标逐步变成可验证、可维护、可交付的实现。**

主要定义：

- Engineering Principle（工程原则）；
- Design / Implementation Flow（设计 / 实施流程）；
- Technology Baseline（技术基线）；
- Technology Decision Rule（技术决策规则）；
- Framework Policy（框架原则）；
- Contract First（契约优先）；
- Evolutionary Development（演进式开发）；
- Vertical Slice（垂直切片）；
- TDD（测试驱动开发）；
- EDD（评估驱动开发）；
- Implementation Workflow（实现流程）；
- Review（审查）；
- Integration / End-to-End Validation（集成 / 端到端验证）；
- Performance / Load Test（性能 / 负载测试）；
- CI/CD（持续集成 / 持续交付）；
- Documentation Governance（文档治理）。

本文档不重新定义：

- System Architecture（系统架构）；
- Feature Architecture（功能架构）；
- Feature Behavior（功能行为）；
- Module Contract（模块契约）；
- Business Metric（业务指标）；
- API Field（接口字段）；
- 具体算法实现。

这些事实由对应 Architecture / Spec / Standard（架构 / 规格 / 标准）维护。

核心原则：

> **Engineering defines how we build and prove the design.**
> **工程规范定义如何实现设计，以及如何证明实现满足设计。**

------

# 2. Core Engineering Principle（核心工程原则）

ChatBI 采用：

> **Architecture Backward, Implementation Forward.**
> **架构倒推，实施顺推。**

------

## 2.1 Design Backward（设计倒推）

设计从上层目标向下收敛：

```
Business Goal
（业务目标）

        ↓

Expected Business Result
（期望业务结果）

        ↓

Feature
（功能）

        ↓

Module
（模块）

        ↓

Contract
（契约）
```

设计阶段主要回答：

> **最终要做到什么，以及为了做到它需要哪些稳定边界。**

------

## 2.2 Implementation Forward（实施顺推）

真正实施从已经确定的 Contract（契约）开始：

```
Contract
（契约）

        ↓

Test / Evaluation
（测试 / 评估）

        ↓

Implementation
（实现）

        ↓

Integration
（集成）

        ↓

Validation
（验证）
```

核心关系：

> **上层定义目标与业务语义。**

> **Architecture（架构）定义结构和边界。**

> **Spec / Contract（规格 / 契约）定义必须满足的要求。**

> **Test / Evaluation（测试 / 评估）负责证明要求。**

> **Implementation（实现）负责满足要求。**

------

# 3. Design & Document Hierarchy（设计与文档层级）

稳定设计层级：

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

原则：

> **上层稳定，下层逐步具体化。**

不同层级不得互相替代。

------

## 3.1 Document Responsibility（文档职责）

工程流程只使用以下简单定位：

```
Product Requirement
（产品需求）
→ 为什么做、为谁做、目标是什么

Business Domain
（业务领域）
→ 业务事实是什么

ARCHITECTURE.md
（系统架构）
→ 系统如何组织

ARCHITECTURE_DECISIONS.md
（架构决策）
→ 为什么采用关键架构决定

Platform Integration Spec
（平台集成规格）
→ Platform 与 ChatBI 如何协作

Feature Architecture
（功能架构）
→ Feature 由什么组成、如何协作

Feature Spec
（功能规格）
→ Feature 必须表现出什么行为

Module Spec
（模块规格）
→ Module 必须满足什么 Contract

Test / Evaluation
（测试 / 评估）
→ 如何证明 Contract

Implementation
（实现）
→ 代码、配置和运行实现
```

具体文档结构：

> 使用对应 Standard（标准），不在本文件重复定义。

------

## 3.2 Implementation Task（实现任务）

Module Spec（模块规格）是：

> **长期设计契约。**

它不是一次开发任务的施工单。

具体 Codex / Developer（编码智能体 / 开发人员）任务可以从正式设计派生临时：

> **Implementation Task / Codex Work Order（实现任务 / Codex 施工单）。**

最小任务信息：

```
Task
（任务）

Sources of Truth
（事实源）

Scope
（范围）

Test / Evaluation
（测试 / 评估）

Constraints
（约束）

Done When
（完成条件）

Deliverables
（交付物）
```

Implementation Task（实现任务）：

> 不成为新的长期设计事实源。

------

# 4. Technology Baseline（技术基线）

System-Level Technology（系统级技术）统一。

Feature / Module Local Technology（功能 / 模块局部技术）：

> 根据真实需求选择。

原则：

> **System-wide technologies are standardized; feature-local technologies remain flexible.**
> **系统级技术统一，功能内部技术保持灵活。**

------

## 4.1 Language（开发语言）

统一使用：

> **Python 3.11**

正式版本约束由：

```
pyproject.toml
```

维护。

------

## 4.2 Dependency Management（依赖管理）

统一使用：

> **uv**

稳定关系：

```
pyproject.toml
        ↓
uv.lock
        ↓
.venv
```

其中：

- `pyproject.toml`：项目及 Direct Dependency（直接依赖）声明；
- `uv.lock`：冻结依赖解析结果；
- `.venv`：派生运行环境。

原则：

> **`.venv` 不是 Dependency Source of Truth（依赖事实源）。**

项目环境必须能够由：

```
pyproject.toml
+
uv.lock
```

重新生成。

------

## 4.3 API Contract（接口契约）

Platform ↔ ChatBI 的正式 Machine-Readable API Contract（机器可读接口契约）使用：

> **TypeSpec**

稳定关系：

```
TypeSpec Source
（TypeSpec 源）

        ↓

Compile / Emit
（编译 / 生成）

        ↓

OpenAPI
（开放接口规范）
```

其中：

> **TypeSpec 是正式 API Contract Source of Truth（接口契约事实源）。**

OpenAPI（开放接口规范）是：

> **Generated Artifact（生成产物）。**

不得通过直接修改 Generated OpenAPI（生成 OpenAPI）反向替代 TypeSpec。

------

## 4.4 Runtime Foundation（运行基础）

当前基础设施实现可以使用：

- Docker Compose（容器编排）；
- PostgreSQL；
- Qdrant。

这些属于：

> **Current Infrastructure Implementation（当前基础设施实现）。**

它们不是：

> Domain / Application Contract（领域 / 应用契约）。

具体产品可以替换，只要仍满足稳定 Port / Contract（端口 / 契约）。

------

# 5. Technology Decision Rule（技术决策规则）

技术决定按照影响范围分为：

```
System Level
（系统级）

        ↓

Feature Level
（功能级）

        ↓

Module Level
（模块级）
```

------

## 5.1 System-Level Decision（系统级技术决定）

影响整个项目，需要统一。

例如：

- Language（语言）；
- Dependency Management（依赖管理）；
- API Contract Technology（接口契约技术）；
- Project-Level Testing（项目级测试规则）；
- Type / Quality Rule（类型 / 质量规则）。

影响长期系统边界的重大变化：

> 应评估是否需要 Architecture Decision Record（架构决策记录）。

------

## 5.2 Feature-Level Decision（功能级技术决定）

只影响一个 Feature（功能）。

例如：

- Function Pipeline（函数管道）；
- LangGraph（图工作流）；
- Feature State Model（功能状态模型）；
- Feature Orchestration（功能编排）。

不同 Feature（功能）：

> 可以采用不同内部技术方案。

------

## 5.3 Module-Level Decision（模块级技术决定）

属于局部实现选择。

例如：

- Retrieval Algorithm（检索算法）；
- Ranking Algorithm（排序算法）；
- Parser Library（解析库）；
- Embedding Model（向量模型）；
- Vector Database（向量数据库）；
- 局部 Graph Algorithm（图算法）。

原则：

> **默认保持可替换。**

局部技术决定：

> 不因为使用某个框架自动升级为 System Architecture（系统架构）。

------

# 6. Framework Policy（框架原则）

ChatBI 不采用：

> **Framework-First Design（框架优先设计）。**

稳定关系：

```
Business Requirement
（业务需求）

        ↓

Feature / Module Contract
（功能 / 模块契约）

        ↓

Required Capability
（所需能力）

        ↓

Technology / Framework
（技术 / 框架）
```

不是：

```
Framework
（框架）

        ↓

强行塑造业务架构
```

------

## 6.1 LangChain（大模型应用框架）

LangChain 可以用于适合的 Feature / Module（功能 / 模块）。

但：

> **LangChain 不是 ChatBI Core（ChatBI 核心）的系统级强制依赖。**

是否使用：

> 由局部 Contract（契约）需求决定。

------

## 6.2 LangGraph（图工作流框架）

LangGraph 主要用于真实存在：

- Branch（分支）；
- Retry（重试）；
- State（状态）；
- Checkpoint（检查点）；
- Resume（恢复）；
- Human-in-the-Loop（人工介入）；
- Multi-Step Orchestration（多步骤编排）

的 Feature（功能）。

如果只是：

```
A
↓
B
↓
C
↓
D
```

简单顺序执行：

> **优先使用 Function Pipeline（函数管道）。**

原则：

> **不要为了使用 LangGraph 而创造 Graph（图）。**

------

## 6.3 Technology Adoption Rule（技术引入规则）

新增重要技术之前必须回答：

1. 它解决什么真实问题？
2. 问题属于 System / Feature / Module（系统 / 功能 / 模块）哪一级？
3. 当前简单方案为什么不足？
4. 是否改变现有 Architecture Boundary（架构边界）？
5. 是否产生不必要的 Framework / Vendor Lock-in（框架 / 供应商锁定）？
6. 是否可以隐藏在稳定 Contract（契约）之后？
7. 如何通过 Test / Evaluation（测试 / 评估）证明它确实带来收益？

最终原则：

> **Use the simplest technology that satisfies the contract.**
> **使用能够满足契约的最简单技术。**

------

# 7. Contract First（契约优先）

进入实现前必须先明确：

```
Responsibility
（职责）

Input
（输入）

Preconditions
（前置条件）

Processing Responsibility
（处理责任）

Output
（输出）

Invariants
（不变量）

Failure
（失败）

Dependencies
（依赖）

Test / Evaluation
（测试 / 评估）
```

完整 Module Contract（模块契约）：

> 遵循 `MODULE_CONTRACT_STANDARD.md`。

工程原则：

> **Contract defines what must be true.**
> **契约定义什么必须成立。**

Implementation（实现）：

> 可以变化。

Contract（契约）：

> 只有需求或设计事实变化时才变化。

------

# 8. Development Strategy（开发策略）

ChatBI 采用：

> **Architecture-Guided Evolutionary Development（架构指导下的演进式开发）。**

不采用：

- Big Bang Implementation（一次性大规模实现）；
- 无 Architecture Constraint（架构约束）的随意增量；
- 为未来可能需求提前建设大量空能力。

稳定方式：

```
Target Architecture
（目标架构）

        ↓

Walking Skeleton
（可运行骨架）

        ↓

Thin Vertical Slice
（薄垂直切片）

        ↓

Test / Evaluation
（测试 / 评估）

        ↓

Incremental Enhancement
（增量增强）
```

原则：

> **架构可以看到终点，实现只解决当前真实需求。**

------

# 9. Vertical Slice（垂直切片）

Feature（功能）应优先沿完整业务链进行增量建设。

每个 Increment（增量）尽量满足：

1. 从真实 Entry（入口）进入；
2. 经过真实 Feature Flow（功能链路）；
3. 调用真实 Module Boundary（模块边界）；
4. 经过必要 External Boundary（外部边界）；
5. 产生真实 Business Result（业务结果）；
6. 可以被 Test / Evaluation（测试 / 评估）验证。

优先：

```
真实入口
↓
真实主链
↓
最小必要模块
↓
真实结果
↓
验证
```

避免：

```
模块 A 做完
模块 B 做完
模块 C 做完
模块 D 做完

但没有任何真实业务链跑通
```

原则：

> **先跑通业务闭环，再横向增强能力。**

------

# 10. Verification-Driven Development（验证驱动开发）

不同类型能力使用不同 Proof Method（证明方式）。

```
Deterministic Software
（确定性软件）
→ TDD

AI / LLM / Retrieval
（AI / 大模型 / 检索）
→ EDD

Hybrid Module
（混合模块）
→ TDD + EDD
```

------

## 10.1 TDD — Test-Driven Development（测试驱动开发）

确定性能力采用：

```
Contract
（契约）

        ↓

Test
（测试）

        ↓

Red
（失败）

        ↓

Minimum Implementation
（最小实现）

        ↓

Green
（通过）

        ↓

Refactor
（重构）
```

适合：

- Deterministic Parser（确定性解析器）；
- Validator（校验器）；
- Relationship Graph（关系图）；
- Join Rule（连接规则）；
- SQL AST Validation（SQL 抽象语法树校验）；
- SQL Guard（SQL 安全防护）；
- Authorization Rule（授权规则）；
- Contract Mapping（契约映射）；
- 其他 Deterministic Business Rule（确定性业务规则）。

原则：

> **Test Code（测试代码）是正式工程资产。**

------

## 10.2 EDD — Evaluation-Driven Development（评估驱动开发）

AI / LLM / Retrieval（人工智能 / 大语言模型 / 检索）等非确定性能力采用：

```
Spec / Contract
（规格 / 契约）

        ↓

Evaluation Dataset
（评估数据集）

        ↓

Baseline
（基线）

        ↓

Implementation
（实现）

        ↓

Evaluation
（评估）

        ↓

Bad Case
（失败案例）

        ↓

Improvement
（改进）

        ↓

Regression Evaluation
（回归评估）
```

适合：

- Intent Recognition（意图识别）；
- Semantic Parsing（语义解析）；
- Retrieval（检索）；
- Schema Linking（包含非确定性检索时）；
- Metric Resolution（包含非确定性匹配时）；
- SQL Generation（SQL 生成）；
- Business Analysis（经营分析）；
- Result Synthesis（结果生成，如包含生成能力）。

原则：

> **没有 Evaluation（评估），就无法证明 AI 能力是否真的改进。**

------

# 11. Evaluation Principles（评估原则）

Evaluation（评估）回答：

> **非确定性能力和最终业务结果做得对不对。**

Test（测试）回答：

> **确定性行为是否满足 Contract（契约）。**

二者：

> 不互相替代。

具体 Feature-Level Acceptance Metric（功能级验收指标）：

> 由各 Feature 的 `ACCEPTANCE_AND_EVALUATION.md` 定义。

------

## 11.1 Retrieval（检索）

根据具体 Retrieval Contract（检索契约）关注：

- Recall（召回）；
- Precision（准确）；
- Ranking Quality（排序质量）；
- Required Context Coverage（必要上下文覆盖）。

这些默认属于：

> Diagnostic Metric（诊断指标）。

是否成为 Release Metric（发布指标）：

> 由 Feature Acceptance Spec（功能验收规格）决定。

------

## 11.2 Text2SQL（文本转 SQL）

业务正确性优先使用：

> **Execution Equivalence（执行等价）。**

不以：

> SQL Exact Match（SQL 文本完全匹配）

作为主要业务正确性判断方式。

------

## 11.3 Business Analysis（经营分析）

重点验证：

- Data Fact Correctness（数据事实正确）；
- Evidence Consistency（证据一致）；
- Analysis Chain Completeness（分析链完整）；
- Conclusion Support（结论有数据支持）。

具体指标和门禁：

> 由 Business Analysis（经营分析）的 Acceptance & Evaluation（验收与评估）定义。

------

# 12. Bad Case Loop（失败案例闭环）

有改进或回归价值的 Bad Case（失败案例）进入：

```
Failure
（失败）

        ↓

Capture
（记录）

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

Regression
（回归）
```

修复后的重要 Bad Case：

> 应沉淀为 Regression Asset（回归资产）。

例如：

- Test Case（测试用例）；
- Evaluation Case（评估案例）；
- Regression Case（回归案例）。

原则：

> **A fixed Bad Case becomes a Regression Case.**
> **修复后的失败案例进入回归。**

不是所有 Runtime Failure（运行时失败）：

> 都自动进入 AI Evaluation Dataset（人工智能评估数据集）。

只有具有：

- 可复现价值；
- 改进价值；
- 回归价值

的案例才进入正式质量资产。

------

# 13. Implementation Workflow（实现流程）

单个开发任务采用：

```
Read Sources of Truth
（读取事实源）

        ↓

Confirm Scope / Contract
（确认范围 / 契约）

        ↓

Write Test / Evaluation
（编写测试 / 评估）

        ↓

Implement Minimum Change
（实施最小改动）

        ↓

Run Test / Evaluation
（运行测试 / 评估）

        ↓

Review Diff
（审查差异）

        ↓

Refactor
（必要重构）

        ↓

Commit
（提交）
```

------

## 13.1 One Task, One Clear Goal（一次任务一个清晰目标）

一个开发任务：

> 尽量只解决一个明确问题。

避免：

- 顺手重构无关模块；
- 顺手升级无关框架；
- 顺手改变业务规则；
- 顺手扩大 Scope（范围）；
- 同一任务同时引入多个无法独立验证的重大变化。

原则：

> **Small Change, Clear Proof（小改动，明确证明）。**

------

## 13.2 Sources of Truth First（事实源优先）

实现前必须确认当前任务受到哪些正式文档约束。

例如：

```
System Architecture
（系统架构）

Feature Architecture
（功能架构）

Feature Spec
（功能规格）

Module Spec
（模块规格）

Test / Evaluation
（测试 / 评估）
```

Developer / Codex（开发人员 / 编码智能体）：

> 不得仅根据旧代码猜测当前设计意图。

如果 Code（代码）与最新正式 Spec（规格）冲突：

> 默认以正式 Source of Truth（事实源）为准。

------

# 14. Review Rule（审查规则）

实现完成后至少检查四个维度。

------

## 14.1 Architecture Alignment（架构对齐）

确认：

- 是否违反 Layer Dependency（分层依赖）；
- Domain（领域层）是否错误依赖 Infrastructure（基础设施层）；
- Application（应用层）是否直接依赖 Vendor SDK（供应商软件开发工具包）；
- Interfaces（接口层）是否绕过 Application（应用层）；
- Infrastructure（基础设施层）是否开始定义业务事实；
- 是否新增了没有真实需求的架构层。

------

## 14.2 Contract Alignment（契约对齐）

确认：

- Input（输入）是否符合 Contract（契约）；
- Preconditions（前置条件）是否满足；
- Output（输出）是否符合 Contract；
- Invariants（不变量）是否成立；
- Failure（失败）是否符合 Failure Contract（失败契约）；
- Dependency（依赖）是否符合设计边界。

------

## 14.3 Business Alignment（业务对齐）

确认：

- 是否改变 Business Meaning（业务含义）；
- 是否违反 Metric Definition（指标定义）；
- 是否改变 Authorization Meaning（授权含义）；
- 是否发生 Silent Semantic Change（静默语义修改）。

------

## 14.4 Proof Alignment（证明对齐）

确认：

- 确定性变化是否有对应 Test（测试）；
- AI / Retrieval（人工智能 / 检索）变化是否有 Evaluation（评估）；
- Bad Case Fix（失败案例修复）是否有 Regression（回归）；
- 测试是否真正证明对应 Contract（契约），而不是只证明代码没有报错。

------

# 15. Integration & End-to-End Validation（集成与端到端验证）

## 15.1 Integration Test（集成测试）

Module-Level Verification（模块级验证）完成后进行 Integration Test（集成测试）。

验证：

> **多个 Module（模块）协作后，Feature Contract（功能契约）是否仍然成立。**

重点检查：

- Input / Output Compatibility（输入 / 输出兼容）；
- Failure Propagation（失败传播）；
- Authorization（权限）；
- State Transfer（状态传递）；
- External Adapter（外部适配器）；
- Module Collaboration（模块协作）。

------

## 15.2 End-to-End Validation（端到端验证）

完整 Feature（功能）必须最终经过：

> **End-to-End Test / Evaluation（端到端测试 / 评估）。**

基本链路：

```
User Request
（用户请求）

        ↓

Real Feature Entry
（真实功能入口）

        ↓

Real Feature Flow
（真实功能链路）

        ↓

Required External Boundaries
（必要外部边界）

        ↓

Business Result
（业务结果）
```

原则：

> **不能仅依靠 Unit Test（单元测试）和 Mock（模拟）证明完整 Feature 可用。**

Mock（模拟）可以用于：

> 隔离测试。

但最终：

> 必须有足够真实的端到端证明。

------

# 16. Performance & Load Testing（性能与负载测试）

Business Correctness（业务正确性）达到要求后，根据真实 Non-Functional Requirement（非功能需求）进行：

- Performance Test（性能测试）；
- Load Test（负载测试）；
- Stress Test（压力测试）；
- 必要时 Soak Test（长时间稳定性测试）。

关注指标根据真实目标选择，包括：

- Throughput（吞吐量）；
- Concurrency（并发）；
- P50 / P95 / P99 Latency（延迟）；
- Error Rate（错误率）；
- Timeout Rate（超时率）；
- Resource Usage（资源使用）；
- External Dependency Bottleneck（外部依赖瓶颈）。

原则：

> **Performance Test（性能测试）服务于真实 Production Requirement（生产要求），不为了数字而测试。**

Production Readiness（生产就绪）性能验证：

> 应尽量在接近真实 Production（生产）的环境进行。

------

# 17. CI/CD（持续集成 / 持续交付）

代码进入主分支前，根据变更范围执行必要：

- Unit Test（单元测试）；
- Integration Test（集成测试）；
- Contract Test（契约测试）；
- Static Check（静态检查）；
- Relevant Evaluation（相关评估）。

稳定发布链：

```
Code
（代码）

        ↓

Review
（审查）

        ↓

CI
（持续集成）

        ↓

Build Artifact
（构建产物）

        ↓

Test / Evaluation
（测试 / 评估）

        ↓

Staging
（预生产）

        ↓

Production
（生产）
```

原则：

> **Build Once, Deploy Many（一次构建，多环境部署）。**

具体：

- Deployment Platform（部署平台）；
- Kubernetes（容器编排，如使用）；
- Environment Governance（环境治理）；
- Rollout（发布）；
- Infrastructure Scaling（基础设施扩缩容）

由 Platform / Deployment Infrastructure（平台 / 部署基础设施）负责。

ChatBI 负责：

> 自身业务质量门槛。

------

# 18. Documentation Governance（文档治理）

设计或实现变化时：

> **只修改真正受到影响的最高正确层级。**

判断流程：

```
Business Meaning Changed?
（业务含义变了吗？）

        ↓ Yes

Business Domain
（业务领域）


System Boundary Changed?
（系统边界变了吗？）

        ↓ Yes

ARCHITECTURE.md
（系统架构）


Architecture Decision Changed?
（关键架构决定变了吗？）

        ↓ Yes

ARCHITECTURE_DECISIONS.md
（架构决策）


Feature Structure Changed?
（功能结构变了吗？）

        ↓ Yes

Feature Architecture
（功能架构）


Feature Behavior Changed?
（功能行为变了吗？）

        ↓ Yes

Feature Spec
（功能规格）


Module Contract Changed?
（模块契约变了吗？）

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

不得因为：

> 某个 Class（类）改名

就修改 Architecture（架构）。

也不得因为：

> 代码实现困难

就静默修改上层 Contract（契约）。

------

## 18.1 No Duplicate Truth（禁止重复事实）

同一个稳定设计事实：

> 只在最高正确 Source of Truth（事实源）维护一次。

下层可以：

> Reference（引用）。

不应：

> Copy and Redefine（复制并重新定义）。

例如：

```
Business Metric Definition
（业务指标定义）
→ Domain Source

Feature Capability Boundary
（功能能力边界）
→ Feature Spec

Module Input / Output
（模块输入 / 输出）
→ Module Spec

Acceptance Metric
（验收指标）
→ Acceptance & Evaluation
```

其他文档只引用。

------

## 18.2 Discussion vs Formal Document（讨论与正式文档）

讨论阶段可以详细记录：

- Why（为什么）；
- Alternatives（备选方案）；
- Examples（例子）；
- Trade-Off（权衡）。

正式文档只保留：

> **当前有效的设计事实和必要规则。**

统一原则：

> **Discussion = Why + What + Alternatives（讨论 = 为什么 + 是什么 + 方案比较）。**

> **Formal Spec = Contract + Rules + Boundary（正式规格 = 契约 + 规则 + 边界）。**

重要 Architecture Why（架构原因）：

> 进入 ADR（架构决策记录）。

普通讨论过程：

> 不需要长期进入正式设计基线。

------

## 18.3 Standard Usage（标准使用）

已有 Standard（标准）包括：

- `FEATURE_ARCHITECTURE_STANDARD.md`
- `FEATURE_SPEC_STANDARD.md`
- `MODULE_CONTRACT_STANDARD.md`

写对应正式文档时：

> 直接遵循 Standard。

`ENGINEERING.md`：

> 不重复维护这些模板的完整定义。

------

# 19. Current State Documentation（当前状态文档）

`current_project_map.md` 用于描述：

> **当前项目真实实现了什么。**

它属于：

> Current State Documentation（当前状态文档）。

它不是：

> Architecture Source of Truth（架构事实源）。

稳定关系：

```
Target Design
（目标设计）

Architecture / Spec
（架构 / 规格）


Current Reality
（当前现实）

current_project_map.md
（当前项目地图）
```

两者可能在演进过程中暂时不同。

工程工作的重要任务之一就是：

> 让 Current Reality（当前实现）逐步满足 Target Design（目标设计）。

------

# 20. Source of Truth Rule（事实源规则）

设计事实总体遵循：

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

Architecture Decision / Integration Contract
（架构决策 / 集成契约）

        ↓

Feature Architecture
（功能架构）

        ↓

Feature Spec
（功能规格）

        ↓

Module Contract
（模块契约）

        ↓

Test / Evaluation
（测试 / 评估）

        ↓

Implementation
（实现）
```

这不是简单的“文件优先级冲突表”。

它表达的是：

> **设计事实从上层目标逐步具体化。**

原则：

> **下层不得无意中反向修改上层事实。**

如果 Implementation（实现）与正式 Spec（规格）冲突：

> 默认修正 Implementation。

如果确认上层设计需要变化：

```
先修改上层设计
        ↓
修改受影响的下层 Contract
        ↓
修改 Test / Evaluation
        ↓
修改 Implementation
```

不得：

```
代码已经这样写了
        ↓
所以规格也跟着改
```

------

# 21. Engineering Baseline（工程基线）

ChatBI 长期采用以下工程原则。

### Business First（业务优先）

> 先解决真实业务问题，再选择技术方案。

### Spec-Driven Development（规格驱动开发）

> 开发从正式设计事实开始，不从自由编码开始。

### Contract First（契约优先）

> 模块先定义承诺，再实现承诺。

### Architecture Backward, Implementation Forward（架构倒推，实施顺推）

> 设计从目标向下，实施从契约向前。

### Architecture-Guided Evolutionary Development（架构指导下的演进式开发）

> 架构明确方向，实现逐步演进。

### Vertical Slice First（垂直切片优先）

> 优先跑通真实业务闭环。

### TDD for Deterministic Software（确定性软件使用测试驱动开发）

> 确定性规则由 Test（测试）证明。

### EDD for AI / LLM / Retrieval（人工智能 / 大语言模型 / 检索使用评估驱动开发）

> 非确定性能力由 Evaluation（评估）衡量。

### Bad Case → Regression（失败案例转回归）

> 已修复的重要错误不得再次无保护地出现。

### System Technology Standardization, Feature Technology Flexibility（系统技术统一，功能技术灵活）

> 系统级技术保持一致，局部技术按真实 Contract（契约）选择。

### Framework Serves Contract（框架服务契约）

> 不使用 Framework-First Design（框架优先设计）。

### Stable Core, Replaceable Edge（稳定核心，可替换边缘）

> 供应商和基础设施实现可以变化，业务语义和核心 Contract（契约）保持稳定。

### No Overbuilding（不过度建设）

> 不为未来假设提前建设复杂基础设施。

### Small Change, Clear Proof（小改动，明确证明）

> 每次改动都应有清晰范围和验证证据。

最终原则：

> **架构倒推，契约先定，测试与评估证明，实施顺推。**

------


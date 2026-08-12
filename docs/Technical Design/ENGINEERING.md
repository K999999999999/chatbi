# ChatBI Engineering Guide（工程设计与开发规范）

> **Status（状态）**：Engineering Baseline（工程基线）  
> **Scope（范围）**：ChatBI 设计、开发、测试、评估与演进方法  
> **Architecture Reference（架构依据）**：`ARCHITECTURE.md`

---

# 1. Purpose（文档目的）

本文档定义 ChatBI 的 Engineering Method（工程方法）。

回答：

> 一个需求如何从业务目标逐步变成可验证、可维护、可交付的实现？

本文档定义：

- Design Hierarchy（设计层级）
- Document Responsibility（文档职责）
- Technology Baseline（技术基线）
- Contract First（契约优先）
- Development Strategy（开发策略）
- TDD（测试驱动开发）
- Evaluation-Driven Development（评估驱动开发）
- Implementation Workflow（实现流程）
- Review（审查）
- Integration / End-to-End Test（集成 / 端到端测试）
- Performance / Load Test（性能 / 压测）
- CI/CD（持续集成 / 持续交付）
- Documentation Governance（文档治理）

本文档不定义：

- System Architecture（系统架构）本身
- Feature（功能）具体流程
- Module（模块）具体实现
- API 具体字段
- 具体业务指标口径

---

# 2. Core Engineering Principle（核心工程原则）

ChatBI 采用：

> **Architecture Backward, Implementation Forward.**

即：

> **架构倒推，实施顺推。**

设计阶段：

```text
Goal
（目标）
        ↓
Expected Result
（期望结果）
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

实施阶段：

```text
Contract
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

核心原则：

> **上层定义目标和语义。**

> **边界定义契约。**

> **模块定义局部规格。**

> **测试与评估证明契约。**

> **实现满足契约。**

---

# 3. Design Hierarchy（设计层级）

完整设计层级：

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

各层职责不同，不得互相替代。

原则：

> **上层稳定，下层逐步具体化。**

---

# 4. Document Responsibilities（文档职责）

## 4.1 Product Requirement（产品需求）

定义：

> 产品需要解决什么问题。

主要包括：

- 用户
- 场景
- 目标
- 核心能力
- 业务结果
- 产品边界

---

## 4.2 Business Domain Spec（业务领域规格）

定义：

> 业务到底是什么意思。

主要包括：

- Business Object（业务对象）
- Grain（粒度）
- Metric（指标）
- Dimension（维度）
- Business Rule（业务规则）
- Business Meaning（业务含义）
- Domain Boundary（领域边界）

Business Domain（业务领域）是业务事实来源。

---

## 4.3 System Architecture（系统架构）

`ARCHITECTURE.md` 定义：

> 系统如何组织。

主要包括：

- System Positioning（系统定位）
- Responsibility Boundary（责任边界）
- Capability Boundary（能力边界）
- Technical Layering（技术分层）
- Dependency Rules（依赖规则）
- Architecture Invariants（架构不变量）

不展开 Feature（功能）内部流程。

---

## 4.4 Architecture Decision（架构决策）

`ARCHITECTURE_DECISIONS.md` 定义：

> 为什么采用当前关键架构选择。

用于记录真正影响：

- 系统边界
- 架构形态
- 依赖方向
- 状态所有权
- 关键技术战略

的重要决策。

普通实现选择不进入 Architecture Decision（架构决策）。

---

## 4.5 Platform Integration Spec（平台集成规格）

定义：

> Platform（平台）和 ChatBI 如何协作。

包括：

- Responsibility Boundary（责任边界）
- Authentication（身份认证）
- Authorization（授权）边界
- Conversation（会话）边界
- Domain State（领域状态）边界
- Run（执行）语义
- Result（结果）语义
- Error（错误）语义
- Streaming（流式）语义

正式 API Contract（接口契约）使用机器可读规范维护。

---

## 4.6 Feature Architecture（功能架构）

定义：

> 一个完整 Feature（功能）需要哪些主要能力，以及这些能力如何协作。

主要描述：

- Feature Boundary（功能边界）
- Major Capability（主要能力）
- Capability Relationship（能力关系）
- Main Processing Flow（主要处理链路）
- External Dependency Boundary（外部依赖边界）

不进入：

- Class（类）
- Function（函数）
- SDK
- 具体算法实现

---

## 4.7 Feature Spec（功能规格）

定义：

> 一个完整 Feature 必须做到什么。

主要包括：

- Goal（目标）
- Scope（范围）
- Input（输入）
- Output（输出）
- Main Flow（主流程）
- Business Outcome（业务结果）
- Clarification（澄清）
- Unsupported Request（不支持请求）
- Failure（失败）
- State（状态）
- Authorization（授权）
- Evidence（证据）
- Acceptance Criteria（验收标准）

Feature Spec 是：

> **Feature 的验收规格。**

---

## 4.8 Module Spec（模块规格）

定义单个 Module（模块）。

主要包括：

- Responsibility（职责）
- Boundary（边界）
- Input Contract（输入契约）
- Output Contract（输出契约）
- Preconditions（前置条件）
- Processing Rules（处理规则）
- Failure Contract（失败契约）
- Dependencies（依赖）
- Test / Evaluation Cases（测试 / 评估用例）

Module Spec 是：

> **模块施工规格。**

Module 不重新定义整个 Feature。

具体 Module Contract（模块契约）结构遵循：

> `MODULE_CONTRACT_STANDARD.md`

---

# 5. Technology Baseline（技术基线）

Technology Baseline（技术基线）统一影响整个项目的工程技术。

原则：

> **System-wide technologies are standardized; feature-local technologies remain flexible.**

即：

> **系统级技术统一，功能内部技术按需求选择。**

---

## 5.1 Current Baseline（当前基线）

### Language（开发语言）

统一使用：

> **Python 3.11**

Python 版本约束由：

```text
pyproject.toml
```

维护。

---

### Dependency Management（依赖管理）

统一使用：

> **uv**

稳定关系：

```text
pyproject.toml
        ↓
uv.lock
        ↓
.venv
```

其中：

- `pyproject.toml`：项目和 Direct Dependency（直接依赖）声明
- `uv.lock`：依赖锁定结果
- `.venv`：派生运行环境

原则：

> **`.venv` 不是依赖事实源。**

项目环境必须能够由：

```text
pyproject.toml + uv.lock
```

重新生成。

---

### API Contract（接口契约）

Platform ↔ ChatBI 正式机器可读 API Contract（接口契约）使用：

> **TypeSpec**

TypeSpec Source（TypeSpec 源文件）是正式契约事实源。

OpenAPI（开放接口规范）属于：

> **Generated Artifact（生成产物）**

不得手工修改 Generated OpenAPI（生成的 OpenAPI）代替 TypeSpec。

---

### Runtime Foundation（运行基础）

当前本地基础环境使用：

- Docker Compose（容器编排）
- PostgreSQL
- Qdrant

这些属于当前 Infrastructure Implementation（基础设施实现）。

具体基础设施产品可以替换，不得成为 Domain（领域层）和 Application（应用层）的直接技术依赖。

---

# 6. Technology Decision Rule（技术决策规则）

技术选择按影响范围分为三级：

```text
System Level
（系统级）
        ↓
Feature Level
（功能级）
        ↓
Module Level
（模块级）
```

## System Level（系统级）

影响整个项目，需要统一。

例如：

- Language（语言）
- Dependency Management（依赖管理）
- API Contract Technology（接口契约技术）
- 项目级测试、类型和代码质量规范

重要系统级技术变化需要评估：

> Architecture Decision Record（架构决策记录）

---

## Feature Level（功能级）

只影响一个 Feature（功能）。

例如：

- Function Pipeline（函数管道）
- LangGraph（图工作流）
- Feature State Model（功能状态模型）
- Feature Orchestration（功能编排）

不同 Feature 可以采用不同内部实现方式。

---

## Module Level（模块级）

属于局部实现选择。

例如：

- Retrieval Algorithm（检索算法）
- Ranking Algorithm（排序算法）
- Graph Algorithm（图算法）
- Parser Library（解析库）
- Embedding Model（向量模型）
- Vector Database（向量数据库）

默认保持可替换。

---

# 7. Framework Policy（框架原则）

ChatBI 不采用：

> **Framework-First Design（框架优先设计）。**

框架服务于 Feature / Module Contract（功能 / 模块契约），而不是反过来决定架构。

---

## LangChain

LangChain 可以用于适合的 Feature 或 Module。

但：

> **LangChain 不是 ChatBI Core（ChatBI 核心）的系统级强制依赖。**

---

## LangGraph

LangGraph 主要用于真实存在：

- Branch（分支）
- Retry（重试）
- State（状态）
- Checkpoint（检查点）
- Resume（恢复）
- Human-in-the-Loop（人工介入）
- Multi-step Orchestration（多步骤编排）

的 Feature。

没有这些真实需求时：

> **优先使用简单 Function Pipeline（函数管道）。**

---

## Technology Adoption（技术引入）

新增重要技术前必须确认：

1. 它解决什么真实问题。
2. 问题属于 System、Feature 还是 Module。
3. 当前简单方案为什么不足。
4. 是否破坏 Architecture Boundary（架构边界）。
5. 是否造成不必要的 Framework / Vendor Lock-in（框架 / 供应商锁定）。
6. 是否可以在现有 Contract（契约）后替换。

原则：

> **Use the simplest technology that satisfies the contract.**

即：

> **使用能够满足契约的最简单技术。**

---

# 8. Contract First（契约优先）

实现之前首先确认：

```text
Input
（输入）

Output
（输出）

Preconditions
（前置条件）

Boundary
（边界）

Failure
（失败）

Invariants
（不变量）
```

Contract（契约）定义：

> 模块或功能承诺什么。

Contract 不定义：

> 必须使用什么具体算法实现。

---

# 9. Development Strategy（开发策略）

ChatBI 采用：

> **Architecture-Guided Evolutionary Development（架构指导下的演进式开发）**

不采用：

- Big Bang Implementation（一次性大规模实现）
- 无架构约束的随意增量

演进方式：

```text
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

---

# 10. Vertical Slice（垂直切片）

Feature（功能）按照完整业务链逐步扩展。

每个 Increment（增量）应尽量：

1. 从真实入口进入。
2. 经过真实 Feature Pipeline（功能链路）。
3. 调用真实模块边界。
4. 产生真实业务结果。
5. 可以被 Test（测试）或 Evaluation（评估）验证。

避免：

> 先横向实现大量暂时没有真实业务链调用的模块。

优先：

> **Vertical Slice（垂直切片）。**

---

# 11. Deterministic Development（确定性能力开发）

确定性能力采用：

> **TDD — Test-Driven Development（测试驱动开发）**

流程：

```text
Contract
        ↓
Test
        ↓
Red
        ↓
Implementation
        ↓
Green
        ↓
Refactor
```

适用于：

- Deterministic Parser（确定性解析）
- Validator（校验）
- Relationship Graph（关系图）
- Join Resolver（连接解析）
- SQL AST Validation（SQL 抽象语法树校验）
- SQL Guard（SQL 安全防护）
- Authorization Rule（授权规则）
- Contract Mapping（契约映射）

原则：

> **Test Code（测试代码）属于正式工程资产。**

---

# 12. AI / LLM / RAG Development（AI 能力开发）

LLM（大语言模型）、RAG（检索增强）等非确定性能力采用：

> **Evaluation-Driven Development（评估驱动开发）**

流程：

```text
Spec
        ↓
Contract
        ↓
Evaluation Dataset
（评估数据集）
        ↓
Implementation
        ↓
Evaluation
        ↓
Bad Case
        ↓
Improvement
        ↓
Regression Evaluation
（回归评估）
```

适用于：

- Intent Recognition（意图识别）
- Semantic Parsing（语义解析）
- Retrieval（检索）
- SQL Generation（SQL 生成）
- Business Analysis（经营分析）
- Result Synthesis（结果生成）

---

# 13. Evaluation Principle（评估原则）

Evaluation（评估）回答：

> **业务结果是否正确。**

Test（测试）更多回答：

> **确定性行为是否满足契约。**

二者不能互相替代。

---

## Retrieval（检索）

主要关注：

- Recall（召回率）
- Precision（准确率）
- Top-K Accuracy（前 K 准确率）
- Required Context Coverage（必要上下文覆盖）

---

## Text2SQL（文本转 SQL）

优先关注：

> **Execution Accuracy（执行准确率）**

而不是只比较 SQL 文本是否完全一致。

---

## Business Analysis（经营分析）

重点验证：

- 数据事实正确
- Evidence（证据）一致
- 分析链完整
- 结论有数据支持

---

# 14. Bad Case Loop（失败案例闭环）

Bad Case（失败案例）进入持续改进闭环：

```text
Failure
        ↓
Capture
        ↓
Classification
        ↓
Root Cause
        ↓
Fix
        ↓
Regression
```

修复后的 Bad Case 应尽量沉淀为：

- Test Case（测试用例）
- Evaluation Case（评估用例）
- Regression Case（回归用例）

原则：

> **同一个已知错误不应重复出现。**

---

# 15. Implementation Workflow（实现流程）

单个开发任务采用：

```text
Read Spec
        ↓
Confirm Contract
        ↓
Write Test / Evaluation Case
        ↓
Implement Minimum Change
        ↓
Run Test / Evaluation
        ↓
Review Diff
        ↓
Refactor
        ↓
Commit
```

一次任务尽量只解决一个清晰问题。

原则：

> **Small Change, Clear Proof（小改动，明确证明）。**

---

# 16. Review Rule（审查规则）

实现完成后至少检查三个维度。

## Architecture Alignment（架构对齐）

确认：

- 是否违反层级依赖
- Domain 是否依赖 Infrastructure
- Application 是否直接依赖供应商实现
- Interfaces 是否绕过 Application
- Infrastructure 是否定义业务事实

---

## Contract Alignment（契约对齐）

确认：

- Input 是否符合 Contract
- Output 是否符合 Contract
- Failure 是否符合 Contract
- Boundary 是否符合 Spec

---

## Business Alignment（业务对齐）

确认：

- 是否改变 Business Meaning（业务含义）
- 是否违反 Metric（指标）口径
- 是否违反 Domain Authorization（领域授权）

---

# 17. Integration Test（集成测试）

Module Test（模块测试）通过后进行：

> **Integration Test（集成测试）**

验证：

> 多个模块协作后，Feature Contract（功能契约）是否仍然成立。

重点检查：

- 模块输入输出兼容
- 错误传播正确
- Authorization（授权）正确
- State（状态）传递正确
- 外部 Adapter（适配器）连接正确

---

# 18. End-to-End Validation（端到端验证）

完整 Feature（功能）必须进行：

> **End-to-End Test / Evaluation（端到端测试 / 评估）**

链路：

```text
User Request
        ↓
Real Feature Pipeline
        ↓
Real External Boundary
        ↓
Business Result
```

不得只依赖 Mock（模拟）证明完整生产链路正确。

---

# 19. Performance & Load Testing（性能与压测）

功能正确之后，根据真实性能目标进行：

- Performance Test（性能测试）
- Load Test（负载测试）
- Stress Test（压力测试）
- 必要时进行 Soak Test（长时间稳定性测试）

主要关注：

- Throughput（吞吐量）
- Concurrency（并发）
- P50 / P95 / P99 Latency（延迟）
- Error Rate（错误率）
- Timeout Rate（超时率）
- Resource Usage（资源使用）
- External Dependency Bottleneck（外部依赖瓶颈）

Performance / Load Test（性能 / 压测）属于：

> **Production Readiness（生产就绪验证）**

应尽量在接近 Production（生产）的环境中执行。

---

# 20. CI/CD（持续集成 / 持续交付）

代码进入主分支前，根据变更范围至少执行：

- Unit Test（单元测试）
- Integration Test（集成测试）
- Contract Test（契约测试）
- Static Check（静态检查）
- Relevant Evaluation（相关评估）

稳定发布链：

```text
Code
        ↓
Review
        ↓
CI
        ↓
Build Artifact
（构建产物）
        ↓
Test
        ↓
Staging
（预生产）
        ↓
Production
（生产）
```

原则：

> **Build Once, Deploy Many（一次构建，多环境部署）。**

Platform（平台）或 Deployment Infrastructure（部署基础设施）负责具体发布和运行环境治理。

ChatBI 负责定义自身质量门槛。

---

# 21. Documentation Flow（文档演进）

设计变化首先判断影响层级：

```text
Business Meaning changed?
        ↓ Yes
Business Domain

System boundary changed?
        ↓ Yes
ARCHITECTURE.md

Architecture decision changed?
        ↓ Yes
ARCHITECTURE_DECISIONS.md

Feature architecture / behavior changed?
        ↓ Yes
Feature Architecture / Spec

Module contract changed?
        ↓ Yes
Module Spec

Implementation only?
        ↓
Code / Test / Evaluation
```

原则：

> **只更新真正受到影响的文档。**

---

# 22. Current State Documentation（当前状态文档）

`current_project_map.md` 用于描述：

> **当前项目真实存在什么。**

它是 Current State（当前状态）审计文档。

不是：

> Architecture Source of Truth（架构事实源）。

Current Project Map（当前项目地图）应尽量保持全局视野，不因为设计文档分层而机械拆散。

---

# 23. Source of Truth Hierarchy（事实源层级）

稳定顺序：

```text
Product Requirement
        ↓
Business Domain
        ↓
System Architecture
        ↓
Architecture Decision
        ↓
Integration Contract
        ↓
Feature Architecture / Contract
        ↓
Module Contract
        ↓
Test / Evaluation
        ↓
Implementation
```

原则：

> **下层不得无意中反向修改上层事实。**

如果 Implementation（实现）与上层 Spec（规格）冲突：

> 默认修正 Implementation。

如果确认上层设计本身需要变化：

> 先修改对应上层设计，再实施代码变更。

---

# 24. Engineering Baseline（工程基线）

ChatBI 长期采用：

> **Business First（业务优先）。**

> **Spec-Driven Development（规格驱动开发）。**

> **Contract First（契约优先）。**

> **Architecture Backward, Implementation Forward（架构倒推，实施顺推）。**

> **Architecture-Guided Evolutionary Development（架构指导下的演进式开发）。**

> **Vertical Slice（垂直切片）优先。**

> **TDD（测试驱动开发）for Deterministic Software（确定性软件）。**

> **Evaluation-Driven Development（评估驱动开发）for AI / LLM / RAG（AI / 大模型 / 检索增强能力）。**

> **Bad Case → Regression（失败案例转回归）。**

> **System Technology Standardization, Feature Technology Flexibility（系统技术统一，功能技术灵活）。**

> **Use the simplest technology that satisfies the contract（使用满足契约的最简单技术）。**

最终原则：

> **架构倒推，契约先定，测试先行，实施顺推。**

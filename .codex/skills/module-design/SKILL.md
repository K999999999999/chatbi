---
name: module-design
description: "为已完成 Module Spec 的指定模块生成基于正式契约与真实仓库的 Implementation Design（模块实现设计），适用于需要确定代码落位、Typed Contract、Port/Adapter、Failure、测试和文件计划的设计任务；必须先经过人工确认，不负责重写 Spec 或编码。"
---

# 模块设计

## 定位与边界

将本 Skill 用于以下流程中的唯一阶段：

```text
Feature Architecture
        ↓
Feature Spec
        ↓
Module Spec
        ↓
【模块设计】
        ↓
Implementation Design
        ↓
设计审查
        ↓
人工批准
        ↓
TDD / Implementation
```

Module Spec 回答“模块必须做到什么”；本 Skill 只回答“在当前真实项目里准备怎么实现”。不得重新定义、扩大、修订或替代 Module Contract，也不得把 Legacy Code（遗留代码）当成正式 Contract 的事实源。

本 Skill 的硬性终点是设计审查前：

- 只做只读上下文检查和 Implementation Design。
- 不写生产代码，不创建实现文件，不写测试代码。
- 不安装依赖，不修改数据库，不启动或修改外部服务，不提交 Git。
- 正式设计输出后立即停止，并等待进入「设计审查」；不得要求用户直接开始编码。

## Source of Truth（事实源）

按以下优先级判断事实和冲突：

1. 当前 Task 指定的正式 Module Spec、所属 Feature Spec、Feature Architecture、Domain / Acceptance 规则。
2. 系统 `ARCHITECTURE.md`、`ARCHITECTURE_DECISIONS.md`、`ENGINEERING.md` 以及项目级设计标准。
3. 当前真实 `src/`、`tests/`、`pyproject.toml` 和直接相关配置、资源、依赖。
4. Legacy Code、旧 Metadata、Derived Artifact（派生产物）只能作为现状证据，不能反向修改已经确认的正式设计。

若正式设计与实现不一致，在正式输出的“当前仓库现状”中明确标记 `Legacy / Conflict`，不要未经要求顺手重构或删除无关代码。若冲突阻止安全设计，结论使用 `BLOCKED`。

## 两阶段门禁

### 状态判断

每次使用本 Skill 时，先检查当前对话是否已经完成本 Skill 的 Phase 1，并且用户是否在 Phase 1 之后明确批准了同一个模块和范围。

- 初次指定模块、尚未输出确认信息，或用户改变了模块 / 范围：执行 Phase 1。
- Phase 1 确认信息刚刚发出：立即结束当前回合，不继续读取、设计或输出方案。
- 只有用户在 Phase 1 之后回复“确认”或语义明确等价的批准（如“可以”“没问题”“按这个设计”“继续设计”）时，才执行 Phase 2。
- 原始请求中附带的“确认”不算门禁批准；必须先发 Phase 1，再等待后续回复。
- 回复含糊、提出疑问或修改范围时，不进入 Phase 2；先重新整理并发送一次简短 Phase 1。

### Phase 1：设计前确认

用户指定 Module 后，先只读读取必要上下文，不开始正式设计：

1. 解析并读取当前 Module Spec，确认其 Feature、输入、输出、前置条件、处理职责、后置条件、不变量、Failure Contract、依赖、Test / Evaluation 以及明确的 Out of Scope。
2. 跟随 Module Spec 的引用读取所属 Feature Architecture、Feature Spec、Acceptance & Evaluation；必要时只读取直接上游 / 下游 Module Spec 来确认边界。
3. 读取系统级 `ENGINEERING.md`、`ARCHITECTURE.md`、`ARCHITECTURE_DECISIONS.md` 和直接相关项目设计标准。当前仓库的常见位置包括：
   - `docs/Technical Design/ENGINEERING.md`
   - `docs/Technical Design/ARCHITECTURE.md`
   - `docs/Technical Design/ARCHITECTURE_DECISIONS.md`
   - `docs/Technical Design/FEATURE_ARCHITECTURE_STANDARD.md`
   - `docs/Technical Design/MODULE_CONTRACT_STANDARD.md`
4. 检查真实 `src/`、`tests/`、`pyproject.toml`，再按正式类型名、能力名和模块名定位直接相关代码、测试、资源、配置和依赖。不要假设目录、Python 版本、Port、Failure Model、Bootstrap 或第三方库已经存在。
5. 在确认信息中只概括模块位置、拟设计范围和明确不做的范围。使用 `rg` / `rg --files` 优先定位文件；中文文件按 UTF-8 读取；保留用户已有工作区修改。

如果找不到唯一 Module Spec、正式上下文缺失或模块范围无法安全判断，停止并简短说明缺失信息，不得猜测或伪造确认内容。

Phase 1 的最终响应只能保持以下格式和简短程度，不得附加完整文件树、接口、类、测试用例、技术解释或 Implementation Task：

```text
【模块设计确认】

模块：
<模块名称>

模块位置：
<用 1～3 行说明它位于哪个 Feature、上游是什么、下游是什么>

本次设计：
<用 3～6 行简要说明准备设计代码落层、Typed Contract、Port/Adapter、
核心职责拆分、Failure、测试和文件计划等内容>

明确不做：
<用 1～3 行说明本轮不会涉及的上下游模块或范围>

如果以上理解正确，请回复：确认
```

发送该信息后必须停止执行，等待人工回复。

### Phase 2：正式模块设计

仅在人工确认后继续。设计必须同时满足：

```text
Formal Contract
+
Engineering Rules
+
Repository Reality
```

先建立简短的证据边界：已确认事实、Repository Reality、Legacy / Conflict、假设、待确认决定和 Acceptance。将“实现怎么做”与“契约必须是什么”分开；发现 Contract 尚未冻结时，不擅自替它做产品或架构决策。

## Implementation Design 规则

### Minimum Sufficient Design（最小充分设计）

只为当前 Module Contract 增加必要的文件、类型、函数、类、Service、Port、Adapter、Repository、Factory、Utility 和第三方依赖。每个设计元素必须能回答“它满足 Module Spec 的哪一项 Input / Output / Preconditions / Processing Responsibility / Postcondition / Invariant / Failure / Dependency / Test Contract”；不能对应真实责任的元素默认不增加。

继承已经冻结的 System-Level Technology，不重新讨论开发语言、依赖管理、系统分层或项目级工程规则。只有当前模块确有局部选择时才列 `Module-Level Technology Decision`，例如 Parser Library、Embedding Model、Vector Database Adapter、局部算法或 Serialization Technology。

遵循以下选择顺序：

```text
需要什么能力
        →
选择什么局部实现
        →
为什么满足当前 Contract
        →
如何限制在 Infrastructure 或局部边界内
```

普通 Python 足够时使用普通 Python；简单的 A → B → C 顺序不得为了使用 LangChain / LangGraph / 其他 Framework 而引入 Graph、Agent 或额外编排。禁止因为“以后可能需要”“更企业级”“保持目录对称”或“框架已经安装”而过度设计。

### Layered Architecture with Ports（带端口的分层架构）

保持项目依赖方向：

```text
Interfaces
    ↓
Application
    ↓
Domain

Application
    ↓
Port / Contract
    ↑ implements
Infrastructure
```

按以下边界落位：

- `Interfaces` 只承接外部交互和适配，不拥有业务事实。
- `Application` 编排用例、边界校验和依赖 Port，不直接绑定 Vendor SDK。
- `Domain` 表达稳定业务规则、Typed Contract 和不变量，不依赖 Infrastructure、Database 或 Platform SDK。
- `Infrastructure` 实现外部技术能力 Adapter，不定义业务真相，不污染稳定 Contract。
- `Bootstrap` 只负责配置和依赖装配，不承载业务逻辑。

只有正式 Contract 需要外部能力时才新增 Port / Capability；如果当前模块是纯确定性处理且已有类型足够，明确写“不需要新增”。

### Contract First 与 Typed Contract

将 Module Spec 中已经稳定的 Input、Output、Enum、Identity、Metadata、Failure 和 Structured Object 合理映射为 Python Typed Contract，并优先复用项目中已有且语义相同的类型。不得用无约束自由 `dict` 代替正式 Contract，也不得重复创建同义 Type。

在不可信边界执行 Runtime Validation：JSON、文件、外部服务响应、LLM Output 和第三方 SDK 返回值都必须在进入稳定 Contract 前验证。模块间已经形成 Typed Contract 的内部边界不重复进行完整序列化 / Schema Validation，但仍遵守类型和不变量。

设计中说明每个重要类型的归属、复用关系、构造边界和验证时机；不输出完整生产代码。

### Failure Contract（失败契约）

严格按 Module Spec 已定义的 Failure Contract 落地，并说明：

- Failure 在哪个边界产生。
- 使用现有 Failure Model 还是确有必要新增类型。
- Application、Domain、Port 和 Adapter 如何传播或映射。
- 必须保留哪些模块、输入、依赖和诊断 Context。
- 哪些失败属于输入 / 前置条件、Contract Violation、Dependency Failure 或 Unsupported Capability（仅在正式契约有定义时区分）。

遵循 `Fail Closed`：不得吞掉错误、静默降级、猜测修复 Contract Violation、忽略坏记录或把部分成功伪装成完整成功。任何新增错误类型都必须有明确 Contract 对应关系。

### Test / Evaluation 设计

从 Contract 推导测试，不从拟议代码反推测试。至少覆盖适用的 Happy Path、Preconditions、Input Validation、Postconditions、Invariants、Failure Contract、Dependency Failure 和 Module Acceptance Requirements；不提前加入当前模块不需要的测试层级。

区分以下证据：

- `Unit / Deterministic Test`：纯规则、类型、不变量和失败映射。
- `Capability Contract Test`：Port 与外部能力的契约行为。
- `Integration Test`：真实模块边界和必要的装配链路。
- `Evaluation`：Acceptance 文档要求的业务 / 检索 / AI 质量证据。

在正式输出中逐项关联“测试目标 → 对应 Contract → 测试层级”，并标出哪些测试属于当前设计、哪些属于上游 / 下游集成，不把 Feature-Level Evaluation 误写成单元测试。

## Phase 2 正式输出格式

人工确认后，使用以下结构输出清晰、可审查的设计。只列与当前模块直接相关的内容，不为模板填充无关信息。

### 1. 模块定位

- `Module`
- `Feature`
- 输入
- 输出
- 上游
- 下游

### 2. 当前仓库现状

只说明直接相关的已有结构、能力、类型、测试以及 `Legacy / Conflict`。路径和能力必须来自真实仓库检查。

### 3. 实现方案

用简洁流程表达：

```text
Input
  ↓
核心处理
  ↓
Output
```

说明各层主要职责、边界验证和依赖方向。

### 4. 分层落位

使用表格，仅列真正需要的组件：

| 组件 | 层 | 职责 | 对应 Contract |
|---|---|---|---|

### 5. Port / Adapter

不需要新增时明确写：`不需要新增。`

需要新增时说明 Port、使用方、Adapter、底层技术、能力失败如何传播，以及为什么该外部技术没有进入稳定 Contract。

### 6. Typed Contract 落地

说明 Module Contract 中的重要类型分别放在哪里、如何复用、在哪个边界进行 Runtime Validation；不得输出完整实现代码。

### 7. Failure 落地

按 Failure 类型或场景说明产生边界、传播路径、Context 保留和 Fail Closed 行为。

### 8. 测试设计

使用表格：

| 测试目标 | 对应 Contract | 测试层级 |
|---|---|---|

### 9. 文件变更计划

使用表格列出真实文件路径和职责。操作只能使用 `ADD`、`MODIFY`、`DELETE`；不要创建未来 Placeholder，不要把设计阶段的建议写成已发生的修改。

| 操作 | Path | 职责 |
|---|---|---|

### 10. 局部技术决定

没有真正的模块局部技术选择时，原样写：`无额外 Module-Level Technology Decision。`

有选择时，只列编码前必须确认的事项，以及“能力 → 选择 → 原因 → 边界”的简要链路；不重新打开已冻结的系统级决定。

### 11. 开发顺序

将当前模块拆成少量顺序施工步骤，例如 Typed Contract + Tests、Port / Adapter、核心处理、Failure / Edge Case、Module Integration & Verification。步骤是供后续实施使用的设计计划，本阶段不得执行。

### 12. 风险 / 待确认

只列不解决就无法安全编码的问题。没有时写：`无阻塞问题。` 普通偏好、未来能力和非阻塞优化不要列为风险。

### 13. 设计结论

只允许使用以下结论：

- `READY`：设计足够进入设计审查。
- `READY WITH LOCAL DECISIONS`：只有少量模块局部技术决定仍需确认。
- `BLOCKED`：存在正式 Contract / Repository 冲突或缺失信息，暂时不能安全进入开发。

正式设计输出结束后，必须追加并停止：

```text
模块实现设计已完成。

下一步应进入「设计审查」。
本次尚未修改生产代码。
```

不要继续写代码、创建文件、安装依赖、修改数据库或 Commit。

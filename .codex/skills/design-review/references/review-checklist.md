# 设计审查清单

本文件是 `design-review` Skill 和 `module_design_reviewer` 使用的审查基准。它描述“如何审查既有 Design”，不提供新的 Module 设计。Reviewer 必须按实际项目路径读取事实源；下列文件名是语义要求，真实仓库存在的等价文件优先。

## 1. 必须读取的事实源

根据当前 Module 所属 Feature，至少读取：

1. 系统级 `ARCHITECTURE.md`；
2. `ARCHITECTURE_DECISIONS.md`；
3. `ENGINEERING.md` 或当前仓库实际使用的 `ENGINEERING_RULES.md`；
4. 当前 Feature 的 `ARCHITECTURE.md`；
5. 当前 Feature 的 `FEATURE_SPEC.md`；
6. 当前 Feature 的 `ACCEPTANCE_AND_EVALUATION.md`；
7. 当前目标 Module Spec；
8. 当前最终版 `Implementation Design`；
9. `pyproject.toml` 或当前项目的依赖 / 运行时事实源；
10. 与目标 Module 直接相关的 `src/`、`tests/`、resources、configuration、现有 Ports、Contracts 和 Infrastructure；
11. 必要时的直接上游 / 下游 Module Spec，用于验证边界，不展开无关 Feature。

只在报告中列出实际读取的内容。如果正式事实源不存在、名称冲突或内容不足以支持安全判断，形成 Finding；缺失导致无法安全编码时使用 `BLOCKED`。

## 2. 事实优先级

发生冲突时按以下顺序判断：

```text
Formal Architecture
        ↓
Feature Spec
        ↓
Module Spec
        ↓
Acceptance & Evaluation
        ↓
Engineering Rules / ADR
        ↓
Repository Reality
        ↓
Implementation Design
        ↓
Legacy Implementation
```

`Implementation Design` 不是正式上层事实源。若 Design 与正式 Contract 冲突，应要求修改 Design，不得为实现方便偷偷改变 Identity、Business Meaning、Mapping、Input / Output、Failure Semantics、Source Trace、Authority 或 Required / Optional 语义。

## 3. Contract Alignment

逐项对照 Module Spec：

- Responsibility；
- Input Contract 与 Preconditions；
- Processing Responsibilities；
- Output Contract 与 Postconditions；
- Invariants；
- Failure Contract；
- Dependencies；
- Test / Evaluation Contract。

为每项建立：

```text
Spec Requirement
      ↓
Implementation Design
```

并标记 `PASS`、`PARTIAL` 或 `FAIL`。重点识别：

- `Missing Contract`：Spec 有要求，Design 没有覆盖；
- `Contract Violation`：Design 与 Spec 冲突；
- `Contract Mutation`：Design 偷改了稳定语义；
- `Partial Success Risk`：Contract 要求 Fail Closed，但 Design 允许部分结果继续。

## 4. Architecture Alignment

验证项目实际采用的分层和依赖方向，通常包括：

```text
Interfaces
    ↓
Application
    ↓
Domain

Application
    ↓
Port / Contract
    ↑
Infrastructure Adapter
```

至少检查：

- Domain 是否依赖 Infrastructure、Database 或 Vendor SDK；
- Application 是否直接依赖 Vendor SDK；
- Infrastructure 类型是否泄漏到稳定 Contract；
- Infrastructure 是否定义 Business Truth；
- Bootstrap 是否混入业务逻辑；
- 是否绕过已有 Port，或重复建设已有 Port；
- 是否出现不必要的循环依赖。

不要把项目尚未确认的分层偏好升级为 Finding；判断必须来自当前正式 Architecture / Engineering Rules 或真实稳定边界。

## 5. Module Boundary

检查当前 Module 是否承担了属于其他 Module 的责任，以及下游是否重新执行上游已承诺的责任。例如：

- Resource Loading 不应偷偷做 Embedding；
- Embedding 不应做 Online Ranking；
- Index Building 不应定义 Metric Business Meaning；
- 当前 Module 不应提前建设 Future Scope；
- 多个明显不同的 Feature 不应因“方便”被合并进当前 Module。

如果责任确实超出边界，说明违反的正式 Scope 和最小 Required Fix；不要提出完整替代设计。

## 6. Repository Compatibility

必须检查真实仓库，而不是只根据文档推断：

- Design 中的文件路径是否真实存在或明确标记为 `ADD`；
- Python / Runtime 版本和 `pyproject.toml` 是否一致；
- Package Layout、Bootstrap 方式和现有命名是否一致；
- 已有 Type、Port、Failure Model、Adapter、测试工具是否能复用；
- Design 是否重复已有实现；
- Design 是否依赖已经删除或仅 Legacy 的代码；
- Design 是否把派生资源、旧 Metadata 或文档描述误当成当前实现能力。

发现 `Design Assumption ≠ Repository Reality` 时，必须形成可追溯 Finding。Repository Reality 可以暴露实现冲突，但不能反向修改已确认的 Architecture / Domain / Contract。

## 7. Typed Contract 与 Validation Boundary

检查正式 Typed Contract 是否被准确映射：

- 稳定结构是否被自由 `dict` 弱化；
- 是否重复创建同义 Type；
- Enum 是否被弱化为任意 String；
- Optional / Nullable 是否改变语义；
- Identity 是否稳定；
- Infrastructure 类型是否进入稳定 Contract。

不可信边界（JSON、文件、API、LLM、External Service 和第三方 SDK 返回值）必须在进入稳定 Contract 前执行 Runtime Validation。内部 Typed Boundary 遵守 Contract / Preconditions，不要为每个内部函数重复完整序列化验证。

## 8. Failure Review

逐项对照 Module Spec Failure Contract，确认：

- Failure 在哪个边界产生；
- 如何传播和映射；
- 是否被吞掉、静默降级或伪装成成功；
- 是否返回部分成功；
- 是否保留机器可判断的信息和诊断 Context；
- 是否违反 Fail Closed；
- 新增 Failure Type 是否有正式 Contract 对应关系。

不能由 Design 自行发明未定义的 Failure Semantics。无法表达核心失败、边界失败或依赖失败时，通常至少是 `MAJOR`，破坏不变量时是 `BLOCKER`。

## 9. Technology Review

只审查 Design 已提出的重要 Module-Level Technology Decision：

```text
当前 Contract 是否需要该技术？
        ↓
项目是否已有 Baseline？
        ↓
是否有更简单的已有方案？
        ↓
是否污染稳定 Core？
        ↓
是否保持可替换？
```

不要仅因为 Reviewer 更喜欢另一套 Library 就要求修改。发现技术选择越过稳定边界、引入未必要的 Framework、或无法满足当前 Contract 时，指出具体影响和最小 Required Fix；不要重新主持全局技术选型。

## 10. Minimality / Overengineering

主动寻找：

- 无必要 Layer、Port、Service、Repository、Factory 或 Abstract Base Class；
- 无必要 Framework、Future Placeholder 或通用化；
- 一项职责拆成大量空壳类；
- 多个明显不同职责塞进一个巨大组件。

判断原则：

> 删除某个设计元素后仍可完整满足 Contract，则必须质疑其必要性；但个人命名偏好本身不是 Finding。

结果使用 `PASS` 或 `NEED SIMPLIFICATION`，并说明删除 / 合并建议如何保持 Contract，不借机重写整套方案。`NEED SIMPLIFICATION` 只属于本节的局部结果，不是最终 Verdict；如果该简化在编码前必须处理，应映射为 `NEED FIX`，否则作为 `PASS WITH MINOR FIXES` 或 `NOTE` 中的非阻塞观察，不得新增最终状态值。

## 11. Test / Evaluation Review

测试必须证明 Contract，而不是只证明拟议代码能运行。检查适用的：

- Happy Path；
- Preconditions；
- Input Validation；
- Postconditions；
- Invariants；
- Failure Contract；
- Dependency Failure；
- Module Boundary；
- Acceptance Requirements。

检查 Test Level 是否正确：

```text
Deterministic Contract
→ Deterministic Test

Port / Adapter
→ Capability / Adapter Test

真实外部集成
→ Integration Test

Semantic Retrieval Quality
→ Evaluation
```

不得用 Recall / MRR 证明确定性 Contract，也不得为纯函数测试强制启动真实 Infrastructure。Feature-Level Evaluation 不应被误写成单元测试。

## 12. Design 自报问题的独立判定

如果 Design 已写出 `BLOCKER`、`Conflict`、`Open Question` 或 `Local Decision`，不得直接继承其结论。逐项重新判断：

| 原问题 | 是否成立 | 正确分类 | 严重度 | 结论 |
|---|---|---|---|---|

问题应被分类为 Contract Conflict、Repository Conflict、Local Implementation Decision，或“不是问题”。例如 `null_if` 与 `MetricPayload`、`SourceResourceDescriptor` 来源、Dimension 缺省字段等，只能在重新读取正式 Type / Contract 和真实代码后判定。

## 13. Severity

### BLOCKER

不修不能安全编码：正式 Contract 冲突、核心输入输出无法表达、严重 Architecture Dependency 违规、或 Invariant 无法满足。

### MAJOR

编码前应处理：重要测试缺失、职责边界错误、明显过度设计、Failure 方案存在风险或 Repository 假设不成立。

### MINOR

不阻塞开发：命名、文件布局或非关键说明的小问题。

### NOTE

非阻塞观察。禁止把个人偏好升级为 `BLOCKER`。

## 14. 固定报告结构

只列实际读取的事实源和与当前 Module 直接相关的证据。

```markdown
## 1. 审查对象
- Feature：
- Module：
- Implementation Design：
- Review Scope：

## 2. 已读取事实源

## 3. Contract Coverage
| Contract | Coverage | Result | Note |
|---|---|---|---|

## 4. Architecture
PASS / Issues Found

## 5. Module Boundary
PASS / Issues Found

## 6. Repository Compatibility
PASS / Issues Found

## 7. Technology
PASS / Issues Found

## 8. Typed Contract
PASS / Issues Found

## 9. Failure
PASS / Issues Found

## 10. Test
PASS / Issues Found

## 11. Overengineering
当前 Design 是否存在删除后仍不影响 Contract 的复杂度？
PASS / NEED SIMPLIFICATION

## 12. Findings
按 BLOCKER → MAJOR → MINOR → NOTE 排序。

### [Severity] R-xxx — 标题
**位置：**
**问题：**
**正式依据：**
**影响：**
**Required Fix：**

## 13. 设计者报告问题的独立判定
| 原问题 | 是否成立 | 正确分类 | 严重度 | 结论 |
|---|---|---|---|---|

## 14. 最终 Verdict
PASS / PASS WITH MINOR FIXES / NEED FIX / BLOCKED
```

`R-xxx` 必须在本次报告中稳定、唯一、按严重度排序。没有 Findings 时明确写 `无 Findings`，不要用空白掩盖未审查项。报告末尾说明 Reviewer 为独立 Read-Only Agent，并等待人工决定。

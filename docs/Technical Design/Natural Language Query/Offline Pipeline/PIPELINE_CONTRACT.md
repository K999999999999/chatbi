# Offline Pipeline Contract
# 离线链路契约

> **Version（版本）：** V1
> **Scope（范围）：** Core Module Responsibility & Inter-Module Contract（核心模块职责与模块间契约）

## 1. Purpose（目的）

本文只定义 Offline Pipeline V1 必要的核心模块职责、输入输出边界和模块间 Contract。

具体数据结构、字段、算法、文件、函数、测试命令、技术框架和实现方案不属于本文。

## 2. Pipeline（链路）

```text
Authoritative Resources
        ↓
M1 Resource Loading & Validation
        ↓
Validated Catalogs
        ↓
M2 Retrieval Projection
        ↓
Retrieval Records
        ↓
M3 Retrieval Representation Generation
        ↓
Represented Retrieval Records
        ↓
M4 Retrieval Asset Building
        ↓
Built Retrieval Assets
        ↓
Post-build Validation / Online Ready Gate
```

Post-build Validation / Online Ready Gate 不是 Core Module。其验收规则只由 `ACCEPTANCE_AND_EVALUATION.md` 定义。

## 3. Shared Invariants（共享不变量）

- Retrieval Object 只允许 `TABLE`、`COLUMN`、`METRIC`。
- 一个正式 Source Object 只对应一个 Logical Retrieval Record。
- Relationship 不进入 Retrieval Record、Retrieval Representation 或 Retrieval Index。
- `relationships.json` 只用于确定性 Relationship Graph 与 Join Resolution。
- V1 只支持 Full Rebuild，不支持部分构建或增量更新。
- 任一关键步骤失败时必须 Fail Closed，不得返回部分成功资产。
- Pipeline 只消费和投影正式事实，不创造或修改 Business Truth。
- Retrieval Asset 必须可追踪到当前权威 Source Resource。
- 新构建失败不得破坏上一版有效资产。
- 未通过验收门禁的资产不得进入 Online Runtime。

## 4. M1 Resource Loading & Validation（资源加载与校验）

- **Responsibility：** 加载并确定性校验当前 Table、Column、Relationship 和 Metric Catalog。
- **Input：** 四份独立的当前权威资源及本次 Full Rebuild 的构建上下文。
- **Output：** `Validated Catalogs`，即完整、可追踪且通过资源契约校验的逻辑目录集合。
- **Core Rules：**
  - 校验资源完整性、唯一性、跨资源引用、Semantic → Physical Mapping 和 Metric Dependency。
  - Relationship Catalog 必须合法并保持独立，不得成为 Retrieval Object。
  - 不得使用 Legacy Resource 补齐当前资源，不得猜测或修复缺失事实。
- **Failure Boundary：** 任一资源缺失、非法、引用不可解析或权威性不成立时，整个 Offline Build 失败。
- **Out of Scope：** Retrieval Projection、Representation Generation、Index Build、Relationship 推断和业务定义修改。

## 5. M2 Retrieval Projection（检索投影）

- **Responsibility：** 将已验证的 Table、Column、Metric 确定性投影为独立 Retrieval Record。
- **Input：** M1 输出的完整 `Validated Catalogs`。
- **Output：** `Retrieval Records`，覆盖全部三类可检索 Source Object。
- **Core Rules：**
  - 保持 One Source Object → One Logical Retrieval Record。
  - 可以重组正式内容，但不得创造或修改业务事实、物理映射或 Relationship。
  - 每条 Record 必须保留 Source Trace；Relationship Catalog 不产生 Record。
- **Failure Boundary：** 任一对象无法唯一投影、无法追踪或无法保持源语义时，整个 Offline Build 失败。
- **Out of Scope：** Retrieval Representation、Index Build、Online Ranking、Schema Linking 和 Join Resolution。

## 6. M3 Retrieval Representation Generation（检索表示生成）

- **Responsibility：** 为每条 Retrieval Record 生成一个满足当前检索表示契约的 Retrieval Representation。
- **Input：** M2 输出的完整 `Retrieval Records`。
- **Output：** `Represented Retrieval Records`，每条 Record 与其 Representation 一一关联。
- **Core Rules：**
  - 每条 Retrieval Record 必须有且只有一个合法 Representation。
  - Representation Generation 不得修改 Record、Business Meaning、Physical Mapping 或 Source Trace。
  - Representation 形式不在本文冻结；Relationship 不生成 Representation。
- **Failure Boundary：** 任一 Record 无法生成合法 Representation 或无法保持一一关联时，整个 Offline Build 失败。
- **Out of Scope：** 具体 Representation 技术、Index Build、Online Retrieval、Ranking 和业务解析。

## 7. M4 Retrieval Asset Building（检索资产构建）

- **Responsibility：** 通过 Full Rebuild 构建候选 Retrieval Assets，并执行必要的构建后完整性验证。
- **Input：** M3 输出的完整 `Represented Retrieval Records`。
- **Output：** `Built Retrieval Assets`，即完整、可追踪但尚未获得 Online Ready Eligibility 的候选资产。
- **Core Rules：**
  - 所有输入 Record 必须完整进入候选资产，不得依赖旧索引补齐。
  - Record、Representation、Payload、Identity 和 Source Trace 必须保持关联。
  - 构建后必须验证资产完整性、记录覆盖和 Relationship Boundary。
  - 构建成功不等于通过 Feature Acceptance，也不等于已经激活。
- **Failure Boundary：** 任一资产不完整、关联失真或构建后验证失败时，新构建整体失败且不得影响上一版有效资产。
- **Out of Scope：** Retrieval Quality Acceptance、Online Retrieval、Ranking、Activation 和多版本在线服务。

## 8. Inter-Module Contract（模块间契约）

- **M1 Output → M2 Input：** M2 只接受完整 `Validated Catalogs`；可以依赖资源合法、引用可解析和 Relationship Catalog 独立，不得依赖 M1 内部实现。
- **M2 Output → M3 Input：** M3 只接受完整 `Retrieval Records`；可以依赖三类 Record 全覆盖、源语义未改变和 Source Trace 完整，不得重新投影或补写 Record。
- **M3 Output → M4 Input：** M4 只接受完整 `Represented Retrieval Records`；可以依赖 Record 与 Representation 一一关联，不得重新生成表示或修改源语义。
- **M4 Output → Validation / Online Ready Boundary：** `Built Retrieval Assets` 只是候选资产；全部 Feature Acceptance Gate 通过后才具备 Online Ready Eligibility。

## 9. Validation / Online Ready Boundary（验证与在线就绪边界）

- 该 Gate 不是 Core Module，不新增独立 Contract、Spec 或 Implementation Design。
- Feature-Level 验收规则和 Online Ready Eligibility 只由 `ACCEPTANCE_AND_EVALUATION.md` 定义。
- Physical Activation 属于 Feature / Application Orchestration Boundary，不属于 Offline Pipeline Core Module。

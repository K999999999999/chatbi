# 统一初始化与运行资源装配

Status: confirmed（用户确认完整 Spec；设计审查局部补充见下文）
Baseline: `08c632e01baae62e161f3eec69993d56a3f441c3`
Last updated: 2026-10-02

## Problem Statement

目前运行资源装配分布在 Query API 入口、Business Analysis runtime 和各模块配置工厂中；部分资源在导入应用时创建，启动检查和关闭逻辑分散。初始化命令分别位于 Control DB CLI、Embedding 准备脚本和 RAG Offline Build 入口，开发者缺少统一的查找与调用位置。

目标是集中初始化入口与资源生命周期，让开发者能清楚找到初始化命令、运行资源装配、启动检查和资源释放，同时保持模块各自拥有具体操作与业务实现。

## Solution

建立专门的初始化目录，作为应用的集中装配入口（Composition Root），统一管理运行资源装配和显式初始化命令。推荐目录为 `src/bootstrap/`；内部文件划分由设计确定，不要求全部内容放入单个文件。

统一入口负责配置加载与校验的编排、资源创建顺序、应用服务装配、就绪检查、失败清理和正常关闭。迁移、权限、索引构建、模型适配器及业务操作继续由所属模块实现，避免在初始化目录复制业务逻辑。

## User Stories

- 开发者能在一个目录找到应用初始化命令和运行资源装配入口。
- 维护者能追踪资源何时创建、由谁持有、何时释放，定位启动失败。
- 运维调用者能按现有显式操作边界完成 migration、首个管理员创建、模型准备和 RAG 构建。
- 测试调用者能导入应用模块和注入替身，而不打开外部连接、下载模型或启动后台线程。

## Scope

### 运行资源

- Query API 所需的数据库资源、Session factory、认证、授权、审计、Tracing、查询服务、LLM 客户端及 RAG Runtime 的集中装配。
- Business Analysis 所需的模型适配器、Control DB engine、checkpoint pool、checkpointer、run store、应用服务及关联后台清理线程的装配与生命周期。
- 资源创建、现有就绪检查、启动失败清理及正常关闭。
- RAG 按需创建的资源仍由 RAG Runtime 管理；集中生命周期在应用结束时触发其释放。

### 显式命令

- Control DB migration，包括现有固定 RBAC、checkpoint 安装和权限处理。
- 首个管理员创建。
- 固定版本 Embedding 模型准备。
- RAG 离线构建、验证与发布。

推荐统一调用形式：

```text
python -m src.bootstrap migrate
python -m src.bootstrap create-admin
python -m src.bootstrap prepare-model
python -m src.bootstrap build-rag
```

以上命名由设计审查核定；操作参数、输出语义和退出码沿用现有命令，除命令路径外不增加行为变化。

## Observable Behavior

### 服务启动和关闭

1. 导入应用或初始化模块不打开外部连接、不创建运行连接池、不加载模型权重、不启动后台线程，也不执行初始化命令。
2. 在服务启动阶段装配资源，完成既有配置和就绪检查后才接收请求；必要配置缺失仍在启动时明确失败。
3. 保持现有环境差异：Control DB 完整性检查及 production RAG 来源指纹、集合和 PostgreSQL catalog 校验继续生效。不得把 production 检查降级或无依据扩大为开发环境全量预加载。
4. RAG 内部继续按需加载快照和 Embedding；production 既有就绪检查需要的加载仍在检查期间执行。
5. 创建或检查失败时，清理本次启动已成功创建且由应用持有的资源，拒绝启动并保留可定位、不泄露 Secret 的错误。
6. 正常关闭时统一释放应用持有的数据库、RAG、checkpoint 和后台线程等资源；避免重复释放和遗漏。资源依赖顺序、清理异常处理与注入资源所有权由设计明确，以保证失败清理不遗漏后续资源。
7. HTTP 接口、认证、授权、查询及经营分析业务行为保持既有 Contract。API 启动方式继续支持 `uvicorn src.query_api.main:app`。

### 初始化命令

- 各操作独立、显式调用；运行任一命令不应因导入统一入口而创建在线服务资源或加载无关模型。
- API 启动不自动执行 migration、创建管理员、下载模型或构建索引。
- migration 沿用幂等性，不创建管理员；首个管理员沿用隐藏密码输入、确认和重复创建拒绝规则。
- 模型准备沿用固定 revision 和本地缓存约定。
- RAG 构建沿用完整验证后原子发布、失败保护当前已发布资产的规则。
- 命令保留现有参数能力、成功 / 失败输出语义和退出码，帮助信息反映统一入口。

## Implementation Decisions

### 已确认决定

- 用户选择范围 A：运行资源完整生命周期和应用初始化命令。
- 用户确认将导入时资源创建调整到服务启动阶段；RAG 保留按需加载。
- 用户明确要求直接移除旧命令入口，保持清晰单一入口，不提供兼容转发。
- 采用集中目录、职责拆分，各模块保留具体实现；不引入通用初始化框架或复杂注册机制。

### 架构和安全边界

- 集中入口属于装配边界，不成为新的业务模块或业务事实源；Domain / Application 不反向依赖初始化入口。
- 不改变 Query API Adapter、Online Query、Business Analysis、Control DB 和 RAG Offline Build 的业务职责。
- 运行进程继续仅使用运行身份；迁移凭据仅用于显式初始化操作，不扩大运行账号权限。
- 不改变 Semantic、SQL Guard、Authorization、数据库 Schema、Seed 或 RAG 发布格式。
- 真实 Secret 不进入源代码、日志、文档、测试数据或命令参数。

### 留给设计与实施的局部决定

- 目录内部文件组织、资源持有对象、启动与关闭实现方式。
- 服务装配和 SQLAdmin 挂载如何在启动阶段衔接，保持现有 HTTP 路由和测试注入能力。
- 资源获取和清理顺序、清理异常处理，以及应用创建资源和调用者注入资源的所有权。
- 迁移命令解析、模型准备与 RAG 命令装配时如何延迟导入无关依赖。

若这些设计需要改变上述可观察行为、架构边界或安全要求，返回 Spec 确认，不在实现时自行扩张。

### 设计审查补充（Contract 内的局部决定）

- HTTP 路由和根应用 Middleware 在构造应用时定义，具体服务在 lifespan 启动阶段绑定；请求不得继续使用构造时的空对象。SQLAdmin 在就绪检查后挂载，应用重启不重复挂载。
- 应用拥有的资源获取成功后立即登记清理；构造函数内部已获取但尚未返回的资源，由该构造函数负责失败清理。
- 清理按依赖逆序，单个清理失败仍尝试其余清理；启动失败保留原始原因。关闭路径可重复调用而不重复释放；命令创建的临时资源同样保证释放。
- Tracing recorder 的 shutdown 纳入生命周期；不为逐查询使用 context manager 的 Query Executor 虚构长期连接池。
- 保留现有直接注入测试 seam 和既有注入资源所有权；统一入口创建的资源由统一生命周期持有，不与 Adapter 重复关闭。详细设计见 `design.md`。

## Compatibility / Migration

删除以下旧命令入口及其重复命令装配，不保留 alias 或转发：

```text
python -m src.chatbi_control migrate
python -m src.chatbi_control create-admin
python -m scripts.prepare_embedding_model
python -m src.rag_offline
```

同步迁移 README、Runbook、适用的 Architecture / Spec / Design、CI、测试和脚本里的调用。数据库测试 runner 和 PostgreSQL reset 脚本仅替换调用的初始化命令，不改变环境操作职责。模块公共业务 API 保留，不因删除命令入口删除其业务实现。

已日期化的 Acceptance、旧报告及长期历史工作记录保留原候选和原命令作为历史证据，不批量改写。旧外部调用需要使用者更新为新入口；本次不提供兼容期。不迁移现有数据、索引或配置格式。

## Testing Decisions

- 确定性生命周期测试：无配置 / 无外部服务时模块可导入；正常启动通过检查；缺少配置或就绪检查失败拒绝启动；部分装配失败释放已获取资源；正常关闭释放应用持有资源与后台线程。
- CLI 测试：统一帮助、四类子命令、现有参数和退出码、缺少参数及错误配置；验证执行单一命令不初始化无关在线资源，旧入口已移除。
- 隔离 PostgreSQL 集成测试：从既有 fixture 完成 migration / checkpoint / grants，重复 migration 幂等；首个管理员创建成功、重复被拒绝、运行权限维持既有边界。
- API 启动冒烟和受影响软件回归：现有启动方式、路由、认证 / SQLAdmin / 查询及经营分析装配可用，production 就绪门禁仍拒绝不一致资源。
- 复用并运行受影响 RAG 软件测试，验证命令重组保持构建失败保护和发布语义；模型下载和真实 RAG 构建不因确定性测试自动触发。
- 执行仓库要求的模块边界、文档链接及 Diff 检查，检查当前可执行调用不再引用旧入口。
- 本目标不改变 Prompt、模型配置、Semantic 或业务查询行为，因此不以重新运行完整 AI Evaluation 为本目标的默认验证；若设计 / 实现影响这些行为，返回范围确认并调整验证要求。路线图已有当前 clean commit Evaluation 待办仍独立存在。
- 验证证据记录适用候选提交、基线、覆盖范围和结果；未执行或不可执行的检查明确说明，不将历史证据改称当前结果。

## Acceptance / Done When

1. 初始化目录提供单一可发现入口，API 入口不再承担分散的实际资源装配。
2. 模块导入无运行资源创建副作用，服务启动、就绪失败、部分装配失败和关闭行为具备确定性证据。
3. 四类初始化命令使用统一入口，旧入口已移除，现有参数能力与操作边界保留。
4. 仓库可执行调用、当前使用文档、CI 和相关测试完成迁移，无兼容转发或重复装配。
5. 适用正式 Contract、Design、Runbook 和代码地图同步更新；历史证据保留身份。
6. 受影响测试、隔离数据库集成、启动冒烟及仓库必需检查通过，实现 Review 和 Diff 检查完成。
7. 检查路线图是否受确认目标、依赖或完成事实影响，并记录更新位置或不适用理由。

## Out of Scope

- 统一 Compose 操作、环境检查 / reset、结构导出等开发环境命令；调用旧初始化命令的位置迁移除外。
- 每次启动自动初始化数据库、创建账号、下载模型或构建索引。
- 新增一键执行全部操作、初始化注册框架、依赖容器、自动重试 / 修复或资源热更新机制。
- 修改业务 Contract、数据库 / Seed、模型和依赖版本、索引格式或环境变量。
- 生产部署、容量保障、Secret 平台和实际环境 / 数据重置。

## Canonical Source / Authorization

- 本文件是当前工程目标的规划 Spec；正式业务 Contract 继续以 `docs/specs/`、Architecture 和产品边界为准。
- 事实来源：`src/query_api/main.py`、`src/query_api/app.py`、`src/business_analysis/runtime.py`、`src/business_analysis/application.py`、`src/online_query/retrieval/rag_runtime.py`、Control DB CLI、Embedding 准备脚本、RAG CLI、相关测试、Runbook 和 CI。
- 用户已确认澄清结果、完整 Spec、三项 Ticket 拆分与整体实施；授权覆盖全部实现、验证、Review 与本地 Commit。没有 Push / PR 发布授权。
- 完整 Spec 确认不自动等于实施授权；复杂目标按仓库要求完成 Design Review、Ticket 草案与当前上下文 Readiness Review，再取得拆分确认及实施授权。
- 规划阶段不修改路线图：本目标尚未进入实施，不改变现有基线验收事实或依赖，不推定新的优先级排序；后续交付重新核对。

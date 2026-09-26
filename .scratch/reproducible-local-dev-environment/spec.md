# ChatBI 可重复本地开发数据环境

Status: confirmed
Last updated: 2026-09-27

## Problem Statement

当前仓库无法保证新开发者从干净 clone 得到完整的 PostgreSQL 开发环境。Compose 将 PostgreSQL 和 Qdrant 持久化到源码目录的 `data/`；Sales Mart 有 Schema DDL 和权限 SQL，但没有当前仓库内可重复生成的完整开发 Seed；Control DB 有初始化代码，但尚未和首次开发环境启动流程组成闭环。

`database/ci/bootstrap.sql` 是 CI 用的小型 fixture。它只有 2025 年 1 月、单一客户/产品/区域及一致的销售金额和成本，不足以支撑日常开发和有区分度的 Natural Query / Business Analysis 验证。

RAG Offline Build 已具备读取 Git 源资产、Embedding、创建版本化 Qdrant 集合、生成 Relationship Graph、发布资产并验证检索的能力。本 Feature 的目标是让开发者能从无运行数据的环境重新建立所需服务和数据，不重复实现索引构建逻辑。

当前仓库已有 Dev Container 配置，但开发数据初始化、运行数据生命周期和 WSL / Linux 本地入口尚未形成可从新 clone 验收的统一闭环。当前开发约定收敛为 WSL / Linux 本地运行 ChatBI 与 RAG 构建，并使用 Docker Compose 运行 PostgreSQL 和 Qdrant。Dev Container 配置文件保留在仓库中，但不属于当前开发、支持或验收入口。开发环境不得依赖 W11 旧项目目录、旧 PostgreSQL / Qdrant 物理数据或某个开发者电脑上的运行资产。

## Solution

新开发者从干净 clone 和 WSL / Linux 环境开始，使用 `uv` 安装依赖、复制 `.env.example`、启动 Docker Compose 基础设施并初始化 PostgreSQL。首次启动后得到可用的 PostgreSQL 开发环境及可连接的 Qdrant 服务；PostgreSQL 首次初始化创建 Sales Mart、Control DB、所需角色和权限，并载入完整的确定性合成开发数据；后续日常启动保留数据且不重复播种。数据库重置和 Qdrant 索引重建 / 清除仍是单独、明确的操作。

开发者使用仓库提供的显式命令，从版本控制中的 Schema、关系和 Semantic 源资产构建 RAG 索引。索引构建使用固定模型权重版本，可复用本地模型缓存；构建完成且通过检索验证后再启动 ChatBI。模型权重、PostgreSQL 数据目录、Qdrant 数据目录和 `.env` 都不进入 Git。

开发数据库重置和 Qdrant 索引重建必须是可分别执行的操作。重置只针对当前 Compose 项目的 named volume；重建完成后，开发者仍可由仓库源文件恢复完整开发环境。

## User Stories

- 作为新开发者，我可以在 WSL / Linux 环境使用 `uv`、`.env` 和 Docker Compose 建立本地开发环境，不需要旧机器数据或手工执行多段 SQL。
- 作为开发者，我可以查询覆盖主要业务维度、时间范围和指标组合的合成 Sales Mart 数据，并使用完整的 Control DB 和正确权限登录及运行应用。
- 作为开发者，我可以按明确命令构建、验证或重建 Qdrant 索引；日常启动服务不会自动重新向量化。
- 作为开发者，我可以运行确定性自动测试而不访问或改动日常开发数据库。
- 作为评测使用者，我可以在日常开发数据库上运行黄金评测；每条 expected SQL 和模型 SQL 都在同一个数据库执行，报告记录当前 Seed 版本及可验证的数据摘要 / Hash。
- 作为开发者，我可以分别重置 PostgreSQL 开发数据和 Qdrant 索引，并通过仓库定义的流程恢复它们。

## Implementation Decisions

### 环境与生命周期

| 环境 | 本 Spec 定义 | 生命周期 |
|---|---|---|
| 日常开发 | `chatbi_mvp` 中的完整合成 Sales Mart 数据，以及同一 PostgreSQL 服务中的 `chatbi_control` | PostgreSQL named volume 持久化；首次建立时初始化，日常 Compose 启动不重播种 |
| 自动测试 | 独立的临时 PostgreSQL / 测试数据环境 | 不使用日常开发数据库或其 named volume；测试完成后可销毁 |
| 黄金评测 | 复用日常开发数据库 `chatbi_mvp`，不创建独立评测数据库 | expected SQL 与模型 SQL 使用同一配置、同一数据环境执行 |
| 生产 | 本 Feature 不创建或配置 | 不适用 |

### 开发入口与持久化边界

- WSL / Linux 是当前唯一支持的本地开发入口。ChatBI、RAG 构建和 `uv` 命令在 WSL / Linux 进程中运行，PostgreSQL 与 Qdrant 由 Docker Compose 管理；`.env.example` 使用宿主机回环地址连接 Compose 发布端口。
- PostgreSQL 与 Qdrant 使用当前 Compose 项目专属 named volume。WSL / Linux 终端和 Compose 服务停止或重启不会删除数据卷。
- 只有明确执行 PostgreSQL 重置或 Qdrant 数据清除操作才会删除对应数据卷。
- Runbook 说明 WSL / Linux 中 `.env` 的放置、Compose 项目身份、宿主机连接端点、初始化与服务验证命令。仓库中的 Dev Container 配置保留，但不纳入当前开发流程或验收范围。

PostgreSQL 首次启动必须能从空的项目专属 named volume 完成初始化。初始化完成状态不能仅以 PostgreSQL 进程健康作为判据；必须验证业务库、Control DB、Schema、Seed 和角色权限均可用。初始化失败时要返回可定位且不泄露 Secret 的错误，并提供安全的恢复方式。日常 `docker compose up` 不得清空、重复插入或重新生成开发数据。

PostgreSQL 重置会清除本地 `chatbi_mvp` 和 `chatbi_control` 的所有开发数据、账号、Session 与审计记录；这些环境数据必须可从仓库重建。重置命令只允许删除当前项目的开发 PostgreSQL volume，不得删除其他 Compose 项目或 W11 旧数据。

Qdrant 使用单独的项目专属 named volume。服务启动只启动 Qdrant，不隐式执行 Embedding 或索引重建。显式索引构建从 Git 源资产依次完成输入校验、TABLE / COLUMN / METRIC 文档生成、Embedding、集合写入、Relationship Graph 生成、发布版本更新和检索验证。只有完整验证成功后才更新当前发布指针；失败不得发布半成品。Qdrant volume 被清除后，必须重新构建并验证索引后再启动依赖该索引的应用。

### PostgreSQL 数据与权限

- 复用当前 Sales Mart Schema 和 Control DB Schema / migration，不改变已确认的表结构、业务指标定义或授权 Contract。
- 开发 Seed 只包含合成数据，由仓库源文件确定性生成；固定生成输入、ID 和时间值后，重建应得到相同的逻辑记录及验证摘要。
- Seed 覆盖当前主要查询需求：多个年份、季度、月份和日期；销售区域、客户区域、客户类型、产品、产品线、类别和技术路线；订单数量与明细行数；人民币销售额、销售成本、毛利和毛利率；单指标、多指标、分组、聚合和能区分结果的 `HAVING` 场景。
- 时间范围至少覆盖现有黄金案例涉及的 2024 年和 2025 年。当前指标以完成日期统计；数据须避免订单日、确认日和完成日全部相同而掩盖日期字段选择错误。
- 销售区域与客户区域、订单与明细、产品各类分组和各指标数值须有足够差异，避免错误 Join、错误分组或漏过滤因数据恒定而碰巧得到相同结果。
- `chatbi_app` 只读访问 Sales Mart；`chatbi_control_user` 仅获得 Control DB 运行所需权限；迁移身份只用于初始化 / migration，不进入应用运行进程。
- Control DB Schema、固定 RBAC、运行账号和 grants 必须能够在首次环境初始化时自动、可重复地创建。初始化不创建管理员账号。
- 首个管理员必须由开发者显式执行一次安全操作创建；使用现有隐藏输入 / 确认式密码输入方式或等价的安全交互，不接受仓库默认密码，不通过命令行参数、Compose、Seed、日志或 Git 提供管理员密码 / Secret。已存在管理员时，重复创建必须明确失败，不得创建第二个首位管理员。

上述数据分布细节是对现有指标和 Schema 的验收细化。尤其是多明细订单、非 completed 状态、不同日期角色、独立区域取值，以及毛利率分母为零时返回 NULL，应纳入 Seed 质量验证。现有黄金案例文件保持不变；Seed 不以修改案例为代价。

### 环境配置与模型资产

- `.env.example` 应包含新 clone 所需的非敏感连接默认值，并说明必须在本地配置的 PostgreSQL、Qdrant、Control DB 和应用 Secret；真实 Secret 只存本地 `.env`。首个管理员密码通过显式的一次性安全操作输入，不提供默认密码，也不作为 Compose 配置或 Seed 数据。
- PostgreSQL、Qdrant 和 WSL / Linux 中运行的应用之间的 host、port、database、账号和认证配置要一致且明确。Compose 不再使用 `./data/postgres` 或 `./data/qdrant` 作为运行数据目录。
- Embedding 模型继续使用 BGE-M3；必须固定可验证的不可变模型 revision，并记录模型标识 / revision、向量维度和 Embedding 运行配置。首次下载方式和可复用缓存目录须在 Runbook 中说明。
- FlagEmbedding、Qdrant 服务版本和 PostgreSQL 主版本应与仓库锁文件 / Compose 配置保持一致。模型权重、向量和物理数据不得提交 Git。
- 外部 LLM 配置用于 Natural Query、Business Analysis 和真实 AI Evaluation；Compose 初始化及确定性自动测试不应隐式调用外部 LLM。

### Application 与兼容性

应用在 WSL / Linux 本地环境中由现有 `uv` 应用入口启动；Docker Compose 负责本地基础设施和数据库生命周期。本 Feature 不增加新的查询链路，不改变 Query API、SQL Guard、Online Retrieval、Semantic、Authorization 或生产业务逻辑 Contract。

## Testing Decisions

### 确定性测试

- 测试开发 Seed 对固定输入可重复，覆盖数量、日期范围、维度区分、状态、订单 / 明细区别、金额关系和关键聚合分布。
- 集成测试验证从空环境初始化后，Sales Mart 可查询、Control DB migration 可用、角色权限符合预期，且重复日常启动不会重复播种。
- PostgreSQL 应用只读权限和 Control DB 最小权限使用隔离测试环境验证；测试不得连接日常 `chatbi_mvp`。
- 现有 `database/ci/bootstrap.sql` 继续作为 CI fixture，不作为日常开发 Seed；不修改现有黄金 SQL 或 Business Analysis 案例来掩盖初始化问题。

### 环境验收

从干净 clone、没有任何 PostgreSQL / Qdrant 运行目录和旧 W11 数据的 WSL / Linux 环境完成以下验收：

1. WSL / Linux 可按 `.env.example` 准备本地配置，使用 `uv sync`、首次 `docker compose up` 和数据库初始化流程成功建立环境。
2. PostgreSQL 中 `chatbi_mvp`、`chatbi_control`、Sales Mart 表、Control DB Schema、开发 Seed 和应用角色均可用。
3. Control DB Schema、固定 RBAC、运行账号和 grants 在自动初始化后可用，但不自动创建管理员；开发者可按显式安全命令创建首个管理员，重复创建被拒绝，且密码不落入 Compose、Seed、日志或 Git。
4. `chatbi_app` 能查询 Sales Mart 且不能写入；Control DB 运行账号能执行应用必要操作但不能超出既有 grants。
5. 同一初始化 / 重置流程重复后得到相同的开发数据摘要；普通 Compose restart 不重新生成或复制数据。
6. WSL / Linux 终端及 Compose 服务普通关闭、重启后 PostgreSQL 和 Qdrant named volume 保留原数据；单独执行对应重置 / 清除命令后，才删除目标数据。
7. 自动测试能在独立、可销毁环境运行；停止或不存在开发数据库不应把自动测试重定向到另一份持久化业务库。
8. Qdrant 服务可用；索引可从 tracked 源资产构建，三个逻辑集合和关系图均发布完成，检索验证通过。
9. ChatBI 可使用本地配置启动；Natural Query / Business Analysis 在配置 LLM 后可基于开发数据运行。
10. 黄金评测报告包含 Seed 版本、数据摘要和可复算的数据 Hash；数据 Hash 与基线不同或基线缺少 Hash 时明确标记不可直接比较，且不报告回退 / 改善；两条 SQL 仍在同一 `chatbi_mvp` 上执行。
11. 分别清除开发 PostgreSQL 和 Qdrant 项目 volume 后，按文档步骤可以恢复数据库、Control DB、合成数据和向量索引。
12. 清理与验证流程不读取、复制、改写或删除 W11 旧目录，不在 Git 中产生物理数据库、Qdrant 数据、Embedding 模型或 `.env`。

### AI Evaluation

黄金评测使用日常开发库，不单独初始化评测库。每个案例的 expected SQL 与模型 SQL 使用同一只读执行边界和同一 PostgreSQL 数据状态比较。每份报告必须记录 Seed 版本、Sales Mart 数据摘要及可复算的完整数据状态 Hash；Hash 基于确定性规范化后的业务表名、字段和行值，行按稳定键排序，不能只用 Seed 源代码版本或黄金案例的 `reference_result_hash` 代替当前实际数据快照。

与显式基线比较时，测试集和参考结果指纹仍须一致，且当前报告与基线的 Sales Mart 数据状态 Hash 必须一致；数据 Hash 不同或基线缺少该字段时，必须标记为 `NOT_COMPARABLE`（不可直接比较），说明原因且不报告回退 / 改善。若 Seed 版本不同但完整数据状态 Hash 相同，应在报告中保留版本差异作为来源信息；是否可比较以实际数据 Hash 为准。该要求只扩展报告元数据和基线判断，不引入独立评测数据库。真实 LLM Evaluation 是显式的独立验收动作，不在 Compose 启动或确定性测试期间自动运行；执行前按仓库规则说明外部请求数量、目标和配置。

## Out of Scope

- 迁移、复制或继续依赖 W11 PostgreSQL / Qdrant 物理目录。
- 将 PostgreSQL、Qdrant、Embedding 模型或 `.env` 提交 Git。
- 生产数据库、生产部署、真实企业数据、企业 SSO 或生产 Secret 管理。
- 修改黄金 SQL 案例、Business Analysis 案例、业务指标、生产查询链路或授权规则来适配本地数据。
- 每次日常 Compose 启动都重置 PostgreSQL、重播开发 Seed 或重建完整 Qdrant 索引。
- 将自动测试库、日常开发库和生产数据合并到同一生命周期。

## Further Notes

- 当前 RAG Builder 已提供版本化集合、旧发布保护和失败时不更新 current pointer 的行为，应优先复用。旧版本集合的清理策略须和显式 Qdrant reset / rebuild 命令一致，不能在失败构建时误删当前可用版本。
- 精确开发 Seed 行数与生成算法、WSL / Linux 对 Compose 的连接端点细节、自动数据库初始化的执行编排、首次管理员命令如何与自动迁移拆分、模型仓库 revision、Qdrant 历史集合清理策略和本地临时 PostgreSQL 的启动方式属于 Implementation Design 细节；后续设计应选定并给出可执行命令与恢复步骤。
- 当前 Evaluation 报告已有 `test_set_hash`、`context_hash` 和由标准 SQL 结果计算的 `reference_result_hash`，可用于评测输入 / 结果指纹；本 Feature 还需为实际 Sales Mart 数据快照增加 Seed 版本、摘要与数据 Hash，并把 Hash 加入基线可比性判定。现有无数据 Hash 的历史报告应标记为不可直接比较，不要求创建新数据库。
- `docs/specs/evaluation.md` 和 `docs/designs/evaluation.md` 当前定义了报告 metadata 与基线 Contract；实现数据快照指纹时应同步更新正式 Evaluation Contract 和设计文档，避免 `.scratch` Feature Spec 与模块事实文档冲突。报告 JSON / Markdown 仍由现有 Evaluation 模块负责，不另建评测报告链路。
- 当前 Control DB CLI 将 Schema / RBAC 初始化与首个管理员创建放在同一显式命令中。目标要求两种生命周期分开：可自动初始化 Schema / RBAC / grants，管理员创建仍显式且一次性。设计阶段需复用已有 migration、`seed_rbac` 和隐藏密码输入能力，避免另造 RBAC 实现。
- 当前开发入口决策（2026-09-27）：只使用 WSL / Linux 宿主环境；`.devcontainer/` 配置文件原样保留，但不作为支持或验收路径。原双入口实现和验收记录作为历史信息保留在已完成的 `05-devcontainer-and-wsl-entrypoints.md` 中。
- 本文档是 `.scratch/` 中已确认的 Feature Spec 和 Design Review 目标。它不授权创建 Ticket、修改代码、重置容器 / 数据库、执行真实 LLM 评测、Commit、Push 或 PR；这些仍需按仓库流程进入相应阶段并获得授权。

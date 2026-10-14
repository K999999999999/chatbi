# Deployment Simplification Spec

Status: confirmed；用户于本会话明确确认完整 Spec；用户已确认四项Ticket及完整本地实施、验证、相关Commit；无发布授权。

## Problem Statement

ChatBI 同时提供容器开发、宿主调试和自研 Stable 发布运维入口。Stable 系统包含发布登记、部署状态、升级回滚、备份调度、隔离恢复和资源切换，超出本项目作为 AI 应用工程的维护目标；应用就绪与请求保护又与其中部分实现耦合，不能整体按名称删除。

目标是源码交付、单一推荐容器开发入口，以及标准 Dockerfile / Compose 运行能力。无需开发者在宿主安装 Python、uv 或 Node，不维护预构建镜像发布流程，不实现企业发布运维平台。

审查基线：`master@f4d0693`。正式事实源：[Architecture](../../docs/architecture.md)、[Product Scope](../../docs/product-scope.md)、[Roadmap](../../docs/roadmap.md)、[Bootstrap](../../docs/specs/bootstrap.md)、[Container Dev](../../docs/specs/container-dev-environment.md)、[Local Deployment](history/docs--specs--local-deployment-v1.md)、[Local Operations](history/docs--specs--local-operations-v1.md)、[Runbook](history/docs--runbook.md)。本草案确认后定义本次变更范围；正式当前 Contract 在交付时同步，旧 R6/R7 证据保留为历史。

## Solution / Scope

- `./dev` 是本地开发、初始化、启动和验证的统一推荐入口，复用现有源码挂载与热更新。
- 移除宿主 `uv run` / npm 开发教程及要求；保留 Dockerfile 和 CI 内的 uv、Python / Node、依赖清单和锁文件。
- 保留必要开发镜像、应用 Dockerfile 和 Compose；Docker 在本机正常构建镜像并运行容器，不建立镜像仓库上传、版本登记或发布管理流程。
- 保留显式数据库迁移、首个管理员、Embedding 模型准备、RAG 构建、业务演示数据初始化和健康检查。
- 删除 Stable 发布运维系统；应用装配、就绪与执行保护保留。
- 企业环境运维仅说明由部署方承担；不增加平台接入、部署工程或新编排机制。

Change Profile: 多阶段、跨脚本 / 容器 / 应用装配 / HTTP 状态 / 网页 / 测试 / 文档；涉及初始化和数据保护，需完整 Spec、Design Review、Ticket Readiness 和实现后 Code Review。默认本地交付，发布另行授权。

## User Stories

- 开发者 clone 后仅准备 Docker Engine / Compose、Git、Bash 和本地配置，即可通过容器完成初始化、开发和测试。
- 开发者修改挂载源码时获得现有后端重载 / 前端热更新；修改依赖时显式构建环境。
- 体验者按 README 完成首次准备后，通过 `./dev up` 启动完整应用，无需理解 Stable、release 或备份系统。
- 管理员和普通用户仍获得符合现有权限的应用状态，不再看到备份提示。

## Observable Behavior

### 1. 首次准备与日常运行

- README 给出唯一推荐顺序：配置 `.env` → `./dev build` → `./dev infra` → `./dev migrate` → `./dev create-admin` → `./dev prepare-model` → `./dev build-rag` → `./dev up`。
- `up` 不自动迁移、创建管理员、重播 Seed 或重建索引。未完成准备时安全失败并提示对应步骤。
- 迁移可在 PostgreSQL 完整健康检查未通过时执行：先等待基础初始化，再迁移，最后等待完整健康，不能形成健康检查与迁移互相等待。
- 日常 `up`、`down`、`status`、`logs` 沿用现有职责；停止保留数据库、Qdrant、模型及 RAG 资产。
- 保留回环端口、单 API 进程、Cookie / CSRF / Origin 边界；端口冲突不停止未知进程。
- 本机路径继续支持 Windows + WSL / Linux；不新增公网、GPU、多 worker 或多副本承诺。
- 应用 / 模型 / 测试在容器中执行；宿主不要求 Python、uv、Node 或本机 `.venv` / `node_modules`。

### 2. 构建与初始化

- 开发 Dockerfile 提供锁定依赖、导出所需 Chromium / 字体及开发工具；运行读取挂载源码。依赖变化显式重建，普通源码变化不要求重建环境。
- 应用 Dockerfile 保留网页构建、后端、导出资产和非 root 运行能力；移除 Stable release 元数据强制门禁、自定义历史缓存选择与运维工具复制。标准 Docker 缓存和可选 OCI revision 标签可以保留。
- 不要求通过构建生成或读取 `.local/release.env`、release 清单或部署状态；不强制 clean Git commit 才能普通本地构建。
- 管理员隐藏输入密码；API 不取得迁移凭据。模型 / RAG 工具可写，API 所需资产只读；保留宿主 UID / GID 和 Chromium sandbox 约束。
- 固定模型 revision、RAG provenance、manifest、集合、关系图和 PostgreSQL catalog 校验继续由既有应用规则裁决；不能随发布兼容矩阵删除。
- Sales Mart 演示数据仅在既有明确初始化 / 重置场景创建；业务只读账号与 Control DB 账号、角色 / grants、数据库结构保持。

### 3. 应用装配与状态

- 保留 bootstrap 的集中装配：配置、数据库、模型客户端、RAG、身份权限、业务服务、生命周期管理和失败清理。
- 保留 `/health` 与 `/ready` 语义、动态依赖检查、过期 / 超时的未知状态、恢复后重新受理，以及安全模型调用观察。
- 保留共享执行额度、取消 / 超时 / 关闭行为、历史 runtime advisory lock / epoch / generation，不能将应用一致性保护误删为 Stable 操作锁。
- 保留 OTel / OTLP 及安全降级；不新增观测平台接入，不删除仍被应用使用的依赖。
- 删除 Stable Unix socket、备份状态文件读取和相关装配；就绪检查不依赖 Stable 挂载或 release 文件。
- `/api/v1/operations/status` 路径、认证、管理员详细状态权限、只读无保活行为及其他字段保持；唯一获准的 API 变更是删除 `details.backup`。
- 网页删除备份时间、逾期及失败提示，保留依赖、模型和执行额度状态及普通用户安全提示。

### 4. 验证入口

- 为 `./dev` 补齐容器验证入口，覆盖 Python 全量回归、前端类型 / 构建 / 浏览器检查、文档 / 模块边界 / Python 质量及隔离数据库集成测试。
- 数据库测试使用专用临时项目 / 空数据库，与日常和旧 Stable 资源隔离；不把 Docker socket 或迁移凭据注入业务 API。
- 容器工具和测试可复用现有脚本的必要能力；仅为选项组织和安全隔离提供薄入口，不建设新的通用编排系统。
- 验证参数、命令组织和调试连接方式在 Design 中确定。调试说明必须可在容器内执行，不再依赖宿主 Python / Node。
- 真实 LLM Evaluation 保留案例、断言与核心链路；操作入口改为容器方式，不把历史报告标为新候选结果。

## Removal Inventory

实施前逐项复核依赖，先迁移仍必要的应用校验，再删除入口。

| 类别 | 候选及处置 |
| --- | --- |
| Stable CLI / Compose | 删除 `local`；删除或替换 `docker-compose.local.yml` 的 Stable 编排，仅保留标准运行所需能力 |
| 运维镜像 | 删除 `docker/operations.Dockerfile` 及 age / 备份 / 恢复工具服务 |
| 发布管理 | 删除 `scripts/local_deployment_state.sh`、`local_build_cache.sh` 及专属发布状态、版本指针和缓存标签机制 |
| 备份与恢复 | 删除 `scripts/local_backup*.py`、`local_backup.sh`、`local_restore*.py`、`local_runtime_binding.py/.sh` 和 `verify_local_backup.py` |
| 发布校验 | `local_release.py`、`local_compatibility.json` 的发布兼容声明移除；模型 / RAG / DB / 网页 / 导出所需门禁迁至已有应用或验证入口 |
| 专属状态 | 删除 `local_operations_status.py`、bootstrap 的备份读取和 Unix socket；保留通用应用状态与 readiness |
| 容器验收 | `local_acceptance.py` / `verify_local_deployment.py` 的隔离、首次部署、持久性和业务验证能力按适用性迁移；删除其 release / backup / restore 依赖 |
| 配置 / 测试 | 清理 Stable 专属模板、变量、资源绑定、挂载及测试；混合测试只移除运维部分，保留应用与容器验证 |

“Stable”语义的指纹、稳定模块边界、正常线程锁和业务执行锁不属于删除目标。现有 `.env.local`、`.local/`、备份、密钥、镜像、容器和持久卷不自动清理或迁移。

## Implementation Decisions

| 决定 | 依据与约束 |
| --- | --- |
| 单一容器开发入口 | 用户明确确认；取消宿主开发教程，保留容器和 CI 内 uv / 锁文件 |
| 源码交付，无镜像发布体系 | 用户确认无需专门维护镜像制品；本机 Docker 构建是运行机制 |
| 保留应用装配和保护 | Bootstrap / API / 执行 Contract 要求；发布精简不能改变应用一致性 |
| 删除备份 API 字段及 UI | 用户明确确认此狭窄例外；不修改其他业务 API、权限或数据结构 |
| 历史资源保留 | 删除仓库运维实现不等于授权删除本机数据；验收使用独立资源 |

不引入新依赖、一级业务模块、通用发布框架或第二套开发入口。必要文件重命名、Compose 服务组织、容器测试参数和门禁复用属于既有边界内的设计选择。

## Compatibility / Documentation

- 现有开发数据、模型缓存与 RAG 资产可继续复用；不要求用户重置数据库或重建已有有效模型 / 索引。
- 旧 `./local` 工作流退出当前支持范围，文档说明旧资源不会自动删除；不提供新的自动接管、搬迁或恢复系统。
- README / Runbook 明确首次配置、初始化、日常启停、构建、容器测试、评测及调试；删除宿主应用运行和 Stable 运维教程。
- Architecture / Product Scope / Roadmap 同步已确认的部署支持边界，不重排功能优先级。
- R7 中现行 readiness / 请求额度 / 状态权限规则迁入适用正式 Spec，修复 Query API、Execution、Observability 等引用后归档已失效的 R6/R7 运维 Spec / Design。
- 历史规划、验收和候选身份保留；不改写为本次完成证据。文档链接检查包含历史记录。

## Testing Decisions / Acceptance

1. 全量 Python 软件回归、既有 SQL Guard / 权限 / 生命周期 / API 测试通过；清理失效的 Stable 测试不导致必要应用测试失去覆盖。
2. 前端类型、网页及导出构建、确定性浏览器测试通过；备份 UI / 字段移除有回归验证，其余状态可见性和无保活保持。
3. 隔离数据库测试覆盖业务只读权限、Control DB migration / checkpoint / history / execution 及业务 / 控制数据边界；启用适用集成开关，逐项报告 skip。
4. 所有保留 Dockerfile 的适用 target 构建通过，锁文件检查通过；Secret 不进入构建上下文、镜像、日志或证据。
5. 独立空卷首次部署按文档顺序完成演示数据、迁移、管理员、固定模型与真实 RAG 索引；验证 `/health`、`/ready`、登录与问数 / 追问 / 分析 / 历史成果 / 导出必要业务闭环。
6. 源码挂载热更新、停止后重新启动的数据与资产持久性、初始化重复执行边界、缺少配置 / 资产 / 索引和端口占用安全失败通过；既有开发 / Stable 资源身份不变。
7. 无 Stable 发布、升级、回滚、备份、恢复、运维锁及专属编排入口；应用启动不依赖 release / backup / socket 资产。当前文档无失效运行指令及引用。
8. 文档、模块边界、Python 质量、适用 CI / 安全检查及 Code Review 完成；全量测试不能只以默认 pytest 中的 skipped 数据库 / 浏览器条件替代。
9. 每项证据记录候选 / 基线、资源、范围、结果及失败 / skip / 未执行项。核心链路与评测案例不变时历史 AI Evaluation 只复用原基线；受影响行为需重跑对应检查。

## Out of Scope

AI 核心链路、模型 / Prompt / SQL Guard、指标口径、权限模型、业务 API（备份字段例外除外）、数据库业务结构、评测案例修改；自研生产运维、镜像仓库发布、多副本、云接入、新数据源、性能承诺；旧 Stable 数据搬迁或资源删除；Push、PR、合并与真实环境替换。

## Further Notes / Authorization

- 用户原始要求授权审查和规划，明确未经确认不修改代码、删除文件、提交或创建 PR。
- 会话已确认开发入口、备份字段例外及完整 Spec；随后用户另行确认四项拆分并授权完整本地实施、验证和相关Commit；Push/PR仍未授权。
- 下一步：只读 Design Review（必要时补实现设计）→ Ticket 草案与当前上下文 Readiness → 用户确认拆分及实施范围 → 按依赖实施。
- 本阶段未运行全量软件测试、容器构建、首次部署或真实模型验收；不得据此宣称 Deployment Simplification 完成。

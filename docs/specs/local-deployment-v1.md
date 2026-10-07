# R6 本地稳定部署 Contract

Status: 用户确认的行为范围已实施；Ticket 01–04 本地实现与适用运行验收完成，最终 clean runtime candidate `2b4a8c8`。事实与限制见 [Acceptance](../acceptance/local-deployment-v1.md)，未发布远端，电脑 / Docker daemon 重启待维护窗口。

需求来源：[R6 完整 Spec](../../.scratch/r6-local-deployment/spec.md)。本文件固化当前已确认的本地稳定运行行为，不构成云端生产部署、容量或可用性承诺。

## 目标与边界

- 目标环境为当前 Windows + WSL2 Linux x86_64 + Docker Engine / Compose；通过 Windows 浏览器访问 WSL 发布的本机回环地址。
- 使用与开发、验收环境分开的配置、Compose project、数据库 / Qdrant 资源和 RAG 目录。业务数据由现有 Sales Mart Schema 与确定性合成 Seed 初始化，不导入开发账号、历史或成果。
- 本地固定版本镜像运行完整应用，不挂载源码、不热更新。API 单进程；Embedding 使用 CPU / FP32；问数和分析沿用用户配置的外部 LLM。
- 本地 HTTP 仅可从 `127.0.0.1` 访问，网页与 API 同源；保留现有 Cookie、CSRF、管理员及 owner 权限 Contract。
- 目标是本地稳定运行和可维护的发布闭环，不代表互联网 / 局域网可访问或完整生产就绪。

## 首次安装和初始化

- 用户显式创建独立稳定配置与随机 Secret；真实 LLM Key 由用户自行填写，不读取或复制开发 `.env`。Secret 不得写入 Git、镜像或日志。
- 用户显式执行镜像构建、PostgreSQL / Qdrant 基础启动、既有数据库 migration、固定 revision 模型准备、RAG 索引构建和首个管理员创建。
- 空 PostgreSQL 稳定卷首次初始化时建立专用运行角色、业务库、Sales Mart Schema 和确定性合成 Seed。后续启动不重播 Seed、不重置账号和历史。
- migration 与管理员创建是分开的交互操作；管理员密码隐藏输入，不通过命令参数传入。
- `up` 只检查前置条件并启动服务，不隐式迁移、下载模型、重建索引或创建管理员。

## 服务操作

| 操作 | 行为 |
| --- | --- |
| `./local build` | 从 clean source commit 构建 API / PostgreSQL 镜像，记录 commit、镜像 tag 和实际 image ID 到 `.local/releases/<commit>.env`，并更新 `.local/release.env` 最新构建指针；运行时按记录校验镜像身份 |
| `./local infra` | 显式启动稳定环境 PostgreSQL / Qdrant，等待基础 Sales Mart 初始化及 Qdrant 私有端口 |
| `./local migrate` | 显式运行当前已有 migration 和 checkpoint 初始化 |
| `./local prepare-model`、`./local build-rag` | 显式准备固定 revision Embedding 模型，并构建稳定环境独立 RAG 索引 |
| `./local create-admin` | 交互创建首个管理员；重复创建遵守既有拒绝行为，不覆盖密码 |
| `./local up` | 校验固定镜像、配置、网页 / 导出资产、管理员、模型、RAG 来源及数据库 catalog 后，后台启动单个 API 进程 |
| `./local upgrade <完整 SHA>` | 只读核验目标兼容声明和当前持久状态；通过后停 API、运行目标 migration、再次核验，再启动目标 API |
| `./local rollback <完整 SHA>` | 先只读核验目标兼容性，再停当前 API 并启动指定旧 API；不运行 migration、不删除数据 |
| `./local down` | 停止 `chatbi-stable` 项目的 API、PostgreSQL、Qdrant；保留命名卷、模型与 RAG 资产 |
| `./local status`、`./local logs [服务]` | 仅定位稳定 Compose project 的容器并查看状态或日志；status 同时显示 `.local/deployment-state.json` 中最后成功版本和最近操作阶段 |

所有会修改配置、镜像、容器或数据的操作由本地非阻塞锁串行化；发生并发时，后到操作以非零状态退出。只读状态、日志和帮助不获取写锁。

## 资源和安全边界

- 项目身份固定为 `chatbi-stable`；稳定 PostgreSQL、Qdrant 使用各自命名卷。数据库与 Qdrant 不发布宿主端口，只有 API 发布到配置的 `127.0.0.1` 端口。
- API 不挂载源码或迁移凭据。数据库迁移器凭据只交给一次性迁移工具；API 只读运行账号访问业务库与 Control DB。
- API 对模型缓存和稳定 RAG 发布目录只读；显式准备工具按当前 WSL 用户身份写入目标目录。
- PNG / PDF renderer 保留 Chromium sandbox；本地 API 配置仓库随附的 Chromium seccomp profile，沿用 R5 已确认的导出隔离要求。
- Secret 使用独立权限受限配置；启动失败诊断不得输出完整 Compose 配置、Secret 或未经授权的数据内容。
- 端口冲突不终止未知进程；启动、资产或依赖检查失败时保留已创建数据和资源，返回非零结果及可操作的恢复提示。
- 手动停止保留所有持久数据。电脑或 Docker 重启后不承诺自动启动，用户可显式执行 `./local up`。
- `/health` 仅代表 HTTP liveness，不代表真实业务请求成功或动态依赖 readiness。

## 版本变更与验收状态

指定版本升级允许短暂停机，必须显式检查目标镜像与数据库 / RAG 资产兼容性；回滚只启动经过验证兼容的旧版本，不执行反向 migration、DROP 或卷删除。不兼容状态必须拒绝并保留数据。每个 API 镜像内嵌 `scripts/local_compatibility.json` 声明可接受状态；检查 Control DB migration marker、checkpoint migration、实际历史快照列与 JSON envelope 版本、Sales Mart Seed、Structure Metadata 指纹、RAG current / manifest 格式、Embedding revision 与来源 provenance。只读 catalog 或兼容状态未知时 fail closed。升级 / 回滚持有同一环境操作锁；`.local/deployment-state.json` 原子记录 active API、PostgreSQL 实际 image ID、运行状态及最后成功或失败阶段。失败不回退已成功的 active 记录，也不伪报 API 仍在运行；migration / 启动失败后保留数据，由用户显式选择兼容版本恢复。

真实版本对的升级、兼容回滚、再次升级及账号 / 历史 / 成果读取验收见 [R6 Ticket 03记录](../../.scratch/r6-local-deployment/issues/03-compatible-upgrade-rollback.md)。Ticket 04 的 Windows Edge 完整业务与专用服务停止恢复验收已通过，见 [Acceptance](../acceptance/local-deployment-v1.md)；不替代电脑 / Docker daemon 重启或 R7 保障验收。

Ticket 02 的独立环境安装、空卷初始化、持久性、端口冲突与真实问数验收已完成；clean 候选和证据身份见 [Ticket 02记录](../../.scratch/r6-local-deployment/issues/02-isolated-local-runtime.md)。Ticket 03 的真实版本对兼容升级 / 回滚 / 再升级与持久状态指纹验收已完成，证据见 [Ticket 03记录](../../.scratch/r6-local-deployment/issues/03-compatible-upgrade-rollback.md)。Ticket 04 的 Windows Edge 完整业务、三格式下载 / 内容及专用服务恢复验收已完成，最终运行身份和 IDM 下载条件见 [Acceptance](../acceptance/local-deployment-v1.md)。任何本地 smoke、`/health` 或单元测试都不单独代表完整验收通过。

完整验收范围见 [R6 Spec 的 Testing Decisions](../../.scratch/r6-local-deployment/spec.md)；本地操作见 [Runbook](../runbook.md) §15。

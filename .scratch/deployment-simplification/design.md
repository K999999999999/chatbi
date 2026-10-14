# Deployment Simplification 实现设计

依据：[已确认 Spec](spec.md)。Owner: 当前实施 Agent；基线 `f4d0693`。本文件记录 Contract 内的实现选择，不授予实施或发布权限。

## 最终入口与依赖

- `dev` 保持 Bash + Docker CLI 的薄入口；日常源码开发仍采用基础 Compose 加开发 override，不改变现有日常卷名、模型路径和端口默认值。
- 增加容器工具入口：`./dev test [python|database|web|renderer|all]`、`./dev check`、`./dev evaluate [原评测参数]`。`all` 不隐式调用收费真实模型；真实业务验收显式进入隔离验收入口。
- 未指定 test 子项默认 python；未知选项返回 2，检查或测试失败保留原退出码。`check` 包含锁文件、文档 / 边界、Python 质量及前端类型 / 构建。命令帮助不启动服务。
- 不新增包依赖。开发镜像中的 Python/Node、uv 和锁文件继续使用当前版本。CI 可以沿用原生 uv/npm 执行，不强迫所有 CI 改为 Docker。
- `.devcontainer` 保留为容器内编辑工具，统一调用同一 `dev` 流程，不建立第二套宿主应用启动指南。

## 容器测试与调试

- 新增仅测试使用的 Compose override / profile，挂载源码、tests、evaluation、必要文档与 Git 元数据；测试报告输出到 ignored 目录。工具容器不得复制宿主 `.venv` / `node_modules`。
- 全量 Python 测试由开发 Python 镜像直接执行 `python -m pytest`；Git/文档检查和依赖检查在工具容器内执行，不依赖宿主 Python。
- 数据库测试的 Docker 创建 / 标签核验 / 清理由宿主 Bash 完成；Python migration 和 pytest 在测试容器执行。复用现有 fixture/profile 规则，不挂 Docker socket到业务 API，也不依赖测试容器安装 Docker CLI。
- CI fixture 与 development fixture 分别在唯一临时 project 中执行，后者覆盖 `RUN_DEVELOPMENT_DATABASE_TESTS=1` 对应的 RBAC、checkpoint、history、execution 与 fingerprint。生成专用凭据，失败时保留安全证据；只清理匹配本次 project 标签的资源。
- 浏览器测试复用 Node browser target；mock API 在 Python 测试服务运行，前端在 Node 测试服务运行，共用临时网络。Playwright 配置支持已启动的容器 fixture，保留 CI 原有默认行为和测试断言，不通过宿主 `uv run` 拉起服务。
- 浏览器 target 安装并配置现有测试需要的浏览器渠道，不能以容器缺少 Chrome 为由跳过用例。PDF renderer 显式开启 `CHATBI_EXPORT_PDF_RENDER_TEST=1`，沿用导出 manifest、字体和实际 Chromium。
- 容器内调试使用现有 Python `pdb` / `breakpoint()` 和交互 exec；说明如何停下自动重载服务后运行单个调试进程，不新增 debugger 依赖或同时启动第二个 history runtime。
- 测试全部结束后，以汇总返回码和 skip 原因报告；数据库、renderer和浏览器套件需单列，不让默认 pytest 成功掩盖条件跳过。

## 应用保护与运维解耦

- 保留 `OperationsState`、`OperationsMonitor`、`ProcessReadinessProbe` 和 `ObservedModel` 的依赖就绪 / 模型 / 容量部分。类名是否局部调整不影响公共 Contract，不为改名制造全仓重构。
- 删除 backup provider、`details.backup`、Unix socket 装配与网页备份分支。API 权限、readonly authentication、no-store和无保活行为不变。
- `bootstrap.readiness`、Control schema、RAG manifest / provenance / Qdrant collection 和 catalog仍是权威校验；移除任何对 `scripts.local_release` 的必要引用。
- Stable `verify_runtime` 中必要检查逐项映射到既有启动 / 初始化 / 验收检查：migration权限、模型 revision、RAG完整性、静态网页、导出 manifest、管理员准备和演示数据。发布 commit、exact版本矩阵、快照版本发布声明不迁入新工具。
- 缺少管理员仍是显式初始化问题，缺少必要资产必须有安全错误；不改变开发启动门禁为生产模式，不放松 production Cookie/RAG规则。
- 保留应用 advisory lock、epoch、generation、导出 runtime lock、并发额度和停止保护；与已删除的宿主运维操作锁明确区分。

## 标准应用 Dockerfile 与 Compose

- 将 `docker/local.Dockerfile` 收敛为根 `Dockerfile`，保留 api / database targets。删 release JSON、compatibility JSON、cache commit/release commit 双身份和 Stable工具复制；可选 OCI revision 仅为信息标签。
- database target仍包含既有角色初始化、DDL、grants和演示 Seed；不更改 SQL 文件。构建上下文显式允许 `database/dev/seed_sales_mart.sql`，修复当前 `.dockerignore` 未覆盖该 COPY 的缺口。
- 标准应用 Compose 使用本地 build，不读取 `.local` / `.env.local` / release.env，不使用 external Stable卷或 restore binding。API、PG、Qdrant及显式 tools足够，无 backup / operations / restore服务。
- 标准应用 Compose 是 Dockerfile 运行验证及可选打包应用的入口，不提供新的日常开发 CLI；README唯一推荐仍是 `dev`。
- 初始化遵循 infra → 基础初始化 → migrate → 完整PG healthy → admin / model / rag → API；migrator不以完整healthy为启动前提，API可依赖完整healthy。
- 模型 / RAG使用独立标准卷或已确认的可配置目录；API只读，初始化工具可写，非root身份与Chromium seccomp保持。持久卷按Compose project隔离，不引用旧 Stable卷。
- 应用 Compose配置仅给API运行凭据，给 migrator必要迁移凭据。生成配置或验收凭据不输出完整Compose配置到日志。

## 迁移切片、删除与失败处理

1. Migrate application：完成应用状态与运维解耦、迁移必要校验，单独验证应用不需要socket/备份/发布文件。
2. Expand container tooling：补齐容器测试、检查和评测入口，独立验证无需宿主Python/Node。
3. Contract Stable：标准Dockerfile/Compose可构建与初始化后，删除Stable CLI、工具、配置和专属测试；重查所有消费者。
4. Cleanup / acceptance：迁移正式当前Contract、归档运维文档、修复历史链接，完成全量及独立首次部署验证。

旧真实资源不启停、不接管、不删除。仅一次性验收资源按标签清理。源码切片可通过Git历史恢复，由当前目标的修复提交处理；不回退用户改动、不提供新的应用内rollback机制。任一切片失败暂停后续删除。无数据库Schema变更，无不可逆数据迁移，无实际运行流量切换，因此不增加Feature Flag或生产rollout流程。

## 替代方案与选择依据

| 方案 | 影响 | 选择 |
| --- | --- | --- |
| 整块删除R7 operations | 会破坏受理、就绪、状态权限和生命周期 | 拒绝；仅删除运维部分 |
| 继续保留宿主测试 / 让工具容器持有Docker socket管理全部环境 | 前者违反无需宿主Python，后者增加特权与隐藏依赖 | 宿主Bash管理Docker，测试容器执行程序 |
| 只保留开发Dockerfile，删除应用构建能力 | 丢失已确认的标准应用容器能力 | 保留简化应用Dockerfile，不维护release体系 |
| 将所有CI重写为容器 | 增加范围，无助于本地统一入口 | 保留有效CI，仅清理失效引用和补必要容器验证 |

Owner为当前目标实施Agent；若需要新依赖、公共API例外扩大、模型/权限/数据结构变化或真实资源迁移，停止并返回Spec确认 / Design Review。

## 验证映射

每个切片先执行受影响的确定性验证并做Code Review；最终在同一候选上运行全量回归、两种PG profile、浏览器、renderer、所有保留Dockerfile target构建，以及独立空卷开发/标准应用Compose初始化、健康、热更新、持久性、失败边界和真实业务闭环。模型下载与LLM配置不可用时明确未执行及恢复条件，不以mock或历史报告替代。

最终搜索当前运行代码/配置/CI/文档中的旧消费者，白名单仅允许归档历史、解释旧资源保留和稳定语义非运维用途。正式文档归档先检查独有内容及全部链接。正式AI Evaluation的案例和核心链路不改，是否重跑按受影响行为记录理由。

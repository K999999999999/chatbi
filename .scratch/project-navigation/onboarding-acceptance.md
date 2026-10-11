# 隔离新人上手验证记录

Date: 2026-10-11
Branch / base: `docs/project-navigation` / `b0af01e4d886df56d58433f6c34e8ec852ebaeef`
Scope: Ticket 03；只验证新 clone 的本地初始化 / 健康 / 确定性测试路径，不做真实业务问数或 LLM Evaluation。

## 导航作者模拟走读

Date: 2026-10-12
Reader: 导航作者（模拟首次接手者；不计作 Spec 要求的非作者独立走查）

按“README → 项目导航推荐阅读路线 → 产品边界 / 架构 → 能力地图 → 在线问数代码链 → Runbook 首次启动与测试”顺序走读。能从能力表定位 `OnlineQueryService.execute`、`OnlineRetriever.retrieve`、授权服务、SQL Guard、数据库访问及对应 Spec / 测试；启动前提、显式初始化次序、健康检查边界和确定性测试命令也能找到。抽查的代码入口与当前源码定义相符。

第一遍发现并修正三处入口问题：README 的项目导航链接原先只出现在较后面的文档列表，现已前移到概览后；README 把“生产部署与运行保障尚未完成”合并描述，和 R7 本机 Stable 恢复已验收的现状矛盾，现改为明确区分“本机 Stable 保障已核验”和“公网生产部署未完成”；导航路线中的 Roadmap 阅读范围现指向“当前阶段”。

第二遍重新从 README 冷读，发现 Roadmap 的“当前阶段”虽有准确状态，但主体是连续的历史验收长段落，新人仍需自行提炼现状。已在该节添加“新读者先看”四点速览，并将导航链接改为直达速览；历史阶段细节仍可按需查阅。第二遍能按路线走到项目边界、主链路代码 / Spec / 测试，以及 Runbook 的配置、启动、健康和软件测试入口，没有遇到必须口头补充才能继续的断点。

两遍模拟均未发现无法继续阅读的路径断点。后续 README 审查确认页面仍同时承担概览、完整模块地图和逐版本功能说明；已按 Spec 收敛为项目入口、推荐容器快速开始、主链路和文档索引，并加入首次 clone Hook 安装提示。测试命令标明由宿主机 `uv` / Python 3.11 运行。链接和 Diff 检查通过；未运行软件测试（纯文档变化）。由于走读者是导航作者，模拟不能证明其他新人不需要口头补充；Spec 第 1 项和 Ticket 03 第 4 项仍等待非作者独立走查。

## 非作者独立新人走查

Date: 2026-10-12
Reader: 未参与导航编写的独立审阅者；未查看本工作项作者模拟记录。只读跟随 README → 项目导航 → Product Scope / Architecture / Roadmap / Runbook 和在线问数代码路线；未运行软件测试、服务或其他有副作用的命令。

| 走查项 | 首轮结果 | 处理与复核 |
| --- | --- | --- |
| 产品边界与成熟度 | PARTIAL：[`docs/product-scope.md`](../../docs/product-scope.md) 将导出列在“当前明确不包含”，后文又说明 R5 已实现。 | 将第 61 行改为“成功快照文件导出已实现并作为 R5 交付”；独立审阅者复核 PASS，歧义已消除。 |
| 能力到代码、权威事实与验证 | PASS：能力地图能定位代码及 Spec / Design / 测试 / Acceptance。 | 无需修正。 |
| 核心在线问数链路 | 首轮链路本身 PASS；另发现导航链接到 [`docs/specs/online-retrieval.md`](../../docs/specs/online-retrieval.md) 时没有突出当前契约实际位于 `.scratch/`。 | 在能力地图和链路事实源说明中直链 [Online Retrieval V1 当前契约](../../.scratch/online-retrieval-v1/spec.md)，并将旧文档标成历史基线；独立审阅者复核 PASS，链接有效。 |
| 本地启动、健康检查和确定性测试 | PASS：Runbook 步骤、命令和健康检查边界均可找到。 | 无需修正。 |

独立审阅者在初次阅读中报告的两处卡点均已修复并由该审阅者复核。Markdown 本地链接检查通过。该走查验证导航阅读路径，不替代软件测试、真实业务验收或 LLM Evaluation。

## 隔离边界

- 使用本任务的新 Git worktree `/home/jojo/Projects/chatbi-engine-project-navigation`；开始时确认 `.env`、`data/`、`.model-cache/` 不存在。
- 生成只供此次运行使用的本地配置和随机数据库 / 管理员 / Qdrant 值；没有读取、复制或复用现有 `.env`、Stable / Dev 配置或用户数据。
- Compose 项目 `chatbi-project-navigation-onboarding` 使用独立 API `18080`、Web `15173`、PostgreSQL `15433`、Qdrant `16333` 端口，以及独立数据库和 Qdrant 卷。
- 既有容器 / 镜像可能共用全局默认标签，因此 Compose 使用专用标签尝试冷构建；完成后仅在本任务项目边界内核对和清理资源。

## 命令与结果

| 步骤 | 命令 / 动作 | 结果 |
| --- | --- | --- |
| 冷构建 | `CHATBI_DEV_COMPOSE_OVERRIDE=… COMPOSE_PROJECT_NAME=… ./dev build` | 两次受 Debian 镜像站 HTTP 502 阻塞：先有 3 个包返回 502，重试时 security InRelease 返回 502。专用 Node 镜像构建成功；专用 Python 镜像没有完成。 |
| 隔离基础服务 | `./dev infra`，使用唯一 Compose 项目 | PostgreSQL / Qdrant 容器和两个带项目标签的专用卷创建成功。 |
| 首次 Schema 初始化 | `./dev migrate` | 成功；PostgreSQL 变为 healthy。 |
| 首个管理员 | `./dev create-admin --username onboard-admin` | 成功；密码仅为本次 disposable 数据库输入，不是用户凭据。 |
| 固定模型 | `./dev prepare-model` | 首次请求受 Xet 日志权限 / 网络问题影响；隔离工具容器设置 `HF_HUB_DISABLE_XET=1` 后恢复并下载固定 BGE-M3 revision，目录约 2.1 GB，`ready=true`。没有 HF Token。 |
| RAG 构建 | `./dev build-rag` | 首次因 disposable `.env` 中 Qdrant 服务键与客户端键不同而收到 401；修正本地测试配置后成功发布：TABLE 7、COLUMN 69、METRIC 7、关系 9，`failure_count=0`。 |
| 服务启动 | `./dev up` | API、Web、PostgreSQL、Qdrant 均 healthy。受冷构建 502 影响，运行服务使用本机已经存在的 `chatbi-python-dev:local` / `chatbi-node-dev:local` 标签；这证明隔离启动路径可运行，但不是从零构建的证明。 |
| HTTP 检查 | `curl --fail … http://127.0.0.1:18080/health`；请求 `http://127.0.0.1:15173/` | API HTTP 200；Web HTTP 200。没有发起真实 LLM / 业务查询。 |
| 全量确定性 Python 测试 | `CHATBI_WEB_ORIGIN=https://test.invalid LANGCHAIN_OPENAI_TCP_KEEPALIVE=0 uv run --python 3.11 --locked python -m pytest -q` | `1035 passed, 44 skipped, 142 subtests passed`，72.71 秒。 |
| 测试配置复核 | `CHATBI_WEB_ORIGIN=https://example.invalid uv run --python 3.11 --locked python -m pytest tests/query_api/test_main.py::QueryApiIntegrationTest::test_production_startup_verifies_rag_and_live_database_schema -q` | `1 passed`；验证 Runbook 推荐的无额外 LangChain 覆盖命令形式。 |
| Web 类型检查 | 隔离 Web 容器内 `npm run typecheck` | 退出码 0。 |
| 独立 PostgreSQL 集成测试 | `uv run python scripts/run_database_tests.py` | `5 passed`；使用一次性测试容器，与 Dev / Stable 数据隔离。 |
| Markdown / Diff 检查 | `python3 scripts/check_markdown_links.py`、`git diff --check` | 通过。 |

初次全量 Python 测试未覆盖 `CHATBI_WEB_ORIGIN` 时，1 个 production startup 测试从本机 `.env` 读到开发用 loopback HTTP Origin 而失败（其余 `1034 passed, 44 skipped, 142 subtests passed`）。Runbook / README / 项目导航现在说明并使用 `CHATBI_WEB_ORIGIN=https://example.invalid` 覆盖测试进程配置；该保留域名不会被请求。

## 清理与残余限制

- 先按 Compose 项目标签确认本次创建的 4 个容器、1 个网络和 2 个卷，再只对 `chatbi-project-navigation-onboarding` 执行 `down --volumes`；三个 runtime 资源类别已不存在。
- 移除了此次创建的唯一专用 Node 镜像标签、隔离 worktree 中的 `.env`、`.model-cache/`、`data/`、测试 `.venv/` 及 `/tmp` Compose Override。清理前确认这些路径在该新 worktree 初始状态不存在。
- 清理后，原 `chatbi-engine-postgres-1` / `chatbi-engine-qdrant-1` 仍运行，既有 Dev / Stable Postgres 和 Qdrant 卷仍存在。
- 由于两个系统包源 HTTP 502，没有证明当前网络下能从零完成 Python 镜像构建；使用已有镜像后的容器启动、迁移、健康和测试路径已通过。Runbook 保留了网络和依赖前提。
- 非作者独立走查已按阅读路线检查关键能力，并对两处修订复核通过；此记录不表示审阅者已在隔离新 clone 中实际执行整张自查清单。真实 LLM Evaluation、浏览器全业务 Acceptance 和公网生产就绪均未执行 / 声明。

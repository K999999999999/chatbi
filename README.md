# ChatBI 0.1.0

ChatBI 是一个面向业务数据查询的 Domain AI Engine（领域 AI 引擎），当前处于 MVP 向生产演进阶段，采用 Modular Monolith（模块化单体）。它把自然语言问题转换为业务语义、受控 SQL 和数据库结果，并通过确定性程序校验模型候选。

当前 MVP 已包含电脑端 Web 登录 / 对话与经营分析入口、自然语言查询、在线 RAG、登录与 RBAC、多轮查询、经营分析、私人历史与独立固定成果。生产部署与运行保障尚未完成；当前候选的 AI Evaluation 状态以候选身份对应的报告为准，历史基线只适用于其报告记录的 commit。本地 Runbook 不代表已完成生产部署。包版本号来源于 [`pyproject.toml`](pyproject.toml)，精确代码状态以 Git commit 为准。

## 新 clone：快速开始

推荐开发入口为 WSL / Linux 容器环境：仅需 Git、Bash 和 Docker，使用 `./dev` 管理前后端与基础设施，支持源码热更新。首次显式执行 `build`、`infra`、`migrate`、`create-admin`、`prepare-model`、`build-rag`，随后 `./dev up`；日常使用 `up / down / status / logs`。保留以下宿主调试方式；Dev Container 配置保留，不作为本次验收入口。完整步骤、环境变量说明和故障排查见 [`docs/runbook.md`](docs/runbook.md)。

### 容器开发（推荐）

复制 `.env.example` 为 `.env`，填入本机配置后运行：

```bash
./dev build
./dev infra
./dev migrate
./dev create-admin --username admin-1
./dev prepare-model
./dev build-rag
./dev up
```

打开 `http://127.0.0.1:5173`。日常启动 `./dev up`，停止 `./dev down`，查看 `./dev status` / `./dev logs --follow`。

### 宿主调试（可选）

1. 从 [`.env.example`](.env.example) 复制出本地 `.env`，按 Runbook 配置服务地址和本地 Secret。不要提交 `.env`。
2. 在 WSL / Linux 终端执行 `uv sync --locked`；安装 Node 24，在 `frontend/` 执行 `npm ci`。
3. 在仓库根目录启动基础服务并按顺序完成首次 Control DB migration：

   ```bash
   docker compose up -d postgres qdrant
   docker compose exec -T postgres sh /workspace/database/init/wait_for_base_initialization.sh
   uv run --env-file .env python -m src.bootstrap migrate
   docker compose up -d --wait postgres qdrant
   ```

   首次初始化会建立完整 Sales Mart、确定性合成开发 Seed 和 Control DB 基础 Schema；`migrate` 还会安装 Business Analysis checkpoint。必须在 migration 后等待 PostgreSQL healthy。日常启动不会重播 Seed；Qdrant 不会自动生成向量索引。
4. 首次运行时，按 Runbook 显式创建首个管理员，准备固定版本的 BGE-M3 模型并从当前 Schema Metadata / Metrics 构建 RAG 索引。
5. 按 Runbook 启动 API 和页面，然后运行确定性测试或需要的 Evaluation（评测）。

容器日常开发使用 `./dev up`；宿主调试另外启动 API 和页面。PostgreSQL 数据会保留，RAG 索引不会随服务启动自动重建。生产服务启动会验证 PostgreSQL Schema、Structure Metadata、Metrics、Embedding 配置与当前 RAG manifest 的一致性；不匹配时拒绝 Ready。PostgreSQL 重置和 Qdrant 索引重建是分开的显式操作，详见 Runbook。

## 主链路

```text
Natural Language
  → Business Semantic Resolution
  → Online Retrieval / certified context
  → LLM proposes SQL candidate
  → deterministic SQL Guard
  → read-only PostgreSQL
  → Query API response / Web display
```

核心原则是 `Model proposes, program decides`：LLM 只提出候选，程序和权威事实最终决定业务口径、数据范围、SQL 安全和数据库执行。

离线资产链路把已确认的结构事实和指标事实构建为 TABLE、COLUMN、METRIC 文档、BGE-M3 dense/sparse Embedding、Qdrant 集合和 Relationship Graph（关系图），供 Online Query 使用。

## 模块地图

| 模块 | 代码入口 | 当前职责 | 详细说明 |
| --- | --- | --- | --- |
| Online Query | [`src/online_query/`](src/online_query/)；`OnlineQueryService.execute()`、`OnlineRetriever.retrieve()` | 授权后的查询编排、上下文、Online Retrieval、SQL Guard 和数据库执行 | [`docs/specs/online-query.md`](docs/specs/online-query.md)、[`docs/specs/online-retrieval.md`](docs/specs/online-retrieval.md) |
| Query API Adapter | [`src/query_api/`](src/query_api/)；`src/query_api/main.py`、`AuthorizedQueryService.query()` | HTTP `POST /api/v1/query` 和 `GET /health`，负责服务端身份授权后调用 Online Query | [`docs/specs/query-api.md`](docs/specs/query-api.md) |
| Web Frontend | [`frontend/`](frontend/) | React + TypeScript + Vite 电脑端登录、问数 / 追问、经营分析及证据展示；只通过 HTTP 访问 API | [Web Spec](docs/specs/web-dialogue-v1.md) |
| ChatBI Account & Admin | [`src/chatbi_control/`](src/chatbi_control/)、[`src/authorization/`](src/authorization/) | 内置账号、数据库 Session、固定角色权限、SQLAdmin 和持久化安全审计 | 初始化见 [`docs/runbook.md`](docs/runbook.md) |
| 应用初始化与装配 | [`src/bootstrap/`](src/bootstrap/)；`python -m src.bootstrap --help` | 运行资源装配、启动检查、失败清理 / 关闭和四类显式初始化命令 | [`docs/specs/bootstrap.md`](docs/specs/bootstrap.md) |
| Business Analysis | [`src/business_analysis/`](src/business_analysis/) | 受控的分析任务拆解、校验、授权查询执行、结果汇总和总结 | [`docs/specs/query-api.md`](docs/specs/query-api.md) |
| RAG Offline Build | [`src/rag_offline/`](src/rag_offline/)；`python -m src.bootstrap build-rag` | 事实校验、文档构建、Embedding、Qdrant、关系图和资产发布 | [`docs/specs/rag-offline-build.md`](docs/specs/rag-offline-build.md) |
| Evaluation | [`evaluation/`](evaluation/)；`python -m evaluation` | 标准案例执行、结果比较和评测报告 | [`docs/specs/evaluation.md`](docs/specs/evaluation.md) |
| Observability | [`src/observability/`](src/observability/) | Trace Contract、No-op、OpenTelemetry 和安全属性处理 | [`docs/specs/observability.md`](docs/specs/observability.md) |

## 仓库地图

| 路径 | 用途 |
| --- | --- |
| `frontend/` | 电脑端网页、npm lockfile 与 Playwright 浏览器验收 |
| `src/` | 产品源码、模块入口和生成的结构事实 |
| `tests/` | Software Test（软件测试）和集成测试 |
| `scripts/` | Metadata Export 和本地开发脚本 |
| `database/` | PostgreSQL DDL、初始化、开发 Seed 和 CI Fixture |
| `docs/` | Architecture、Runbook、Module Spec、Implementation Design 和验收证据 |
| `.scratch/` | 本地 Feature 的 Spec、Ticket 和过程记录 |
| `reports/` | 历史报告和评测证据；本地生成输出按 `.gitignore` 管理 |
| `data/`、`models/`、`.venv/`、`.idea/` | 本地生成数据、模型、环境和 IDE 资产，不属于产品源码 |

当前数据基线包含 7 张表、69 个字段、25 条关系事实和 7 个业务指标；这些数量以对应源文件为准。单轮、多轮和经营分析 Golden Set 分别有 29 个案例、7 个对话和 10 个案例，Query Understanding 的 6 个案例作为辅助评测。

Schema 维护顺序是 `database/` DDL → 更新实际 PostgreSQL → 从 PostgreSQL catalog 导出 `src/structure/generated/`。`src/semantic/metrics.json` 是指标定义事实源；Structure JSON 是 Schema 导出投影；Qdrant 与 `data/rag/` manifest 是派生产物。PostgreSQL / Qdrant 运行数据、BGE-M3 模型和 `.env` 不提交到 Git。

## 验证与文档入口

常用确定性回归：

```bash
uv run --python 3.11 --locked python -m pytest -q
```

纯软件测试验证确定性软件行为，不证明真实 LLM 准确率或 Production Readiness。数据库集成测试、RAG Build、真实 LLM Evaluation 和 Business Acceptance（业务验收）属于不同证据层级。

- [`docs/runbook.md`](docs/runbook.md)：新 clone、首次初始化、日常启动、重置、RAG 构建、测试、评测和故障排查。
- [`docs/product-scope.md`](docs/product-scope.md)：当前 MVP Contract 和生产演进边界。
- [`docs/architecture.md`](docs/architecture.md)：稳定架构、模块边界和代码地图。
- [`docs/specs/`](docs/specs/) 与 [`docs/designs/`](docs/designs/)：模块行为契约和实现设计。
- [`tests/`](tests/) 与 [`docs/acceptance/`](docs/acceptance/)：确定性测试和历史验收证据。历史结果只代表对应运行时；修改代码后应基于当前 commit 重新验证。

## 电脑端 Web 入口

当前默认入口为 React + TypeScript + Vite 网页。开发 / 打包入口见 [Runbook](docs/runbook.md#web-开发与打包)，行为见 [Web Spec](docs/specs/web-dialogue-v1.md)，证据见 [R1 验收](docs/acceptance/web-dialogue-v1-20261003.md)。Streamlit 已移除。刷新保留有效登录但清空当前对话；图表、长期历史和流式按后续路线推进。

### 结果图表与表格（R2）

问数同时展示可信结果图表和表格，支持指标卡、时间趋势、分类对比、单位拆图、千分位金额和百分比；原始返回值可核对。经营分析展示后端已对账的产品与因素贡献。图表绘制及切换不重新查询；未知语义或图表故障保留原始表格。详见[R2行为](docs/specs/result-visualization-v1.md)、[设计](docs/designs/result-visualization-v1.md)和[运行说明](docs/runbook.md#r2-图表与数字展示)。

R3 的刷新重开、完整条件恢复与成果生命周期见 [History Spec](docs/specs/history-results-v1.md)，当前本地验收入口见 [Acceptance](docs/acceptance/history-results-v1.md)。

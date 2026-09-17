# ChatBI 0.1.0

ChatBI 是一个面向业务数据查询的 Domain AI Engine（领域 AI 引擎），当前采用 Modular Monolith（模块化单体）。它把自然语言问题转换为业务语义、受控 SQL 和数据库结果，并通过确定性程序校验模型候选。

当前是 `0.1.0` Development Snapshot（开发快照），不是 Production Ready（生产可用）系统。版本号来源于 [`pyproject.toml`](pyproject.toml)；当前精确开发状态以 Git commit 和 `git describe --tags --always` 为准。`Streamlit`、测试页面和部分评测场景可以称为 POC（验证入口），但不能用 POC 概括整个 ChatBI。

## 先看什么

新开发者建议按下面顺序阅读：

1. 本 README：项目定位、主链路、模块和当前状态。
2. [`docs/architecture.md`](docs/architecture.md)：稳定架构、模块边界和代码地图。
3. [`docs/runbook.md`](docs/runbook.md)：本地环境、启动、测试、RAG Build、评测和故障排查。
4. 对应的 [`docs/specs/`](docs/specs/) 和 [`docs/designs/`](docs/designs/)：Module Contract（模块契约）和实现设计。
5. 对应的 [`tests/`](tests/) 与 [`docs/acceptance/`](docs/acceptance/)：确定性测试和历史验收证据。

当前 Feature 的工作地图见 [`workspace-map.md`](.scratch/repository-structure-readability/workspace-map.md)。

## 主链路

```text
Natural Language
  → Business Semantic Resolution
  → Online Retrieval / certified context
  → LLM proposes SQL candidate
  → deterministic SQL Guard
  → read-only PostgreSQL
  → Query API response / Streamlit display
```

核心原则是 `Model proposes, program decides`：LLM 只提出候选，程序和权威事实最终决定业务口径、数据范围、SQL 安全和数据库执行。

离线资产链路独立负责把已确认的结构事实和指标事实构建为 TABLE、COLUMN、METRIC 文档、BGE-M3 dense/sparse Embedding、Qdrant 集合和 Relationship Graph（关系图），再由 Online Query 使用已发布资产。

## 模块地图

| 模块 | 代码入口 | 当前职责 | 状态和证据 |
| --- | --- | --- | --- |
| Online Query | [`src/online_query/`](src/online_query/)；`service.py` 的 `OnlineQueryService.query()`、`retrieval/` 的 `OnlineRetriever.retrieve()`、`sql_guard/` 的 SQL 校验入口 | 查询编排、上下文、Online Retrieval、SQL Guard 和数据库执行；根目录保留核心 Contract 与外部能力适配，复杂子域按目录组织 | 已实现；见 [`docs/specs/online-query.md`](docs/specs/online-query.md)、[`docs/specs/online-retrieval.md`](docs/specs/online-retrieval.md) 和 [`tests/online_query/`](tests/online_query/) |
| Query API Adapter | [`src/query_api/`](src/query_api/)；`src/query_api/main.py` | HTTP `POST /api/v1/query` 和 `GET /health`，只适配 Online Query | 已实现；见 [`docs/specs/query-api.md`](docs/specs/query-api.md) 和 [`tests/query_api/`](tests/query_api/) |
| Streamlit | [`src/streamlit_app.py`](src/streamlit_app.py) | 通过 HTTP 调用 Query API 的当前验证页面和内部入口 | POC / 内部入口；见 [`tests/streamlit/`](tests/streamlit/) |
| RAG Offline Build | [`src/rag_offline/`](src/rag_offline/)；`python -m src.rag_offline` | 事实校验、文档构建、Embedding、Qdrant、关系图和资产发布 | 已实现；见 [`docs/specs/rag-offline-build.md`](docs/specs/rag-offline-build.md) 和 [`tests/rag_offline/`](tests/rag_offline/) |
| Evaluation | [`src/evaluation/`](src/evaluation/)；`python -m src.evaluation` | 标准案例执行、结果比较和评测报告 | 已实现；见 [`docs/specs/evaluation.md`](docs/specs/evaluation.md) 和 [`tests/evaluation/`](tests/evaluation/) |
| Observability | [`src/observability/`](src/observability/) | Trace Contract、No-op、OpenTelemetry 和安全属性处理 | V1 已实现；见 [`docs/specs/observability.md`](docs/specs/observability.md)、[`tests/observability/`](tests/observability/) 和验收记录 |

## 工作区地图

| 路径 | 用途 |
| --- | --- |
| `src/` | 产品源码、模块入口和生成的结构事实 |
| `tests/` | Software Test（软件测试）和集成测试 |
| `scripts/` | Metadata Export 和本地开发脚本 |
| `database/` | PostgreSQL DDL、权限和 CI Fixture |
| `docs/` | Architecture、Runbook、Module Spec、Implementation Design 和验收证据 |
| `.scratch/` | 当前 Feature 的 Spec、Ticket 和过程基线 |
| `reports/` | 历史报告和评测证据；本地生成输出按 `.gitignore` 管理 |
| `data/`、`models/`、`.venv/`、`.idea/` | 本地数据、模型、环境和 IDE 资产，不属于产品源码 |

权威离线输入位于 [`src/structure/generated/`](src/structure/generated/) 和 [`src/semantic/metrics.json`](src/semantic/metrics.json)。本地 PostgreSQL、Qdrant、BGE-M3 和 `.env` 不提交到 Git，也不把 Secret 写入文档、日志或测试数据。

## 当前状态与验证证据

项目成熟度分开描述：

- 版本：`pyproject.toml` 声明 `0.1.0`；当前是 Git 开发快照，不是当前 HEAD 的发布 tag。
- 开发状态：Online Query、Online Retrieval V1、RAG Offline Build、Query API、Evaluation 和 Observability V1 已有代码与对应测试 / 验收文档。
- POC 范围：`Streamlit` 是当前内部验证页面；测试入口和部分评测场景可以使用 POC 术语。
- 验证证据：Software Test、真实 PostgreSQL/Qdrant 集成、BGE-M3/RAG Build、真实 LLM Evaluation 和 Business Acceptance 是不同证据层级，不能互相替代。
- 生产状态：当前仍不是 Production Ready；认证、用户和数据权限、审计、限流、性能与负载、Secret 管理、生产部署和回滚仍需按真实需求推进。

常用确定性回归命令：

```powershell
uv run --with pytest python -m pytest -q
```

该命令证明给定输入下的软件行为，不证明真实 LLM 准确率或 Production Readiness。完整启动、数据库集成、RAG Build 和真实 LLM Evaluation 命令见 [`docs/runbook.md`](docs/runbook.md)。历史验收入口见 [`docs/acceptance/`](docs/acceptance/)，其中的结果是对应运行时的证据快照，重新修改代码后应按当前 commit 重新验证。

## 运行和开发入口

- 本地配置：复制 [`.env.example`](.env.example) 为 `.env`，只在本地填写真实配置。
- 基础设施：按 [`docs/runbook.md`](docs/runbook.md) 启动 PostgreSQL 和 Qdrant。
- API：`uv run uvicorn src.query_api.main:app --host 127.0.0.1 --port 8000`。
- 页面：`uv run streamlit run src/streamlit_app.py --server.address 127.0.0.1 --server.port 8501`。
- 结构事实导出：[`scripts/metadata/export_schema.py`](scripts/metadata/export_schema.py)，只读取数据库系统目录并生成结构资产。
- Feature 工作流：Spec 和 Ticket 使用 `.scratch/`，规则见 [`docs/agents/issue-tracker.md`](docs/agents/issue-tracker.md)。

README 只做入口导航；启动参数、环境变量、测试分层、故障排查和停止方式以 [`docs/runbook.md`](docs/runbook.md) 为准。

## 下一步阅读

1. 想理解系统边界：读 [`docs/architecture.md`](docs/architecture.md)。
2. 想运行本地系统：读 [`docs/runbook.md`](docs/runbook.md)。
3. 想修改模块行为：先读对应 `docs/specs/`，再读 `docs/designs/` 和测试。
4. 想继续当前结构 Feature：读 [Feature Spec](.scratch/repository-structure-readability/spec.md) 和 [Ticket 01～08](.scratch/repository-structure-readability/issues/)。

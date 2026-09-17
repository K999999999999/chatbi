# Workspace Map（Ticket 01 Baseline）

## 1. 核对基线

本地图基于 2026-09-17 在仓库根目录的只读盘点生成。它记录当前工作区事实、入口关系、后续结构整理候选和保留边界，不替代 Architecture（架构）、Module Spec（模块规格）或 Feature Contract（Feature 契约）。

| 项目 | 当前事实 |
| --- | --- |
| Checkout | `E:/Kaifa/project 2026/chatbi-engine` |
| Branch | `ci-integration`，相对 `origin/ci-integration` ahead 4 |
| HEAD | `5525e37234c19985d0a69a7cb573a46cab14e2a7`，`docs(sql-guard): 完善校验复用验收记录` |
| Git 描述 | `v0.1.0-87-g5525e37`；HEAD 没有 exact tag |
| 项目配置版本 | `pyproject.toml` 声明 `0.1.0` |
| 可用 tags | `v0.1.0`、`db-v1.0.0`；`db-v1.0.0` 是数据库基线标识，不作为项目版本 |
| 工作树状态 | 基线开始时除当前 Feature 的 `.scratch/repository-structure-readability/` 外没有其他未提交修改；该 Feature 的 Spec/Tickets 是既有用户工作，必须保留 |
| 版本结论 | 当前应描述为 `0.1.0` 开发快照，并附 Git commit；不能把 `v0.1.0` 表述为当前 HEAD 的发布 tag，也不能把版本号表述为 Production Ready（生产可用）证据 |

`.env`、本地数据库、模型和其他 Secret-bearing（含 Secret）配置只确认其存在和边界，不读取、不复制、不写入本文档。

## 2. 顶层工作区地图

| 路径 | 当前内容和职责 | Git / 维护边界 |
| --- | --- | --- |
| `AGENTS.md` | Repository Agent rules（仓库 Agent 规则）、Source of Truth、分层边界和交付门禁 | tracked；规则源，不作为运行入口 |
| `.github/workflows/` | `ci.yml` 快速 CI；`real-e2e.yml` 独立 Real E2E workflow | tracked；CI 配置，不等同于本地业务验收 |
| `.scratch/` | 当前 Feature 的 Spec、Ticket、过程基线，以及历史工作记录 | 当前 Feature 目录由用户创建且尚未全部 tracked；保留本地工作流，不迁移到其他文档目录 |
| `src/` | 产品源码、模块入口和已生成的结构事实 | tracked；业务行为和稳定 Contract 的主要实现位置 |
| `tests/` | 按模块组织的 Software Test（软件测试）和集成测试 | tracked；验证程序行为，不替代 AI Evaluation 或 Business Acceptance |
| `scripts/` | 本地开发启动脚本和 Metadata Export 工具 | tracked；脚本入口和生成边界由对应 Ticket / Runbook 说明 |
| `database/` | PostgreSQL CI bootstrap、权限脚本和 `sales_mart` DDL | tracked；数据库结构与权限事实，不在本 Feature 改动 |
| `docs/` | Architecture、Runbook、Module Spec、Implementation Design、Acceptance 和 Agent 说明 | tracked；按职责读取，不做无目标内容迁移或瘦身 |
| `reports/` | 历史验收和评测报告；`reports/evaluation/` 也存在本地生成输出 | 10 个文件 tracked；部分评测输出被 `.gitignore` 排除，历史证据默认保留 |
| `data/` | 本地 `postgres`、`qdrant`、`rag` 运行数据 | ignored；运行资产，保留原位置，不重建、不删除 |
| `models/` | 本地 `bge-m3` 模型资产 | ignored；模型运行资产，不提交、不移动、不删除 |
| `.venv/` | 本地 Python 虚拟环境 | ignored；环境资产，不纳入产品源码 |
| `.idea/` | IDE 配置 | ignored；开发工具资产，默认保留 |
| `项目参考课程/` | 本地参考课程材料 | ignored；不是产品源码，但是否清理需要单独确认 |
| `.env` | 本地真实配置 | ignored；禁止读取 Secret 内容、提交或写入报告 |
| `.env.example` | 安全配置模板 | tracked；可作为配置入口，不包含真实 Secret |
| `pyproject.toml` / `uv.lock` | Python 项目元数据、依赖声明和锁定依赖 | tracked；`pyproject.toml` 是当前声明版本来源，`uv.lock` 是依赖复现来源 |
| `docker-compose.yml` | 本地 PostgreSQL / Qdrant 基础设施编排 | tracked；启动边界由 `docs/runbook.md` 说明 |

Ticket 01 基线规模快照：`src` 43 个文件、`tests` 40 个文件、`docs` 23 个文件、`database` 3 个文件、`scripts` 2 个文件；本地 `data`、`models` 和 `.venv` 的文件量较大，不应与产品源码数量混计。完成 Ticket 03～07 后，实际 tracked / source 文件为：`src` 51 个、`tests` 40 个、`docs` 23 个、`database` 3 个、`scripts` 6 个；新增文件均属于已确认的内部职责拆分，不是新的一级 Module。

## 3. 源码、模块和验证入口

| Module / 区域 | 代码入口与主要职责 | 对应验证和文档 |
| --- | --- | --- |
| `src/online_query/` Online Query | `OnlineQueryService.query()` 负责查询编排；根目录保留共享 Contract、静态上下文、Prompt、LLM、Database 和 Trace；`retrieval/` 负责 Online Retrieval；`sql_guard/` 负责 SQL 范围、认证 Join 和 Multi-Metric 校验 | `tests/online_query/`；`docs/specs/online-query.md`、`docs/specs/online-retrieval.md`、`docs/designs/online-query.md`、`docs/designs/online-retrieval.md`；`docs/acceptance/online-retrieval-20260907.md` |
| `src/query_api/` Query API Adapter | `main.py` 组装真实服务；`app.py` 提供 HTTP `query` 和 `health` 入口；只适配 Online Query，不复制查询业务逻辑 | `tests/query_api/`；`docs/specs/query-api.md`、`docs/designs/query-api.md`；启动命令在 `docs/runbook.md` |
| `src/streamlit_app.py` Streamlit | `main()` 和 `query_api()` 提供当前验证页面，通过 HTTP 调用 Query API，不直接访问 LLM 或 PostgreSQL | `tests/streamlit/`；`docs/architecture.md`、`docs/runbook.md`；属于明确的 POC / 内部入口，不代表整个 ChatBI 是 POC |
| `src/rag_offline/` RAG Offline Build | `python -m src.rag_offline` 是 CLI；`build_offline_assets()` 组织事实加载、文档构建、Embedding、Qdrant、Relationship Graph 和资产发布 | `tests/rag_offline/`；`docs/specs/rag-offline-build.md`、`docs/designs/rag-offline-build.md`；构建命令在 `docs/runbook.md` |
| `src/evaluation/` Evaluation | `python -m src.evaluation` 是评测入口；加载案例，调用正式查询入口，比较结果并生成报告 | `tests/evaluation/`；`docs/specs/evaluation.md`、`docs/designs/evaluation.md`；真实 LLM Evaluation 与 Software Test 分开记录 |
| `src/observability/` Observability | `contracts.py` 定义 Trace Contract；`tracing.py` 负责 Scope、Recorder 和 Provider；`tracing_safety.py` 负责安全属性 / Trace ID；`tracing_export.py` 负责 Exporter Fail-open | `tests/observability/`，以及 `tests/online_query/`、`tests/evaluation/` 中的链路测试；`docs/specs/observability.md`、`docs/designs/observability.md`、`docs/acceptance/observability-t5-20260914.md` |
| `src/structure/generated/` | `tables.json`、`columns.json`、`relationships.json`，是当前结构事实和离线构建输入 | 被 `Online Query` 上下文和 `RAG Offline Build` 使用；属于生成事实资产，不能用旧文件反向修改 Contract |
| `src/semantic/metrics.json` | 当前指标事实输入 | 被上下文加载和离线事实加载使用；不是独立业务模块入口 |
| `src/runtime/` | 当前为空目录，没有可确认的运行时代码入口 | 不在当前 Feature 中强行补模块或删除目录 |

结构整理后的内部文件职责已与实际目录同步：Online Query、Observability 和 Metadata Export 的公共入口仍保持原路径，新增文件都是内部实现组织，不升级为新的一级 Module 或公共 API。

当前主要模块关系：

```text
Streamlit
  → Query API Adapter
    → Online Query Service
      → Online Retrieval / Context / SQL Guard / Database
        → 结构事实、指标事实和已发布 RAG 资产

Evaluation
  → 复用 Online Query 正式入口

RAG Offline Build
  → 结构事实、指标事实
  → BGE-M3 / Qdrant / Relationship Graph
  → 已发布离线资产
```

## 4. 文档和工作入口关系

当前根目录没有 `README.md`，因此新开发者还没有统一的第一入口；这属于后续 Ticket 02 的实现范围，本 Ticket 只记录事实。

| 文档入口 | 责任 | 当前使用方式 |
| --- | --- | --- |
| `docs/architecture.md` | 稳定 Architecture、模块地图、代码地图、数据模型和离线资产关系 | 解释系统结构和稳定边界 |
| `docs/runbook.md` | 本地环境、数据库 / Qdrant、API / Streamlit、RAG Build、测试和故障排查 | 执行运行与验证命令；不应复制成 README |
| `docs/specs/` | 稳定 Module Contract | 先读对应 Module Spec，再判断实现行为 |
| `docs/designs/` | 已确认 Contract 的 Implementation Design | 解释如何实现，不反向定义业务事实 |
| `docs/acceptance/` | Software Test、AI Evaluation、Business Acceptance 的历史验收证据 | 记录已发生的验证，不替代当前运行 |
| `docs/product-scope.md` | 产品范围和当前业务边界 | 当前文件标题仍为“ChatBI POC 范围”，与 Feature 计划中“不要用 POC 概括整个 ChatBI”的目标存在待统一表述 |
| `docs/roadmap.md` | 当前状态、路线和长期后续能力 | 记录已实现模块与后续路线；其测试数字是文档中的历史快照，本 Ticket 未重新执行测试 |
| `docs/agents/issue-tracker.md` | `.scratch` Spec / Ticket 的生命周期和状态规则 | 规定 Ticket 选择后才进入实现，并要求保留结果和边界 |
| `docs/agents/domain.md` | 领域文档读取顺序和职责边界 | 防止用实现或旧 Metadata 改写业务事实 |
| `.scratch/<feature>/spec.md` | 当前 Feature Contract | 本 Feature 的确认范围、实现决策和验证边界 |
| `.scratch/<feature>/issues/` | 当前 Feature 的实现 Ticket | 本次按直接依赖顺序从 Ticket 01 开始；Ticket 02～07 依赖本基线，Ticket 08 做最终验收 |

当前文档入口关系：

```text
README（当前缺失，Ticket 02）
  → docs/architecture.md
  → docs/runbook.md
  → docs/specs/<module>.md
  → docs/designs/<module>.md
  → tests/<module>/ 与 docs/acceptance/

.scratch/<feature>/spec.md
  → .scratch/<feature>/issues/01..08
```

现有 `docs/architecture.md` 和 `docs/runbook.md` 使用 `POC` 描述 Streamlit / 本地运行入口；这是局部入口语义。`docs/product-scope.md` 和 Runbook 的标题及整体措辞仍需在后续 Ticket 02 中核对，不能在 Ticket 01 中顺手改写。

## 5. 大文件和职责拆分候选

下表只记录基于实际文件大小和现有声明的候选，不表示必须拆分。每个候选都保留现有公共入口，先以对应 Ticket 的 targeted tests（针对性测试）和完整 deterministic tests（确定性测试）证明兼容性。

| 文件 | Ticket 01 基线 → 当前大小 | 当前公共入口 / 责任 | 对应 Ticket 与验证 |
| --- | ---: | --- | --- |
| `src/online_query/retrieval/retrieval.py` | 34,243 → 23,748 bytes | `OnlineRetriever.retrieve()` 编排 Retrieval、候选闭包和关系解析；候选范围位于同一子包的 `retrieval_selection.py`，Trace 辅助和结果构造分别位于 `retrieval_trace.py`、`retrieval_results.py` | Ticket 03；`tests/online_query/test_retrieval*.py` 和完整确定性测试 |
| `src/online_query/retrieval/resource_retrieval.py` | 18,765 → 10,803 bytes | TABLE、COLUMN、METRIC 候选检索和 SearchHit 转换；指标字段依赖已移至同一子包的 `metric_requirements.py`，原模块路径保留内部兼容转发 | Ticket 03；`tests/online_query/` 和完整确定性测试 |
| `src/online_query/retrieval/multi_metric.py` | 15,323 → 13,061 bytes | 保留 `build_retrieval_request()`、`plan_retrieved_metrics()` 和多指标约束兼容性判断；请求形态和列举解析已移至 `metric_request_shape.py` | Ticket 03；`tests/online_query/test_multi_metric.py` 和完整确定性测试 |
| `src/online_query/sql_guard/sql_guard.py` | 25,129 → 4,941 bytes | `validate_candidate_scope()`、`validate_sql()`、`validate_multi_metric_sql()` 由 `sql_guard/__init__.py` 保留公共入口；AST 作用域、表绑定和字段白名单已移至 `sql_guard_scope.py`，认证 Join 和 Multi-Metric 校验仍位于同一子包 | Ticket 04；`tests/online_query/test_sql_guard.py` 和 SQL 安全回归 |
| `src/online_query/service.py` | 19,514 → 10,213 bytes | `OnlineQueryService.query()` 保留请求、Prompt、LLM、SQL Guard 和数据库主编排；Retrieval 上下文解析和失败映射已移至同目录的 `service_retrieval.py`，Trace 辅助已在 `query_trace.py` | Ticket 05；服务、Query API、请求 ID 和完整确定性测试 |
| `src/observability/tracing.py` | 24,961 → 14,883 bytes | Scope、Recorder 和 Provider 生命周期保留；安全属性 / Trace ID 和 Exporter 已分别移至独立模块 | Ticket 06；Observability 和相关链路测试 |
| `scripts/metadata/export_schema.py` | 24,289 → 3,153 bytes | 保留配置、只读读取、结构投影、文件写入的 CLI 总编排；具体职责已拆到 `export_schema_*` 内部模块 | Ticket 07；`tests/metadata/test_export_schema.py` 和完整确定性测试 |

观察到但当前没有对应拆分 Ticket 的较大文件包括 `src/rag_offline/build.py`、`src/evaluation/reporting.py`、`tests/online_query/test_retrieval.py` 和若干大型 Design / Spec 文档。它们不在 Ticket 03～07 的已确认范围内，本 Feature 不因文件大小单独扩张 Scope。

## 6. 非缓存删除候选和保留边界

本 Ticket 不执行删除。当前没有足够事实证明任何非缓存文件已经废弃；以下只列出需要未来单独确认的候选，不代表批准删除：

| 候选 | 当前判断 | 删除影响 / 下一步 |
| --- | --- | --- |
| `项目参考课程/` | ignored 的本地参考材料，不属于产品源码 | 可能影响课程复现和业务背景核对；确认不再需要后才能删除 |
| `.idea/` | ignored 的 IDE 配置，共 7 个文件 | 影响本地开发体验，不影响运行；除非明确清理本地工具配置，否则保留 |
| `src/runtime/` | 当前为空目录，没有 tracked 文件和调用入口 | 可能是预留目录，也可能是残留；需单独确认后再决定是否删除，不能因为空就自动删除 |

以下路径明确按运行资产、配置或证据保留，当前不作为删除候选：`.env`、`.venv/`、`data/`、`models/`、`reports/`、历史 `.scratch/`、`docs/`、`src/structure/generated/` 和 `src/semantic/metrics.json`。Python bytecode、测试 / lint 缓存和本地 `uv` cache 属于已确认的缓存清理边界，但本 Ticket 未执行清理。

## 7. Ticket 01 结论和后续边界

- 全工作区的主要目录、源码模块、测试入口、文档职责、版本来源和本地资产边界已记录。
- 当前版本只能表述为 `pyproject.toml` 的 `0.1.0` 开发快照，并附 HEAD commit；不能把当前状态写成 `v0.1.0` 发布版或 Production Ready。
- `README.md` 缺失、部分整体 `POC` 表述待统一、以及 5 个内部实现拆分候选已明确交接给后续 Ticket。
- 非缓存文件没有被删除；疑似本地参考材料、IDE 配置和空目录已单独列出，等待未来明确确认。
- Ticket 02～07 可以以本基线为前置事实继续，但仍必须严格遵守各自的 `Blocked by`、公共入口和验证边界；Ticket 08 负责最终结构一致性验收。

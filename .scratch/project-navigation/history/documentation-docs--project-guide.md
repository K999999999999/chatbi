# ChatBI 项目导航

本文面向第一次接手仓库的开发者。它提供从产品全景走到主要功能、模块、关键代码、行为事实和验证入口的阅读路线；具体行为以链接指向的事实源为准。

## 推荐阅读路线

建议按以下顺序熟悉项目：

1. **先看边界**：阅读本页的[产品是什么](#产品是什么)和[架构与主查询链路](#架构与主查询链路)，再读 [`docs/product-scope.md`](../../../docs/product-scope.md)；当前路线概况看 [`docs/roadmap.md` 的当前阶段](../../../.scratch/remove-roadmap-and-audit/history/roadmap.md#当前阶段)，更细的阶段记录按需查阅。
2. **认识代码地图**：先看[主要能力地图](#主要能力地图)和[仓库结构](#仓库结构)，遇到模块职责冲突时以 [`docs/architecture.md`](../../../docs/architecture.md) 为准。
3. **沿一条真实链路深入**：从[在线问数链路](#在线问数链路)开始，沿 Web → API → 授权 → Online Query → SQL Guard → PostgreSQL 追踪。
4. **按工作场景扩展**：在[功能专题路线](#功能专题路线)中选择历史、经营分析、导出、RAG、运行保障或 Evaluation。
5. **亲手启动和验证**：按 [`docs/runbook.md`](../../deployment-simplification/history/docs--runbook.md) 的“新 clone 与开发入口”完成本地启动，检查服务健康并运行确定性测试。
6. **需要行为细节时查证据**：Spec 定义行为，Design 说明实现方案，Tests / Evaluation / Acceptance 提供不同种类的验证证据；区别见[文档与验证地图](#文档与验证地图)。

阅读时可用本页最后的[新人自查清单](#新人自查清单)记录自己是否已能独立定位入口。

## 产品是什么

ChatBI 是面向业务数据查询的 Domain AI Engine（领域 AI 引擎），采用 Modular Monolith（模块化单体）。它把自然语言问题转为业务语义、受控 SQL 和数据库结果，并提供经营分析、图表、历史成果、流式执行状态、结果导出及本机运行保障。

系统的核心原则是 **Model proposes, program decides**：模型输出始终是候选，程序和权威事实负责业务口径、授权、数据范围、SQL 安全与状态裁决。产品边界、已支持能力和不支持项以 [`docs/product-scope.md`](../../../docs/product-scope.md) 为准；跨阶段状态和优先级以 [`docs/roadmap.md`](../../../.scratch/remove-roadmap-and-audit/history/roadmap.md) 为准。MVP 和本机 Stable 能力不代表公网生产部署或通用多租户、多数据源能力。

## 架构与主查询链路

ChatBI 把产品组织为一个模块化单体。依赖方向是 `Interfaces → Application → Domain`；Application 面向 Port / Contract，Infrastructure 提供 Adapter。业务定义属于 Domain 和权威事实源，Infrastructure 不决定业务真相。完整模块边界、依赖规则和架构图见 [`docs/architecture.md`](../../../docs/architecture.md)。

核心查询必须经过业务语义解析和认证的物理映射，不能从自然语言直接映射到数据库列：

```text
Natural Language
  → Business Semantic Resolution
  → SemanticQuery
  → Certified Physical Mapping / Retrieval Context
  → LLM 提出 SQL Candidate
  → SQL Guard 确定性校验
  → 只读 PostgreSQL 执行
  → 受控结果与错误返回 Web
```

其中 Semantic 指标定义和 Structure 结构事实提供业务含义及物理映射边界；Online Retrieval 组合经过核验的上下文；SQL Guard 负责检查模型给出的 SQL 候选。模型不会决定授权、指标口径、数据范围或是否执行 SQL。

## 主要能力地图

这张表是查找索引，按你要了解或修改的能力选对应行即可，不需要从头逐行读完。代码入口链接到仓库内的实际文件；行为和验证细节仍以对应 Spec、Design、Tests、Evaluation 或 Acceptance 为准。

| 能力 / 场景 | 主要模块与关键入口 | 行为事实 / 实现说明 | 验证与运行入口 |
| --- | --- | --- | --- |
| 登录、首次改密、Session、RBAC 与审计 | Web [`frontend/src/App.tsx`](../../../frontend/src/App.tsx)；API [`src/query_api/app.py`](../../../src/query_api/app.py) `create_app`；[`src/authorization/`](../../../src/authorization)、[`src/chatbi_control/`](../../../src/chatbi_control) | [Web 对话 Spec](../../../docs/specs/web-dialogue-v1.md)、[Query API Spec](../../../docs/specs/query-api.md)、[架构](../../../docs/architecture.md) | [`tests/authorization/`](../../../tests/authorization)、[`tests/chatbi_control/`](../../../tests/chatbi_control)、[`tests/query_api/test_auth_api.py`](../../../tests/query_api/test_auth_api.py)；[Web 验收](../../chatbi-product-v1/history/acceptance--web-dialogue-v1-20261003.md)；[Runbook](../../deployment-simplification/history/docs--runbook.md) |
| 自然语言问数、澄清与多轮追问 | [`frontend/src/Chat.tsx`](../../../frontend/src/Chat.tsx)、[`frontend/src/api.ts`](../../../frontend/src/api.ts)；[`src/query_api/conversation.py`](../../../src/query_api/conversation.py)；[`src/online_query/service.py`](../../../src/online_query/service.py) `OnlineQueryService.execute` | [Online Query Spec](../../../docs/specs/online-query.md)、[Query API Spec](../../../docs/specs/query-api.md)、[架构](../../../docs/architecture.md) | [`tests/online_query/`](../../../tests/online_query)、[`tests/query_api/test_conversation.py`](../../../tests/query_api/test_conversation.py)；[多轮验收](../../multi-turn-conversation-v1/history/acceptance--multi-turn-query-v1-20260919.md)；[Evaluation](../../../docs/specs/evaluation.md) |
| Online Retrieval 与可认证上下文 | [`src/online_query/retrieval/retrieval.py`](../../../src/online_query/retrieval/retrieval.py) `OnlineRetriever.retrieve`；[`src/online_query/retrieval/`](../../../src/online_query/retrieval) | [Online Retrieval V1 当前契约](../../online-retrieval-v1/spec.md)、[多指标检索 Spec](../../online-retrieval-v1/history/documentation-docs--specs--multi-metric-retrieval.md)、[实现 Design](../../../docs/designs/online-retrieval.md)；[历史基线 Spec](../../../docs/specs/online-retrieval.md) | [`tests/online_query/test_retrieval.py`](../../../tests/online_query/test_retrieval.py)、[`tests/online_query/test_multi_metric.py`](../../../tests/online_query/test_multi_metric.py)、[`tests/online_query/test_relationship_graph.py`](../../../tests/online_query/test_relationship_graph.py)；[Retrieval 验收](../../online-retrieval-v1/history/acceptance--online-retrieval-20260907.md) |
| SQL 安全校验与只读数据库查询 | [`src/online_query/sql_guard/`](../../../src/online_query/sql_guard)、[`src/online_query/database.py`](../../../src/online_query/database.py) | [Online Query Spec](../../../docs/specs/online-query.md)、[Architecture](../../../docs/architecture.md) | [`tests/online_query/test_sql_guard.py`](../../../tests/online_query/test_sql_guard.py)、[`tests/online_query/test_database.py`](../../../tests/online_query/test_database.py)、[`tests/online_query/test_database_integration.py`](../../../tests/online_query/test_database_integration.py)；[数据库测试 Runbook](../../deployment-simplification/history/docs--runbook.md) |
| 结果表格、图表与经营分析展示 | [`frontend/src/results.tsx`](../../../frontend/src/results.tsx)、[`frontend/src/Chart.tsx`](../../../frontend/src/Chart.tsx)、[`frontend/src/Analysis.tsx`](../../../frontend/src/Analysis.tsx)；[`src/semantic/result_display.json`](../../../src/semantic/result_display.json) | [结果可视化 Spec](../../../docs/specs/result-visualization-v1.md)、[Design](../../result-visualization-v1/history/documentation-docs--designs--result-visualization-v1.md) | [`tests/query_api/test_result_metadata.py`](../../../tests/query_api/test_result_metadata.py)、[`tests/business_analysis/test_result_display.py`](../../../tests/business_analysis/test_result_display.py)；[可视化验收](../../result-visualization-v1/history/acceptance--result-visualization-v1-20261004.md) |
| 受控经营分析和因素归因 | [`frontend/src/Analysis.tsx`](../../../frontend/src/Analysis.tsx)；[`src/business_analysis/application.py`](../../../src/business_analysis/application.py) `BusinessAnalysisApplication.analyze`、[`src/business_analysis/decomposer.py`](../../../src/business_analysis/decomposer.py)、[`src/business_analysis/attribution.py`](../../../src/business_analysis/attribution.py) | [产品范围](../../../docs/product-scope.md)、[Query API Spec](../../../docs/specs/query-api.md)、[架构](../../../docs/architecture.md) | [`tests/business_analysis/`](../../../tests/business_analysis)；[`evaluation/suites/business_analysis/`](../../../evaluation/suites/business_analysis)；[Business Analysis 验收](../../business-analysis-v1/history/acceptance--business-analysis-v1-20260921.md) |
| 个人历史、查询续聊与固定成果 | [`frontend/src/HistoryPanel.tsx`](../../../frontend/src/HistoryPanel.tsx)、[`frontend/src/history.ts`](../../../frontend/src/history.ts)；[`src/query_api/history_api.py`](../../../src/query_api/history_api.py)、[`src/query_api/history_runtime.py`](../../../src/query_api/history_runtime.py)、[`src/chatbi_control/history.py`](../../../src/chatbi_control/history.py) | [History & Results Spec](../../../docs/specs/history-results-v1.md)、[Design](../../../docs/designs/history-results-v1.md) | [`tests/query_api/test_history_api.py`](../../../tests/query_api/test_history_api.py)、[`tests/query_api/test_history_application.py`](../../../tests/query_api/test_history_application.py)、[`tests/chatbi_control/test_history_postgres.py`](../../../tests/chatbi_control/test_history_postgres.py)；[验收](../../history-results-v1/history/acceptance--history-results-v1.md) |
| 后台执行、取消、阶段状态、SSE 和报告草稿 | [`frontend/src/execution.ts`](../../../frontend/src/execution.ts)、[`frontend/src/executionStream.ts`](../../../frontend/src/executionStream.ts)；[`src/query_api/execution_api.py`](../../../src/query_api/execution_api.py)、[`src/query_api/execution_runtime.py`](../../../src/query_api/execution_runtime.py)、[`src/chatbi_control/execution.py`](../../../src/chatbi_control/execution.py) | [Execution & Streaming Spec](../../../docs/specs/execution-streaming-v1.md)、[Design](../../../docs/designs/execution-streaming-v1.md) | [`tests/query_api/test_execution_api.py`](../../../tests/query_api/test_execution_api.py)、[`tests/query_api/test_execution_runtime.py`](../../../tests/query_api/test_execution_runtime.py)、[`tests/query_api/test_execution_events.py`](../../../tests/query_api/test_execution_events.py)；[验收](../../execution-streaming-v1/history/acceptance--execution-streaming-v1.md) |
| XLSX / PNG / PDF 成果导出 | [`frontend/src/ChartExportButton.tsx`](../../../frontend/src/ChartExportButton.tsx)；[`src/query_api/result_export_api.py`](../../../src/query_api/result_export_api.py)、[`src/query_api/export_application.py`](../../../src/query_api/export_application.py)、[`src/query_api/export_worker.py`](../../../src/query_api/export_worker.py) | [Result Export Spec](../../../docs/specs/result-export-v1.md)、[Design](../../../docs/designs/result-export-v1.md) | [`tests/query_api/test_result_export_api.py`](../../../tests/query_api/test_result_export_api.py)、[`tests/query_api/test_result_export_xlsx.py`](../../../tests/query_api/test_result_export_xlsx.py)、[`tests/query_api/test_result_export_pdf.py`](../../../tests/query_api/test_result_export_pdf.py)；[验收](../../result-export-v1/history/acceptance--result-export-v1.md) |
| 指标、维度、结构及业务映射事实 | [`src/semantic/`](../../../src/semantic)、[`src/structure/runtime_schema.py`](../../../src/structure/runtime_schema.py)、[`src/structure/generated/`](../../../src/structure/generated)、[`database/sales_mart/`](../../../database/sales_mart) | [Product Scope](../../../docs/product-scope.md)、[Architecture](../../../docs/architecture.md)；指标以 Semantic 源文件为准，生成结构是 catalog 投影 | [`tests/metadata/`](../../../tests/metadata)、[`tests/online_query/test_metric_certification.py`](../../../tests/online_query/test_metric_certification.py)；结构导出见 [`scripts/`](../../../scripts) |
| RAG 离线资产构建与在线使用 | [`src/rag_offline/build.py`](../../../src/rag_offline/build.py) `build_offline_assets`、[`src/rag_offline/`](../../../src/rag_offline)；在线 [`src/online_query/retrieval/`](../../../src/online_query/retrieval) | [RAG Offline Build Spec](../../../docs/specs/rag-offline-build.md)、[Design](../../../docs/designs/rag-offline-build.md) | [`tests/rag_offline/`](../../../tests/rag_offline)、[`tests/online_query/test_rag_runtime.py`](../../../tests/online_query/test_rag_runtime.py)；[Runbook RAG 构建](../../deployment-simplification/history/docs--runbook.md) |
| 启动装配、初始化、健康与本机运维 | [`src/bootstrap/commands.py`](../../../src/bootstrap/commands.py) `main`、[`src/bootstrap/runtime.py`](../../../src/bootstrap/runtime.py)、[`src/bootstrap/operations.py`](../../../src/bootstrap/operations.py)；[`frontend/src/OperationsStatus.tsx`](../../../frontend/src/OperationsStatus.tsx)；根目录 [`dev`](../../../dev)、[`local`](../../deployment-simplification/history/docs--runbook.md) | [Bootstrap Spec](../../../docs/specs/bootstrap.md)、[Local Deployment Spec](../../deployment-simplification/history/docs--specs--local-deployment-v1.md)、[Local Operations Spec](../../deployment-simplification/history/docs--specs--local-operations-v1.md) | [`tests/bootstrap/`](../../../tests/bootstrap)、[`tests/scripts/`](../../../tests/scripts)；[开发与 Stable Runbook](../../deployment-simplification/history/docs--runbook.md)、[R6 验收](../../r6-local-deployment/history/acceptance--local-deployment-v1.md)、[R7 验收](../../local-operations-v1/history/acceptance--local-operations-v1.md) |
| Trace 与外部观测导出 | [`src/observability/`](../../../src/observability)、API [`src/query_api/app.py`](../../../src/query_api/app.py) | [Observability Spec](../../../docs/specs/observability.md)、[Design](../../../docs/designs/observability.md) | [`tests/observability/`](../../../tests/observability)、[`tests/query_api/test_observability_t4a.py`](../../../tests/query_api/test_observability_t4a.py)；[Observability 验收](../../current-documentation/history/acceptance--observability-t5-20260914.md) |
| 确定性软件测试与 AI Evaluation | [`tests/`](../../../tests)；[`evaluation/__main__.py`](../../../evaluation/__main__.py)、[`evaluation/suites/`](../../../evaluation/suites) | [Evaluation Spec](../../../docs/specs/evaluation.md)、[产品交付入口](../../product-v1-delivery-closeout/history/acceptance--product-v1-delivery.md) | [Runbook 测试 / Evaluation](../../deployment-simplification/history/docs--runbook.md)；正式评测需显式环境和候选身份 |

表中测试名称用于导航到主要验证位置，不意味着其中每个用例都覆盖整个功能。测试、Evaluation、Acceptance 的证据用途不同，见[文档与验证地图](#文档与验证地图)。

## 在线问数链路

需要追踪主要业务代码时，可依次打开：

1. **Web 页面与 API 调用**：[`frontend/src/App.tsx`](../../../frontend/src/App.tsx)、[`frontend/src/Chat.tsx`](../../../frontend/src/Chat.tsx)、[`frontend/src/api.ts`](../../../frontend/src/api.ts) 负责登录态和对话交互；浏览器只通过 HTTP / SSE 访问 API，不直连模型或数据库。
2. **HTTP Adapter 与 Application 入口**：[`src/query_api/main.py`](../../../src/query_api/main.py) 创建服务应用；[`src/query_api/app.py`](../../../src/query_api/app.py) `create_app` 装配路由、身份和应用服务。
3. **认证、授权和审计**：身份能力位于 [`src/authorization/`](../../../src/authorization)，账号 / Session / RBAC 持久化位于 [`src/chatbi_control/`](../../../src/chatbi_control)。[`src/authorization/query_entry.py`](../../../src/authorization/query_entry.py) `AuthorizedQueryService` 决定当前身份是否能查询。
4. **查询编排**：[`src/online_query/service.py`](../../../src/online_query/service.py) `OnlineQueryService.execute` 承接 `QueryRequest`，结合当前业务语义和请求状态组织一次查询。
5. **语义检索**：[`src/online_query/retrieval/retrieval.py`](../../../src/online_query/retrieval/retrieval.py) `OnlineRetriever.retrieve` 及同目录 pipeline 读取认证的指标 / 表字段上下文和 Relationship Graph；检索资产由离线构建流程发布。
6. **候选与安全边界**：模型提出 SQL Candidate；[`src/online_query/sql_guard/`](../../../src/online_query/sql_guard) 对 SQL 作确定性校验后才允许只读执行。
7. **数据与结果**：[`src/online_query/database.py`](../../../src/online_query/database.py) 执行受限查询；结果契约再经 Query API 转为 Web 结果。业务库连接、只读用户和初始化流程见 [`docs/runbook.md`](../../deployment-simplification/history/docs--runbook.md) 与 [`database/`](../../../database)。

查询行为的权威入口是 [Online Query Spec](../../../docs/specs/online-query.md)、[Online Retrieval V1 当前契约](../../online-retrieval-v1/spec.md)、[Query API Spec](../../../docs/specs/query-api.md)；[`docs/specs/online-retrieval.md`](../../../docs/specs/online-retrieval.md) 是保留追溯的历史基线。对应的软件测试从 `tests/query_api/`、`tests/authorization/` 和 `tests/online_query/` 开始；要了解真实模型表现，再看 [Evaluation Spec](../../../docs/specs/evaluation.md) 和 `evaluation/`，不能把单元测试通过等同于真实模型准确率。

## 功能专题路线

- **身份到业务请求**：先读 [Web Spec](../../../docs/specs/web-dialogue-v1.md)，再看 [Query API Spec](../../../docs/specs/query-api.md)、[架构中的授权边界](../../../docs/architecture.md) 和 `tests/query_api/test_auth_api.py`。
- **多轮、历史和成果**：多轮会话是 Query API 之上的短期应用状态；长期个人历史和固定成果由 Control DB 持有。读 [History & Results Spec](../../../docs/specs/history-results-v1.md)，再沿 `frontend/src/history.ts` → `src/query_api/history_*` → `src/chatbi_control/history.py`。
- **经营分析**：从 `BusinessAnalysisApplication.analyze` 和 `src/business_analysis/` 开始；分析任务必须绑定当前身份，并复用授权查询和 SQL Guard。行为 / 边界以 [Product Scope](../../../docs/product-scope.md) 和 [Query API Spec](../../../docs/specs/query-api.md) 为准。
- **执行与导出**：先读 [Execution & Streaming Spec](../../../docs/specs/execution-streaming-v1.md)，理解接受、执行、事件和终态，再读 [Result Export Spec](../../../docs/specs/result-export-v1.md)。导出使用已完成快照，不重新执行查询或模型请求。
- **Semantic / Structure / RAG**：从业务事实源走到 `src/rag_offline/` 构建，再到 Online Retrieval；构建物是来源事实的派生资产，不反向决定业务口径。参考 [RAG Spec](../../../docs/specs/rag-offline-build.md)、`src/semantic/` 和 `src/structure/`。
- **本地运行和运维**：开发使用 `./dev`，本机 Stable 使用 `./local`，两者配置和数据隔离。读 [Runbook](../../deployment-simplification/history/docs--runbook.md)、[Bootstrap Spec](../../../docs/specs/bootstrap.md)、[Local Operations Spec](../../deployment-simplification/history/docs--specs--local-operations-v1.md)。`/health` 是存活检查，不等于业务链路验证或依赖就绪。
- **观测与 Evaluation**：从 `src/observability/` 与 `evaluation/` 开始，结合 [Observability Spec](../../../docs/specs/observability.md)、[Evaluation Spec](../../../docs/specs/evaluation.md)。AI Evaluation 的历史报告绑定候选、案例集和资源身份，不自动代表当前代码。

## 仓库结构

| 路径 | 职责 | 阅读提示 |
| --- | --- | --- |
| `src/` | Python 产品模块和领域 / 应用 / Adapter 实现 | 一级模块见上表；不要跨层把业务规则放入 Infrastructure |
| `frontend/` | React + TypeScript + Vite Web；包含问数、分析、历史、执行和导出视图 | `frontend/src/` 是主要页面 / API / 展示逻辑 |
| `database/` | Control DB、Sales Mart、开发初始化、测试 Fixture | SQL DDL / migration 与运行状态事实分层维护 |
| `src/semantic/` | 指标、维度、Query Binding、结果展示语义 | 以已确认的业务定义为准 |
| `src/structure/generated/` | 从当前数据库 catalog 导出的结构事实 | 属于投影，更新过程见 Runbook / 架构文档 |
| `evaluation/` | AI Evaluation 案例、执行器、比较器和报告生成 | 真实模型评测需单独准备配置和授权 |
| `tests/` | 确定性软件测试、集成测试和 E2E 支持 | 按产品模块分区；入口见 Runbook / CI |
| `scripts/` | 开发、检查、初始化辅助、验收和本机运维脚本 | 先读对应 Runbook / Spec 再执行有副作用的命令 |
| `docs/specs/`、`docs/designs/`、`docs/acceptance/` | 行为 Contract、实现设计和验收事实 | 各目录不可互相替代 |
| `docs/agents/`、`AGENTS.md` | 仓库协作与 Agent 工程规则 | 规则入口为根目录 `AGENTS.md` |
| `.scratch/` | 长期工作 Spec、Ticket 和过程 / 验收记录 | 工作项资料，不是产品运行代码 |
| `.github/`、`.githooks/` | CI / E2E 自动化与提交前本地 Hook | CI 定义不是业务 Contract |
| `docker/`、`docker-compose*.yml`、`dev`、`local` | 镜像、Compose 开发和本机 Stable 入口 | Dev 与 Stable 的数据 / 配置按 Runbook 隔离 |
| `config/` | 仓库附属配置，按具体引用确认用途 | 不要因为名称猜测其业务权威性 |
| `reports/` | 历史 Evaluation 报告与本地产生的候选输出 | 仓库含已提交的历史报告；新的候选输出通常被忽略且不会随 clone 提供。每份结果都须按报告中的 commit、案例集和资源身份判断适用性 |
| `.env`、`.model-cache/`、`.local/`、容器卷 | 本机 Secret、模型和运行数据等可能生成的资产 | 不属于源代码；不要提交、跨环境复制或清理未知资源 |

克隆后尚未运行开发流程时，`.model-cache/`、`data/`、`.local/` 等本地产物目录可能不存在；不要把 README 中提到的可选运行目录理解为源码必备目录。

## 文档与验证地图

| 资料类型 | 回答的问题 | 权威位置 |
| --- | --- | --- |
| Agent 项目规则 | 在仓库中如何协作、读取什么 | [`AGENTS.md`](../../../AGENTS.md)、[`docs/agents/`](../../../docs/agents) |
| 产品边界 / 业务范围 | 当前产品承诺什么、不支持什么 | [`docs/product-scope.md`](../../../docs/product-scope.md) |
| 架构 | 系统边界、模块职责和依赖方向 | [`docs/architecture.md`](../../../docs/architecture.md) |
| 行为 Contract | 功能输入、输出、不变量和失败语义 | [`docs/specs/`](../../../docs/specs) |
| 实现设计 | 已确认行为如何在代码中实现 | [`docs/designs/`](../../../docs/designs) |
| 软件验证 | 确定性代码行为是否符合预期 | [`tests/`](../../../tests)、CI、[Runbook 测试章节](../../deployment-simplification/history/docs--runbook.md) |
| AI Evaluation | 模型 / 生成行为对标准案例的结果 | [`evaluation/`](../../../evaluation)、[Evaluation Spec](../../../docs/specs/evaluation.md) |
| Business Acceptance | 候选或运行环境是否满足业务验收 | [Runbook 测试章节](../../deployment-simplification/history/docs--runbook.md#8-运行测试)；历史验收按功能保存在所属 `.scratch/` 工作记录中，报告受候选 / 时间 / 环境身份约束 |
| 开发、测试和运维步骤 | 命令如何执行及其前提 / 副作用 | [`docs/runbook.md`](../../deployment-simplification/history/docs--runbook.md) |
| 当前方向与历史阶段 | 依赖、路线和优先级状态 | [`docs/roadmap.md`](../../../.scratch/remove-roadmap-and-audit/history/roadmap.md) |

冲突时依照 `AGENTS.md`：已确认的上层事实源优先于旧代码、历史 Metadata 或派生产物；若事实源之间冲突，先指出冲突并核实，不以导航页自行裁定业务事实。

## 新 clone：首次启动与健康检查

推荐开发路径、配置边界和明确初始化顺序以 [`docs/runbook.md` 第 3 节](../../deployment-simplification/history/docs--runbook.md#3-新-clone-与开发入口) 为准。容器环境要求 WSL / Linux、Git、Bash 和 Docker Engine / Compose。安全配置模板是 [`.env.example`](../../../.env.example)；真实 Secret 仅写本机 `.env`，不复制旧 `.env` 或用户 Stable 配置。

Runbook 的推荐顺序是 `./dev build` → `./dev infra` → `./dev migrate` → `./dev create-admin` → `./dev prepare-model` → `./dev build-rag` → `./dev up`。其中模型准备会下载固定版本 BGE-M3，RAG 构建会生成本地检索资产；首次执行需要相应网络和磁盘空间。不要绕过显式迁移、管理员创建和 RAG 准备，也不要用 `docker compose down -v` 重置数据。

服务启动后按 [`docs/runbook.md`](../../deployment-simplification/history/docs--runbook.md) 使用 `./dev status` 和 `curl --fail http://127.0.0.1:8000/health` 检查进程存活；网页默认位于 `http://127.0.0.1:5173`。`/health` 不能证明真实问数成功、外部 LLM 可用或所有下游依赖动态就绪。

确定性纯软件回归命令为：

```bash
CHATBI_WEB_ORIGIN=https://example.invalid uv run --python 3.11 --locked python -m pytest -q
```

由于 production 启动测试会读取本机 `.env`，若其中配置了回环 HTTP Origin，Runbook 使用 `CHATBI_WEB_ORIGIN=https://example.invalid` 临时覆盖纯测试进程，避免测试配置污染；该测试不会访问此保留域名。命令需 Python 3.11 和锁定的 `uv` 环境；隔离 PostgreSQL 集成测试、前端测试、容器真实业务验收和 AI Evaluation 另有前提，见 [Runbook 测试与验收章节](../../deployment-simplification/history/docs--runbook.md#8-运行测试)。若执行环境不满足前提，应记录未运行及原因，不能把健康响应或文档检查当成业务验收。

## 新人自查清单

完成基础阅读和启动后，确认自己不需要口头补充就能：

- [ ] 用自己的话说明 ChatBI 的用途、当前支持边界，以及本机运行和公网生产就绪的区别。
- [ ] 从 Web 入口定位 API、授权服务、`OnlineQueryService.execute`、`OnlineRetriever.retrieve`、SQL Guard 和数据库访问代码。
- [ ] 说明业务指标事实、Structure 投影、Qdrant / RAG 派生资产分别在哪里维护，遇到冲突该查哪个事实源。
- [ ] 为登录 / 权限、经营分析、历史、执行流、导出和本机运维各找出一个代码入口及对应行为 Spec。
- [ ] 区分 Software Test、AI Evaluation 和 Business Acceptance 的用途，并找到本地测试命令。
- [ ] 在隔离的新 clone 中按 Runbook 完成启动和健康检查；明确它们没有证明的事项。

如某项找不到入口，先检查本页的能力地图和文档事实源，再将缺口作为导航或源文档问题记录。

# ChatBI

ChatBI是面向业务数据查询的领域AI引擎。它提供电脑端问数、多轮追问、两期经营分析、图表、私人历史与成果、执行状态和文件导出。

模型提出候选，程序裁决业务口径、权限与SQL安全。当前支持本机单API进程运行；完整能力与限制见 [产品范围](docs/product-scope.md)。

## 从哪里开始

| 你要做什么 | 阅读入口 |
| --- | --- |
| 了解产品和支持边界 | [产品范围](docs/product-scope.md) |
| 理解模块、数据和核心链路 | [架构](docs/architecture.md) |
| 首次启动或日常开发 | [Runbook](docs/runbook.md) |
| 查具体功能行为 | [当前Spec](docs/specs) |
| 理解重要实现机制 | [Design](docs/designs) |
| 看当前阶段与后续方向 | [Roadmap](docs/roadmap.md) |
| 使用AI协作开发 | [AGENTS.md](AGENTS.md) |

## 开始运行

推荐Windows + WSL / Linux环境下使用Docker Engine / Compose和仓库的 `./dev`。容器提供应用依赖；首次配置、数据库迁移、管理员、模型与索引须按 [Runbook](docs/runbook.md) 显式准备。

日常使用 `./dev up`、`./dev down`、`./dev status` 和 `./dev logs --follow`。本机Stable使用独立的 `./local` 和配置 / 数据资源，按运行手册选择对应路径。

真实Secret只保存在本地配置。新clone首次提交前安装仓库Git Hook；完整前提、端口、数据保留与故障处理见Runbook。

## 代码地图

| 能力 / 子系统 | 主要入口 | 当前规则 |
| --- | --- | --- |
| HTTP、身份与多轮 | [query_api/app.py](src/query_api/app.py)、[authorization](src/authorization)、[chatbi_control](src/chatbi_control) | [API](docs/specs/query-api.md)、[Web](docs/specs/web-dialogue-v1.md) |
| 一次自然语言查询 | [online_query/service.py](src/online_query/service.py) | [在线查询](docs/specs/online-query.md) |
| 检索与SQL安全 | [retrieval](src/online_query/retrieval)、[sql_guard](src/online_query/sql_guard) | [检索](docs/specs/online-retrieval.md) |
| 经营分析与归因 | [business_analysis/application.py](src/business_analysis/application.py)、[attribution.py](src/business_analysis/attribution.py) | [分析](docs/specs/business-analysis.md) |
| 私人历史与成果 | [history_api.py](src/query_api/history_api.py)、[history.py](src/chatbi_control/history.py) | [历史](docs/specs/history-results-v1.md)、[恢复条件](docs/specs/query-restoration.md) |
| 后台执行与SSE | [execution_api.py](src/query_api/execution_api.py)、[executionStream.ts](frontend/src/executionStream.ts) | [执行](docs/specs/execution-streaming-v1.md) |
| 结果与图形 | [results.tsx](frontend/src/results.tsx)、[Chart.tsx](frontend/src/Chart.tsx) | [可视化](docs/specs/result-visualization-v1.md) |
| 文件导出 | [export_application.py](src/query_api/export_application.py)、[export_worker.py](src/query_api/export_worker.py) | [导出](docs/specs/result-export-v1.md) |
| 业务事实与物理结构 | [semantic](src/semantic)、[structure](src/structure)、[database](database) | [架构](docs/architecture.md) |
| 离线检索资产 | [rag_offline](src/rag_offline) | [构建规则](docs/specs/rag-offline-build.md) |
| 初始化与装配 | [bootstrap](src/bootstrap)、[dev](dev)、[local](local) | [初始化](docs/specs/bootstrap.md) |
| 诊断与本机保障 | [observability](src/observability)、[scripts](scripts) | [观测](docs/specs/observability.md)、[运行保障](docs/specs/local-operations-v1.md) |
| 测试与AI评测 | [tests](tests)、[evaluation](evaluation)、[CI](.github/workflows/ci.yml) | [评测规则](docs/specs/evaluation.md) |

## 验证与历史证据

确定性软件、隔离PostgreSQL、真实LLM和运行验收的前提与命令见 [Runbook](docs/runbook.md)。它们验证不同范围，历史结果只对原报告记录的提交、案例集和资源有效。

开发过程、历史方案与验收保存在 [.scratch](.scratch)。原始本机报告位于ignored的 `reports/evaluation/`，不会随clone分发；当前规则统一在正式文档维护。

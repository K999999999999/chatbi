# ChatBI POC 范围

## 目标

让用户针对 `mart_sales` 提出自然语言问题，由 LLM 生成只读 SQL，经过安全校验后执行，并返回真实数据库结果。

## 当前范围

- 数据源固定为 PostgreSQL `mart_sales`。
- 数据库结构来自 `src/structure/generated/`。
- 业务指标口径来自 `src/semantic/metrics.json`。
- LLM 直接生成 SQL 候选。
- 程序负责 SQL 安全校验和数据库执行。
- 数据库使用 `chatbi_app` 只读权限。
- 当前运行方式为同步、单次问答。
- 提供同步 HTTP API Adapter（接口适配层）：`POST /api/v1/query` 和 `GET /health`。
- 提供 Streamlit POC 页面，通过 HTTP API 验证查询交互。
- 当前继续使用 Streamlit 作为 POC 和内部使用入口；正式前端不是当前必需项。
- 使用 `src/evaluation/eval_cases.json` 作为开发期标准评测集。
- 提供独立的 RAG Offline Build（RAG 离线构建），将已确认事实构建为 TABLE、COLUMN、METRIC 三类 Qdrant 集合和确定性关系图。
- Online Query 已接入 Online Retrieval V1（在线检索 V1）：实体类、单指标和多指标问题统一走 `metrics=0/1/N` 检索流程，从同一已发布资产组装动态上下文；在线 RAG 技术故障 Fail Closed（失败关闭）并返回 `CONTEXT_ERROR`，不使用静态全量 Schema fallback。多指标最多 5 个，直接关系只允许认证 FK→PK 和 `LEFT JOIN`；真实在线 RAG 结果以当前分支重新执行的报告为准。

## 业务与安全约束

- 只能查询 `mart_sales`，不得访问其他 Schema。
- 指标定义以 `metrics.json` 为准，LLM 不得自行创造业务口径。
- 当前指标统一使用完成日期口径：`completion_date_key -> dim_date.full_date`。
- LLM 输出是不可信候选，未经 SQL Guard 不得执行。
- 数据库失败或没有数据时，不得编造结果。

## 当前不做

- 基础 Multi-Metric Retrieval（多指标在线检索）的生产化边界；当前实现、确定性测试和当前分支 21/21 真实评测已完成，但不把该结果直接描述为 Production Ready（生产可用）。
- 多轮对话和复杂分析 Agent。
- SQL 自动修复和多模型投票。
- React、Vue 或其他正式前端 UI（等生产化需求明确后再做）、API Gateway、登录、限流、审计和生产运维。
- 多数据源、多 Schema 和多租户。

## 当前验收目标

- 完成一次真实的“问题 -> SQL -> 安全校验 -> 数据库结果”闭环。
- HTTP API 能调用同一条在线查询链路并返回 JSON 结果。
- Streamlit 页面能完成问题输入、结果展示和受控错误展示。
- 合法只读查询能够执行，危险或越界 SQL 被拒绝。
- 软件测试、AI 评测和业务验收分别记录结果。
- 21 条标准测试集能够通过同一条在线查询链路执行和统计。
- RAG Offline Build 能够构建并重载三个独立集合和关系图；失败时不替换当前已发布资产。

## 已有基础

- `mart_sales` 建表脚本和本地 PostgreSQL 运行配置。
- `chatbi_app` 只读授权脚本。
- 7 条表记录、69 条字段记录、25 条关系记录；10 个字段包含 `value_examples`。
- 5 个业务指标定义。
- 21 条标准评测数据。
- 已发布的 BGE-M3 / Qdrant 离线检索资产和 5 条固定 Retrieval Evaluation（检索评测）案例。

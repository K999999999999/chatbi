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
- 使用 `src/evaluation/eval_cases.json` 作为开发期标准评测集。

## 业务与安全约束

- 只能查询 `mart_sales`，不得访问其他 Schema。
- 指标定义以 `metrics.json` 为准，LLM 不得自行创造业务口径。
- 当前指标统一使用完成日期口径：`completion_date_key -> dim_date.full_date`。
- LLM 输出是不可信候选，未经 SQL Guard 不得执行。
- 数据库失败或没有数据时，不得编造结果。

## 当前不做

- RAG 和向量数据库。
- 自动化 Offline Build 模块。
- 多轮对话和复杂分析 Agent。
- SQL 自动修复和多模型投票。
- 正式前端 UI、API Gateway、登录、限流、审计和生产运维。
- 多数据源、多 Schema 和多租户。

## 当前验收目标

- 完成一次真实的“问题 -> SQL -> 安全校验 -> 数据库结果”闭环。
- HTTP API 能调用同一条在线查询链路并返回 JSON 结果。
- Streamlit 页面能完成问题输入、结果展示和受控错误展示。
- 合法只读查询能够执行，危险或越界 SQL 被拒绝。
- 软件测试、AI 评测和业务验收分别记录结果。
- 20 条标准测试集能够通过同一条在线查询链路执行和统计。

## 已有基础

- `mart_sales` 建表脚本和本地 PostgreSQL 运行配置。
- `chatbi_app` 只读授权脚本。
- 7 条表记录、69 条字段记录、25 条关系记录和 10 条字段值记录。
- 5 个业务指标定义。
- 20 条标准评测数据。

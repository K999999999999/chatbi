# ChatBI MVP 产品范围

## 产品定位

ChatBI 是面向业务数据分析的 Domain AI Engine（领域 AI 引擎）。当前处于 **MVP 向生产演进** 阶段：核心用户链路已经实现，当前工程重点是资源一致性、全新环境初始化、正确性证据和生产运行准备。仓库中的本地开发 Runbook 和历史 Acceptance 不构成生产部署证明。

## 当前 MVP Contract

### 自然语言查询

- 数据源固定为 PostgreSQL `mart_sales`；查询使用 `chatbi_app` 只读身份。
- LLM 生成 SQL 候选；确定性 SQL Guard 校验作用域、Join、指标和安全约束后才可执行。
- Online Retrieval V1 使用 TABLE、COLUMN、METRIC 三类 Qdrant 集合和确定性 Relationship Graph 组装动态上下文。多指标请求最多 5 个；数据库物理关系必须由已认证的 FK→PK 关系支持。
- RAG、Embedding 或发布资产故障时，在线查询 Fail Closed，不以静态全量 Schema 回退。
- 当前以完成日期 `completion_date_key → dim_date.full_date` 作为已完成销售指标的时间口径。

### API、身份与多轮查询

- Query API 提供同步 HTTP JSON 接口和 Streamlit MVP 页面。
- 内置账号、Session、固定 RBAC、授权校验及持久化审计已实现；首个管理员必须显式创建。
- Multi-Turn Query V1 已实现服务端 `conversation_id`、身份绑定、短期结构化状态、TTL、并发控制和失败后保留上一成功状态。

### 经营分析

- Business Analysis Application 已实现；任务拆解、计划校验、授权执行、结果汇总和总结由受控工作流完成。
- 当前经营分析受已登记语义和产品边界约束；代码明确支持毛利与人民币净销售额的分析，不代表任意指标、维度或跨事实表组合均受支持。

## 业务事实源与派生产物

- `database/` 中的 DDL 定义期望 PostgreSQL Schema；当前环境实际生效结构以 PostgreSQL catalog 为准。
- 维护 Schema 的顺序是 DDL → 更新 PostgreSQL → 从实际 catalog 导出 Structure JSON。
- `src/structure/generated/tables.json`、`columns.json`、`relationships.json` 是结构导出投影；不是 DDL 的替代品。
- `src/semantic/metrics.json` 是指标定义和计算口径的事实源。
- Qdrant 向量集合、Relationship Graph 和 `data/rag/` manifest 是派生产物，不拥有业务真相。production 服务启动前校验其来源指纹与 PostgreSQL / Metadata 一致。

## 当前数据与评测集规模

数量随源文件变化；以下为本次文档核对时的仓库状态：

- Sales Mart：7 张表、69 个字段、25 条关系事实；其中形成 9 条外键 Join Edge。
- Semantic Metrics：7 个指标，名称为已完成订单数、已完成订单明细行数、人民币净销售额、人民币销售成本、已完成销售数量、人民币毛利、毛利率。
- 单轮自然查询：29 个案例。
- 多轮自然查询：7 个 Conversation、15 个轮次。
- Business Analysis：10 个案例。
- Query Understanding：6 个辅助语义案例。

当前 HEAD 的正式 Evaluation 基线由对应报告确认；旧报告只代表报告记录的 commit 和资源状态。不要用历史 `20/21` 或其他旧分数描述当前能力。

## 当前明确不包含

- 任意 PostgreSQL 数据库、多个 Schema 或多租户支持。
- 超出当前 Semantic Contract 的指标、维度、跨事实表 Join、多跳 Join 或超过 5 个指标的组合。
- 任意复杂分析 Agent、SQL 自动修复、多模型投票或开放式任务编排。
- SSE / WebSocket 和独立 React / Vue 前端；当前使用同步 API 与 Streamlit。
- 生产环境部署方案、容量 / 可用性承诺、生产数据迁移和流量发布流程；这些不由 MVP 本地运行证据自动满足。

## 生产演进中的当前基线工作

- RAG 来源指纹、PostgreSQL catalog 对比和 production Ready fail-closed 门禁已实现。
- clean bootstrap 会安装 Control DB migration、LangGraph checkpoint 表和运行权限；healthcheck 验证这些对象。
- 当前 HEAD 的完整 AI Evaluation 基线仍须在最终 clean commit 上按评测 Contract 重新运行；本文件不预填尚未得到的成绩。

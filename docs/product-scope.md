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

- Query API 保留同步 HTTP JSON 兼容入口；电脑端 Web 的历史问数、重查和经营分析使用 R4 后台 execution 与 SSE 观察，默认问数并手动切换独立经营分析模式。Streamlit 已移除；完整边界见 [R4 Spec](specs/execution-streaming-v1.md)。
- 内置账号、Session、固定 RBAC、授权校验及持久化审计已实现；首个管理员必须显式创建。
- Multi-Turn Query V1 已实现服务端 `conversation_id`、身份绑定、短期结构化状态、TTL、并发控制和失败后保留上一成功状态。

### 网页身份与状态

- 指定账号使用，无公众注册；浏览器 HttpOnly Cookie，同源网页 / API 与 CSRF 校验，线上要求 HTTPS；旧 Bearer / SQLAdmin 兼容。
- 30 分钟无活动 / 8 小时绝对登录期限；无记住我与周期保活。查询权限账号共享同一套业务数据，无部门 / 区域行列隔离。
- 网页已接入 R3 私人历史与独立成果；刷新按 URL 读取已保存快照，不执行查询；重新登录从新对话开始，可重开历史。问数恢复最后成功完整条件，分析按原问题 / run 和 24 小时 checkpoint 手动恢复。R4 通过可查询 execution 与 SSE 恢复真实进度；分析草稿明确标记为未校验，只有最终报告校验并保存成功后才展示正式结果。query / analysis 草稿与记录分开，断连不自动重发。当前候选验收状态见 [R3 Acceptance](acceptance/history-results-v1.md)、[R4 Acceptance](acceptance/execution-streaming-v1.md) 与本机实时工作状态。
- 详细行为见 [Web Spec](specs/web-dialogue-v1.md)，实际候选证据见 [R1 Acceptance](acceptance/web-dialogue-v1-20261003.md)。

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

当前候选的正式 Evaluation 基线只有在三套报告均记录同一最终 clean commit、`git_dirty=false`，并满足零失败、零无效案例后才能确认。历史通过基线包括 `31a04549924f622777f106d4fe5a758bd2ca2beb` 和较新的 `564343216e4493f832f07efb345c03b058a04eb5`，后者此前也出现多轮失败，记录见[验收工作项](../.scratch/engineering-quality-gates/issues/04-current-candidate-evaluation-baseline.md#result)。它们不代表当前候选或稳定性；旧报告只代表报告记录的 commit 和资源状态。不要用历史 `20/21` 或其他旧分数描述当前能力。

## 当前明确不包含

- 任意 PostgreSQL 数据库、多个 Schema 或多租户支持。
- 超出当前 Semantic Contract 的指标、维度、跨事实表 Join、多跳 Join 或超过 5 个指标的组合。
- 任意复杂分析 Agent、SQL 自动修复、多模型投票或开放式任务编排。
- 手机适配、WebSocket 和导出；当前网页通过同源 HTTP / SSE 提供执行反馈，已支持的图表范围见下方 R2 结果展示及对应 Spec。
- 生产环境部署方案、容量 / 可用性承诺、生产数据迁移和流量发布流程；这些不由 MVP 本地运行证据自动满足。

## 生产演进中的当前基线工作

- R4 已在本地分支实现执行受理 / 状态、阶段与报告文字观察、取消和恢复 Contract；当前最终候选的真实浏览器、真实模型和 Evaluation 身份见 [R4 Acceptance](acceptance/execution-streaming-v1.md) 与 Git 公共目录的本机实时状态。此本地状态不代表远端发布或生产部署。

- RAG 来源指纹、PostgreSQL catalog 对比和 production Ready fail-closed 门禁已实现。
- clean bootstrap 会安装 Control DB migration、LangGraph checkpoint 表和运行权限；healthcheck 验证这些对象。
- 完整 AI Evaluation 基线只对三套正式报告共同绑定的最终 clean commit 成立；当前候选 SHA、报告身份与运行结果记录在 Git 公共目录的本机实时工作状态中。本文件不重标历史成绩或预填本机候选报告。

## R2 结果展示

电脑端新增可信结果说明、图表与表格默认同显、统一数值格式及既有经营归因贡献图；边界见[R2 Spec](specs/result-visualization-v1.md)。不增加查询、分析业务范围、长期历史或全量导出。展示事实由确定性后端认证，前端不从列名猜业务定义。


## R3 历史与成果

已接入网页自动历史、列表 / 搜索 / 重命名 / 删除、固定成果副本、完整条件续聊与显式重查。Control DB 管理长期状态，旧 Bearer 短期会话不强制保存。完整边界见 [R3 Spec](specs/history-results-v1.md)；候选验收进度见本机实时工作状态，本地验收不构成生产运行就绪或发布。

# ChatBI MVP → 生产演进路线

## 当前阶段

ChatBI 的 MVP 核心能力已经形成：自然语言查询、Online Retrieval、Query API、内置身份与 RBAC、多轮查询、经营分析及对应测试 / Evaluation 工具均在当前代码中实现。

生产准备基线已在 clean commit `6a5e6ccc6504ebc0947a6addb4abb02d87b566d3` 核验：正式单轮 29/29、多轮 7/7（15 个轮次）、Business Analysis 10/10，均 `0 FAIL`、`0 INVALID_CASE`，三次独立多轮诊断各 7/7 通过。原始报告保存在本机 ignored 目录 `reports/evaluation/baseline-20261003T6a5e6cc/{formal,diagnostic-1,diagnostic-2,diagnostic-3}`；它们绑定该提交、案例集和运行资源，后续提交不自动继承通过身份，报告也不保证在新 clone 中存在。

下一阶段为已确认的 ChatBI 产品 V1 目标细化。仓库尚未声称已完成生产部署、容量验证或生产运行保障；具体部署和运营 Contract 需在相应工作启动前定义。

历史完整 Evaluation 基线包括 commit `31a04549924f622777f106d4fe5a758bd2ca2beb` 和较新的 `564343216e4493f832f07efb345c03b058a04eb5`；后者的三套通过证据及此前多轮失败见[工作项验收记录](../.scratch/engineering-quality-gates/issues/04-current-candidate-evaluation-baseline.md#result)。历史通过结果不代表当前 HEAD 或模型稳定性。当前候选只有在三套正式报告均指向同一最终 clean commit、`git_dirty=false` 且各自 `0 FAIL`、`0 INVALID_CASE` 后才能标记为已核验。

## 路线顺序与优先级状态

三套验收入口、报告身份检查及基线核验已经完成。用户于 2026-10-03 确认产品 V1 目标与以下阶段路线：先明确产品行为和验收，完成对话分析用户闭环，再完成生产准备和作品交付。阶段内优先级、技术选择及容量等目标仍待澄清；检索优化和额外产品扩展不因旧文档将其列为“后续”而成为已授权目标。

路线图按已确认目标和可核验证据维护；状态变化与优先级决定分别记录。读取时机、更新触发条件及用户确认边界见 [Harness 路线图维护规则](agents/agent-harness.md#路线图读取与维护)。

## 已确认的产品 V1 目标与路线

目标：面向销售经营分析的完整 AI 数据产品作品，用户通过对话获得可信的数据、图表和分析报告；开发者能够独立部署、维护并核验正确性与运行能力。

第一版聚焦销售领域与单一 PostgreSQL 数据源，以 SQLBot 的交互和产品完整度为参照。目标能力包含独立 Web 前端、连续对话、图表、流式反馈、历史记录、成果保存与导出，以及部署和运行证据。已确认目标、候选验收场景及未决问题见[产品 V1 工作记录](../.scratch/chatbi-product-v1/spec.md)。

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| 1. 目标细化 | 明确用户、核心场景、支持边界和验收标准，并澄清部署约束 | 目标已确认，行为与技术待澄清 |
| 2. 用户闭环 | 独立 Web 前端、对话、图表、流式反馈、历史及成果保存与导出 | 阶段目标已确认，Spec / Design / Tickets 待完成 |
| 3. 生产准备 | 目标环境部署、安全检查、监控、容量与恢复验收 | 阶段目标已确认，运行 Contract 和具体优先级待确认 |
| 4. 作品交付 | 演示、架构说明及可复现评测和运行证据 | 阶段目标已确认，交付验收待细化 |

流式反馈涵盖真实执行阶段及逐步展示分析文字；生成中内容与最终结果区分，查询结果有效后展示表格和图表，SQL 校验完成后提供查看入口。断连、取消、恢复、重复提交行为及传输协议仍待确认。长期历史与短期多轮状态的关系需单独定义。

此处确认目标和阶段路线，不代表完整行为 Spec 或功能实施授权；按仓库流程完成需求与技术澄清、Spec 确认、设计审查及 Ticket 拆分后进入功能实施。当前 MVP 的公共 Contract 以产品范围和正式 Spec 为准。

## 基线工作与适用证据

- [x] RAG manifest 记录 Structure Metadata、Metrics 和 Embedding 配置来源指纹。
- [x] production Ready 校验当前 PostgreSQL catalog、结构 metadata 与发布资产；无法验证或不一致时拒绝服务。
- [x] clean bootstrap 安装 Control DB migration、LangGraph checkpoint 表与权限；缺少关键对象时 healthcheck 失败。
- [x] Runbook 描述从新环境初始化到服务运行的步骤。
- [x] 运行资源装配、启动检查、失败清理和关闭集中到 `src/bootstrap/`；四类初始化命令统一入口，旧入口已移除。行为与验收边界见 [初始化 Spec](specs/bootstrap.md)。
- [x] 在 clean commit `6a5e6cc` 完成 29 个单轮、7 个多轮、10 个 Business Analysis 案例的正式 Evaluation；各必需套件 `0 FAIL`、`0 INVALID_CASE`。后续候选按 Evaluation Contract 判断复用与重跑要求。
- [x] `6a5e6cc` 报告记录同一 commit、`git_dirty=false`、案例集及资源身份，统一身份验收通过；报告在上述本机 ignored 目录保留。
- [x] 正式三套统一验收入口和手动 Real E2E 实现已补齐，自动检查 clean commit、案例 / 轮次完整性、案例集 Hash、RAG / 数据与模型身份；软件验证通过，真实外部工作流运行仍需独立核验。
- [x] 在 `6a5e6cc` 正式基线之外保存三次完整多轮诊断，各 7/7 通过；此前失败证据保留，`MT-FAILURE-ISOLATION` 历史模型波动仍按报告解释。诊断不替换失败的正式报告，也不改变现有零失败验收门槛。

## 当前 MVP 能力边界

- 单一 PostgreSQL `mart_sales` 数据源；没有多 Schema、多租户或多数据源 Contract。
- 在线多指标查询最多支持 5 个指标，Join 只使用可认证的直接 FK→PK 关系。
- Business Analysis 受当前已登记的指标和分析范围约束。
- 同步 API 与 Streamlit 是当前入口；SSE 和独立 Web 前端不属于当前 MVP。

## 后续生产工作

在明确目标运行环境和业务要求后，再为生产部署、Secret 注入、可用性 / 容量、备份恢复、监控告警、发布和回滚设计独立 Contract 与验收。此路线图不预先承诺具体平台或实现方案。

生产设计需显式处理以下现有运行边界，具体方案和优先级待目标确认：

- 多轮会话保存在进程内；多 worker / 多副本之间不共享会话，必须定义请求路由与会话可见性策略，不能直接增加 worker 后宣称多轮能力可用。
- `/health` 只反映启动后 HTTP 存活，不检测下游实时状态；需定义 liveness、动态 readiness、依赖故障与恢复验收。
- 已有 SQL 超时与结果行数上限，但没有 API 限流；需根据目标流量明确并发 / 资源限制、容量与延迟要求，不预先指定网关、连接池或共享存储产品。

## 事实源

- 产品行为和支持范围：[`product-scope.md`](product-scope.md) 与 `docs/specs/`。
- 架构边界：[`architecture.md`](architecture.md)。
- 可执行初始化和维护流程：[`runbook.md`](runbook.md)。
- 当前 Evaluation 结果：带有当前 commit 身份的报告；日期化 `docs/acceptance/` 与旧 reports 是历史证据。

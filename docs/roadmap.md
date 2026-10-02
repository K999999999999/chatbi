# ChatBI MVP → 生产演进路线

## 当前阶段

ChatBI 的 MVP 核心能力已经形成：自然语言查询、Online Retrieval、Query API、内置身份与 RBAC、多轮查询、经营分析及对应测试 / Evaluation 工具均在当前代码中实现。

当前工作是建立可重复核验的生产准备基线。仓库尚未声称已完成生产部署、容量验证或生产运行保障；具体部署和运营 Contract 需在相应工作启动前定义。

历史完整 Evaluation 基线包括 commit `31a04549924f622777f106d4fe5a758bd2ca2beb` 和较新的 `564343216e4493f832f07efb345c03b058a04eb5`；后者的三套通过证据及此前多轮失败见[工作项验收记录](../.scratch/engineering-quality-gates/issues/04-current-candidate-evaluation-baseline.md#result)。历史通过结果不代表当前 HEAD 或模型稳定性。当前候选只有在三套正式报告均指向同一最终 clean commit、`git_dirty=false` 且各自 `0 FAIL`、`0 INVALID_CASE` 后才能标记为已核验。

## 路线顺序与优先级状态

当前路线先补齐三套验收入口与报告身份检查，再完成生产准备基线核验并记录模型稳定性风险，随后依据明确的目标运行环境和业务要求安排生产工作。生产目标澄清可与基线准备并行。后续生产工作中的各项优先级尚未确认；检索优化和产品能力扩展也不因旧文档将其列为“后续”而成为已授权目标。

路线图按已确认目标和可核验证据维护；状态变化与优先级决定分别记录。读取时机、更新触发条件及用户确认边界见 [Harness 路线图维护规则](agents/agent-harness.md#路线图读取与维护)。

## 当前基线工作

- [x] RAG manifest 记录 Structure Metadata、Metrics 和 Embedding 配置来源指纹。
- [x] production Ready 校验当前 PostgreSQL catalog、结构 metadata 与发布资产；无法验证或不一致时拒绝服务。
- [x] clean bootstrap 安装 Control DB migration、LangGraph checkpoint 表与权限；缺少关键对象时 healthcheck 失败。
- [x] Runbook 描述从新环境初始化到服务运行的步骤。
- [x] 运行资源装配、启动检查、失败清理和关闭集中到 `src/bootstrap/`；四类初始化命令统一入口，旧入口已移除。行为与验收边界见 [初始化 Spec](specs/bootstrap.md)。
- [ ] 在最终 clean commit 上核对 Golden Set 与当前 Contract，然后运行 29 个单轮、7 个多轮、10 个 Business Analysis 案例的完整 Evaluation；要求各必需套件 `0 FAIL`、`0 INVALID_CASE`。
- [ ] 保留并清楚标记 Evaluation 报告的 commit、工作区状态、案例集及资源身份，避免历史结果被误认为当前 HEAD 结果。
- [x] 正式三套统一验收入口和手动 Real E2E 实现已补齐，自动检查 clean commit、案例 / 轮次完整性、案例集 Hash、RAG / 数据与模型身份；软件验证通过，真实外部工作流运行仍需独立核验。
- [ ] 在正式基线之外保存三次完整多轮诊断及全部失败证据，登记 `MT-FAILURE-ISOLATION` 的历史模型波动。诊断不替换失败的正式报告，也不改变现有零失败验收门槛。

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

# ChatBI MVP → 生产演进路线

## 当前阶段

ChatBI 的 MVP 核心能力已经形成：自然语言查询、Online Retrieval、Query API、内置身份与 RBAC、多轮查询、经营分析及对应测试 / Evaluation 工具均在当前代码中实现。

当前工作是建立可重复核验的生产准备基线。仓库尚未声称已完成生产部署、容量验证或生产运行保障；具体部署和运营 Contract 需在相应工作启动前定义。

历史完整 Evaluation 基线对应 commit `31a04549924f622777f106d4fe5a758bd2ca2beb`。当前候选只有在三套正式报告均指向同一最终 clean commit、`git_dirty=false` 且各自 `0 FAIL`、`0 INVALID_CASE` 后才能标记为已核验。

## 当前基线工作

- [x] RAG manifest 记录 Structure Metadata、Metrics 和 Embedding 配置来源指纹。
- [x] production Ready 校验当前 PostgreSQL catalog、结构 metadata 与发布资产；无法验证或不一致时拒绝服务。
- [x] clean bootstrap 安装 Control DB migration、LangGraph checkpoint 表与权限；缺少关键对象时 healthcheck 失败。
- [x] Runbook 描述从新环境初始化到服务运行的步骤。
- [ ] 在最终 clean commit 上核对 Golden Set 与当前 Contract，然后运行 29 个单轮、7 个多轮、10 个 Business Analysis 案例的完整 Evaluation；要求各必需套件 `0 FAIL`、`0 INVALID_CASE`。
- [ ] 保留并清楚标记 Evaluation 报告的 commit、工作区状态、案例集及资源身份，避免历史结果被误认为当前 HEAD 结果。

## 当前 MVP 能力边界

- 单一 PostgreSQL `mart_sales` 数据源；没有多 Schema、多租户或多数据源 Contract。
- 在线多指标查询最多支持 5 个指标，Join 只使用可认证的直接 FK→PK 关系。
- Business Analysis 受当前已登记的指标和分析范围约束。
- 同步 API 与 Streamlit 是当前入口；SSE 和独立 Web 前端不属于当前 MVP。

## 后续生产工作

在明确目标运行环境和业务要求后，再为生产部署、Secret 注入、可用性 / 容量、备份恢复、监控告警、发布和回滚设计独立 Contract 与验收。此路线图不预先承诺具体平台或实现方案。

## 事实源

- 产品行为和支持范围：[`product-scope.md`](product-scope.md) 与 `docs/specs/`。
- 架构边界：[`architecture.md`](architecture.md)。
- 可执行初始化和维护流程：[`runbook.md`](runbook.md)。
- 当前 Evaluation 结果：带有当前 commit 身份的报告；日期化 `docs/acceptance/` 与旧 reports 是历史证据。

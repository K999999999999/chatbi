# 02 用 LangGraph 编排经营分析固定查询 Task

Status: open

## Owner

ChatBI Engine 实施 Agent

## Blocked by

01 添加已完成销售数量语义指标

## What to build

- 在当前经营分析入口使用 LangGraph `StateGraph` 编排指标 / 时期识别、确定性校验、Task 查询、归因和总结阶段。
- LLM 只提取候选目标指标和两个时期；确定性程序拒绝缺失、歧义或未支持指标，并根据目标指标生成固定查询 Task。
- Task 顺序执行，每个 Task 独立调用一次当前已授权的 Natural Query / Online Query 链路。
- 每个时期分别查询整体指标和产品归因所需数据。毛利需要 4 次 Natural Query：两个时期各查询一次整体毛利、一次按产品查询人民币净销售额 / 已完成销售数量 / 人民币销售成本。销售额需要 4 次 Natural Query：两个时期各查询一次整体人民币净销售额、一次按产品查询人民币净销售额 / 已完成销售数量。
- 澄清结果直接返回，不查询数据库；不把普通查询的 Multi-Turn 状态作为经营分析状态。

## Acceptance criteria

- 毛利与销售额问题分别生成 Spec 规定的固定 Task，不增加区域、客户、客户类型、产品线等分析维度或筛选条件。
- 两个明确时期的毛利或销售额问题各生成 4 次 Natural Query 调用；每次只查询一个时期，产品数据调用只包含 Spec 规定的指标和产品维度。
- Task 由普通 Natural Query 执行，授权、RAG、SQL Guard 和只读数据库边界均由现有链路提供；经营分析自身不生成或执行 SQL。
- 比较时期不明或目标指标歧义时返回澄清，调用 Natural Query 次数为零。
- 每个 Task 的调用身份来自当前已认证请求，Task 按顺序执行；成功结果按 Task ID 保留在本次图状态。
- 图状态是单次运行状态，不作为不同 `analysis_run_id` 之间的会话记忆。

## Change Profile

- Lifetime: 长期经营分析流程。
- Size: 中到大。
- Risk: 高；替换当前人工编排并调用模型和数据库查询链路。
- Evidence: Graph 节点和路由确定性测试、Task 适配器测试、普通查询集成测试、真实 LLM 评估。
- Delivery: 本地 Feature branch；无独立运行时 Feature Flag。

## Canonical Source

`.scratch/business-analysis-root-cause-v1/spec.md`；Online Query 公共边界以 `docs/specs/online-query.md` 与 `docs/specs/query-api.md` 为准。

## Owned files

- `pyproject.toml`、`uv.lock`
- `src/business_analysis/`
- `tests/business_analysis/`
- 必要时更新 `src/query_api/` 的经营分析装配，但本 Ticket 不实现 checkpoint 生命周期 API

## Migration / Rollback

- 不改普通查询 Multi-Turn Contract。
- LangGraph 流程未通过验收时，恢复经营分析入口到当前 Application 编排；不改写旧版验收记录。

## Verification evidence

- 固定结构候选的校验、歧义与错误路由测试。
- 注入查询服务验证每个 Task 形成一个 `QueryRequest` 并进入 Online Query。
- BA04 / BA05 澄清用例证明无 Natural Query 调用。
- 真实 LLM + 在线 RAG 的任务分解与执行报告。

## Done When

支持场景能产生且仅产生固定 Task，澄清可在查询前返回，正常 Task 通过授权 Natural Query 顺序完成。

## Result

待实施。

## Comments

- 持久化 checkpoint、运行恢复 ID、重试和恢复 API 由 Ticket 04 负责。

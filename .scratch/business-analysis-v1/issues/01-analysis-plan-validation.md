# Ticket 01：经营分析计划拆解与确定性校验

- Status: open
- Owner: Business Analysis Application / Semantic
- Blocked by: None (can start immediately)
- Canonical Source: `.scratch/business-analysis-v1/spec.md`

## Change Profile

- Lifetime：经营分析 V1 的核心计划 Contract。
- Size：中等；新增分析计划和校验能力，不改变普通查询入口。
- Risk：高 LLM / Semantic 风险，Task Decomposer 输出必须视为不可信候选。
- Evidence：确定性计划校验测试，配合后续 AI Evaluation 验证拆解质量。
- Delivery：本地 Feature branch；不单独发布公共 API。

## What to build

- 定义 `AnalysisTask`、`AnalysisPlan` 和计划校验 Contract。
- 实现 Task Decomposer 的结构化 LLM 输出适配。
- 让 Decomposer 接收原始问题、时间上下文、Semantic 指标/维度事实和拆解规则。
- 确保 Task 只描述业务语义查询，不生成 SQL、不访问数据库、不创建未登记指标或维度。
- 确定性校验指标、维度、Task 类型、Task ID、依赖引用和循环依赖。
- 校验根任务第 0 层、最多 2 层下钻和单次分析最多 12 个 Task。
- 拒绝执行结果驱动的新增 Task、动态下钻和动态 `Replanning`。
- 对指标或维度无法唯一确定的计划返回 `CLARIFICATION_REQUIRED`。
- 对计划非法、超出深度或 Task 数量限制返回 `CANNOT_ANSWER`。

## Owned paths

- `src/business_analysis/`
- `tests/business_analysis/`

## Acceptance criteria

- 合法 `AnalysisPlan` 能通过确定性校验并保留合法依赖关系。
- 未登记指标、未确认维度、重复 Task ID、不存在的依赖和循环依赖均被拒绝。
- 超过第 2 层或 12 个 Task 的计划在执行前被拒绝。
- Decomposer 输出中出现 SQL、数据库字段或未登记业务事实时不能直接进入执行。
- 计划校验不调用数据库，不调用 Online Query，不执行任何 Task。
- 任务计划不会在执行阶段自动新增或动态重写。
- 模型输出失败、结构化 Contract 无法解析和业务语义不明确时返回约定的公开错误，不泄露内部异常。

## Verification evidence

- `tests/business_analysis/` 中的计划 Contract 和校验确定性测试。
- 使用固定模型候选覆盖正常计划、非法指标、循环依赖、深度超限和数量超限。
- 测试证明 Plan Validator 不调用数据库、授权查询和 SQL 生成器。
- 后续 Ticket 05 补充标准经营分析案例的 AI Evaluation 证据。

## Migration / Rollback

不涉及数据库、用户会话或持久化数据迁移。回滚时移除 Business Analysis 计划模块，不影响普通查询和现有 Multi-Turn。

## Done When

- 计划 Contract 和确定性校验测试通过。
- 计划边界、错误语义和不动态扩张规则均有测试证据。
- 普通查询相关代码和测试没有行为变化。

## Result

已完成经营分析计划 Contract、确定性校验和 Task Decomposer：

- 新增 `AnalysisTask`、`AnalysisPlan`、Semantic Catalog、计划错误和 LLM 错误 Contract；
- 支持指标别名规范化，未明确的“利润”不会自动映射为“毛利”；
- 校验 Task ID、依赖引用、循环依赖、最大下钻深度 2 和最多 12 个 Task；
- 拒绝 SQL、物理字段和未允许的 Task 字段；
- Task Decomposer Prompt 固定为业务语义计划，不输出 SQL 或动态 Replanning；
- LLM Provider、非法 JSON 和结构化 Contract 错误均转换为安全的公开错误。

验证结果：

- `uv run pytest -q tests/business_analysis`：10 passed；
- `uv run python -m compileall -q src/business_analysis tests/business_analysis`：通过；
- `git diff --cached --check`：通过。

## Comments

- Ticket Readiness Review：READY。
- 不引入 `langgraph` 或其他新的编排 Framework；具体 LLM Provider 复用现有工程配置，留在 Implementation Design 中确定。
- 当前 Ticket 不装配真实 LLM、Retrieval 或数据库；完整链路由后续 Ticket 负责。

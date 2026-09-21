# Ticket 05：经营分析回归、AI Evaluation 与 Business Acceptance

- Status: done
- Owner: Evaluation / Business Acceptance
- Blocked by: Ticket 04
- Canonical Source: `.scratch/business-analysis-v1/spec.md`

## Change Profile

- Lifetime：经营分析 V1 的验收证据和回归保护。
- Size：中等；主要增加测试、标准案例和验收文档。
- Risk：高，因为涉及 Task Decomposer、Online Query、Summary LLM 的完整链路。
- Evidence：Software Test、AI Evaluation、Business Acceptance；Real E2E 已在用户授权后执行本地真实链路，hosted CI 和批量真实 AI Evaluation 仍单独记录。
- Delivery：不改变产品范围，不以报告流畅度替代业务正确性。

## What to build

- 增加经营分析标准案例。
- 覆盖趋势、期间对比、维度拆解、原因分析、歧义指标和无法回答问题。
- 覆盖依赖 Task 失败、独立 Task 失败、跳过、空结果和截断。
- 验证普通查询回归不受影响。
- 记录 Software Test、AI Evaluation 和 Business Acceptance 证据。
- 形成 `docs/acceptance/` 下的经营分析 V1 验收记录。
- Real E2E 获得授权后执行；执行范围、失败传播、空结果和未覆盖范围必须如实记录。

## Owned paths

- `tests/business_analysis/`
- `tests/evaluation/`
- `src/evaluation/` 中与标准案例和报告相关的文件
- `docs/acceptance/`

## Acceptance criteria

- 既有普通查询、Multi-Turn、授权和 Online Query 回归测试继续通过。
- 至少完成一个正常多任务经营分析案例。
- 至少覆盖一个依赖 Task 失败和一个独立 Task 失败案例。
- 报告能引用真实的完成 Task，并标记失败、跳过、空结果和截断证据。
- “利润”无法唯一确定时不会自动解释为“毛利”。
- 报告自然语言可供人工阅读，但流畅度不作为唯一业务正确性证据。
- 验收记录明确区分 Software Test、AI Evaluation、Business Acceptance 和 Real E2E。
- Real E2E 未通过或未授权时，不声称完整真实业务链路已经验收。

## Verification evidence

- 确定性测试结果及测试 Commit。
- AI Evaluation 标准案例、任务拆解和证据引用结果。
- Business Acceptance 场景和人工验收结论。
- 如获得授权，记录真实 LLM、RAG、SQL Guard、PostgreSQL 链路的 Real E2E 结果，不记录 Secret。

## Migration / Rollback

不涉及迁移。验收失败时保留失败证据，回到对应实现 Ticket 修复，不修改普通查询边界。

## Done When

- 验收文档完整记录各类证据和未验证范围。
- 普通查询回归通过。
- Business Analysis V1 的正常、失败、歧义和部分证据场景均有可追溯结果。
- 没有把未执行的 Real E2E 或 AI Evaluation 误报为通过。

## Result

已完成经营分析标准案例、确定性评测器、本地真实端到端验收和验收记录：

- 新增 5 个标准案例，覆盖趋势、期间对比、维度拆解、原因分析和歧义“利润”；评测器验证 Task 类型、指标、维度、最小 Task 数量和澄清行为。
- 复用 Business Analysis 单元测试覆盖正常多 Task、依赖失败、独立失败、跳过、空结果、截断、报告证据引用和普通查询回归。
- 验收记录写入 `docs/acceptance/business-analysis-v1-20260921.md`，明确区分 Software Test、AI Evaluation、Business Acceptance 和 Real E2E。
- 已执行真实 LLM、BGE-M3、Qdrant、Retrieval、SQL Guard、只读 PostgreSQL、认证和 HTTP API 链路；有数据的明确期间案例成功，空结果和依赖失败均按 Contract 标记不完整。
- 真实 5-case 批量 AI Evaluation、hosted CI 21-case 和人工业务复核仍未执行，未把本地样本通过扩大解释为全量准确率或 Production Ready。
- Real E2E 期间发现并补充了最近月份时间标准化、时间维度别名和 Summary 列表字段 Prompt 的确定性保护及回归测试。

验证：`uv run --with pytest python -m pytest -q` → 435 passed、6 skipped、123 subtests；`uv run python -m compileall -q src tests` → 通过；`git diff --check` → 通过。

## Comments

- Ticket Readiness Review：READY。
- 本 Ticket 只建立验收证据和必要的 Contract 修复，不扩大到预测、模拟、自动经营动作或 Production Readiness。

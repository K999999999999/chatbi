# 05 更新经营分析 Golden Set、确定性评测和 LLM Judge

Status: done

## Owner

ChatBI Engine 实施 Agent

## Blocked by

01 添加已完成销售数量语义指标
02 用 LangGraph 编排经营分析固定查询 Task
03 实现产品因素确定性归因并交给总结模型
04 实现 checkpoint、运行恢复和失败处理生命周期

## What to build

- 在现有 `src/evaluation/business_analysis_cases.json` 更新五条已确认案例的 Task、时期、指标、产品结果和参考 SQL。
- 正常系统链路使用真实 LLM 与在线 RAG；独立 PostgreSQL 只读参考 SQL 核对查询结果。
- 确定性校验计划、Task 执行结果、因素贡献方向 / 金额、汇总对账和澄清前零查询。
- 增加 LLM Judge，评估最终总结是否忠于查询与归因证据；Judge 不重算金额，也不替代确定性数值判定。
- 保留每次评测的模型、RAG 资产、数据库 Seed 指纹和报告证据。

## Acceptance criteria

- BA01 原问法保持不变，并纠正数据不支持的“下降”前提；不修改 Seed 迎合问法。
- BA02 / BA03 与已确认的毛利、销售额方向和因素贡献一致。
- BA04 / BA05 在澄清完成前不执行查询。
- 每个成功案例的正常链路查询结果与独立参考 SQL 对账；所有显示贡献来自确定性归因。
- LLM Judge 检出总结中与方向、产品、因素、金额依据不符或无证据支持的陈述。

## Change Profile

- Lifetime: 长期回归门禁。
- Size: 中。
- Risk: 高；AI Evaluation、RAG、SQL 参考结果和报告可信度均受影响。
- Evidence: AI Evaluation、确定性软件测试、独立 PostgreSQL 参考结果和 Business Acceptance 报告。
- Delivery: 本地评测报告；真实 LLM / RAG 使用仓库既有本地配置，不输出 Secret。

## Canonical Source

`.scratch/business-analysis-root-cause-v1/spec.md`；案例事实来自独立 PostgreSQL 参考 SQL，历史 V1 验收记录保持不变。

## Owned files

- `src/evaluation/business_analysis_cases.json`
- `src/evaluation/business_analysis_evaluation.py`
- `src/evaluation/business_analysis_runner.py`
- `src/evaluation/business_analysis_reporting.py`
- `tests/evaluation/test_business_analysis_*.py`
- `docs/acceptance/` 新版验收报告

## Migration / Rollback

- 不覆盖历史 Golden Set 评测报告或旧版验收文档。
- 新报告标注新的 Spec / Evaluation 版本；确定性 SQL 和归因检查判定数值正确性，LLM Judge 的事实一致性结论及依据单独记录。当前 Spec 未定义 Judge 通过阈值，不在本 Ticket 中自行增加阈值。

## Verification evidence

- 五条案例真实 LLM + 在线 RAG 完整报告。
- PostgreSQL 参考 SQL 查询结果及 Task 对账。
- 归因公式测试报告和 LLM Judge 依据一致性报告。

## Done When

五条案例、数值检查、Summary Judge 与业务验收结果均可追溯到当前 Spec、数据库 Seed 指纹和已发布 RAG 资产版本。

## Result

已完成 BA01–BA05、独立 PostgreSQL 参考 SQL、确定性计划 / Task / 归因对账和 Summary LLM Judge。最终干净 candidate 上真实 LLM + 在线 RAG 评测 `5/5 PASS`、`INVALID_CASE=0`，所有适用准确率均为 100%。证据见 `docs/acceptance/business-analysis-root-cause-v1-20260928.md` 和 `reports/evaluation/20260928T051000Z-2591c9c-business-analysis.json`。

## Comments

- Golden Case 数量保持五条；归因公式边界通过确定性固定数据测试覆盖，不额外扩充 AI Case 数量。

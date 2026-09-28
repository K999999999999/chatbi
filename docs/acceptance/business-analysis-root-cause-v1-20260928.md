# 经营分析双期因素归因 V1 验收记录

## 结论

已完成双期毛利 / 人民币净销售额变化原因分析的 LangGraph 编排、确定性产品因素归因、checkpoint 恢复和 BA01–BA05 评测。最终真实 LLM + 在线 RAG 评测 `5/5 PASS`、`INVALID_CASE=0`，评测对应干净代码 commit `2591c9c536df31516a5a52ba94c03d1fb3b94aed`。

该结论只覆盖当前 5 条 Golden Case、本地 Seed、RAG 资产和模型配置，不代表任意用户问法的准确率，也不替代人工业务复核或生产环境验收。

## 验证结果

- Software Test：`532 passed, 14 skipped, 124 subtests passed`。
- Control DB 隔离迁移、权限和运行生命周期集成测试：`18 passed`。
- `uv lock --check`、`git diff --check` 和本次提交 Python 文件的 Ruff import / SIM102 检查通过。
- 真实 BA Evaluation：计划准确率、Task 执行准确率、报告依据率、归因准确率、Summary Judge 准确率和端到端准确率均为 `100%`。
- Summary Judge 覆盖 3 个成功分析案例，`3/3 PASS`；BA04、BA05 为澄清案例，不调用查询或 Summary Judge。

| 案例 | 结果 | 归因方向 / 变化 | 结果说明 |
|---|---|---|---|
| BA01 | PASS | 毛利增加 `18,195.317795` 元 | 纠正问句中“下降”的错误前提；Task、产品因素及 Judge 一致 |
| BA02 | PASS | 毛利下降 `25,889.557484` 元 | 产品因素方向、排序和总结一致 |
| BA03 | PASS | 净销售额增加 `38,673.145550` 元 | 产品因素方向、排序和总结一致 |
| BA04 | PASS | 不适用 | 比较时期不明确，澄清前零查询 |
| BA05 | PASS | 不适用 | “利润”指标口径不明确，澄清前零查询 |

## 真实评测证据

- 命令：`uv run --env-file .env python -m src.evaluation --business-analysis --online-retrieval --output-dir reports/evaluation`
- JSON：`reports/evaluation/20260928T051000Z-2591c9c-business-analysis.json`
- Markdown：`reports/evaluation/20260928T051000Z-2591c9c-business-analysis.md`
- Run ID：`20260928T051000Z-2591c9c`
- Git：`2591c9c536df31516a5a52ba94c03d1fb3b94aed`，`git_dirty=false`
- Model：`deepseek-flash`，temperature `0.1`
- RAG 资产：`20260928-ba-sales-quantity-v1`
- Sales Mart Seed：`chatbi-sales-mart-dev-v2`
- 数据指纹：`6fd3a4fa5847ceed823bb8778a4df3dddbf645df911ff33d31d523db9369efd8`
- 测试集哈希：`f1059309d3fc29044b4aa3bc36b2ca538d89b2cc069665245aea8649d4481bd1`

## 本次评测发现和处理

1. 首次真实评测发现 BA01–BA03 的参考 SQL 使用了 SQL Guard 不允许的事实表到维表 `JOIN`。修正为当前只读 SQL 规则允许的 `LEFT JOIN` 后，12 条参考 SQL 均通过 SQL Guard 并在 PostgreSQL 执行成功。
2. 最终 candidate 的评测发现 BA01 的 Summary LLM 将毛利单位成本负贡献描述为正贡献，Judge 正确拒绝该报告。通用修复是在程序归因中为产品和因素显式计算 `effect_on_metric`，并要求 Summary / Judge 以该标签解释目标指标方向；之后重新运行的最终评测 BA01–BA05 全部通过。

## 范围限制

- 归因只支持两个明确时期、毛利或人民币净销售额，并按产品拆分；不分析区域、客户或其他维度。
- 新品 / 退出产品按该时期完整指标变化计为产品贡献。
- 产品因素按名称跨期配对；产品改名识别和 `product_id` 实体配对不在 V1 范围内。
- checkpoint 保存在 `chatbi_control`，以 `analysis_run_id` 作为 LangGraph `thread_id`，24 小时后清理；认证上下文不持久化。
- 评测的 Judge 是 LLM 事实一致性抽检，不替代确定性 SQL 结果比较和归因对账。

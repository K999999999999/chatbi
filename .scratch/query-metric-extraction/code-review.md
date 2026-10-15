# 实现 Review

Review: PASS

Scope: 基线 `a247096` 至当前工作区；Ticket `01-metric-extraction` 的源码、评测、测试和三份正式 Spec。只读 Review，不包含旧分支 `fix/full-validation-findings`。

## Change Description

- What：Query Understanding 的指标候选保留用户原话；历史条件在当前发布事实认证时统一规范指标及排序 / 聚合引用；语义评测支持受控澄清案例；同步修正文档中的职责和检索次数描述。
- Why：解析阶段不应把别名改写成规范名；规范身份应由现有 Retrieval / certification 业务边界裁决。
- Risk：历史排序、聚合筛选和状态证书的身份衔接；已增加同指标别名、真实指标替换、零数据库调用回归覆盖。
- Verification：`uv run pytest -q`、`./dev test all`、`./dev check`、文档检查均通过；真实 Query Understanding、Online Retrieval 和 Multi-Turn 评测均在同一候选提交上通过。

## Findings

- 无阻塞问题。
- Query Understanding 不再输出规范化别名；词汇表仅用于受控歧义判断。
- Online Retrieval 继续按原话消费并按候选登记名称 / 别名唯一认证；未增加候选选择 LLM、未改变阈值、资产或 SQL Guard。
- History certification 仅在当前已选 Metric 记录中规范化条件引用；指向被替换指标的旧聚合条件返回 `CLARIFICATION_REQUIRED`，不生成 SQL、不执行数据库。
- 已确认历史快照格式和规范身份保持不变；失败或澄清不推进成功状态。

## Review Dimensions

Correctness / Comprehension / Consistency / Testability / Architecture / Security：通过。未改变依赖方向、权限、SQL 安全、部署或公共 HTTP 字段；未引入 Secret、生成物或无关重构。

## Tests

- `uv run pytest -q`：979 passed, 51 skipped, 142 subtests passed。
- `./dev test all`：Python 979 passed / 51 skipped / 142 subtests；database 5 + 53；web 67；renderer 2。
- `./dev check`：文档 / Markdown links、稳定模块边界、Ruff、Web 和 export 构建均通过。
- `python3 -m scripts.check_documentation`：通过。
- `./dev evaluate --query-understanding`：7/7，100%；报告 `20261015T091137Z-1f24c8c-query-understanding`。
- `./dev build-rag`：构建并发布 7 个 Metric、69 个 Column、7 个 Table 文档；`build_id=20261015T091731Z-c95bed778154`。
- `./dev evaluate --online-retrieval`：29/29，100%；报告 `20261015T093416Z-1f24c8c`。
- `./dev evaluate --multi-turn --online-retrieval`：7/7 场景、15/15 轮次、执行准确率 100%；报告 `20261015T095221Z-1f24c8c-multi-turn`。

Next: Ticket 与 Harness 记录已更新；本目标仅保留本地 Commit，不 Push、不创建 PR。

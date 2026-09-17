# 05: V1 回归、业务验收与文档状态同步

**What to build:**

完成 01～04 后，执行完整的 Software Test（软件测试）、AI Evaluation（AI 评估）和 Business Acceptance（业务验收），并同步项目文档，使文档、Spec、测试和实际实现保持一致。

**Blocked by:**

04

**Status:** done

## Acceptance criteria

- [x] 正向场景通过：查询销售额；查询销售额和完成订单数；按客户类型分组查询销售额；按产品分组查询 2025 年销售额；查询客户名称。
- [x] 拒答场景通过：缺少必要表、字段或指标；需要中间表或多跳 Join；日期关系不明确；指标不兼容；SQL Guard 失败。
- [x] 技术失败场景返回正确状态：Qdrant/Embedding 失败、Asset Snapshot 版本不一致、LLM 超时、数据库超时。
- [x] 空结果被识别为合法成功结果。
- [x] 旧文档中与当前 Spec 冲突的行为被删除、合并修正，或改为指向当前 Spec。
- [x] 评估报告可在本地生成，但不强制提交到 GitHub 或作为远程 Issue/PR 内容。
- [x] 所有相关确定性测试和评估结果均有可复核证据。
- [x] 完成 Diff Review、`git diff --check` 和 Secret 检查。
- [x] 没有混入无关代码、文档或生成文件。

## Result

已完成。统一 V1 行为通过全量确定性回归：`248 passed, 6 skipped, 85 subtests passed`；新增 `tests/evaluation/test_v1_acceptance.py`，以当前 20 条标准案例、静态 SQL Guard 和空结果成功契约完成 `20/20` 离线验收。静态评测上下文现在从关系事实构建 9 条认证直接 FK→PK Join 约束，标准案例统一使用 `LEFT JOIN`，避免评测入口绕过当前安全契约。

正向、业务拒答、技术失败、调用停止边界、SQL Guard、空结果和超行数证据分别保留在 `tests/online_query/` 的检索、关系图、服务、集成和 Guard 测试中。在线 RAG 的真实 Qdrant/LLM/PostgreSQL 20/20 与 Business Acceptance 继续使用既有本地验收记录；本 Ticket 未自动重新调用外部 LLM 或数据库。

`docs/specs/online-retrieval.md`、`docs/specs/multi-metric-retrieval.md` 及对应历史设计文档已增加当前 V1 指针；Online Query、架构、范围、路线图、运行手册和评测规格已同步统一流程、最多 3 个指标、直接 `LEFT JOIN`、Fail Closed 和本地报告策略。评测 JSON/Markdown 报告继续由 `.gitignore` 忽略，不进入 GitHub Issue/PR。

## Comments

这是交付验收 Ticket，不提前实现新的业务能力；只有 01～04 的行为闭环完成后才执行。

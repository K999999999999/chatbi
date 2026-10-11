# 公共指标口径校验验证与 Review

基线：`b7dd82386d877ccf6669bd2e02698e81da19f975`。适用范围为本报告所绑定的最终源码 / 测试指纹；报告随本地候选提交，提交 SHA 及后续交付状态由 Git 公共目录 `harness/work-items/single-metric-sql-certification/status.md` 保存。历史评测不重标为本候选成绩。

## 行为结果

单指标与多指标复用认证公式和固定条件 AST 检查；单指标遗漏 / 改写公式、额外聚合、固定条件缺失或 OR / NOT 绕过被拒绝。通过真实 AuthorizedQueryService → OnlineQueryService → SQL Guard 的确定性组件链路验证 `SQL_REJECTED` 且数据库调用为 0；经营分析通过真实 TaskSemanticAdapter / TaskExecutor 调用同一绑定身份的查询链路。正确查询保持成功。

七个登记指标的 SQL 模板通过；表别名、无意义括号、合法附加筛选（包括固定条件之外的 OR）、现有 HAVING / 日历表达式、实体与无认证指标的显式静态模式保持适用行为。未扩展时间、排序等完整语义校验，也不宣称修复独立的嵌套 Join 问题。

## TDD 与软件验证

- Red：`.venv/bin/python -m pytest -q tests/online_query/test_metric_certification.py` 在生产源码改动前 **20 failed / 13 passed**。失败来自错误候选未拒绝及分析 Task 被错误标为成功，不是依赖或环境错误。
- 初次 Green：新增回归与原 SQL Guard **54 passed / 43 subtests passed**。
- 最终受影响回归：`.venv/bin/python -m pytest -q tests/online_query/test_metric_certification.py tests/online_query/test_sql_guard.py tests/online_query/test_history_calendar_guard.py tests/online_query/test_history_query_execution.py tests/online_query/test_retrieval_service.py tests/business_analysis/test_execution.py tests/query_api/test_multi_turn_revision.py`：**107 passed / 47 subtests passed**。
- 最终全量：`.venv/bin/python -m pytest -q`：**1033 passed / 41 skipped / 139 subtests passed**，55.97 秒。41 个显式外部环境用例未在该命令运行，不能计为通过。
- 隔离数据库：`.venv/bin/python scripts/run_database_tests.py`，PostgreSQL 16 CI profile：**5 passed**，临时容器由 runner 清理；不访问日常开发库或 Stable。此证据验证已有执行器与固定 SQL 链路，指标拒绝路径由上述组件测试验证。
- 合法 Gold SQL 兼容：针对 `evaluation/suites/single_turn/cases.json` 的 27 个 SQL 案例，按各案例业务要求手工明确指标及顺序，使用当前 metrics.json 构造认证约束后经真实 `validate_sql`，**27/27 PASS**；R01/R02 为两个无 SQL 的受控结果案例，不参与 SQL 兼容检查。覆盖 S01–S06、M01–M09、T01、C01–C07、F01、N01、H01、A01。此检查不调用模型或执行数据库，不是 AI Evaluation 成绩。
- `bash scripts/check_python_quality.sh`：PASS，项目固定 Ruff 0.16.8，覆盖 src / evaluation / tests；309 个文件格式检查通过。
- `uv lock --check`、`.venv/bin/python -m compileall -q src evaluation tests`、`python3 -m scripts.check_markdown_links`、`python3 -m scripts.check_module_boundaries`、`git diff --check`：PASS。

未运行：真实 LLM / Qdrant Evaluation、真实浏览器业务验收、Control DB development profile、Stable 升级。理由：本项不修改模型 / 检索、HTTP / 前端或持久化，目标是确定性 AST 拒绝边界；模型和数据库以替身隔离可可靠注入 Bad Case，现有 Gold SQL 与隔离数据库验证适用兼容性。不将这些软件证据描述为真实模型或生产运行通过。

## Code Review

Review：**PASS**。Mode：Main Agent；使用 workflow-code-review 在当前上下文审查，无独立 Agent。

- Acceptance：单指标漏检已补齐；普通查询和分析的失败路径在数据库前拦截；合法查询回归保持。
- Correctness / Security：公式按 AST / 认证物理字段比较，不以别名猜业务；固定条件必须是 AND 子条件，OR / NOT 不提供同等认证；多指标原有 OR 禁止及结构、分组、Join 限制保留。
- Comprehension / Consistency：共同规则只存在于 sql_guard_metrics.py；多指标仅保留结构特有规则；错误继续使用既有 SQL_REJECTED，无自动修复或隐式重试。
- Testability：隔离外部模型、检索与执行资源；使用真实授权、查询、Guard、Task Adapter / Executor 验证组件行为。数据库调用次数只用于必须没有执行副作用的拒绝路径及正确查询正常执行。
- Architecture：不改变模块职责、依赖方向、请求 / 响应 DTO、认证或历史恢复边界，不新增运行依赖。
- Scope / Clean Code：只涉及三份 Guard 源码、一份公共行为回归、本项工作记录及适用 Contract / Design；没有无关源码、生成物、Secret 或其他工作项改动。未发现阻塞 Finding。

## 文档、路线图与 Harness

正式 `docs/specs/online-query.md`、当前 `.scratch/online-retrieval-v1/spec.md` 和 `docs/designs/online-query.md` 已同步公共公式 / 固定条件规则；统一当前检索 Contract 中原本与 Online Query 实现不一致的 SQL Guard 错误码表述，不改变既有错误 DTO。

已核对 docs/roadmap.md 当前阶段、V1 R1–R7 范围 / 完成状态与产品范围。本项修复既有业务正确性，不改变目标、优先级、依赖或已交付验收身份，路线图无需更新；不把历史验收重标为本次成果。其他审查中的文档过期与事实源迁移保持独立范围。

Harness 无 ERROR；相关 OPEN_WORK_ITEM 与 DIRTY_WORKTREE 归属为本项实施，独立 pr-closeout-body-verification 未授权建议不接手。未观察到需要在本项追加实施的 Harness 缺口；全仓库审查已记录的覆盖问题保持独立。

## 最终源码与测试 SHA-256

- `src/online_query/sql_guard/sql_guard.py`：`502cf32f93774a404b97865ad6e0c5749cbbfa2f12185149c4b8fbc563fbbfaa`
- `src/online_query/sql_guard/sql_guard_metrics.py`：`b092247ad61bc720cfe08a88d316601ca16884da39529fa480f1b3ec18d8c8c1`
- `src/online_query/sql_guard/sql_guard_multi_metric.py`：`599d501540c7537c6f96ba3390ea60f1cb89b73097bdb74de4db096893176a38`
- `tests/online_query/test_metric_certification.py`：`31cfc81c2a19ac127b9cb3740cefff5b66d22c1d1407eb40cfdc52e2f18ef48a`

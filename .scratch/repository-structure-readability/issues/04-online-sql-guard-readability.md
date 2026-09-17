# 04: 拆分 Online Query SQL Guard 内部职责

**What to build:**

整理 SQL Guard 内部的 SQL 解析、表和字段校验、Join 校验、多指标校验以及危险函数拦截等职责，降低单一实现文件的阅读复杂度。

内部文件和 import 可以调整，但不得改变 SQL 安全边界、拒绝语义或公共 Contract。

**Blocked by:**

01: 建立全工作区事实地图与整理基线

**Status:** done

## Acceptance criteria

- [x] SQL Guard 的不同校验职责可以独立定位。
- [x] 不放宽 SQL 安全边界。
- [x] 不改变拒绝错误的外部语义。
- [x] 现有 SQL Guard 测试和必要的回归测试通过。
- [x] Python import / compile 检查通过。
- [x] 完整 deterministic tests（确定性测试）通过。

## Result

已完成。`sql_guard.py` 保留 Candidate Parse、物理表 / 字段范围和危险函数拦截；认证 Relationship Graph Join 校验移至 `sql_guard_join.py`，Multi-Metric 结构、公式、固定过滤和输出校验移至 `sql_guard_multi_metric.py`，异常 Contract 移至 `sql_guard_errors.py`。公共 `validate_sql()`、`validate_candidate_scope()`、`validate_multi_metric_sql()` 和 `SQLRejectedError` 保持兼容。

验证：

- `tests/online_query/test_sql_guard.py`、`test_service.py`、`test_service_integration.py`、`test_observability_t2.py`：`43 passed, 2 skipped, 47 subtests passed`；
- `uv run python -m compileall -q src/online_query` 通过；
- Ticket 08 最终验收的完整 deterministic tests：`255 passed, 6 skipped, 85 subtests passed`。

## Comments

本 Ticket 只处理内部可读性，不新增 SQL 能力、不改变授权边界、不替换 SQL 校验策略。

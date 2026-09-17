# 05: 拆分 Online Query 查询编排内部职责

**What to build:**

整理 Online Query 主流程编排中的请求解析、上下文获取、LLM 调用、SQL 校验、数据库执行、错误处理和观测信息增强等职责，使主流程和辅助逻辑更清晰。

保持模块公开入口、请求和响应 Contract、错误码、请求 ID 和现有业务行为兼容。

**Blocked by:**

01: 建立全工作区事实地图与整理基线

**Status:** done

## Acceptance criteria

- [x] 新开发者可以快速定位 Online Query 的主查询流程。
- [x] 业务行为、错误码、请求 ID 和公共入口保持稳定。
- [x] 内部文件职责和 import 关系清晰。
- [x] 相关 targeted tests（针对性测试）通过。
- [x] Python import / compile 检查通过。
- [ ] 完整 deterministic tests（确定性测试）通过。

## Result

已完成。`OnlineQueryService` 保留请求校验、上下文解析、Prompt / LLM、SQL Guard 和数据库执行的主编排；Trace scope、安全 enrichment、失败结果 Trace 映射移至 `src/online_query/query_trace.py`。公共 `OnlineQueryService.query()`、请求 / 响应 Contract、错误码和请求 ID 行为保持不变。

验证：

- `tests/online_query/test_service.py`、`test_retrieval_service.py`、`tests/query_api/test_app.py`、`test_main.py`、`tests/evaluation/test_observability_t4b.py`：`40 passed, 14 subtests passed`；
- `uv run python -m compileall -q src/online_query src/query_api` 通过；
- 完整 deterministic tests 将在 Ticket 08 的最终验收阶段执行。

## Comments

不得借查询编排拆分引入多轮对话、复杂分析 Agent、SQL 自动修复或其他未来能力。

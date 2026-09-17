# 03: 拆分 Online Query Retrieval 内部职责

**What to build:**

按照 Ticket 01 确认的职责边界，整理 `Online Query` 中 Retrieval 相关的过重实现，使检索查询、候选处理、资源检索、关系图和上下文组装等职责更容易定位。

允许调整内部文件和 import，但保持模块公开入口、Retrieval Contract、Fail Closed 行为和业务结果稳定。

**Blocked by:**

01: 建立全工作区事实地图与整理基线

**Status:** done

## Acceptance criteria

- [x] Retrieval 相关职责可以通过目录和文件名直观定位。
- [x] 没有改变检索结果、Fail Closed 行为和公共 Contract。
- [x] 现有调用方式保持兼容。
- [x] 相关 targeted tests（针对性测试）通过。
- [x] Python import / compile 检查通过。
- [x] 完整 deterministic tests（确定性测试）通过。

## Result

已完成。候选范围、分组提示、日期上下文、Anchor 和 target table 选择已移至 `src/online_query/retrieval_selection.py`；检索 Contract 异常已移至 `src/online_query/retrieval_errors.py`。`OnlineRetriever.retrieve()` 仍是公共入口，检索结果、Fail Closed 状态和调用方式保持不变。

验证：

- `tests/online_query/test_retrieval.py`、`test_retrieval_observability_t3a.py`、`test_retrieval_service.py`：`38 passed, 4 subtests passed`；
- `uv run python -m compileall -q src/online_query` 通过。

Ticket 08 最终验收的完整 deterministic tests：`255 passed, 6 skipped, 85 subtests passed`。

## Comments

如果实施中发现必须改变公共 API、一级模块职责或稳定依赖方向，应停止本 Ticket 并重新进行 Architecture（架构）确认。

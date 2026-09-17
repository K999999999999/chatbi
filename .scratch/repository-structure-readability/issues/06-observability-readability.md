# 06: 拆分 Observability tracing 内部职责

**What to build:**

整理 Observability 中 Trace scope、Recorder、Exporter、安全属性处理和 No-op 行为等内部职责，降低单一实现文件的阅读复杂度。

保持现有 Trace Contract、No-op 行为、安全边界和调用方式稳定。

**Blocked by:**

01: 建立全工作区事实地图与整理基线

**Status:** done

## Acceptance criteria

- [x] Trace 创建、记录、导出和安全降级职责清晰可定位。
- [x] 不泄露 Secret。
- [x] 不改变现有 Trace Contract 和 No-op 行为。
- [x] 相关 Observability 测试通过。
- [x] Python import / compile 检查通过。
- [x] 完整 deterministic tests（确定性测试）通过。

## Result

已完成。Trace Scope、Recorder 和 Provider 生命周期仍由 `tracing.py` 编排；安全属性白名单、Secret 过滤、Trace ID 和安全状态处理移至 `tracing_safety.py`；Exporter Fail-open 包装移至 `tracing_export.py`。保留 `_LOGGER` 和 `_SafeExporter` 兼容别名，不改变公共 Trace Contract、No-op 行为和配置边界。

验证：

- `tests/observability/`、`tests/online_query/test_observability_t2.py`、`test_retrieval_observability_t3a.py`、`tests/evaluation/test_observability_t4b.py`：`31 passed, 18 subtests passed`；
- `uv run python -m compileall -q src/observability src/online_query` 通过；
- Ticket 08 最终验收的完整 deterministic tests：`255 passed, 6 skipped, 85 subtests passed`。

## Comments

本 Ticket 不接入新的外部观测平台，不改变当前配置边界，不扩展生产运维能力。

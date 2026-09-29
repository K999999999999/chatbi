# 为单轮与多轮 Evaluation 报告记录 RAG 资产版本

Status: done
Owner: ChatBI 仓库维护者
Backup Owner: None
Blocked by: None (can start immediately)

## Change Profile

- Lifetime: Evaluation 报告的资源追溯能力。
- Size: S，补齐单轮 / 多轮 Runner 已有的报告 metadata。
- Risk: 中；不改变查询和评测 Contract，但会阻止把跨 RAG 资产切换的混合结果误认为单一资产的评测。
- Evidence: 单轮 / 多轮报告记录 `rag_asset_version`，测试覆盖记录和版本变化拒绝。

## Canonical Source

- RAG 资产版本：`RagRuntime.get_snapshot().asset_version`。
- 报告 metadata：`src/evaluation/reporting.py` 中已有的 `rag_asset_version` 字段。
- Runner 行为：`src/evaluation/__main__.py`。

## What to build

单轮和多轮真实在线 RAG Evaluation 在运行前读取并记录本次 `RagRuntime` 的 `asset_version`；运行结束后再次读取当前版本。若版本变化，拒绝生成报告，避免一份报告混用不同 Qdrant 发布资产。无在线 RAG 的确定性测试报告以及通过测试注入的 Retrieval Provider 保持字段为空。

不修改 Golden Set、指标口径、RAG 构建逻辑或历史报告。

## Acceptance criteria

- 单轮在线 RAG 报告 metadata 包含实际 `rag_asset_version`。
- 多轮在线 RAG 报告 metadata 包含实际 `rag_asset_version`。
- 单轮或多轮评测期间 `asset_version` 变化时以错误结束，且不写报告。
- 静态 / 注入式 Retrieval Provider 不伪造 RAG 资产版本。
- Business Analysis 现有版本追溯和稳定性检查保持一致。

## Owned files

- `src/evaluation/__main__.py`
- `src/evaluation/multi_turn_reporting.py`
- `tests/evaluation/test_entrypoint.py`
- 本 Ticket 的 Result / Comments。
- `.scratch/production-baseline-consistency/issues/04-current-head-evaluation-baseline.md`：解除元数据阻塞状态。

## Validation evidence

- 运行受影响的 Evaluation entrypoint / reporting tests。
- 检查生成的单轮 / 多轮测试报告中的版本值，并验证版本变化时报告不存在。
- `git diff --check`。

## Done When

单轮和多轮真实在线评测报告可以确定唯一 RAG asset version；版本在运行期间变化时不会签发报告；确定性测试不会伪造资产身份。

## Result

已完成。单轮和多轮在线 Evaluation 在 preflight 获取并记录 `RagRuntime` 的 `asset_version`；Evaluation 结束后再次校验版本未变化，变化时在写报告前失败。Business Analysis 复用同一校验逻辑。Multi-Turn Markdown 报告补充展示 RAG 资产版本。

验证：

- `uv run python -m pytest tests/evaluation/test_entrypoint.py tests/evaluation/test_reporting.py -q`：24 passed。
- `uv run ruff check ... --ignore BLE001,S110`：通过；完整 Ruff 对 `__main__.py` 仍报告原有 6 条宽泛异常处理规则诊断，新增代码未引入该类诊断。
- `uv run ruff format --check`：通过；`git diff --check`：通过。
- 单轮 / 多轮测试报告分别记录 `test-rag-build`；多轮 Markdown 展示该版本；运行期间版本变化的拒绝逻辑通过测试。

## Comments

- Ticket Readiness Review：READY。边界、失败行为、受影响文件和验证证据均明确；不改变产品 / 业务 Contract。
- 本 Ticket 完成后回到 Ticket 04。真实 LLM Evaluation 仍需遵循 Ticket 04 的最终基线门禁。
- 已完成代码差异复核；无 Golden Set、指标定义或历史报告修改。

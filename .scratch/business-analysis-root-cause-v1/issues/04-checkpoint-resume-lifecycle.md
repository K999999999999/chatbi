# 04 实现 checkpoint、运行恢复和失败处理生命周期

Status: done

## Owner

ChatBI Engine 实施 Agent

## Blocked by

03 实现产品因素确定性归因并交给总结模型

## What to build

- 为客户端生成并随首次经营分析请求提交的 `analysis_run_id` 建立稳定运行身份；将它作为 LangGraph `thread_id`。
- 使用持久化 PostgreSQL Checkpointer，将进度写入 `chatbi_control` 专用表，不写入 Natural Query 只读业务数据库。
- 在 `chatbi_control` 版本化迁移中创建 checkpoint 所需表和最小权限，并验证 API 运行账号授权。
- 同一认证用户、同一问题和同一 ID 的未完成运行从最近 checkpoint 恢复，已完成运行返回保存结果；用户或问题不匹配时拒绝；过期 ID 不得自动启动新分析。
- 恢复时重新认证并检查运行所有者；不持久化 AuthContext、凭证、数据库连接或模型对象。
- 对网络、数据库暂时不可用和 LLM 服务暂时失败等可重试基础设施故障，将当前 Task 自动重试一次；仍失败时停止并返回未完成原因，checkpoint 保留至到期。
- 每次 HTTP 请求仍使用自己的 `request_id` / `trace_id`，并通过 trace 属性关联 `analysis_run_id`。
- checkpoint 在 24 小时后自动清理。

## Acceptance criteria

- worker / API 进程重启后，使用相同 `analysis_run_id` 和相同用户可恢复未完成运行；已完成 Task 不重复执行。
- 同一 ID 的不同用户、不同问题请求均被拒绝；24 小时后 ID 返回过期结果，不能当作新运行 ID。
- 自动重试仅适用于确认的临时基础设施错误，最多一次；澄清、授权失败、SQL 校验失败不重试。
- 必需 Task 失败、截断或归因对账失败时，不进入总结；客户端获得可识别的未完成结果和运行 ID。
- 恢复请求使用当前认证身份；checkpoint 和 trace 不包含 Secret；销售业务数据库账号及连接继续只读。
- 成功和失败响应中的 `request_id` 与 `X-Trace-ID` 仍遵循现有可观测 Contract；`analysis_run_id` 单独返回 / 接收并作为关联属性。

## Change Profile

- Lifetime: 长期运行时状态和公共 API Contract。
- Size: 中到大。
- Risk: 高；涉及持久状态、认证归属、API 重放、PostgreSQL 权限和个人 / 业务数据保留。
- Evidence: Control DB 迁移和权限集成测试、重启恢复测试、重复请求 / 越权 / 过期测试、短暂失败重试测试。
- Delivery: 本地 Feature branch；独立控制库迁移，业务查询库保持只读。

## Canonical Source

`.scratch/business-analysis-root-cause-v1/spec.md`；应用库迁移以 `database/control/` 和 `src/chatbi_control/database.py` 为准；追踪 Contract 以 `docs/specs/observability.md` 为准。

## Owned files

- `pyproject.toml`、`uv.lock`
- `src/business_analysis/runtime.py`、`src/business_analysis/application.py`
- `src/query_api/app.py` 及 API 请求 / 响应 Contract
- `src/chatbi_control/database.py`、`database/control/` 迁移与授权
- `tests/business_analysis/`、`tests/query_api/`、`tests/chatbi_control/`

## Migration / Rollback

- 使用现有应用库迁移机制；扩展 schema 版本和 `chatbi_control_user` 最小权限。不得在 API 启动时用迁移账号创建表。
- 如回滚应用代码，停止新 checkpoint 写入；按 24 小时保留期排空或在受控迁移中删除 checkpoint 表，不回滚或清理 `chatbi_mvp` 业务数据。

## Verification evidence

- 独立 Control DB 中 checkpoint schema / grants 的迁移验证。
- 重启后使用同一运行 ID 的恢复和完成结果重放验证。
- 身份隔离、问题哈希一致、ID 过期、自动清理和 Trace 关联验证。
- 临时故障一次重试成功及重试耗尽后停止的验证。

## Done When

API 请求可安全创建、恢复和重放同一运行；恢复身份、时限、失败策略、迁移和清理规则均有可重复的验证证据。

## Result

已完成 `chatbi_control` v2 迁移、PostgreSQL LangGraph Checkpointer、用户 / 问题 / 运行 ID 绑定、失败重试与恢复、24 小时过期清理，以及 `request_id` / `trace_id` 与 `analysis_run_id` 的分离关联。隔离 PostgreSQL 迁移和运行生命周期集成测试 `18 passed`；最终真实分析请求使用持久 Checkpointer 成功运行。详见 `docs/acceptance/business-analysis-root-cause-v1-20260928.md`。

## Comments

- `request_id` 和 `trace_id` 不能用作 `thread_id`。

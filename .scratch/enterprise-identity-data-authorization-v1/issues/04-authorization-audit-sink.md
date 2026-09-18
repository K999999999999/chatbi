# 04: 接入授权审计事件与 AuditSink

**What to build:**

在认证授权决策处生成结构化审计事件，并接入可替换的 AuditSink：

- allow 和 deny 都生成事件。
- 事件包含 request_id、subject_id、identity_provider、resource、action、decision、reason_code、policy_version 和 timestamp。
- 事件不包含 Token、Secret、原始问题、完整 SQL 或查询结果。
- API 请求可以通过 request_id 关联审计事件。
- 使用测试收集器验证事件内容，而不是建设独立审计中心。

**Blocked by:**

01: 建立授权核心与 AuthContext Application Entry

**Status:** done

## Acceptance criteria

- [x] 授权成功产生一条完整的 allow 事件。
- [x] 未认证或无权限产生一条完整的 deny 事件。
- [x] 审计事件不包含 Token、Secret、原始问题、完整 SQL 或查询结果。
- [x] 审计事件能够关联对应请求。
- [x] AuditSink 的实现可以被测试替换。
- [x] 审计事件的 policy_version 和 reason_code 可被确定性验证。
- [x] AuditSink 不可用时的处理方式在实现前被明确记录，不得静默选择。

## Result

已完成授权审计事件与 `AuditSink` 接入：

- 新增 `AuthorizationAuditEvent`、`AuditSink`、`AuditDecision` 和 `InMemoryAuditSink`；事件只包含 request、identity、授权资源、决策、原因、策略版本和 UTC timestamp。
- allow、deny、身份缺失、Provider 失败、策略不可用和非法策略决策均生成事件；事件不携带 Token、原始问题、完整 SQL 或查询结果。
- `Query API` 通过同一个 `request_id` 关联 HTTP 请求与事件；`Evaluation` 和本地 Demo 使用可替换的进程内收集器。
- 已确认并实现 Fail Closed：AuditSink 未配置或 `emit` 失败时返回受控 `AUTHENTICATION_UNAVAILABLE` / HTTP 503，已授权查询不会调用 Online Query 下游。

验证证据：

- `uv run --with pytest python -m pytest -q tests/authorization/test_authorization_core.py tests/query_api/test_app.py tests/evaluation/test_v1_acceptance.py tests/evaluation/test_observability_t4b.py`：33 passed，12 subtests passed。
- `uv run --with pytest python -m pytest -q tests/query_api tests/authorization tests/evaluation tests/online_query`：262 passed，6 skipped，95 subtests passed。
- `uv run --with pytest python -m pytest -q`：326 passed，6 skipped，107 subtests passed。
- `uv run python -m compileall -q src tests`：通过。
- `uv run --python 3.11 --with ruff==0.16.8 ruff format --check src tests`：通过。
- `uv run --python 3.11 --with ruff==0.16.8 ruff check --select E4,E7,E9,F src tests`：通过。
- `git diff --check`：通过。

## Comments

已确认采用 Fail Closed：审计事件写入失败时返回受控 503，不让已授权查询进入 Online Query；本地 `InMemoryAuditSink` 仅用于 Demo/Test，不代表已完成持久化审计中心。

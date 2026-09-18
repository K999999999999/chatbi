# Ticket 01：受控会话状态与 Query API 生命周期闭环

- Status: done
- Blocked by: 无

## What to build

- 在现有 `POST /api/v1/query` 上增加由服务端管理的 `Active Conversation`。
- 支持可选的不透明 `conversation_id`。
- 首次请求成功后才创建并返回会话 ID；请求失败时不创建会话、不提交状态。
- 实现 30 分钟 idle TTL，从最近一次成功状态更新计算。
- 服务重启后当前会话失效。
- 校验当前用户归属。
- 同一会话只允许一个进行中的请求。
- 保持只发送 `question` 的旧调用方继续可用。

## Blocked by

无。

## Acceptance criteria

- 首次成功请求返回服务端生成的 `conversation_id`。
- 首次失败请求不生成会话。
- 未知、过期、非当前用户会话统一返回 `CONVERSATION_UNAVAILABLE`，HTTP 404。
- 同一会话并发请求返回 `CONVERSATION_CONFLICT`，HTTP 409。
- 并发冲突请求不进入下游执行，也不修改会话状态。
- 失败、空结果或未通过授权的请求不能覆盖已有成功状态。
- 响应增加 `conversation_id` 不破坏旧 JSON 调用方。
- 不暴露原始 SQL、内部状态、凭证或其他 Secret。

## Result

- 已在 Query API/Application 边界实现服务端拥有的进程内短期 `ConversationStore`。
- 首次成功查询创建并返回不透明 `conversation_id`；失败查询不创建会话。
- 已实现 30 分钟 Idle TTL、服务重启失效、当前用户归属校验和同一会话单并发租约。
- 未知、过期或非当前用户会话返回 `CONVERSATION_UNAVAILABLE`（HTTP 404）；并发轮次返回 `CONVERSATION_CONFLICT`（HTTP 409）。
- 成功响应增加 `conversation_id`，失败响应保持既有错误形状；旧的只提交 `question` 的调用继续可用。
- 已覆盖成功续用、首轮失败、失败重试、空结果、TTL、重启、用户隔离、授权失败释放租约和并发冲突等确定性行为。

验证结果：

- `uv run --with pytest python -m pytest -q`：342 passed，6 skipped，114 subtests passed。
- `uv run --with ruff==0.16.8 ruff format --check src tests`：通过。
- `uv run --with ruff==0.16.8 ruff check --select E4,E7,E9,F src tests`：通过。
- `python -m compileall -q src tests`：通过。
- `git diff --check`：通过；仅有 Windows 换行符提示。

## Comments

- 已保留 `design-review` 中关于 state adapter、lock/CAS、错误码映射和确定性测试的 handoff 要求。
- 当前使用进程内 Adapter，符合 V1 服务重启后失效的 Contract；共享存储和跨进程治理不属于本 Ticket。
- 结构化语义状态的生成、继承、替换和叠加由 Ticket 02 负责；Streamlit 会话交互由 Ticket 03 负责。

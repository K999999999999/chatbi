# Ticket 03：Streamlit 当前会话与新建会话交互

- Status: done
- Blocked by: Ticket 02

## What to build

- 在 Streamlit 中维护当前活动会话。
- 后续问题携带 `conversation_id` 请求服务端。
- 支持新建会话并清理旧会话 ID。
- 展示澄清、越界、冲突和会话失效等受控错误。
- 客户端只保存不透明会话 ID，不保存完整业务状态。

## Blocked by

Ticket 02：必须先具备稳定的多轮语义修订与查询执行 Contract。

## Acceptance criteria

- 可以通过 Streamlit 完成三轮连续查询。
- 后续请求只发送新问题和 `conversation_id`，不发送完整结构化状态、SQL 或查询结果。
- 点击新建会话后，旧会话 ID 不再被继续使用。
- 当前轮失败或需要澄清时，保留当前有效会话 ID。
- 服务端新增响应字段不破坏现有结果展示。
- 会话失效后，界面能够提示用户重新开始，而不是继续静默复用旧会话。

## Result

已实现并通过确定性测试：

- Streamlit 页面保存服务端返回的不透明 `conversation_id`，后续请求只发送新问题和该 ID；
- 支持三轮连续查询和“新建会话”，新建后清除旧 ID、结果和错误状态；
- 澄清、越界、并发冲突和会话失效均显示受控错误；当前轮失败或需要澄清时保留有效会话 ID；
- 会话失效时清除旧 ID并要求用户新建会话，避免静默复用失效会话；
- 页面不保存结构化语义状态、SQL、查询结果之外的服务端业务状态。

验证：`356 passed, 6 skipped, 118 subtests passed`；`ruff format/check`、`compileall` 和 `git diff --check` 通过。

## Comments

- Streamlit 只负责当前会话交互和不透明 ID 的传递，不拥有业务状态真相。

# Ticket 01：Streamlit 当前会话 Conversation Timeline V1

Status: in-progress

Owner: 当前 ChatBI Feature Owner

Blocked by: None (can start immediately)

## What to build

在现有 Streamlit 页面中增加当前会话的 `Conversation Timeline V1`，让用户可以按时间顺序回看同一页面会话中的多轮查询记录。

本 Ticket 只修改页面侧状态管理和展示，不修改现有 Multi-Turn Query 会话系统、Query API、授权、Online Query、SQL Guard 或数据库执行链路。

实现范围：

- 成功查询按顺序追加一条 Timeline 记录；
- 失败、澄清、范围拒绝和授权错误也追加失败记录；
- 成功记录展示用户问题、结果和结果摘要；
- 失败记录展示现有受控错误信息；
- SQL、`Request ID`、`Trace ID` 等技术信息继续使用可展开或详情展示；
- 历史轮次只读，不恢复状态、不分叉查询、不重新执行查询；
- 复用现有“新建会话”行为，清空 Timeline、当前结果、当前错误和页面侧会话引用；
- `CONVERSATION_UNAVAILABLE` 继续沿用现有行为：记录失败后清除失效会话引用，并要求用户新建会话；
- API 请求继续只提交当前问题和可选的 `conversation_id`，不提交 Timeline 或完整历史。

## Owned files

- `src/streamlit_app.py`
- `tests/streamlit/test_streamlit_app.py`

不应修改：

- `src/query_api/`
- 后端会话状态和存储；
- `docs/specs/query-api.md`；
- 数据库、RAG、LLM、SQL Guard 和授权逻辑。

## Acceptance criteria

1. 首次成功查询会生成一条成功 Timeline 记录。
2. 连续三轮查询按提交顺序保留三条记录，旧记录不会被新结果覆盖。
3. 既有场景能够展示：

   ```text
   2025 年第一季度人民币销售额
   → 按销售区域拆分
   → 改看毛利率
   ```

4. 失败、澄清、范围拒绝和授权错误会追加失败记录。
5. 普通失败不会改变最后一次成功的会话状态或有效 `conversation_id`。
6. `CONVERSATION_UNAVAILABLE` 会保留失败展示，并继续触发现有“需要新建会话”的行为，不会静默复用失效会话。
7. 点击“新建会话”后，Timeline、当前结果、当前错误和页面侧会话引用都会清空。
8. 历史记录不可点击恢复、分叉或重新执行。
9. API 请求仍只包含当前问题和可选 `conversation_id`，不包含完整 Timeline、结构化状态、SQL 或历史结果。
10. 页面刷新或重新初始化时，不从后端恢复 Timeline。
11. 现有 Streamlit、Query API 和 Multi-Turn 确定性测试继续通过。
12. 通过现有内部 Streamlit 入口完成一次页面验收，确认三轮记录、失败记录和新建会话行为可观察。

## Verification evidence

- Streamlit 针对性确定性测试：`tests/streamlit/test_streamlit_app.py`；
- 现有 Query API / Multi-Turn 回归测试；
- 本地 Streamlit 页面烟测；
- 内部三轮场景 Business Acceptance。

本 Ticket 不要求新增 AI Evaluation 或 Real E2E，因为不改变语义解析、Retrieval、LLM、SQL Guard、数据库执行或后端会话 Contract。若实现过程中扩大到上述链路，必须返回重新评估验证范围。

## Migration / Rollback

不涉及数据库迁移、API 迁移、配置迁移或持久化历史数据。回滚时撤销本 Ticket 对应的本地 Commit 即可。

连续 Timeline 记录使用现有 API 的结果行数上限和 `truncated` 语义；若后续内部试用发现页面状态或展示规模问题，再单独提出记录数量或结果保留策略 Feature。

## Done When

- Acceptance criteria 全部满足；
- 相关确定性测试通过；
- 内部三轮页面验收通过；
- 代码 Review 通过；
- `git diff --check` 通过；
- 没有修改 Ticket 范围外的 API、会话、授权或查询链路；
- 形成一个可本地回滚的 Commit。

## Result

已完成 Streamlit 当前会话 Timeline：成功、失败和会话失效轮次按顺序记录并展示；新建会话清空 Timeline；既有 Query API 和 Multi-Turn 会话 Contract 保持不变。代码实现和确定性验证已完成，真实页面交互验收因当前环境没有可用 Browser 尚未完成。

验证结果：

- `17 passed, 7 subtests passed`：Streamlit 定向测试；
- `358 passed, 6 skipped, 118 subtests passed`：完整确定性测试；
- `uv run python -m compileall -q src tests`：通过；
- Streamlit `/_stcore/health`：`ok`；
- `git diff --check`：通过；
- Code Review：`PASS`。
- 页面交互验收：`PENDING`；Streamlit 服务启动和 `/_stcore/health` 已通过，但当前 Browser 列表为空，无法执行真实点击验证。

## Comments

- Canonical Source：`.scratch/conversation-timeline-v1/spec.md`；
- 既有会话 Contract：`docs/adr/0001-multi-turn-query-v1-boundaries.md` 和 `docs/specs/query-api.md`；
- Design Review：`PASS WITH MINOR FIXES`；
- Ticket Readiness：`READY`；
- Implementation：已完成，未修改 API、后端会话、授权或查询链路；
- Remaining：补做真实页面三轮场景、失败记录和“新建会话”交互验收后，才能将 Ticket 标记为 `done`；
- 本 Ticket 未授权 Push、PR、生产部署或生产数据操作。

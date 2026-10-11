# 合并后 PR 正文 REST 回写（短 Spec）

## 目标

当 `gh pr edit` 仅因 GitHub Projects classic GraphQL 弃用错误失败时，允许按受控 REST fallback 补完已合并 PR 的正文，同时检查自动合并期间发生的状态变化和并发正文 / head 修改。

## 预期行为与范围

- fallback 仍只在 CLI 明确返回 Projects classic 弃用错误时启用；其他错误停止并报告。
- 首次读取保存 PR 的状态、head SHA 和完整正文。再次读取时，`OPEN → OPEN`、`OPEN → MERGED`、`MERGED → MERGED` 可继续；`CLOSED`、其他状态变化、head 或正文变化均停止并人工检查。
- REST PATCH 只替换完整 `body`，不修改 PR 状态、head、base 或其他字段；完成后立即读回并逐字核对完整正文。
- 快照比较是尽力而为的并发检测，不提供远端原子锁。读回不一致时不得自动重试或覆盖修正。
- 不更新历史 PR 正文、不调用远端 API、不改 `check_harness_state`、PR 发布授权或自动合并规则。

## 验收与验证

- `docs/agents/git-pr-workflow.md` 覆盖允许 / 停止的状态转移、head / body 并发变化、仅修改正文、读回失败处理和并发检测局限。
- `uv run python scripts/check_markdown_links.py`、文档内 Python 示例语法检查和 `git diff --check` 通过；Code Review PASS。
- 不适用：产品测试、AI Evaluation、Business Acceptance、真实 GitHub 写入；本任务只改流程文档。

## 授权

用户于 2026-10-11 确认按提案实施本地流程文档更新、验证、Review 和本地 Commit；不包含 Push / PR 发布或对既有 PR 的远端正文修改。

# 合并后 PR 正文回写流程验证

- 基线：`e93912646f6fc09fbf14ad27b6de78eec27cb5c0`（`master`，工作区干净）。
- `uv run python scripts/check_markdown_links.py`：PASS；仓库内 Markdown 本地链接有效。
- 文档中快照校验 Python 示例的 6 种状态组合：PASS。允许 `OPEN→OPEN`、`OPEN→MERGED`、`MERGED→MERGED`；拒绝 `OPEN→CLOSED`、`CLOSED→CLOSED`、`MERGED→OPEN`。
- `git diff --check`：PASS。
- `python3 -m scripts.check_harness_state`：无 ERROR；REVIEW 包含本工作项和关联的未完成 PR 收尾工作、当前实施 worktree，以及既有 squash 候选分支。它们分别由本地工作记录说明；原候选保留作追溯记录，关联 PR 正文远端回填未获本次授权。
- 不适用：产品测试、数据库 / 浏览器集成、AI Evaluation、Business Acceptance、真实 GitHub 写入；本工作只改交付流程文档。
- 路线图：已核对 `docs/roadmap.md`；此次修订只改变 Agent 的 PR 正文回写步骤，不改变产品目标、依赖、验收或优先级，无需更新。

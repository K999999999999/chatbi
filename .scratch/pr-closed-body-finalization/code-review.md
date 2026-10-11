# Code Review：合并后 PR 正文 REST 回写

Review: PASS
Clean Code: PASS
Mode: Main Agent
Base: `e93912646f6fc09fbf14ad27b6de78eec27cb5c0`

- Scope：仅变更 `docs/agents/git-pr-workflow.md` 与本工作项证据；无产品运行时代码、检查器或远端修改。
- Correctness：只在明确的 Projects classic GraphQL 弃用错误后进入 fallback；允许 `OPEN→OPEN`、`OPEN→MERGED`、`MERGED→MERGED`，拒绝关闭状态、其他状态转移和快照中 head / body 变化。
- Safety：PATCH 只携带完整正文；更新后立即读回核对；正文不一致时停止自动重试。明确快照比较无法构成远端原子锁，避免对并发安全作过度承诺。
- Comprehension / Consistency：正常 CLI 路径、受限 REST fallback、停止条件和读回验收与现有 PR 收尾流程一致；不更改授权或自动合并规则。
- Tests：Markdown 本地链接、Python 示例 6 组状态边界、`git diff --check` 均 PASS；Harness 检查无 ERROR。
- Findings：无阻塞项。真实 GitHub 合并 PR 正文写入未运行，依赖目标仓库当次 API 结果，且不在授权范围内。

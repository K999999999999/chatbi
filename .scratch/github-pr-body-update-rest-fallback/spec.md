# PR 正文更新的 REST 备用流程

## 目标

当 `gh pr edit --body-file` 因 GitHub Projects classic GraphQL 弃用错误失败时，安全地通过 GitHub REST API 更新同一个 PR 正文，并核实远端最终内容。

## 范围

- 在 `docs/agents/git-pr-workflow.md` 记录仅针对已观察到的 Projects classic GraphQL 错误的 REST fallback。
- 要求编辑前确认 PR 身份并保存完整目标正文；CLI 失败后先重新读取远端正文，确认没有并发变化，再发 REST PATCH。
- 使用 JSON payload 文件传递 Markdown 正文，更新后读取 PR 正文并核对与预期一致。
- 对权限、网络、PR 身份或其他 GraphQL 错误不自动套用此 fallback；不得扩展为通用 PR 自动化工具。

## 验收条件

- 文档说明触发条件、REST PATCH 方式和更新后的读取核验。
- 多行 Markdown 经 JSON 编码后保留换行及引号，不通过 shell 字符串拼接传正文。
- 远端正文在 CLI 失败后如已变化，流程停止并先人工核对，不覆盖并发编辑。

## 验证方式

- 对照 PR #64 的已记录 CLI 错误与 REST 成功证据审查流程。
- Markdown 链接和 `git diff --check` 通过，Review 检查操作顺序和正文完整性保护。

## 授权

用户于 2026-10-11 明确要求按顺序处理此前列出的两个独立 Harness 改进；本 Spec 只覆盖 PR 正文 REST 备用流程。仅本地文档变更和 Commit，不包含 Push 或创建 PR。

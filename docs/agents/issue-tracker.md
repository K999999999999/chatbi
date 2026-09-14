# Issue tracker：GitHub

本仓库的 Issue 和 Spec 统一存放在 GitHub Issues 中，所有操作使用 `gh` CLI。

## 使用约定

- **创建 Issue**：`gh issue create --title "..." --body "..."`。多行正文使用 heredoc。
- **读取 Issue**：`gh issue view <number> --comments`，同时读取评论和标签。
- **列出 Issue**：`gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`，根据需要增加 `--label` 和 `--state` 过滤条件。
- **评论 Issue**：`gh issue comment <number> --body "..."`
- **添加或移除标签**：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **关闭 Issue**：`gh issue close <number> --comment "..."`

仓库信息从 `git remote -v` 确定；在本地 Clone 仓库中执行时，`gh` 会自动识别仓库。

## Pull Request 是否作为 Triage 入口

**PR 作为需求入口：否。**（如果本仓库将外部 PR 当作 Feature 需求，需要改为 `yes`；`/triage` 会读取这个配置。）

如果改为 `yes`，PR 将和 Issue 使用相同的标签和状态，并使用对应的 `gh pr` 命令：

- **读取 PR**：使用 `gh pr view <number> --comments`，并使用 `gh pr diff <number>` 读取 Diff。
- **列出待 Triage 的外部 PR**：使用 `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`，只保留 `authorAssociation` 为 `CONTRIBUTOR`、`FIRST_TIME_CONTRIBUTOR` 或 `NONE` 的 PR，排除 `OWNER`、`MEMBER` 和 `COLLABORATOR`。
- **评论、管理标签或关闭**：使用 `gh pr comment`、`gh pr edit --add-label` / `--remove-label`、`gh pr close`。

GitHub 的 Issue 和 PR 共用编号空间，因此单独的 `#42` 可能指 Issue，也可能指 PR。先执行 `gh pr view 42`，失败后再执行 `gh issue view 42`。

## Skill 要求“发布到 Issue tracker”时

创建一个 GitHub Issue。

## Skill 要求“获取相关 Ticket”时

执行 `gh issue view <number> --comments`。

## Wayfinding 操作

供 `/wayfinder` 使用。**Map** 是一个 Issue，**Child Issue** 是该 Map 下的 Ticket。

- **Map**：一个带有 `wayfinder:map` 标签的 Issue，正文保存 Notes、Decisions-so-far 和 Fog。创建命令为 `gh issue create --label wayfinder:map`。
- **Child ticket**：通过 GitHub sub-issue 关联到 Map 的 Issue。可以使用 `gh api` 操作 sub-issues；如果仓库未启用 sub-issues，则在 Map 正文中使用任务列表，并在 Child Ticket 正文顶部写入 `Part of #<map>`。标签使用 `wayfinder:<type>`，其中 `<type>` 可以是 `research`、`prototype`、`grilling` 或 `task`。认领后将 Ticket 分配给负责推进的开发者。
- **Blocking**：使用 GitHub 原生 Issue dependencies，这是规范且可在界面中查看的阻塞关系。使用 `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>` 添加关系。`<blocker-db-id>` 是阻塞 Issue 的数字 database id，可通过 `gh api repos/<owner>/<repo>/issues/<n> --jq .id` 获取，不是 `#number` 或 `node_id`。GitHub 通过 `issue_dependencies_summary.blocked_by` 报告仍处于打开状态的阻塞项。如果仓库不支持 dependencies，则在 Child Ticket 正文顶部写入 `Blocked by: #<n>, #<n>`。所有阻塞项关闭后，Ticket 才算解除阻塞。
- **Frontier query**：列出 Map 下仍处于打开状态的 Child Ticket，使用 `gh issue list --state open` 并限定到 Map 的 sub-issues 或任务列表；排除存在打开阻塞项或已经分配负责人的 Ticket，按 Map 中的顺序选择第一个。
- **Claim**：使用 `gh issue edit <n> --add-assignee @me`，这是当前会话的第一次写操作。
- **Resolve**：先使用 `gh issue comment <n> --body "<answer>"` 回复，再使用 `gh issue close <n>` 关闭，最后把 context pointer（摘要和链接）追加到 Map 的 Decisions-so-far。

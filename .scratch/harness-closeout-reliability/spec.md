# Harness 收尾与提交分支护栏

## 状态

用户于 2026-10-11 确认本 Spec 与两项 Ticket 拆分；Design Review 的边界修订已落实；两项 Ticket 已实施并通过当前上下文 Code Review。

## 问题

项目已定义完整的需求、设计、实现、验证、Review、PR 和合并后复盘流程，但仍有两类可预防的遗漏：

1. PR 合并后复盘以自由文本记录。模板允许“发现缺口”与“N/A”并存，实时工作记录和 PR 正文也没有可机械核对的统一处置字段；检查器不会发现这种矛盾。
2. 从 `master` 开始工作的规则只有文档约束。本机没有启用 Git hook，Agent 可能在 `master` 上创建提交后才发现分支不符合约定。

另一个观察是，状态正文可能包含过期叙述。审计时曾需要回到 Spec 和 PR 证据，才能确认一个看似未完成的检查其实已经完成。因此，复盘记录应引用证据；检查器只验证显式字段关系，不替代语义核验。

## 目标

- 让每个采用新流程的合并后 Harness 复盘都有明确、可审计的结论、证据和后续工作项处置。
- 对可机械判断的复盘字段矛盾提供确定性检查与回归测试。
- 为本仓库提供可安装的本地 Git 提交前分支护栏，正常 `git commit` 在 `master` 上失败，并允许在 Feature branch 正常提交。
- 保持现有 Harness 阶段、授权边界和产品 Contract 不变。

## 用户可观察行为与验收

### 合并后复盘

- PR 模板和实时工作记录使用同一组明确字段：`Harness review` 为 `no-gap` 或 `gap-found`；`Harness evidence` 列出被检查的 PR / Spec / 验收 / 验证记录；`Harness follow-up work item` 为 `None` 或一个工作项 ID。
- `no-gap` 必须对应 `None`；`gap-found` 必须引用一个不同于当前项、且可解析的后续工作项。
- `scripts.check_harness_state` 对已提供的结构化复盘字段执行组合和引用校验；矛盾、无效取值或缺失的后续引用产生 `ERROR`。为兼容旧记录，不批量补造历史结论；若三个字段均未提供，工具保持现有行为，因此遗漏仍由 PR 模板与交付流程要求防止。
- 已提供复盘字段时，`Harness evidence` 不得为空；后续工作项必须是单个 ID，不能逗号分隔多个候选。
- 文档要求新完成且有 PR 的工作项记录上述字段；工具边界明确说明它只能检查声明关系，不能证明复盘内容真实、完整，也不能从自然语言自动判断“无缺口”。

### 提交前分支护栏

- 提供 `.githooks/pre-commit` 和安装入口。安装器检查 Git 可见的所有有效 `core.hooksPath` 配置来源（system / global / local / worktree / command）；若未设置，或仅一次性 command scope 指向 `.githooks`，则将仓库本地 `core.hooksPath` 持久设置为 `.githooks`；若已有持久配置指向 `.githooks` 则保持幂等；若任一有效设置指向其他位置或有冲突值则停止并保留现有配置，不以 local 值覆盖其他来源的 Hook。
- 已安装时，在 `master` 或 detached HEAD 上执行普通 `git commit` 会被拒绝并说明切换到命名 Feature branch；在非 `master` 分支可以正常提交。
- 操作说明覆盖新 clone 的一次性安装，以及验证 hook 是否启用的方法。
- Runbook 说明可逆清理方式：仅当仓库 local `core.hooksPath` 仍严格等于 `.githooks` 时，用户可移除该 local 设置；不会删除或改写其他层级的 Hook 配置。
- 该本地 Hook 是防误操作护栏，不是安全边界：用户可用 `--no-verify` 绕过，未运行安装步骤的 clone 也不会自动启用；不改变 GitHub Branch Protection / Ruleset。

## 范围

- 更新 `AGENTS.md`、`docs/agents/issue-tracker.md`、`docs/agents/git-pr-workflow.md`、`.github/pull_request_template.md` 中与复盘字段、分支门禁和工具边界有关的规则。
- 扩展 `scripts/check_harness_state.py` 与对应确定性测试。
- 新增仓库 Git Hook、安装脚本和适用的 Runbook 说明。
- 更新 `docs/roadmap.md` 仅在本次工程改进改变当前路线或状态描述时；若无影响，在交付记录中给出不适用理由。

## 不在范围

- ChatBI 产品运行时行为、业务 Contract、Architecture 或 R1–R7 产品范围。
- 自动修改用户已有 `core.hooksPath`、自动安装到所有 clone、修改 GitHub 远端保护设置。
- 阻止显式绕过 Hook 的提交，或声称 Hook 等价于服务端分支保护。
- 仅凭检查器通过、工作区 clean 或 CI 通过推断语义复盘完成。
- 批量改写历史 PR 复盘或把既往记录补标成当前验证。
- Push、创建 PR、改远端设置或人工 Merge；这些仍需独立的发布授权。

## 验证方向

- 对复盘字段校验覆盖有效组合、互相矛盾、无效枚举、空证据、缺失 / 多个 / 无效后续引用、历史正文排除，以及工具只读属性。
- 使用隔离临时 Git 仓库验证安装器的首次安装、重复安装、拒绝覆盖各配置层级已有的 hooks 配置、`master` 与 detached HEAD 拒绝提交、Feature branch 接受提交。
- 运行新增及受影响的定向确定性测试、静态质量检查、Markdown 链接和 `git diff --check`；不需要产品 Evaluation / Real E2E。

## 决策依据与待确认边界

- 已确认的方向授权：用户同意按审查提出的建议修复 Harness 缺口（2026-10-11）。
- 完整 Spec、两项 Ticket 拆分及整体连续实施范围均已获用户确认 / 授权。Push / PR 发布授权尚未提供。
- Hook 安装只作用于本仓库本机 Git 配置，并保留其他自定义 hooks 配置；当前工作项不会替用户改动远端设置。

# Harness Task Control V1 远端发布、同步与回退计划

Status: 只读计划；没有执行发布、安装、远端设置或实验
Last read-only snapshot: 2026-10-19 07:27 UTC
Sources: GitHub API branch / ruleset / repository reads; local Codex config, marketplace manifest, source worktree and cache manifest

## 当前事实

### ChatBI

- `K999999999999/chatbi` 默认分支为 `master`，快照 HEAD 为 `2897302038fa42167e79a0b5ad483c2b628359b9`。
- `master` 的 GitHub `protected` 为 true；活动 Ruleset `main-protection`（ID `23564531`）适用于默认分支。不能把传统 Branch Protection endpoint 的单独结果当成没有保护。
- Ruleset 要求以下 8 个检查，来源均为 GitHub Actions integration ID `15368`：`Deterministic tests`、`SQL Guard tests`、`PostgreSQL integration`、`Application startup smoke`、`Dependency audit`、`Secret scan`、`Static security scan`、`Code quality`。
- 当前 `strict_required_status_checks_policy` 为 false；规则不要求 PR approval、Code Owner review 或 thread resolution；限制删除 / 非快进并要求 linear history；仓库允许 Auto-merge、合并、Squash、Rebase。当前没有 bypass actor。

### Plugin 仓库

- `K999999999999/agent-plugins` 默认分支 `master` 快照 HEAD 为 `6681366453eedce45e36f989a082df8a78b85819`；当前无活动 Repository Ruleset，`master` branch API 的 `protected` 为 false。
- 仓库 `allow_auto_merge` 为 false；允许合并、Squash、Rebase；合并后不自动删分支。
- 本地候选新增 `.github/workflows/harness-tests.yml`，配置 `push`、`pull_request`、手动触发及 `contents: read`，用 Python 3.11 运行标准库测试。它能产生 workflow checks，但当前 Plugin 仓库没有 required-check 规则，故工作流存在不等于远端保护已启用。

### 本机 Plugin 来源与缓存

- `/home/jojo/.codex/config.toml` 中 `engineering-workflow@personal` 为 enabled；`personal` Marketplace source 指向 `/home/jojo/Projects/agent-plugins-codex-harness`，Marketplace entry 指向其 `./plugins/engineering-workflow`。
- 该源目录是既有 `feature/harness-workflow-control` worktree，HEAD `9d97431b0e8d3870db5d06c748a23ddae6a2d1cd`，与本目标候选 worktree 分离；它包含用户未跟踪的 `engineering-process-audit.7z`。必须保留归档和源 worktree 既有内容。
- 当前缓存 `/home/jojo/.codex/plugins/cache/personal/engineering-workflow/0.1.0+codex.20260918204832` 存在，版本和旧 Plugin manifest 相同，但缓存中没有 `tools/harness.py`。启用状态、配置源、缓存内容与当前会话实际加载状态是不同事实；尚未验证本会话是否加载任何新 CLI。
- 本候选 Plugin manifest 已升到 `0.2.0+codex.20261019`，以区分含 Harness 工具的候选版本。该版本未安装、未同步，不能据此推断缓存已更新。

## 后续发布与同步顺序

每一步都需要用户对相应外部动作的明确授权；当前授权不包括以下操作。

1. **发布候选前检查。** 重新读取两仓 master SHA、当前候选 HEAD / Diff、源 checkout 与 archive 状态。确认 Plugin 候选仅基于其远端 master，不覆盖既有源分支工作；分别报告 ChatBI 与 Plugin PR 的目标、提交范围、验证、风险、CI 和 Auto-merge 行为。
2. **Plugin 发布。** 获得 Push / PR 授权后，创建指向 `agent-plugins:master` 的 PR，检查新 workflow 在真实 hosted runner 上的结果。Plugin 仓库当前关闭 Auto-merge 且无 required checks，不能宣称 CI 是合并门禁，也不能由 Agent 人工 Merge。若要设置 required checks，作为单独远端规则决定提出。
3. **ChatBI 发布。** 获得相应授权后，向 `chatbi:master` 创建 PR。候选必须针对 PR 当时实际 base 重跑适用的完整测试；检查 8 个 Required checks 的真实名称、GitHub Actions 来源、SHA 与结果。ChatBI 当前允许 Auto-merge；是否启用必须逐 PR 按仓库规则和用户授权处理，不能把旧 SHA 结果当新候选通过。
4. **更新本机 Marketplace 来源。** 先检查既有 `feature/harness-workflow-control` checkout 是否有分支提交和工作区改动；保留 7z 归档。合并后的远端提交与该 checkout 有分叉时，先展示差异并选择不覆盖既有工作的方法。不得把本目标 worktree 直接复制覆盖旧源目录，也不得自行改用户 Marketplace 配置。
5. **受支持的安装 / 刷新与会话核验。** 在源目录明确包含合并后的 Plugin 包后，通过当前 Codex / ChatGPT 支持的 Marketplace 更新或本地插件刷新路径更新；不要手改 `~/.codex/plugins/cache`。重启对应客户端 / 新建会话，然后读取实际插件包版本与 `tools/harness.py` 路径，并在该会话执行只读 `state` / `onboard discover`，确认加载的不是旧缓存。失败时报告配置源、缓存与会话结果各自状态。

## ChatBI strict-base 远端规则变更方案

**唯一拟议变化**：对 `K999999999999/chatbi` Ruleset `23564531` 的 `strict_required_status_checks_policy` 从 false 改为 true。保留 Ruleset 名称、目标分支、8 个检查及其 integration ID、其他保护规则和 bypass actor 完全不变。GitHub 将严格模式定义为要求 PR 分支先更新到目标分支最新状态；base 前进时可能需要重跑检查。

获得针对该 Ruleset 的明确授权后：

1. 再次 GET 完整 Ruleset，并记录时间、响应身份、SHA-256 与规则前像；核对仍是同一目标、ID、8 个检查和 strict=false。
2. 检查当前实现 PR 是否针对最新 `master`、8 个 required checks 是否都在当前候选 SHA 上通过。若前置不满足，不修改设置。
3. 使用拥有 Repository Administration 写权限的受支持 GitHub API / UI，只改 strict 布尔值一次；不顺带增删检查或改变审核 / bypass / merge 规则。
4. 立即 GET 回读完整 Ruleset，做结构化前后差异。预期唯一差异是 strict false→true；意外差异时停止，并在仍获授权的同一操作中按保存的完整前像恢复，再次读回核对。

这项修改需要 Repository Administration 权限；本计划不授权调用写 API。规则前像应安全保存在本机工作记录中，不含 Secret。

## 无 Secret 隔离实验

ChatBI 的真实 `master` 不用于失败注入。只有在另行授权后，在一次性私有测试仓库或隔离测试规则中创建不含 Secret 的空工作流 / canary：先让检查成功，再移动 base 并观察旧 SHA 是否失效，最后运行一个明确失败的必需检查，确认无法放行。记录仓库、规则、commit SHA、check run、失败 / 取消 / skip 和 base 变化；验证完成后按批准计划移除临时规则与分支，同时保留可审计结果。没有 GitHub 管理权、失败结果不明确或实验触达真实仓库时立即停止，不扩大权限。

## 回退与停止条件

- PR 尚未合并：不改目标分支；按用户决定关闭或保留 PR，保留检查和 Review 证据。
- 已合并但 Plugin 源尚未刷新：以单独 revert PR 撤销本目标，不能 reset / force push；候选 worktree 和原源归档继续保留。
- Plugin 来源 / 安装刷新失败：不改缓存文件；保留旧缓存，回到 Marketplace 支持的旧版本 / 刷新路径并重启，再验证旧版本恢复。不能只凭刷新命令成功声称生效。
- strict 设置意外变化：停止其他远端动作，对比保存前像，只按已授权回退完整原值，并核验读回；无写权限或无法确认时保留现场并通知用户。
- 任何 PR base、必需 check 名称 / 来源、Marketplace 源分支或用户文件与计划不一致时暂停相关外部步骤，重新核对；不得自动改规则、覆盖源 worktree 或扩大授权。

## 依据

- OpenAI Plugin 打包和本地 Marketplace 文档说明 Marketplace 指向 Plugin 源目录、安装使用缓存副本，变更后需刷新 / 重启并实际验证：[OpenAI Plugin packaging](https://developers.openai.com/plugins/build/plugins)。
- GitHub Rules API 与可用分支规则文档用于核实 Required checks / Ruleset 行为及后续更新权限：[Rules API](https://docs.github.com/en/rest/repos/rules)、[Available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)。

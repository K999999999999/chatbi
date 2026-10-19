# Harness Task Control V1 远端发布、同步与回退计划

Status: Plugin 与 ChatBI 远端代码已交付；PR #90–#92 均已合并；新版 Plugin 已安装启用并在当前会话加载；历史 baseline 已于 2026-10-19 重建；未修改远端规则或执行隔离实验
Last checked: 2026-10-19 12:02 UTC
Sources: GitHub PR / Actions / branch / ruleset reads; local Codex CLI marketplace / plugin state, source worktree and cache manifest

## 当前事实

### ChatBI

- `K999999999999/chatbi` 默认分支为 `master`，当前 HEAD 为 `08020cb81c2578c168d89504ab697ee2613b4de3`；本目标 PR #90、#91、#92 已依次通过既有 Squash Auto-merge 合并。
- `master` 的 GitHub `protected` 为 true；活动 Ruleset `main-protection`（ID `23564531`）适用于默认分支。不能把传统 Branch Protection endpoint 的单独结果当成没有保护。
- Ruleset 要求以下 8 个检查，来源均为 GitHub Actions integration ID `15368`：`Deterministic tests`、`SQL Guard tests`、`PostgreSQL integration`、`Application startup smoke`、`Dependency audit`、`Secret scan`、`Static security scan`、`Code quality`。
- 当前 `strict_required_status_checks_policy` 为 false；规则不要求 PR approval、Code Owner review 或 thread resolution；限制删除 / 非快进并要求 linear history；仓库允许 Auto-merge、合并、Squash、Rebase。当前没有 bypass actor。
- PR [#90](https://github.com/K999999999999/chatbi/pull/90) head `61b4645ea480ed202b912208f4f533eda6086b08` 于 `2026-10-19T10:29:59Z` 合并，merge commit `248ec84d4716d6ff0526df9b82ccfc33a03284db`。该 head 的8项 required checks 均通过，Actions run `39237424659`；自动合并由仓库 workflow 启用并由 GitHub 执行。
- PR [#91](https://github.com/K999999999999/chatbi/pull/91) head `7f1c41f7e4f48bf6251ca6b89e7dc2ec7749ca4c` 于 `2026-10-19T10:51:04Z` 合并，merge commit `b0ed0d85a862ab53c4fb4b4d20402d0111bd27ed`；PR [#92](https://github.com/K999999999999/chatbi/pull/92) head `048d705650430c18c660b922e8a5179d76e88411` 于 `2026-10-19T10:57:42Z` 合并，merge commit / 当前 `master` 为 `08020cb81c2578c168d89504ab697ee2613b4de3`。两项 PR 的8个 required checks 均通过（Actions runs `39239982987`、`39240801605`）。
- 首轮 CI 在 head `92136a0e4a6f954c7cc29732d65a6925b172cd39` 的 `Code quality` 失败，原因为新 adapter 测试文件未格式化。运行 `bash scripts/check_python_quality.sh` 定位并修复后，质量检查及最终 head 的 CI 通过。该遗漏记录为 `gap-found`，follow-up `harness-candidate-preflight` 尚未授权实施。

### Plugin 仓库

- `K999999999999/agent-plugins` 默认分支 `master` 当前 HEAD 为 `140f2ef95f611f378047683c379ae3724e4f5826`，即本目标 Plugin 候选；用户授权直接推送，没有创建 Plugin PR。
- 当前无活动 Repository Ruleset，`master` branch API 的 `protected` 为 false；仓库 `allow_auto_merge` 为 false，合并后不自动删分支。
- 仓库允许 Merge、Squash 和 Rebase。
- 本地候选新增 `.github/workflows/harness-tests.yml`，配置 `push`、`pull_request`、手动触发及 `contents: read`，用 Python 3.11 运行标准库测试。它能产生 workflow checks，但当前 Plugin 仓库没有 required-check 规则，故工作流存在不等于远端保护已启用。
- 用户决定不额外设置 Plugin required-check 规则。直推 `master` 后 GitHub Actions run `39237092713` 对 `140f2ef95f611f378047683c379ae3724e4f5826` 完成，53项测试通过；这只是 Hosted CI 结果，不是分支合并门禁。

### 本机 Plugin 来源与缓存

- `personal` Marketplace source 仍指向 `/home/jojo/Projects/agent-plugins-codex-harness`，只保留 `agent-engineering-skills@personal` `0.1.1` 启用。旧 `engineering-workflow@personal` 已卸载。
- 该源目录是既有 `feature/harness-workflow-control` worktree，HEAD `9d97431b0e8d3870db5d06c748a23ddae6a2d1cd`，与新 `master` 分叉，merge-base 为 `86731d4dcdfbcefea1efd33f5c4bfd33863ab10d`；它包含用户未跟踪的 `engineering-process-audit.7z`。本次没有改动该 source checkout 或归档，后续刷新不能覆盖或重置它。
- 新增本机 Marketplace `/home/jojo/.codex/.tmp/marketplaces/harness-task-control-v1/.agents/plugins/marketplace.json`，只提供 `engineering-workflow`，source 指向 `https://github.com/K999999999999/agent-plugins.git` 的 `./plugins/engineering-workflow` 子目录和 `master` ref。没有修改原 `personal` manifest。
- `engineering-workflow@harness-task-control-v1` 已安装并启用，版本 `0.2.0+codex.20261019`，由 `agent-plugins:master@140f2ef95f611f378047683c379ae3724e4f5826` 提供；缓存路径 `/home/jojo/.codex/plugins/cache/harness-task-control-v1/engineering-workflow/0.2.0+codex.20261019`，其中存在 `tools/harness.py`。Codex CLI `plugin list`、Harness CLI `--help` 和项目状态只读查询均核验成功；`onboard discover` 正常返回但 `complete=false`，没有发现测试入口，CI 文件只标记为本地观察，未远程核实。当前 API 会话是否热加载新版尚未验证，需新会话 / 重启后检查。
- 主实时记录已按显式 `migrate` 操作升级，原件备份保留；当前状态查询成功且为 `legacy_read_only=false`。2026-10-19 在临时 linked worktree 中依据历史提交 `2897302038fa42167e79a0b5ad483c2b628359b9` 和 `b0ed0d85a862ab53c4fb4b4d20402d0111bd27ed` 重新捕获 task / slice baseline，并写入共享本机实时记录；`captured_at` 明确是本次重建时间。此前因缺基线而未就绪的结果保留为历史事实；当前候选的收尾结果以 Harness 实时记录为准。

## 后续发布与同步顺序

用户于 2026-10-19 确认外部交付，并指定 Plugin 直接推送且不新增 required-check 规则。以下已执行结果与剩余动作分别记录；未获授权修改 GitHub 规则或运行隔离实验。

1. **发布候选前检查。已完成。** 重新核对两仓 master、候选 HEAD / Diff、源 checkout 与 archive；Plugin 候选基于当时远端 master，没有覆盖旧 checkout。
2. **Plugin 发布。已完成。** 按用户指示直接将 Plugin commit `140f2ef95f611f378047683c379ae3724e4f5826` 推至 `agent-plugins:master`；Hosted Actions run `39237092713` 的53项标准库测试通过。没有配置 required-check 规则，也没有创建 Plugin PR。
3. **ChatBI 发布。已完成。** PR [#90](https://github.com/K999999999999/chatbi/pull/90) 指向 `chatbi:master`，最终 head `61b4645ea480ed202b912208f4f533eda6086b08` 的8项 required checks 全部通过；既有 workflow 启用 Squash Auto-merge，GitHub 于 `2026-10-19T10:29:59Z` 合并，merge commit 为 `248ec84d4716d6ff0526df9b82ccfc33a03284db`。后续 PR [#91](https://github.com/K999999999999/chatbi/pull/91) 与 [#92](https://github.com/K999999999999/chatbi/pull/92) 分别同步验收 / 发布事实和最终状态，均由同一自动合并策略完成且8项 required checks 全部通过。
4. **保护原 Marketplace source。已完成核对。** `personal` 仍指向原 `feature/harness-workflow-control` checkout；该 checkout 与新 `master` 分叉，且包含用户归档。它和归档均未改动。安全激活不能通过覆盖或重置旧 source 来实现。
5. **Plugin 安装、CLI 与当前会话加载核验。已完成。** 新增独立 Marketplace 后安装并启用 `0.2.0+codex.20261019`，移除旧 `engineering-workflow@personal`，保留原 Marketplace、另一个 Plugin、source worktree 和归档。缓存包存在 Harness CLI，状态查询及只读 `onboard discover` 通过；当前会话 Skill 目录提供并已实际调用 `workflow-delivery` 与 `workflow-code-review`。

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
- Plugin 已安装但新会话加载失败：不改缓存文件；保留新旧包缓存和原 source / 归档，按 Marketplace 支持方式恢复旧版并重启验证。不能只凭安装命令成功声称新会话生效。
- strict 设置意外变化：停止其他远端动作，对比保存前像，只按已授权回退完整原值，并核验读回；无写权限或无法确认时保留现场并通知用户。
- 任何 PR base、必需 check 名称 / 来源、Marketplace 源分支或用户文件与计划不一致时暂停相关外部步骤，重新核对；不得自动改规则、覆盖源 worktree 或扩大授权。

## 依据

- OpenAI Plugin 打包和本地 Marketplace 文档说明 Marketplace 指向 Plugin 源目录、安装使用缓存副本，变更后需刷新 / 重启并实际验证：[OpenAI Plugin packaging](https://developers.openai.com/plugins/build/plugins)。
- GitHub Rules API 与可用分支规则文档用于核实 Required checks / Ruleset 行为及后续更新权限：[Rules API](https://docs.github.com/en/rest/repos/rules)、[Available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)。

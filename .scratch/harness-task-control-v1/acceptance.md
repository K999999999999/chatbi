# Harness Task Control V1 验收与远端交付

Status: 本地验收、Hosted CI、ChatBI / Plugin 远端交付和本机 Harness overall closeout 均已完成；历史 baseline 于 2026-10-19 重建并写入实时记录
Snapshot: 2026-10-19 12:15 UTC
ChatBI baseline: `2897302038fa42167e79a0b5ad483c2b628359b9` (`docs/harness-task-control-v1`)
Plugin baseline: `6681366453eedce45e36f989a082df8a78b85819` (`feature/harness-task-control-v1`)
Plugin candidate version: `0.2.0+codex.20261019`

本记录验证已确认 Spec 的本地工具和 ChatBI 适配行为。初次验收时 ChatBI 主记录仍为旧格式，实际工具查询明确返回 `legacy_read_only: true`；没有伪造 task / slice 起始基线。PR #90 合并后的 Harness 收尾复核中，主实时记录已按显式迁移命令升级并保留原件备份；当前 `state` 查询返回 `legacy_read_only: false`。跨仓端到端行为在临时合成仓库中验证。最终 Code Review 为 PASS AFTER FIX。ChatBI 实现提交为 `0e8189bf0eeace38cffdc2ca16debd103e7e1b19`，最终 PR head 为 `61b4645ea480ed202b912208f4f533eda6086b08`，Squash merge commit 为 `248ec84d4716d6ff0526df9b82ccfc33a03284db`；Plugin 提交 `140f2ef95f611f378047683c379ae3724e4f5826` 已直推远端 `master`。本机实时进度以 Git 公共目录主记录为准。

2026-10-19 的最终收尾复核从 Git 对象库恢复了工具上线前的任务起点 `2897302038fa42167e79a0b5ad483c2b628359b9` 与收尾切片起点 `b0ed0d85a862ab53c4fb4b4d20402d0111bd27ed`，并在隔离 linked worktree 中通过 ChatBI 容器适配器捕获至本机 Harness 记录。两条记录的 `captured_at` 分别为 `2026-10-19T11:59:58+00:00` 和 `2026-10-19T11:59:59+00:00`。这是依据历史提交于该时间重建的基线，不代表它们在原始开发时已被捕获；最终候选及其当前证据状态以本机 Harness 实时记录为准。

## Spec 覆盖与证据

| Spec 行为 | 证据 | 结果与边界 |
| --- | --- | --- |
| 状态读取、旧记录兼容、合法转换、拒绝非法 / 过期写入、原子写和并发冲突 | Plugin `tests/test_harness_state.py`；临时 Git / linked worktree | 覆盖只读旧记录、显式迁移备份、坏阶段 / 摘要 / 锁 / 双写入者及损坏原件；拒绝时保持原记录 |
| 本轮 / 累计 Diff、候选指纹、敏感路径、base 移动及旧候选证据失效 | Plugin `tests/test_harness_evidence.py` | 提交、staged、unstaged 和未跟踪变更分开列示；不输出文件内容；敏感内容不读取；GitHub 远端检查仅是快照，不伪装为实时成功 |
| 3 轮 / 30 分钟诊断预算、跨进程恢复、等待上限、重命名绕过和 Secret 拒绝 | Plugin `tests/test_harness_budget.py` | 用合成时间证明第 3 轮和 1800 秒边界；已记录但未被新证据推进的尝试不会清零；超过边界的继续被拒绝 |
| 动态文件清单、local / overall closeout、恢复、follow-up 效果证据 | Plugin `tests/test_harness_closeout.py` | 验证清单缺项、候选或 Manifest 改变后的评估失效、关联工作项改变后的完成失效，以及缺验证 / Review 时拒绝完成 |
| 新项目发现与本地计划、保留已有文件、只读远端检查与规则来源区分 | Plugin `tests/test_harness_onboarding.py` | 合成文件系统 / 远端响应验证路径遍历、符号链接、敏感路径、旧文件指纹变化、未知栈不编造检查、required check 来源和远端权限不足 |
| Plugin 包含路径、阶段 Skill 共享 Contract、插件清单与 CI 源码约束 | Plugin `tests/test_harness_plugin_integration.py` 和 `.github/workflows/harness-tests.yml` | CLI 只在 `plugins/engineering-workflow/tools/` 有一份；13 个 Skill 链接同一集成 Contract；工作流由源码定义、Actions 引用固定到 commit SHA、只读权限、不用缓存 / secret / 服务 |
| ChatBI 容器入口、只读 Plugin、明确状态写权限及旧检查兼容 | ChatBI `tests/scripts/test_harness_adapter.py` | 12 项通过；覆盖 Plugin 仓库根 / 包根、linked worktree 公共目录、容器挂载、缺工具 / 镜像 / 路径失败、禁止 adapter 覆盖以及旧 `./dev harness check` 路径 |
| ChatBI 实际命令到 Plugin 包的组合行为 | 临时合成 Git 仓库，经 ChatBI 容器 adapter 执行 Plugin 候选 CLI | 验证旧记录只读、显式备份迁移、非法转换不改状态、task / slice baseline、Diff、3 轮升级和拒绝第 4 轮、read-only recovery / onboarding、follow-up 效果门槛、逐项 Manifest 评估及缺验证 / Review 时不 closeout。临时仓库由临时目录清理，无用户文件参与 |
| ChatBI 现有状态检查兼容和文档结构 | `python3 -m scripts.check_harness_state`、`./dev check docs` | 检查 54 条记录：0 ERROR、3 REVIEW。Review 为本工作项未完成、无关工作项 `long-task-progress-clarity` 仍 open、当前任务工作区 dirty；均按事实保留。文档检查通过 |

Plugin 完整 unittest 在宿主 Python 3.14.4 与现有开发容器 Python 3.11.16 均通过 53 项；Hosted Actions run `39237092713` 对 Plugin `master` 成功。ChatBI `./dev test python` exit code 为 0，Python 3.11.16 容器内 1118 passed、0 failed、0 errors、61 skipped、155 subtests passed；报告状态为 `incomplete`，因为本地隔离 PostgreSQL / PDF renderer / 真实 LLM 覆盖被跳过，Business Acceptance 未运行。定向 adapter 测试 12 项、`bash scripts/check_python_quality.sh`、`./dev check docs` 和 Markdown 链接检查通过。ChatBI PR [#90](https://github.com/K999999999999/chatbi/pull/90) 最终 head 的 8 项 required checks 均通过，CI run `39237424659`，并由仓库既有 Squash Auto-merge 合并。首轮 head `92136a0e4a6f954c7cc29732d65a6925b172cd39` 的 `Code quality` 失败，原因是新增 adapter 测试未通过 Ruff 格式检查；提交 `61b4645` 只格式化该测试文件，之后本地质量检查与最终 Hosted CI 均通过。ChatBI 完整产品验收未运行。

## 动态文件评估

以下为 `.harness/dynamic-files.json` 中 8 项文件的语义核对。初次验收时真实任务记录为旧格式，人工评估和结果先保存在本表；2026-10-19 恢复历史 baseline 后，相关 disposition 通过 Harness CLI 绑定到最终候选。overall closeout 已通过；候选指纹、报告摘要和当前认可状态保存在本机实时记录。

| 文件 | 结论 | 本次处理 |
| --- | --- | --- |
| `AGENTS.md` | updated | 添加 Harness 工作状态恢复、动态文件和检查边界入口 |
| `docs/agents/documentation.md` | updated | 登记清单职责和维护入口 |
| `docs/agents/issue-tracker.md` | updated | 增加 Harness 状态恢复与本机检查说明 |
| `docs/agents/git-pr-workflow.md` | reviewed-no-change | 核对现有 PR / Auto-merge Contract 并按用户授权交付；继续沿用仓库既有规则，没有修改规则或授权边界 |
| `docs/roadmap.md` | updated | 初次候选记录了当时的本地 / 未发布状态；本次 closeout 同步 PR #90–#93、Plugin master 和今日重建的历史 baseline |
| `docs/runbook.md` | updated | 记录 Plugin 工具的显式容器入口和约束 |
| `.harness/project.json` | updated | 登记项目阶段、转换和记录位置 |
| `.harness/dynamic-files.json` | updated | 建立本项目动态文件唯一清单 |

初次候选 Diff 含全部 `updated` 路径。PR 正文的 Harness 复盘字段已回填 `gap-found` 并从 GitHub 读回核验；由于 PR 合并后发布事实发生变化，本次 closeout 同步更新路线图、验收记录和远端发布状态。首次 `closeout check` 因缺少基线及候选绑定证据返回未就绪；2026-10-19 正式重建历史 baseline、绑定最终候选的文件评估与验证 / Review / 远端证据后，overall closeout 已通过并记录到本机 Harness extension。历史失败结果只描述当时检查，不覆盖当前通过状态。业务产品 Spec / Domain Contract 未变，保持不适用。原始测试输出由本地测试入口管理，未把 ignored 报告纳入源码提交。初次实现候选的两仓 `git diff --check`、本次 closeout 的 `git diff --check`、`./dev check docs` 和 Markdown 链接检查通过；文档检查报告之一为 `reports/tests/20261019T104616Z-248ec84-check-docs-b56b8bbb2f2c.json`。

## Hosted CI 与发布结果

- Plugin `master` 为 `140f2ef95f611f378047683c379ae3724e4f5826`；GitHub Actions run `39237092713` 的 53 项标准库测试通过。按用户决定未创建 Plugin PR、未设置 required checks；仓库仍没有分支保护规则。
- ChatBI PR [#90](https://github.com/K999999999999/chatbi/pull/90) 以 `61b4645ea480ed202b912208f4f533eda6086b08` 为 head，经既有 Squash Auto-merge 于 `2026-10-19T10:29:59Z` 合并，merge commit 为 `248ec84d4716d6ff0526df9b82ccfc33a03284db`。8 项 required checks 全部通过，CI run `39237424659`。
- PR [#91](https://github.com/K999999999999/chatbi/pull/91) 以 `7f1c41f7e4f48bf6251ca6b89e7dc2ec7749ca4c` 为 head，于 `2026-10-19T10:51:04Z` 合并至 `b0ed0d85a862ab53c4fb4b4d20402d0111bd27ed`；8 项 required checks 全部通过，CI run `39239982987`。
- PR [#92](https://github.com/K999999999999/chatbi/pull/92) 以 `048d705650430c18c660b922e8a5179d76e88411` 为 head，于 `2026-10-19T10:57:42Z` 合并至 `08020cb81c2578c168d89504ab697ee2613b4de3`；8 项 required checks 全部通过，CI run `39240801605`。该提交同步前两项 PR 的交付与状态事实，没有变更产品行为。
- PR [#93](https://github.com/K999999999999/chatbi/pull/93) 以 `c104fe6beee9d18f444d69d1835fb6da1bdfa463` 为 head，于 `2026-10-19T12:09:35Z` 合并至 `314cb2ceb5aefec27bdecef3949558b987b4f130`；8 项 required checks 全部通过，CI run `39249219958`。该 PR 仅同步验收、路线图、远端发布和状态事实。
- Agent Harness 复盘为 `gap-found`：首次 Push 前遗漏运行仓库指定的 `bash scripts/check_python_quality.sh`，导致首轮 Code quality 失败；格式修复与复测已完成。后续提案 [harness-candidate-preflight](../harness-candidate-preflight/spec.md) 已登记，尚未确认或授权实施。

## 本机 Plugin 安装与 Harness CLI 核验

- 为避免替换含另一个新版 Plugin 的 `personal` Marketplace，新增本机独立 Marketplace `harness-task-control-v1`，其 manifest 仅提供 `engineering-workflow`，Git source 为 `K999999999999/agent-plugins` 的 `plugins/engineering-workflow` 子目录，跟随 `master`。
- `codex plugin add engineering-workflow@harness-task-control-v1` 成功安装并启用 `0.2.0+codex.20261019`；Codex 管理的缓存包含 `tools/harness.py`。旧 `engineering-workflow@personal` 已卸载；`agent-engineering-skills@personal` `0.1.1` 保持启用。原 Plugin source checkout 与未跟踪 `engineering-process-audit.7z` 均未修改。
- 新版 CLI `--help`、ChatBI `state --work-item harness-task-control-v1 --json` 和只读 `onboard discover` 均已运行。状态查询确认项目已接入；显式迁移保留原状态文件 `.bak` 备份。当前会话已加载 `engineering-workflow` `0.2.0+codex.20261019`，且 `state` 显示工作项已到 `done / 完成`。
- 初次 `closeout check` 因缺少 task / slice baseline、动态文件评估和当前候选验证 / Review 证据未就绪。2026-10-19 正式重建并绑定当前最终候选后，`local_ready=true`、`overall_ready=true`；`closeout finalize overall` 已完成。本机实时状态保留完整候选指纹、证据和采集时间，未把历史失败检查改写为成功。
- 当前会话的 Skill 目录已暴露 `engineering-workflow` `0.2.0+codex.20261019`，并已实际使用其 `workflow-delivery` 与 `workflow-code-review`；这是当前会话加载的核验依据。

## 未验证及授权边界

- 未修改 ChatBI Ruleset，未在隔离仓库注入失败或移动 base；远端配置和回退事实见 [远端发布与回退状态](remote-release-plan.md)。
- 未运行真实模型、付费 API、真实业务数据或生产应用变更；这些不适用于本地工程工具行为验收。
- 旧工作项 `long-task-progress-clarity` 仍 open；本目标不继承其授权，也不将其标记为解决。

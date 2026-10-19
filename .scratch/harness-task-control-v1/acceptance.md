# Harness Task Control V1 本地验收

Status: 本地验收记录；不代表已 Push、PR、安装、同步或启用
Snapshot: 2026-10-19 07:38 UTC
ChatBI baseline: `2897302038fa42167e79a0b5ad483c2b628359b9` (`docs/harness-task-control-v1`)
Plugin baseline: `6681366453eedce45e36f989a082df8a78b85819` (`feature/harness-task-control-v1`)
Plugin candidate version: `0.2.0+codex.20261019`

本记录验证已确认 Spec 的本地工具和 ChatBI 适配行为。ChatBI 主记录仍是旧格式，实际工具查询明确返回 `legacy_read_only: true`；没有伪造 task / slice 起始基线，也没有把当前真实工作项迁移成“已通过新版门禁”。跨仓端到端行为在临时合成仓库中验证。最终 Code Review 为 PASS AFTER FIX；提交候选身份写入 Git 公共目录主实时记录，工作树改动可由目标分支 Diff 核对。

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

Plugin 完整 unittest 在宿主 Python 3.14.4 与现有开发容器 Python 3.11.16 均通过 53 项；宿主 Python 3.14.4 已在 Plugin manifest 版本调整后再次复跑。ChatBI `./dev test python` exit code 为 0，Python 3.11.16 容器内 1118 passed、0 failed、0 errors、61 skipped、155 subtests passed；报告状态为 `incomplete`，因为隔离 PostgreSQL / PDF renderer / 真实 LLM 覆盖被跳过，Business Acceptance 未运行。定向 adapter 测试 12 项、`./dev check docs` 和 Markdown 链接检查通过。ChatBI 完整产品验收未运行。两仓 Code Review 已通过，当前仅待本地 Commit。

## 动态文件评估

以下为 `.harness/dynamic-files.json` 中 8 项文件的语义核对。临时合成 E2E 验证工具可逐项记录评估；当前真实任务记录为旧格式，没有把评估伪登记到该旧记录中。

| 文件 | 结论 | 本次处理 |
| --- | --- | --- |
| `AGENTS.md` | updated | 添加 Harness 工作状态恢复、动态文件和检查边界入口 |
| `docs/agents/documentation.md` | updated | 登记清单职责和维护入口 |
| `docs/agents/issue-tracker.md` | updated | 增加 Harness 状态恢复与本机检查说明 |
| `docs/agents/git-pr-workflow.md` | reviewed-no-change | 只读核对现有 PR / Auto-merge Contract；本次没有发布授权，也没有改其授权边界 |
| `docs/roadmap.md` | updated | 记录已确认目标的本地候选和未发布状态，不标为远端交付完成 |
| `docs/runbook.md` | updated | 记录 Plugin 工具的显式容器入口和约束 |
| `.harness/project.json` | updated | 登记项目阶段、转换和记录位置 |
| `.harness/dynamic-files.json` | updated | 建立本项目动态文件唯一清单 |

候选 Diff 含全部 `updated` 路径；PR 正文与合并后记录不适用，因为没有 PR。业务产品 Spec / Domain Contract 未变，保持不适用。原始测试输出由本地测试入口管理，未把 ignored 报告纳入源码提交。两仓 `git diff --check`、`./dev check docs` 和 Markdown 链接检查通过。

## 未验证及授权边界

- 尚无托管 GitHub CI 结果；本地通过不等于远端 workflow 已运行或 required check 生效。
- 尚未 Push / 创建 PR；没有候选远端 SHA、PR 状态或 Auto-merge 结果。
- 尚未安装 / 同步 Plugin 或重启会话。当前启用配置源指向原 Plugin checkout；当前安装缓存仍缺 Harness CLI。候选 Plugin 位于另一隔离 worktree。
- 尚未修改 ChatBI Ruleset，尚未在隔离仓库注入失败或移动 base；远端状态及后续计划见 [远端发布与回退计划](remote-release-plan.md)。
- 未运行真实模型、付费 API、真实业务数据或生产应用变更；这些不适用于本地工程工具行为验收。
- 旧工作项 `long-task-progress-clarity` 仍 open；本目标不继承其授权，也不将其标记为解决。

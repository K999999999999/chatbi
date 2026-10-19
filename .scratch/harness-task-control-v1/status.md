# Harness 改进规划状态

Status: ChatBI 与 Plugin 远端代码及 PR #90–#92 文档收尾均已交付；新版 Plugin 已安装启用并在当前会话加载；历史 task / slice baseline 已于 2026-10-19 重建，当前 Harness closeout 状态以本机实时记录为准
Stage: 已合并待复盘

当前会话已逐项确认通用能力归 engineering-workflow Plugin、ChatBI 首轮适配、工具化状态管理、人工介入规则、3轮 / 30分钟无进展预算、聊天批准候选及显式项目接入方式。

用户已整体确认[Spec](spec.md)。[Design Review](design-review.md)为PASS WITH MINOR FIXES，D1–D4在[设计说明](design.md)中落实并核对；[8项Ticket草案](ticket-drafts.md)的[Readiness](ticket-readiness.md)为READY。用户于 2026-10-19 确认8项拆分并授权整体本地实施、验证、Review和Commit；之后确认外部交付，指定 Plugin 直接推送且不新增 required-check 规则。未授权修改 ChatBI / Plugin 远端规则或进行隔离失败实验。

正式 Tickets 01–08 的本地实现、验收、Review 与 Commit 已完成。Plugin `140f2ef95f611f378047683c379ae3724e4f5826` 已直接推送至 `agent-plugins:master`，GitHub Actions run `39237092713` 成功（53项）；未创建 Plugin PR、未配置 required checks。ChatBI PR [#90](https://github.com/K999999999999/chatbi/pull/90) 于 2026-10-19 10:29:59 UTC 由既有 Squash Auto-merge 合并，merge commit 为 `248ec84d4716d6ff0526df9b82ccfc33a03284db`；最终 head `61b4645ea480ed202b912208f4f533eda6086b08` 的8项 required checks 全部通过。首轮 CI 的 `Code quality` 因适配器测试未格式化而失败；补充格式提交后质量检查与该 head 的 CI 均通过。

PR [#91](https://github.com/K999999999999/chatbi/pull/91) 同步交付与安装事实，于 2026-10-19 10:51:04 UTC 由既有 Squash Auto-merge 合并，head `7f1c41f7e4f48bf6251ca6b89e7dc2ec7749ca4c`，merge commit `b0ed0d85a862ab53c4fb4b4d20402d0111bd27ed`；Actions run `39239982987` 的8项 required checks 全部通过。合并后已删除该 PR 的远端与本地工作分支，ChatBI 主工作区回到 `master` 并保持干净。

为避免整体替换 `personal` Marketplace（其中 `agent-engineering-skills` 当前为 `0.1.1`），已新增独立 Marketplace `harness-task-control-v1`，只安装并启用 `engineering-workflow@harness-task-control-v1` `0.2.0+codex.20261019`；旧 `engineering-workflow@personal` 已卸载，另一个 Plugin 保持不变。原 `feature/harness-workflow-control` checkout 及未跟踪的 `engineering-process-audit.7z` 保持未改。缓存含 `tools/harness.py`；`--help`、状态读取成功。只读 `onboard discover` 返回 `complete=false`，未发现测试入口且 CI 文件只标记为本地观察，未远程核验。主实时状态记录已显式迁移并保留备份，当前 Harness `state` 查询成功。新会话仍需重新加载后核验 Skill 实际生效。

本次 `closeout check` 返回 `local_ready=false`、`overall_ready=false`：工作项在 Harness 上线前未捕获 task / slice baseline，且旧验证、Review 与动态文件语义评估没有绑定到当前候选，因此工具拒绝完成声明。验收文档保留既有手工评估与证据；此旧候选记录不会被伪改成新工具已通过。远端发布、Hosted CI 和本地源 / 缓存事实以[验收记录](acceptance.md)、[发布与回退状态](remote-release-plan.md)及 GitHub 实时状态为准。

合并复盘发现可行动的 Harness 缺口：首次发布前遗漏运行仓库指定的 `bash scripts/check_python_quality.sh`，导致首轮 CI 失败。跟进工作项 `harness-candidate-preflight` 已登记为待确认提案；它不代表已授权实施。原问题发现 `long-task-progress-clarity` 保留原生命周期，不继承本目标授权，也不提前标记解决。

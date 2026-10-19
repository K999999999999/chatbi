# ChatBI Roadmap

本文记录当前项目阶段和已确认的后续方向。能力与支持边界见[产品范围](product-scope.md)，系统职责见[架构](architecture.md)，操作与验证入口见[Runbook](runbook.md)。历次候选、验收和交付过程保存在所属 `.scratch/` 工作记录中。

## 当前阶段

- 产品 V1 的 R1–R7 历史目标已完成交付；问数、分析、图表、私人历史、后台执行和导出保持。原本机Stable部署/运维属于历史交付，当前按已确认Deployment Simplification目标精简。
- 本机源码开发、测试与体验统一使用dev容器；不再提供独立业务APP镜像构建路线。此决定及执行边界见[测试可靠性 Spec](../.scratch/test-reliability/spec.md)。
- 历史本机 Stable 的 R7 部署及 Docker Desktop / Windows 整机重启恢复，最后记录的核验日期为 2026-10-10；详细候选和证据见[运行保障验收归档](../.scratch/local-operations-v1/history/acceptance--local-operations-v1.md)。这不构成公网生产部署、容量或可用性承诺。
- 新的 AI Evaluation 结果只适用于报告记录的提交、案例集与运行资源；历史分数不能代表当前代码或模型表现。
- 已确认桌面 Web 视觉升级目标，聚焦正式产品观感与信息直观度；边界和验收见[短 Spec](../.scratch/professional-ui/spec.md)。该工程改进不扩展产品能力或改变支持范围 / 路线优先级。

## 已确认的后续方向

已确认全仓审计问题修复目标，范围为[审计报告](audits/project-audit-20261016.md)中的22项问题（AUD014已排除）；[Spec](../.scratch/project-audit-remediation/spec.md)、设计审查修订和12项Ticket拆分均已确认。Ticket 01–12的本地实现、验证、Review和Commit已完成，最终候选`a43b320`工作区干净：`./dev test all` 1255/1255、0 skip，`./dev check`通过。clean候选`c95ca34`上的正式AI Evaluation为single-turn 29/29、business-analysis 10/10、multi-turn 7/7（15/15轮），隔离容器业务验收3/3且无skip；报告均clean且provenance stable，三套Evaluation通过官方validator。`a43b320`仅更新测试编排与收尾文档，未改变应用行为或Contract，详细报告及证据复用边界见[Ticket 12](../.scratch/project-audit-remediation/issues/12-final-validation-and-documentation.md)。两条历史失败的底层原因/拒绝分类按用户决定暂缓定位，不视作已修复；阿里云Trace配置已传入，但未能查询确认云端收件。用户已授权提交PR；目标仓库启用8项required CI checks与Squash Auto-merge，满足条件后由GitHub自动合并。

已完成dev分类入口与本机管理员恢复目标，按[Spec](../.scratch/dev-command-entrypoints/spec.md)交付七项Ticket；当时纳入的标准APP管理路线已由后续[测试可靠性目标](../.scratch/test-reliability/spec.md)确认退役，历史候选和验证仍见[原验收记录](../.scratch/dev-command-entrypoints/acceptance.md)。

已完成测试可靠性与运行路线精简目标，按[Spec](../.scratch/test-reliability/spec.md)完成七项Ticket，覆盖本地测试可靠性、报告追溯及 CI 中的 development 数据库与 PDF renderer 检查；[PR #86](https://github.com/K999999999999/chatbi/pull/86) 已合并，最终 8 项 required checks 全部通过。真实 LLM 评测与业务验收未运行；不改变其他路线优先级。

已确认 Harness 任务控制与持续维护 V1，范围和授权见[Spec](../.scratch/harness-task-control-v1/spec.md)。ChatBI 项目适配及收尾文档已通过 [PR #90](https://github.com/K999999999999/chatbi/pull/90)、[#91](https://github.com/K999999999999/chatbi/pull/91)、[#92](https://github.com/K999999999999/chatbi/pull/92)、[#93](https://github.com/K999999999999/chatbi/pull/93) 合并至 `master`；`engineering-workflow` Plugin `0.2.0+codex.20261019` 已按用户决定直接推送至 `agent-plugins:master`，其 GitHub Actions 标准库测试通过。功能覆盖状态 / 阶段转换、Diff 与证据、诊断预算、动态文件收尾、项目接入及维护反馈；本地与 Hosted 验收证据见[验收记录](../.scratch/harness-task-control-v1/acceptance.md)。为保留包含另一个已启用 Plugin 的 `personal` Marketplace 与原 source worktree，已新增独立 `harness-task-control-v1` Marketplace，并安装启用新版 `engineering-workflow`；当前会话已加载该版本，CLI 状态读取已验证。只读 `onboard discover` 返回 `complete=false`，未发现测试入口且 CI 仅标记为本地观察。原 source worktree 与用户归档保持未改动。首次 Harness 收尾因缺少历史 task / slice baseline 未就绪；2026-10-19 已依据仍可读取的 Git 提交在临时 worktree 中重建并记录基线，真实采集时间明确为本次重建时间；当前 Harness overall closeout 已通过，详细证据见[验收记录](../.scratch/harness-task-control-v1/acceptance.md)及本机实时状态。未修改 GitHub 规则，不改变产品业务行为和其他路线优先级。合并复盘发现候选发布前遗漏本地 Python 质量检查，后续提案见[候选前置验证工作项](../.scratch/harness-candidate-preflight/spec.md)，尚未获实施授权。

已确认部署精简目标，实现与验收已完成并通过 [PR #81](https://github.com/K999999999999/chatbi/pull/81) 合并：统一dev容器入口，保留标准Dockerfile/Compose、初始化和应用保护，删除自研Stable运维及宿主开发教程。范围见[Spec](../.scratch/deployment-simplification/spec.md)，证据见[验收记录](../.scratch/deployment-simplification/acceptance.md)；不新增产品功能或调整其他优先级。增加数据源、部署副本、数据权限、分析场景或容量承诺前，应先确认用户目标、支持范围和验收要求，再形成相应 Spec；本段不授予实施授权。

## 路线图维护

只在已确认目标、依赖、验收方式或完成事实改变时维护本页。不得把已完成的阶段过程、候选结果或未确认建议追加为当前路线。维护边界见[文档维护规则](agents/documentation.md#更新与归档)。

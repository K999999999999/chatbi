# 08 — 两仓候选验收、恢复走查与交付计划

Status: in-progress
Ticket Readiness: READY


Change Profile: 两仓总体验收；一次收尾并保留长期证据；风险为跨仓假完成 / 清理唯一证据；合成流程与安全只读核验；本地交付。
Owner: 当前主 Agent
Blocked by: 07

### What to build

用ChatBI adapter和已实现Plugin候选完成合成任务：查看、拒绝转换、Diff、预算升级、恢复、动态文档、follow-up与收尾；建立逐项Spec覆盖和两仓证据引用。准备各仓发布、安装同步、严格base远端配置以及无Secret隔离阻断实验的具体计划和回退说明。

### Acceptance criteria

- Spec适用行为都有对应实际软件证据；实际运行与Mock、旧报告、未执行CI / 安装 / 远端实验明确分开。
- 两仓候选/基线/范围、相关长期记录、主关联实时记录、未提交用户文件归属可核实；已有long-task-progress-clarity只在适用目标和实际效果核实后处置，不自动继承授权或提前关闭。
- 源变更与安装/会话生效分别说明；未授权发布或更新时保持本地完成，不写整个远端目标完成。
- 远端计划明确目标、当前配置、strict变化、检查来源、授权需求、步骤、失败处理和回退；隔离实验不向实际master注入失败。
- 当前过期文档事实按真实Git/PR修正，历史验收不重标；无相关内容变更的业务Spec明确不适用。

owned files: ChatBI本目标验收与过程文档、适用Roadmap/Runbook/Agent文档；Plugin工具文档/验证记录及本目标关联记录。仅为验收发现且在已确认范围内的修复返回所属Ticket，不夹带无关重构。

Verification evidence: 两仓实际定向/完整工具回归、ChatBI容器合成走查、文档/链接/边界检查、Diff Review；基于可得权限的只读远端核验。真正远端阻断实验另等明确授权。

Migration / Rollback: 仅清理已确认本目标临时测试资源；保留候选/报告身份与唯一证据；不动Plugin源用户7z归档、不直接写master；无远端写入就不执行远端回退。

Done When: 本地验收覆盖、证据、两仓Review与项目规定本地Commit完成；待发布/安装/远端实验明确列出，不因等待额外授权否定已完成的本地范围，也不冒充整体交付。

## 依赖与交付

直接依赖：01 → 02；02 → 03、04；04 → 05；03、05 → 06；06 → 07；07 → 08。按编号在各仓同一目标候选上推进；依赖不等于先创建远端PR。两仓各一个活动实现候选，Plugin源的既有用户归档保持原位。

用户确认拆分和本地实施授权后，依赖连续实施，不逐Ticket等待“继续”。如只确认粒度未授权实施，先一次确认范围。发布、安装、远端设置及实验授权不由此推定。

Result: Ticket 07 完成后开展两仓交叉验收。Plugin 包内 CLI 的标准库 unittest 在宿主 Python 3.14.4 与 Python 3.11.16 容器中各 53 项通过；ChatBI `./dev test python` 的 1118 项通过、61 项隔离数据库 / renderer / 真实 LLM 检查跳过、0 失败 / 错误，另有 155 subtests；报告标记 `incomplete`，Business Acceptance 未运行。ChatBI adapter 定向测试 12 项、Markdown 文档检查、Shell 语法检查及两仓 `git diff --check` 通过。临时合成仓库的真实容器 adapter → Plugin CLI 走查验证旧状态只读、显式迁移 / 备份、非法转换拒绝、Diff、预算升级 / 停止、恢复、onboarding、动态文件清单及缺验证 / Review 时拒绝 closeout。GitHub 只读快照确认 ChatBI master active Ruleset 和 8 个 required checks、strict=false；Plugin master 无 Ruleset，auto-merge=false。当前用户级配置仍指向旧源 worktree，启用缓存不含 Harness CLI；未安装 / 同步、未运行 hosted CI、未改远端规则、未执行隔离实验。两仓 Code Review 均通过；适配器允许 `--adapter` 覆盖项目规则的发现项已修复并有回归测试。验收矩阵和具体回退步骤见 [acceptance.md](../acceptance.md)、[remote-release-plan.md](../remote-release-plan.md)。当前待按授权完成两个本地 Commit，提交后核对工作区与候选 SHA。
Comments: 用户于 2026-10-19 确认 8 项拆分并授权整体本地实施、验证、Review 和 Commit；不含 Push / PR、Plugin 安装更新、远端设置或实验。

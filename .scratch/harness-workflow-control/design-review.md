# Design Review：Harness 工作流控制与交付闭环

Date: 2026-10-01
Mode: 当前主 Agent，只读审查，无独立 Agent。
Review Target: spec.md（用户已在本会话确认整体 Spec 和技术方案）
Initial Review: PASS WITH MINOR FIXES
Final Review: PASS / 小修已落实并核对

## Evidence Sources

- 当前工作项 Spec 和 15 项用户决定。
- ChatBI AGENTS、docs/agents/agent-harness.md、issue-tracker.md、git-pr-workflow.md、PR 模板、CI 和 Auto-merge workflow。
- ChatBI Architecture：本项属于 Agent 工程环境，不修改产品 Domain、Application、Infrastructure 或查询链路。
- 外置 Plugin README、13 个 Skill 的职责与调用配置、交付和初始化规则、当前 Git / worktree 状态。
- Git 公共目录解析结果：本 Feature worktree 与主仓库共用 `/home/jojo/Projects/chatbi-engine/.git`。
- workflow-design-review 的 Architecture Knowledge Core，重点检查复杂度、信息隐藏、跨边界数据、状态 / 失败、Design Twice、迁移和 Overengineering Guard。

## Findings

### R01：引用需在 worktree 清理后仍可定位

- Signal：共享状态可保留，但 Spec / Ticket / 验收引用可能仍指向即将删除的 worktree 绝对路径。
- Evidence：Spec 将 Worktree 与 Spec 路径同时纳入状态，S03 要求删除 head / worktree 后仍能恢复；未明确长期引用的解析方式。
- Impact：旧路径失效后无法定位授权依据和证据，恢复成本增加。
- Recommendation：长期引用记录仓库身份、仓库相对路径和适用提交；worktree 绝对路径仅作当前位置。未提交规划文件必须保留所在 worktree，不能通过清理丢弃。
- Classification：补齐 D02 / D05 的保存与恢复边界，不改变用户决定。

### R02：共享状态需要明确写入责任和冲突处理

- Signal：多个 worktree 共享同一记录，缺少唯一写入者与半写文件处理规则。
- Evidence：Spec 有 Owner，S04 覆盖共享读写，但没有明确另一会话是否可直接覆盖、记录损坏时如何处理。
- Impact：旧进度或旧授权覆盖新记录，无法可靠恢复。
- Recommendation：同一目标一个当前写入 Owner；写入前重新读取并核对版本 / 更新时间，发现不同 Owner 或新更新时暂停写入；先保存完整临时文件再替换，保留损坏记录，不自动推断授权。跨仓库以主目标记录为授权和总体阶段的权威，关联记录保存本仓库交付与主记录引用。
- Classification：落实既有单目标工作线和保护已有修改原则，不新增状态服务、数据库或并发 Agent 平台。

### R03：依赖 PR 转 Ready 前须核实切换 base 后的证据

- Signal：检查通过可能来自旧 head / 旧 base，不能只看绿色状态。
- Evidence：现有 CI 不以所有 PR edited 事件触发；Spec 要求依赖 PR 等前置合并和最终 base 正确后自动合并。
- Impact：旧验证被误用于新集成版本。
- Recommendation：保持 Draft 完成前置与 base 同步，核对 head 与验证基线，再通过目标仓库现有 CI 触发方式取得适用证据；证据不足不转 Ready。Auto-merge 动作应读取实时 PR 状态，避免只依赖过期事件。
- Classification：落实 D04 / D07，不增加人工 PR Review，不绕过 required checks。

### R04：模拟结果不能冒充真实远端或持久后台能力

- Signal：18 个验收场景覆盖 GitHub、会话和本机状态，但模拟 / 真实的证据类型未明确。
- Evidence：Spec 允许可重复模拟，同时要求 GitHub 实时事实和新会话恢复；不新增后台守护进程。
- Impact：仅复述流程即可被误记为通过，或错误宣称真实 PR / 后台监控已验证。
- Recommendation：明确 fixture 与真实执行证据类型；场景需观察实际动作和状态，不只审阅说明。授权边界场景验证拒绝写入；共享状态场景使用隔离 Git 仓库；新 Thread 与安装缓存使用支持方式验证，并明确不能热更新当前 Thread。
- Classification：细化 D11 / S01–S18 的证据要求，不增加生产验证或未经授权的远端操作。

### R05：Plugin 源、安装来源和关联记录不可成为多份授权真相

- Signal：跨仓库源、缓存、marketplace 来源和共享记录分别存在，容易从旧源更新缓存，或在同 ID 的两份记录间产生冲突。
- Evidence：外置 Plugin 有独立源码 checkout，另有 marketplace worktree；源 README 要求通过支持方式更新并在新 Thread 验证。
- Impact：代码已更新但实际使用旧缓存；跨仓库目标错误报告全部完成。
- Recommendation：执行前核实实际配置指向的源和 worktree；源与缓存逐文件核对；关联记录指向唯一主目标授权；迁移和清理不能破坏仍在使用的安装来源。发布前独立核对该仓库的发布边界。
- Classification：完善已批准的跨仓库同步和来源核实要求，不自动改变无关 Plugin 或许可。

## Design Twice / Alternatives

| 方案 | 评估 |
| --- | --- |
| 继续将实时状态提交到 .scratch | 仍需合并后提交或额外 PR，无法解决更新状态与清理的冲突。 |
| 以未跟踪 .scratch 文件维护状态 | 易随 worktree 删除丢失；需要额外忽略规则，不天然共享。 |
| 公共 Git 目录内的独立 Markdown 状态 | 符合本机共享、与 Git diff 分离的需求，使用现有工具；需明确引用和唯一写入 Owner。 |
| 数据库 / 后台服务 / 跨机同步 | 引入本次无需求的运维和部署负担，超出已确认范围。 |

选择：公共 Git 目录 + Markdown + 现有 Git / gh / Codex 工具。Owner 为当前主 Agent；重审触发条件是实际需要多写入者、跨机器实时同步或持久监控服务，届时作为新目标确认。

## 边界与结论

- 需求、授权、状态与交付职责可明确表达，产品架构不受影响。
- 小修均落实已经确认的恢复、安全、依赖和证据要求，无新增公共功能或技术栈。
- 当前 Spec 确认不授权实施或发布；需继续形成 Ticket 草案并由用户确认拆分与实施范围。
- 小修落实后可进入 workflow-to-tickets；发现会改变关键方案的新问题时回到用户确认。

## 修订核对

- R01：Spec 已规定仓库相对路径与提交引用，并禁止删除包含未提交规划文件的 worktree。
- R02：Spec 已规定唯一状态写入 Owner、重读与版本核对、完整替换和损坏保留；跨仓库授权以主记录为准。
- R03：Spec 已明确切换 base 后的证据核对与 Draft 门禁，并要求 Auto-merge 读取实时 PR 状态。
- R04：Spec 已区分模拟 / 真实证据，加入 S19 更新冲突与损坏、S20 跨仓库引用场景；新 Thread 不等于当前 Thread 热更新。
- R05：Spec 已要求核实 marketplace 实际来源、源 / 缓存一致性和安装来源的清理依赖。
- 以上小修在完成只读审查后，通过独立 Spec 修订步骤落实；未修改正式规则、代码、测试或远端配置。
- Next：workflow-to-tickets，准备草案并在当前上下文执行 Readiness。

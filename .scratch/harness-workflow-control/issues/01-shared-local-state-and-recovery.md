# Ticket 01：共享本机状态与安全恢复

Status: done
Owner: 当前主 Agent
Blocked by: None (can start immediately)

## 公共目标约束与已确认授权

- 依据 `../spec.md`；完整 Spec 已确认，用户已授权按依赖完成本 Ticket 与本目标其余四项。
- 授权覆盖此目标范围内的修复、Review、验证、记录和本地交付，不覆盖未确认的目标或关键方案变化。
- Push、创建 / 更新 PR、合并授权设置或发布需要取得发布授权；不得直接人工 Merge。
- 保留用户修改，不自动清理历史、其他 worktree、其他 Plugin 或远端保护设置。
- 真实 API Key、Token、Password、Connection String 等 Secret 不进入源代码、记录或测试数据。
- 跨仓库工作分别核对各仓库当前分支、规则、自动化和用户改动；阶段记录不能越权扩张。

### Change Profile

长期规则；中等大小；风险为进度丢失、用户工作被覆盖和授权推断错误；证据为隔离 Git / worktree 场景；交付为 ChatBI 状态 / 入口文档与可执行的操作约定。

### What to build

- 定义公共 Git 目录内的 Markdown 状态位置、工作项 ID、字段、Owner、更新和保留方式。
- 区分长期 .scratch 记录与本机实时状态；长期引用包含仓库相对路径与提交，临时路径失效仍可恢复。
- 定义单写入、重读核对、完整替换、损坏保留和跨仓库主 / 关联记录规则。
- 新会话区分实施恢复和 PR 收尾；无活动工作直接处理请求，master checkout 不使未完成交付丢失。
- 旧记录仅在恢复当前活动任务时导入；无依据的授权不重建为已授权。

### Owned files

- ChatBI：docs/agents/issue-tracker.md 的状态、保存、恢复与迁移部分。
- ChatBI：docs/agents/agent-harness.md 的组成、入口与本机记录说明。
- ChatBI：AGENTS.md 的状态入口、恢复与改动归属规则。
- 当前工作项的结果与验收引用；本机状态模板可置于上述文档，不新增生产模块。

### Acceptance criteria / Evidence

- S03–S07、S17、S19–S20 有具体可观察结果：多个 worktree 解析同一目录，状态更新不改变 git status，worktree 删除后引用仍可核实。
- 损坏、缺字段、写入冲突和未知授权时保留文件并说明恢复条件。
- 用户修改阻碍清理时不执行删除；无活动任务不强制用户选择旧记录。
- 本 Ticket 的文档与字段检查通过；实际场景覆盖和证据汇总由 Ticket 05 完成，不提前宣称全部验收。

### Migration / Rollback / Done When

保留历史 .scratch 文件和用户修改。旧机制迁移在 Ticket 05 执行；回滚规则时保留共享记录供诊断。Done When：保存、字段、引用、授权与恢复规则无歧义且可由现有工具执行，适用本地检查完成。

### Result / Comments

完成：已按 Spec 定义主记录 / 关联记录、授权字段、稳定引用、单 writer 和安全替换规则；已在 ChatBI 与 Plugin 两个 Git 公共目录建立本工作项状态。Markdown 本地链接与 `git diff --check` 通过；所有 ChatBI worktree 解析到同一公共目录，状态文件不改变 Git status，Plugin 状态保存在其独立公共目录并指向主记录。实际损坏、冲突、删除 worktree 后恢复等场景由 Ticket 05 留存证据。对应 D02、D05、D13，设计修订 R01、R02、R05。

## Comments

Spec and shared project / delivery constraints are defined in `../spec.md`.

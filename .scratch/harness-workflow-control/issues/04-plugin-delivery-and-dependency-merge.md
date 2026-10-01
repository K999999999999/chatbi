# Ticket 04：通用恢复、交付与依赖合并保护

Status: done
Owner: 当前主 Agent
Blocked by: Ticket 03

## 公共目标约束与已确认授权

- 依据 `../spec.md`；完整 Spec 已确认，用户已授权按依赖完成本 Ticket 与本目标其余四项。
- 授权覆盖此目标范围内的修复、Review、验证、记录和本地交付，不覆盖未确认的目标或关键方案变化。
- Push、创建 / 更新 PR、合并授权设置或发布需要取得发布授权；不得直接人工 Merge。
- 保留用户修改，不自动清理历史、其他 worktree、其他 Plugin 或远端保护设置。
- 真实 API Key、Token、Password、Connection String 等 Secret 不进入源代码、记录或测试数据。
- 跨仓库工作分别核对各仓库当前分支、规则、自动化和用户改动；阶段记录不能越权扩张。

### Change Profile

长期交付规则；中等大小；风险为合并早于告知、旧事件启用合并、依赖检查或安装来源失效；证据为 PR fixture 与 Bash / 元数据检查；交付为 Plugin 源和必要的 ChatBI workflow 防护。

### What to build

- 更新 setup 与本地 tracker 参考：显式初始化仍先检查项目规则；共享状态机制按项目适配，不直接把 ChatBI 目录写成所有项目事实。
- 更新 delivery 和 CI Feedback：发布前说明自动合并，持续授权 / 监控，真实中断交接，复盘、范围外反馈、安全清理和聊天报告。
- delivery 调用元数据与 Ticket 03 的阶段约定一致；完成 README 中全部 10 个阶段 Skill 的说明。
- 依赖 PR 记录前置和最终 base，保持 Draft，切换 base 后核对最新 head 与基线证据，再转 Ready。
- 对 ChatBI Auto-merge workflow 做必要一致性防护：动作前查询实时 Draft / head / base；与过期事件冲突时不启用不满足条件的 PR。
- 明确新机器恢复、跨仓库主 / 关联记录和 marketplace 来源不能因清理失效；不自动修改远端保护设置。

### Owned files

- Plugin 源：workflow-delivery 的 SKILL.md、agents/openai.yaml、references/ci-feedback.md。
- Plugin 源：setup-engineering-workflow 的 SKILL.md、issue-tracker-local.md；必要的 README 同步。
- ChatBI：.github/workflows/enable-auto-merge.yml；docs/agents/git-pr-workflow.md 中对应依赖 / 实时检查说明。

### Acceptance criteria / Evidence

- S01、S02、S06、S13、S15、S16 可以用明确 fixture 验证持续跟进、依赖门禁和完成报告。
- PR 创建前告知；未知状态、Draft、错误 base、变动 head 或依赖未解决时不调用启用合并动作。
- 同目标已授权的范围内更新和复盘不重复询问；无发布授权不写远端。
- 模拟工具调用、YAML / Bash 检查与 Skill 校验通过，真实与模拟证据明确区分。
- 未调用直接人工 Merge，未削弱 required checks、未新增用户 PR Review。

### Migration / Rollback / Done When

保持默认独立 PR 自动合并，依赖交付受到已确认门禁保护。若远端状态不可核实保留 Draft / 分支并记录原因。Done When：项目 workflow 与 Plugin delivery / setup 的调用顺序、恢复和保护规则一致。

### Result / Comments

已完成：Plugin delivery / CI Feedback / setup 与本地 tracker 规则已补齐持续发布授权、发布前聊天告知、PR 后即时交接与持续跟进、依赖 PR Draft / 最终 base 检查、恢复记录保留、跨仓库主 / 关联记录和 marketplace 来源保护；十个阶段 Skill 的 README 与元数据已同步。ChatBI Auto-merge workflow 在请求启用前读取实时 PR，并比较状态、Draft、head SHA、base branch 和 head repository 与事件快照；过期、不确定或不满足条件时不调用启用命令。

验证：十个阶段 Skill 与 setup Skill 的 `quick_validate.py` 均通过；13 个 Plugin Skill 的元数据值有效，恰好十个阶段 Skill 允许隐式调用；Plugin manifest JSON 解析通过。ChatBI workflow YAML 解析、内嵌 Bash `bash -n`、`git diff --check` 通过；10 个模拟 GitHub 响应覆盖允许合并、Draft / 未解决依赖、错误 base、head 变化、fork、关闭 PR、过期事件、状态查询失败和已启用等路径，结果符合预期。当前上下文 Code Review：PASS。`actionlint` 与专用 `validate_plugin.py` 在本机未找到；以 YAML / Bash、Skill、元数据及模拟响应检查替代。只读确认 `gh api --jq` 可返回 live PR 字段；未修改远端 Ruleset / Protection，未 Push 或创建 PR。整体 S01–S20 与安装 / 新 Thread 验收留 Ticket 05。

## Comments

Spec and shared project / delivery constraints are defined in `../spec.md`.

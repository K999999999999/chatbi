# Ticket 03：通用 Skill 阶段调用与关键方案控制

Status: done
Owner: 当前主 Agent
Blocked by: Ticket 02

## 公共目标约束与已确认授权

- 依据 `../spec.md`；完整 Spec 已确认，用户已授权按依赖完成本 Ticket 与本目标其余四项。
- 授权覆盖此目标范围内的修复、Review、验证、记录和本地交付，不覆盖未确认的目标或关键方案变化。
- Push、创建 / 更新 PR、合并授权设置或发布需要取得发布授权；不得直接人工 Merge。
- 保留用户修改，不自动清理历史、其他 worktree、其他 Plugin 或远端保护设置。
- 真实 API Key、Token、Password、Connection String 等 Secret 不进入源代码、记录或测试数据。
- 跨仓库工作分别核对各仓库当前分支、规则、自动化和用户改动；阶段记录不能越权扩张。

### Change Profile

长期 Plugin 规则；中等大小；风险为自动调用绕过授权或继续强制逐阶段手动调用；证据为 Skill / 元数据校验与已授权 / 未授权场景；交付为 Plugin 源的本地变更。

### What to build

- 对齐 discovery、grill、to-spec 的关键技术澄清、小实验、短 / 完整 Spec 与记录门禁。
- 对齐 design-review、to-tickets、ticket-readiness 的修订核对、草案 / 正式区分和整体授权延续。
- 对齐 implement、tdd、code-review 的范围控制、验证复用、正式事实源同步与范围外反馈。
- 阶段 Skills 可在任务和授权满足时按阶段使用；同步 policy.allow_implicit_invocation 与正文，允许调用不等于授权写入。
- ask-matt 保持可选导航，setup / Wayfinder 保留显式启动边界；专项 agent-engineering-skills 不变。

### Owned files

- Plugin 源：上述 9 个阶段 Skill 的 SKILL.md、agents/openai.yaml 和实际受影响的 references。
- Plugin 源：ask-matt 的 SKILL.md、阶段 / Readiness / 项目适配 / 交付门禁 references（只更新与新流程冲突的内容）。
- Plugin 源：engineering-workflow README 和仓库 README 的阶段调用说明。

### Acceptance criteria / Evidence

- 9 个阶段 Skill 的调用政策与确认边界一致；delivery 的对应修改由 Ticket 04 完成。
- setup、Wayfinder、导航与其他 9 个专项 Skill 的调用配置未被误改。
- 同一目标整体授权后允许连续推进；纯问答、未确认复杂 Spec、未授权实验和关键方案变化不自动进入实施。
- 使用已有 quick_validate 检查修改的 Skills；Plugin JSON 和调用元数据检查通过。专用 validator 不可用时记录未运行及替代检查，不伪称运行。
- Plugin 源检查和本地 Review 完成；本 Ticket 不直接编辑安装缓存或写远端。

### Migration / Rollback / Done When

通用 Plugin 沿用目标仓库事实源，不强加 ChatBI 路径或自动合并默认。本机同步在 Ticket 05 做。Done When：源中阶段调用与范围控制完整一致，校验通过；尚未同步的缓存明确区分。

### Result / Comments

已完成：Plugin 源九个前置阶段 Skill 的调用元数据和确认边界已与 Spec 对齐；`ask-matt` 保持可选导航，setup、Wayfinder、delivery 和专项 Skill 未提前改变。九个目标 Skill 的 `quick_validate.py` 全部通过；YAML 检查确认恰好九个阶段 Skill 为 `allow_implicit_invocation: true`，其余四个本 Plugin Skill 为 `false`；Plugin manifest JSON 解析通过；`git diff --check` 通过。当前上下文 Code Review：PASS，未发现范围、授权门禁、阶段交接或文档策略矛盾。专用 `validate_plugin.py` 未找到，Ticket 05 再检查可用验证器并记录替代证据。Plugin 源修改仍在本地工作区，未提交、未同步安装缓存、未写远端；Ticket 04 接续同一工作线。

## Comments

Spec and shared project / delivery constraints are defined in `../spec.md`.

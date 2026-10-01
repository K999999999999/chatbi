# Ticket 02：ChatBI 确认、实施和交付闭环

Status: done
Owner: 当前主 Agent
Blocked by: Ticket 01

## 公共目标约束与已确认授权

- 依据 `../spec.md`；完整 Spec 已确认，用户已授权按依赖完成本 Ticket 与本目标其余四项。
- 授权覆盖此目标范围内的修复、Review、验证、记录和本地交付，不覆盖未确认的目标或关键方案变化。
- Push、创建 / 更新 PR、合并授权设置或发布需要取得发布授权；不得直接人工 Merge。
- 保留用户修改，不自动清理历史、其他 worktree、其他 Plugin 或远端保护设置。
- 真实 API Key、Token、Password、Connection String 等 Secret 不进入源代码、记录或测试数据。
- 跨仓库工作分别核对各仓库当前分支、规则、自动化和用户改动；阶段记录不能越权扩张。

### Change Profile

长期工程规则；中等大小；风险为重复确认、越过关键决定与过早报告完成；证据为规则核对和阶段 / 授权场景；交付为 ChatBI 流程 Contract。

### What to build

- 明确需求与关键技术澄清覆盖、完成条件、用户确认与小实验边界。
- 明确短 Spec 先留存、明确小任务指令作为实施授权；复杂目标仍经过完整 Spec、设计审查、拆分确认。
- 整体授权后连续推进；有条件通过先落实修订；关键变化重新确认。
- 验证证据绑定版本、基线和覆盖范围，按实际影响复用 / 重跑；同步正式事实源作为 Done When。
- 发布前说明默认自动合并，不新增用户 PR Review；发布授权在同目标内延续至 PR 更新、范围内修复、复盘和安全清理。
- 明确持续监控、真实中断交接、合并后复盘与清理阻塞；完整结果在聊天汇报。

### Owned files

- ChatBI：AGENTS.md 的阶段、授权、验证与交付规则。
- ChatBI：docs/agents/issue-tracker.md 的澄清、Spec、设计审查、Ticket 和授权部分。
- ChatBI：docs/agents/git-pr-workflow.md。
- ChatBI：docs/agents/agent-harness.md 的流程与 Skill 依赖说明。
- ChatBI：.github/pull_request_template.md 的实际结果与复盘记录约定。

### Acceptance criteria / Evidence

- D01、D03、D06–D15 在对应事实源中可追溯，旧的重复确认与两分钟后结束规则不与新 Contract 冲突。
- Spec 确认、Ticket 拆分、实施授权和发布授权分别表达；已明确授权的同范围动作不重复请求。
- S08–S12、S14–S16 有可执行判断标准；未授权的关键变化和实验必须暂停。
- 实施、合并、复盘、清理分别有结果，清理阻塞不等于全部 done。
- 文档检查、当前上下文 Review 与 Diff 检查通过。

### Migration / Rollback / Done When

与 Ticket 01 的状态接口保持一致；不删除历史决定和 Ticket。Done When：完整流程可从入口连续执行，所需确认点、停止条件、证据与完成报告一致。

### Result / Comments

完成：已统一需求 / 技术澄清、短 Spec 与整体实施授权、Ticket 连续推进、`PASS WITH MINOR FIXES` 修订闭环、版本关联验证与正式事实源要求；PR 授权在聊天中取得、目标仓库自动合并策略提前说明，发布后即时聊天交接并持续核实；普通独立 PR 不增加用户 Review，依赖 PR 单独保护。Review PASS（Ticket 01 / 02 当前变更范围），Markdown local links 与 `git diff --check` 通过。未修改可执行代码；流程场景由 Ticket 05 验收。对应 D01、D03、D06–D10、D12–D15。

## Comments

Spec and shared project / delivery constraints are defined in `../spec.md`.

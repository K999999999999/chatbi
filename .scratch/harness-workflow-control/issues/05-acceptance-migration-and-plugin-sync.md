# Ticket 05：整体验收、当前任务迁移与本机安装同步

Status: done
Owner: 当前主 Agent
Blocked by: Ticket 04

## 公共目标约束与已确认授权

- 依据 `../spec.md`；完整 Spec 已确认，用户已授权按依赖完成本 Ticket 与本目标其余四项。
- 授权覆盖此目标范围内的修复、Review、验证、记录和本地交付，不覆盖未确认的目标或关键方案变化。
- Push、创建 / 更新 PR、合并授权设置或发布需要取得发布授权；不得直接人工 Merge。
- 保留用户修改，不自动清理历史、其他 worktree、其他 Plugin 或远端保护设置。
- 真实 API Key、Token、Password、Connection String 等 Secret 不进入源代码、记录或测试数据。
- 跨仓库工作分别核对各仓库当前分支、规则、自动化和用户改动；阶段记录不能越权扩张。

### Change Profile

目标内验收与迁移；中等大小；风险为规则看似一致但实际不能恢复、缓存未更新或虚报真实验证；证据为 S01–S20、源 / 缓存核对和新 Thread；交付为长期验收记录与已核实的安装状态。

### What to build

- 构建隔离 Git / worktree 和模拟 PR 状态场景，逐项执行 S01–S20，保存输入、授权、动作、结果、证据类型和重现方式。
- 对关键确认边界、新会话恢复与阶段调用做适用的新 Thread 情境验收，验证实际行为，不只给模型复述规则。
- 核实支持的安装更新来源，校验源后按支持方式同步 engineering-workflow；逐文件核对源 / 缓存，并验证新 Thread 加载。
- 将本工作项实时阶段迁移到共享本机状态，当前 `.scratch/<feature>/status.md` 留作历史规划快照；保留长期 Spec / Tickets / 证据。
- 最终检查 15 项决定在正式规则中的覆盖、证据版本和用户已有修改；记录尚未验证的真实远端范围。

### Owned files

- ChatBI：docs/acceptance/harness-workflow-control.md（实际验收结果，按需创建，不生成空文档）。
- 当前工作项：issues/ 的 Result / Comments、必要的隔离 fixture 与重现记录。
- 两个仓库的当前目标共享本机状态与来源引用，不提交实时状态。
- engineering-workflow 安装缓存仅由支持的安装命令更新，不直接编辑缓存。

### Acceptance criteria / Evidence

- S01–S20 逐项给出通过、失败、未运行或阻塞及证据；必要场景未通过时不能宣称 Harness 行为完成。
- Git / worktree 共享、状态更新不污染工作区、引用存活、冲突保留和未知授权拒绝有实际动作证据。
- 源与缓存一致、新 Thread 加载及越权拒绝有可核查结果；当前 Thread 不称为热更新成功。
- 未授权的旧 PR / 真实远端写入不用于验收；模拟通过不能表述为真实 PR 已验证。
- 不运行无关 ChatBI 产品测试；若 workflow 或 fixture 有可执行变更，完成对应确定性检查。

### Migration / Rollback / Done When

迁移只处理本目标及经核实需要恢复的活动记录，不批量改旧历史，不删除其他工作线。同步失败时保留源和诊断，按支持方式恢复已知有效安装；不能通过手改缓存换取一致。

Done When：本地适用验收、Review、Diff 和安装核对完成，两个仓库形成可审阅的 candidate；报告当前目标仍待发布授权，不能将本地实施完成表述为整个交付完成。

### Result / Comments

已完成；S01–S20 逐项验收及证据边界见 [`docs/acceptance/harness-workflow-control.md`](../../../docs/acceptance/harness-workflow-control.md)。S03–S06、S19–S20 由隔离 Git / worktree fixture 实际执行；S13 的十种 PR 状态由读取真实 workflow 脚本的 mock fixture 执行；S07、S09、S10、S14、S17、S18 使用更新后 Plugin 缓存启动的新 Codex CLI session 验收；其余场景按报告标为授权边界、模拟或规则核对，没有冒充真实 PR 行为。S08 验证整体实施授权与发布授权分别记录；发布授权保持未授权。

安装核对：通过支持的 `codex plugin add engineering-workflow@personal --json` 同步；当前 Plugin 保持 installed / enabled，源与缓存共 39 个文件，路径集合及 SHA-256 全部一致。十个阶段 Skill 与 setup Skill 的 `quick_validate.py` 检查通过；22 个 Plugin Skill metadata 均为 boolean，其中 10 个阶段 Skill 为 `true`、12 个其他 Skill 为 `false`，manifest JSON 解析通过。新 CLI session 读取了更新缓存；未验证 Codex Desktop 重载或当前已打开 Thread 热更新。

最终上下文 Code Review：PASS，无发现；覆盖本 Ticket 新增验收矩阵 / fixture 与整体变更范围。ChatBI 与 Plugin `git diff --check`、相关 Markdown 链接检查通过；两项 fixture 全部通过。`actionlint` 与专用 `validate_plugin.py` 不可用，替代检查及真实远端验证限制见验收报告。未运行无关 ChatBI 产品测试 / Evaluation；未写远端、Push 或创建 PR。

Ticket 05 的本地工作已完成并形成可审阅 candidate；整个目标仍待发布授权和后续远端交付，不标记为整体 done。

## Comments

Spec and shared project / delivery constraints are defined in `../spec.md`.

# 路线图维护规则修复（短 Spec）

## 目标与授权

用户在确认路线图读取、变化时更新和优先级决策边界建议后，指示“按你建议来 修复”，构成本次小范围文档改动及本地 Commit 的实施授权。Push / PR 未授权。

基线：`291a500b30137f82b3125a9c9fca547eb6094ffc`；初始 `master` 干净，fetch 后与 origin/master 一致。
Branch：`docs/roadmap-maintenance`；worktree：当前仓库主 worktree。

## 范围与预期结果

- AGENTS.md 将 docs/roadmap.md 纳入规划读取入口、文档地图及 Done When。
- docs/agents/agent-harness.md 定义读取时机、更新触发、跨文档核对和优先级授权边界。
- docs/roadmap.md 明确当前顺序和优先级确认状态，引用维护规则；保留现有产品边界和验收门槛。
- docs/agents/git-pr-workflow.md 与 PR 模板加入路线图适用性检查。
- 不改变产品功能、架构、评测门槛，不将本次咨询建议写成已确认的新生产目标或优先级，不修改外置 Plugin。

## 验收与验证

- 规划入口要求结合 roadmap、产品范围、相关 Spec / Design / Acceptance；识别旧“后续”已被后续工作覆盖的情况。
- 已确认目标、依赖、验收或完成事实影响路线图时，依据证据更新；未影响时记录不适用理由。
- Agent 可更新已核实事实；重排优先级、新增承诺或改变范围须用户确认；未知和建议显式标记。
- 路线图不替代本机实时记录，历史评测仍绑定其 commit；修改文档不把旧报告改称当前 HEAD 结果。
- 运行现有 Markdown 本地链接检查、git diff --check，并在当前上下文执行 Code Review；纯文档不运行产品测试或真实评测。

## Done When

五个入口文件一致、验收及 Review 通过并形成本地 Commit；工作区干净，本机记录保留候选和发布授权边界。

## 验证与 Review 结果

- `python3 -m scripts.check_markdown_links`：PASS。
- `git diff --check`：PASS。
- 当前上下文 workflow-code-review：PASS；对基线 `291a500` 核对五个入口文件与本 Spec，全部验收条件满足。正常维护、证据不足、旧“后续”过期和优先级变更均有明确规则；无产品、架构或安全边界变更，无 Secret 或无关改动。
- 路线图更新位置：`docs/roadmap.md` 的“路线顺序与优先级状态”；本次只明确既有路线与维护入口，未排定新的生产工作优先级或改写历史评测成绩。
- 产品测试、AI Evaluation、Real E2E：未运行；纯文档修改，不影响产品代码和运行行为。
- Harness 反馈：本目标覆盖的路线图入口与维护缺口已修复；未观察到额外符合门槛的 Harness 缺口。
- 回滚：撤销本目标文档提交即可，不涉及数据库或运行配置迁移。

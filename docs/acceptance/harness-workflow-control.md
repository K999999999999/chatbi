# Harness 工作流控制与交付闭环验收

- Date: 2026-10-01
- Spec: [`.scratch/harness-workflow-control/spec.md`](../../.scratch/harness-workflow-control/spec.md)
- Baseline: ChatBI `1fe3014dc7916b2c7bd8d348c31c381f32c30820`; Plugin `86731d4dcdfbcefea1efd33f5c4bfd33863ab10d`
- Mode: 隔离 Git / worktree fixture、模拟 PR 状态、真实本机 Codex CLI 新 session 与规则核对；没有对当前目标创建真实 PR 或写入远端。

## 证据边界

- **真实本机结果**：隔离 Git 仓库 / worktree 的实际文件操作、当前 Codex CLI 配置与安装缓存、通过新 CLI session 对安装 Skill 的读取和场景处理。
- **模拟结果**：受控的 GitHub PR JSON / CI 状态；不证明真实 GitHub Actions 执行、当前目标 CI 或后台 monitor。
- **规则核对**：对照 Spec、正式规则和 Skill 的输入 / 授权 / 停止条件；不冒充实时 PR 或生产行为证据。
- 新 CLI session 使用 `codex exec --ephemeral`，实际读取更新后的安装缓存。本次没有重启或验证 Codex Desktop，也没有证明当前已经打开的 Thread 热更新。
- 当前工作项没有发布授权；所以没有等待真实 PR 两分钟、创建 / 更新 PR、检查其 required checks、运行真实 Auto-merge 或做远端清理。此边界不影响本地模拟 fixture。

可复现的本地 fixture：

- [local-state-fixture.py](../../.scratch/harness-workflow-control/fixtures/local-state-fixture.py)：S03–S06、S19、S20。
- [auto-merge-workflow-fixture.py](../../.scratch/harness-workflow-control/fixtures/auto-merge-workflow-fixture.py)：读取实际 workflow 的内嵌 Bash，以 mock `gh` 执行 S13 的十种状态。

## S01–S20 场景结果

| 场景 | 结果 | 输入与可观察证据 |
| --- | --- | --- |
| S01 PR 发布后两分钟 CI 仍运行 | PASS（模拟 / 规则核对） | 输入 `PR=OPEN`、required check `IN_PROGRESS`、已等待超过两分钟。按交付规则继续保存 `in-progress`，下次检查依据是 CI / PR 事件；没有真实等待或真实 PR。 |
| S02 最后检查后 PR 合并，原 session 中断 | PASS（模拟 / 规则核对） | 输入旧状态仍为 `OPEN`、新 session 读到 live `MERGED`。先信任新的 PR 状态，再做 Harness 复盘与安全清理并在聊天汇报；没有模拟真实会话进程中断或当前目标远端 PR。新机器恢复的实际 CLI 场景见 S17。 |
| S03 位于 master，原 head / worktree 已删除 | PASS（真实隔离 Git fixture） | 删除 feature worktree 和 branch 后，从 master 经 Git common directory 读取同一工作项状态，记录仍可访问。 |
| S04 两个 worktree 读取 / 更新同一目标 | PASS（真实隔离 Git fixture） | main、feature、detached 三个 worktree 解析到同一 Git common directory；从 common-dir 写状态不改变 surviving worktree 的 `git status`。 |
| S05 合并后只更新状态 | PASS（真实隔离 Git fixture） | 在 feature worktree 删除后更新本机状态；`HEAD` 未改变、没有新 Commit、master / surviving worktree 的 `git status` 保持干净。 |
| S06 用户修改或其他依赖阻碍清理 | PASS（真实隔离 Git fixture） | 在独立 feature worktree 添加用户文件；dirty 状态使清理条件为 false，branch、worktree 和原文件均保留。 |
| S07 无活动工作或只读咨询 | PASS（真实 Codex CLI 新 session） | 新建干净 Git fixture，没有活动工作项。自然语言只要求探索 `/hello` 偶发 4 秒延迟。CLI 实际读取缓存中的 `workflow-discovery/SKILL.md`，报告未知影响和一个关键问题；未建 Spec / Ticket / 代码，fixture `git status` 干净。 |
| S08 整体实施授权与发布授权分开记录 | PASS（实际授权边界） | 用户授权本目标连续完成 Ticket 01–05，无逐 Ticket “是否继续”提示；发布授权单独保持未授权，因此没有 Push / PR。此场景验证授权分离和未越权发布，不代表真实 PR 发布已验证。 |
| S09 技术方案 / Contract 需要变化 | PASS（真实 Codex CLI 新 session） | 隔离仓库要求 `/hello` 增加 request ID 且兼容旧客户端，但未决定 Header 或 JSON body。CLI 实际读取 `workflow-grill-with-docs/SKILL.md`，列出可观察选项并等待用户确定；API 文件未改、`git status` 干净。 |
| S10 明确的小改动 | PASS（真实 Codex CLI 新 session） | 用户明确授权在隔离 README 追加精确句子。CLI 实际读取 `workflow-implement/SKILL.md`，先写 `.scratch/acceptance-fixture-line/spec.md`，后修改 README；断言句只出现一次；无 Ticket / Commit / Push / PR。 |
| S11 Design Review 为 `PASS WITH MINOR FIXES` | PASS（规则核对 / 模拟） | 对照 `workflow-design-review`：逐项落地并核对修订后才进入下一阶段；如改变已确认目标或关键决定先重新确认。本目标最终 Design Review 为 PASS，没有真实触发 minor-fix 分支。 |
| S12 旧验证证据复用 / 失效 | PASS（规则核对 / 模拟） | 对照目标 HEAD、base 与变更范围：只改无关文档时复用未受影响证据；行为、依赖或基线变化时重跑受影响验证。没有当前目标 PR，故未测试 GitHub required checks 的重跑。 |
| S13 依赖 PR 条件不满足 / 满足 | PASS（模拟 GitHub fixture） | 十种状态实际运行 workflow 脚本：ready 且 head/base 与事件匹配时请求启用；Draft（代表依赖未解决）、错误 stacked base、head 变化、fork、关闭 PR、过期事件或 live API 失败都不调用 merge；已启用时保持幂等。 |
| S14 未确认的小实验 | PASS（真实 Codex CLI 新 session） | 只询问是否对 `.invalid` 测延迟，并明确没有授权。新 session 未执行网络命令或创建文件，说明该测试域名不能代表服务，并先请求真实 target、环境、side effect 与判断标准。 |
| S15 Harness 复盘提出范围外缺口 | PASS（规则核对） | `workflow-implement` 要求记录类别、证据、建议位置与预期效果；超出当前 Ticket 的改进先报告，不自行扩 scope。本目标没有观察到需要另建的范围外改进。 |
| S16 正式文档同步与最终报告 | PASS（本目标实际交付） | 15 项决定分别映射到 ChatBI / Plugin 正式规则；Spec、Tickets、fixture 和本验收报告保存在版本库。本机实时进度放在 Git common directory。最终报告区分本地实施、发布授权、合并、复盘和清理。 |
| S17 新机器无实时状态 / 旧记录过期 | PASS（真实 Codex CLI 新 session） | 隔离仓库只有 tracked `.scratch` 记录，没有 common-dir 实时状态；新 session 恢复本地阶段，指出找不到候选实现、发布授权为 `unknown`，未改文件或执行远端命令。 |
| S18 Plugin 源、缓存与新 session | PASS（真实本机安装 / 新 session） | `personal` marketplace 指向当前 Plugin 源 checkout；通过 `codex plugin add engineering-workflow@personal --json` 更新受支持安装。启用状态保持 true；源 / 缓存 39 个文件路径和 SHA-256 全部相同。新 CLI session 实际加载并执行 Discovery、Implement、Clarification Skill。 |
| S19 写入冲突、损坏或缺字段 | PASS（真实隔离 Git fixture） | 旧 writer 的内容 hash 与最新记录不同后拒绝覆盖；缺少 `Stage` / `Owner` 等字段时授权保持未知，损坏记录字节未变。 |
| S20 跨仓库关联记录 / 临时路径失效 | PASS（真实隔离 Git fixture） | 两个 Git common directory 的关联记录使用同一稳定 ID；linked record 引用唯一 primary record 和仓库相对 Spec 路径，没有复制实施授权。删除 feature worktree 后引用仍可核实。 |

## 验证与限制

- `local-state-fixture.py`：S03–S06、S19、S20 全部 PASS。
- `auto-merge-workflow-fixture.py`：workflow YAML 可解析、内嵌 Bash `bash -n` 通过；十种 mock PR 状态全部符合预期。
- Plugin：十个阶段 Skill 与 setup Skill 的 `quick_validate.py` 全部 PASS；13 个 engineering-workflow `openai.yaml` 都是 boolean，10 个阶段 Skill 为 `true`、ask-matt / setup / Wayfinder 为 `false`；Plugin manifest JSON 解析通过。
- 安装同步：Codex CLI 报告 `engineering-workflow@personal` 为 installed / enabled；源与缓存 39 个文件逐项 SHA-256 相同。同步使用 `codex plugin add`，没有直接写缓存。
- GitHub CLI v2.46.0 的 `gh api --jq` 实际只读查询可返回需要的 PR 状态字段。没有对 Ruleset / Branch Protection 作写操作。
- `git diff --check`、Markdown 链接检查和当前上下文 Code Review 在最终提交前完成，结果记在当前 Ticket。
- 本机没有 `actionlint` 和专用 `validate_plugin.py`；已用 YAML 解析、内嵌 Bash 语法、Skill 快速校验、metadata / manifest 检查及 PR 状态 fixture 替代。没有运行无关 ChatBI 产品测试、AI Evaluation 或真实服务 E2E。

本验收证明的是本机工作流规则、隔离 fixture 和新 Codex CLI session 的行为。它没有证明当前目标已 Push、真实 PR 已通过 CI / Auto-merge、Codex Desktop 已重载或有后台服务可在 session 结束后唤醒 Agent。

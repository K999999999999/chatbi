# Ticket 02：校准仍作为当前事实的文档状态与路径

Status: done
Owner: 当前主 Agent
Blocked by: 01-project-guide
Change Profile: Lifetime S；Size S–M；Risk Low；Evidence 权威 Spec / Acceptance / Roadmap 与内容逐项核对；Delivery 本地文档提交，无运行时发布。
Canonical Source: 已确认的 Spec / Acceptance 和可核实的当前代码 / 运行记录；Roadmap 汇总状态须遵循事实源。日期化 Acceptance 保持历史语义。

## What to build

审计 README、Runbook、Product Scope、Roadmap、模块 Spec 及既有 workspace map 中仍被读作当前状态的陈述。按权威证据修正明确过期的状态、链接和入口，或将只对历史候选成立的陈述标为历史 / 候选绑定事实。

优先核对已发现的 R5 README 验收描述、Runbook 的 R7 阶段说明、R7 Spec 状态字段和过时 workspace map。不得改写日期化 Acceptance 历史结果。无法由证据确认的内容应保留并标未确认，不猜测改写。

## Acceptance criteria

1. 每项修订有可追溯依据，不从旧实现、过时候选或链接检查推断当前状态。
2. 已完成能力不再写成待完成；候选专属限制和日期历史准确标注身份。
3. 不更改 Acceptance 历史结果、不重排 Roadmap 优先级、不新增产品承诺；本地链接和交叉引用有效。
4. README、导航页、Runbook、Roadmap 与当前主要目录 / 入口不存在本次发现的相互矛盾陈述。

## Owned files

- `README.md`（当前功能 / 验收状态段）
- `docs/runbook.md`
- `docs/product-scope.md`
- `docs/roadmap.md`
- 经核实需要修订的当前 Spec 状态元数据
- `.scratch/repository-structure-readability/workspace-map.md`（确认仍会误导后才更新或标快照）

不触碰 `.git/` 实时记录或本机配置。

## Verification evidence

- 逐条来源对照表：`.scratch/project-navigation/fact-reconciliation.md`
- `python3 scripts/check_markdown_links.py`
- Diff 事实一致性检查

## Migration / Rollback

不适用；文档可按 Diff 回退。证据冲突无法判断时保留原文并标注未确认。

## Result

已校准 README 的 R5 验收状态、Runbook 的 R7 能力状态、Product Scope 中 R6 / R7 重启验收的区别、R7 Spec 阶段元数据，并将旧 workspace map 明确标成历史快照。逐项对照见 `.scratch/project-navigation/fact-reconciliation.md`；Roadmap 当前状态抽查一致而保留未改；日期化 Acceptance 未改写。`python3 scripts/check_markdown_links.py` 与 `git diff --check` 均通过。

## Comments

- 来源：用户确认的 `.scratch/project-navigation/spec.md` 与 `ticket-drafts.md`。
- Ticket Readiness：READY（当前上下文只读检查）。

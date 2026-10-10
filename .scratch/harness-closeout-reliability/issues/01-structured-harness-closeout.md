# 01 为合并后 Harness 复盘增加结构化闭环检查

Status: done
Owner: 当前主 Agent
Blocked by: None (can start immediately)

## What to build

按 `.scratch/harness-closeout-reliability/spec.md` 定义，统一 PR 模板和本机实时工作记录的 Harness 复盘字段，并扩展 `scripts/check_harness_state.py` 校验明确填写的字段组合。工具继续只读，不自动判断自然语言的复盘真伪，不批量补造旧记录。

字段为：

- `Harness review: no-gap | gap-found`
- `Harness evidence: <PR / Spec / 验收 / 验证证据>`
- `Harness follow-up work item: None | <单个工作项 ID>`

`no-gap` 必须对应 `None`；`gap-found` 必须引用不同于当前工作项且能解析的记录。

## Scope / Out of Scope

- In Scope: 状态字段解析、复盘字段组合 / 引用校验、PR 模板与合并复盘流程文档、确定性回归测试。
- Out of Scope: ChatBI 产品逻辑、历史 PR 复盘批量迁移、远端 PR API 查询、从自由文本推断语义结论。

## Owned files

- `scripts/check_harness_state.py`
- `tests/scripts/test_check_harness_state.py`
- `.github/pull_request_template.md`
- `docs/agents/issue-tracker.md`
- `docs/agents/git-pr-workflow.md` 的合并后 Harness 复盘章节

## Acceptance criteria

- 有效 no-gap 与 gap-found 组合不会产生 ERROR。
- 部分字段、重复字段、无效枚举、空证据、no-gap 带 follow-up、gap-found 缺失 / 多个 / 自引用 / 不存在 follow-up 均会产生确定性 ERROR；输出不包含原始记录正文。
- 历史章节与 fenced examples 不影响当前字段解析；三个字段均缺失的旧记录维持兼容。
- 检查器只读取工作记录与 Git 状态，不改记录、refs 或工作区。
- 模板、流程说明和 Spec 字段定义一致。

## Verification plan

- `python3 -m pytest -q tests/scripts/test_check_harness_state.py`
- 隔离临时 Git 仓库检查有效 / 无效报告和只读性。
- Markdown 链接检查、`git diff --check`、当前上下文 Code Review。

## Migration / Rollback

不迁移历史记录。若发现误报，修正校验或字段约定并重跑原有 fixture；无产品数据迁移。

## Result

实现完成；本 Ticket 定向测试 `31 passed`，全量 Python 测试 `995 passed, 41 skipped, 139 subtests passed`；当前上下文 Code Review PASS。

## Comments

- Canonical Source: `.scratch/harness-closeout-reliability/spec.md`。
- Ticket Readiness: READY；用户于 2026-10-11 确认此拆分。
- Roadmap: 无需更新；本 Ticket 只改变 Harness 复盘记录与本机检查行为，不改变产品目标、依赖或优先级。

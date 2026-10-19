# 工作项取消终态

## 目标

让已明确停止的工作项可以用 `cancelled` 关闭，并保留与 `done`（已完成交付）不同的语义。用户已确认在 ChatBI 和 `engineering-workflow` Plugin 支持该状态，并将 `harness-candidate-preflight` 与 `long-task-progress-clarity` 标记为取消。

## 范围与 Contract

- 实时工作项状态接受 `open | in-progress | blocked | done | cancelled`；长期 Ticket 状态保持 `open | in-progress | blocked | done`。
- `cancelled` 是终态，表示授权者明确停止该工作项。它不表示交付完成，不要求 `done` 的整体收尾证据，也不能作为汇总里的 `Active work item`。
- 取消保留当前 `Stage`、工作记录、分支和文件，不自动删除、回滚、关闭 PR 或级联修改关联工作项 / Ticket。取消命令要求工作项已迁移到 Harness v1、`PRs: None`、提供原因、确认者和当前记录 SHA；状态记录写入结构化取消依据，并以锁、摘要校验和原子替换更新。
- 已取消工作项可读、可检查 Diff；不能再经 Harness 写入命令变更。`done` 的收尾门禁维持原样。
- ChatBI 旧只读检查器识别 `cancelled` 为终态、不发出 `OPEN_WORK_ITEM`；取消项被引用为活动子项时报告错误。父项取消不要求其 Ticket 变成 `done`；Ticket 状态校验仍拒绝 `cancelled`。
- 只显式迁移并取消上述两个本机旧记录，原格式备份保留；不批量迁移其他记录。

## 验收

- Plugin 可严格验证取消元数据、显式 `cancel`、取消后只读，拒绝旧格式直写、缺少依据、非空 PR、重复取消及取消后的状态写入。
- ChatBI 检查器与 Plugin 测试覆盖取消终态、活动引用、Ticket 状态边界、收尾语义和记录更新安全性。
- 两个指定记录显示 `cancelled`、保留原 Stage、Next 为 `None`，并保留迁移前 SHA 备份和取消原因 / 确认来源。
- 对应文档同步说明工作项状态与命令；路线图优先级不变，本工作不涉及产品路线承诺。

## 验证

- Plugin：`uv run --no-project --python 3.11 python -m unittest discover -s tests -v`。
- ChatBI：定向运行 `tests/scripts/test_check_harness_state.py`，再运行 `python3 -m scripts.check_harness_state --json`；确保退出码及两项记录结果符合预期。
- 逐仓检查 Diff 和代码 Review；只在本地提交，不推送。

## 授权依据

用户于 2026-10-19 明确确认新增 `cancelled` 状态并关闭上述两个工作项。该确认覆盖本 Spec 所列的本地实现、验证和本地提交；不含远端推送、PR 或其他工作项迁移。

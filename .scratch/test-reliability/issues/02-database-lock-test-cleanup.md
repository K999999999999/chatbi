# 02 修复数据库并发测试的失败退出与清理

Status: open
Canonical Source: [Spec](../spec.md)、[Design](../design.md)、[草案](../tickets-draft.md#02-修复数据库并发测试的失败退出与清理)
Owner: 当前主 Agent
Change Profile: 小范围测试修复；并发 / 退出风险中等；隔离 PostgreSQL 与有界故障注入。
Blocked by: None (can start immediately)

## What to build

让测试 worker 使用可识别 backend PID 的独立连接；只在观察到自身 worker 确实等待目标锁时通过；先在有界清理路径释放本测试持有的锁，再等待 worker。连接、SQL、观察与 join 均有上限；失败时保留首个诊断原因并清理本测试资源。

Owned files: `tests/chatbi_control/test_history_postgres.py`、必要的测试辅助、如必需的进程有界失败验证、Runbook 相关诊断说明。

Out of Scope: 修改生产 `HistoryStore` / `HistoryRuntime` 行为；取消其他进程 / 会话；为让测试通过而跳过等待断言或单纯加长超时。

## Acceptance criteria

- 正常测试观察到自身 worker 等锁，释放后完成保存；隔离重复执行通过。
- 未观察到等待、worker 异常、等待超时或断言失败时能有界退出、非零结束并保留诊断；没有后台线程阻止进程退出。
- 只取消 / 关闭本测试拥有的连接；锁、连接和资源均释放；CI 与 development 数据库 profile 回归通过。

Migration / Rollback: 无生产或数据迁移；切片可独立恢复，不触及日常数据库。

## Result

Pending.

## Comments

首次调查观察到原断言失败及线程池退出挂起；未确认首次未观测到锁等待的根因，不在本 Ticket 中预设根因。

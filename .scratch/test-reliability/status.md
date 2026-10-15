# 测试可靠性与运行路线精简：规划记录

- 需求见 [Spec](spec.md)；用户已整体确认。
- 调查基线：`47a9dc8cee10298504d9daec6be79712a5bf194d`。
- [Design](design.md) 与 [Design Review](design-review.md) 已完成，Review PASS；[七项 Ticket 草案](tickets-draft.md) 已确认，[Readiness Review](ticket-readiness.md) READY；正式 Ticket 已登记在 [issues](issues/)。
- 用户已确认七项 Ticket 拆分，并授权全部本地实施、验证和 Commit；Push / PR 仍未授权。
- 七项正式 Ticket 已登记在 [issues](issues/)；Ticket 01 完成并本地提交后，按依赖继续实施 Ticket 02。
- 下一步：完成数据库并发测试失败退出与清理修复；随后按编号连续推进剩余已授权 Ticket。
- 本机实时阶段以 Git 公共目录 `harness/work-items/test-reliability/status.md` 为准；本文件仅保存规划快照。
- 旧 `full-validation-findings` 工作项及其保留 branch / worktree 不在本目标范围。

# 统一初始化规划状态

ID: unified-bootstrap
Status: in-progress
Stage: 待发布授权
Last updated: 2026-10-02

## 已确认

- 范围 A：集中运行资源装配与完整生命周期、四类显式初始化命令。
- 运行资源在服务启动时装配，失败及关闭时释放；RAG 保留按需加载。
- 直接移除旧命令入口，不保留兼容转发。
- 用户确认需求澄清结果并授权整理 Spec。
- 用户确认完整 Spec；Design Review 的局部补充已落实核对；Ticket Readiness 为 READY。
- 用户确认三项正式拆分及整体实施，已连续完成全部 Tickets。

## 当前产物与下一步

- 完整规划 Spec：`spec.md`，已确认。
- 设计与审查：`design.md`、`design-review.md`；Ticket 草案和 readiness 见对应文件。
- 正式 Tickets 位于 `issues/`，实现与受影响验证完成。
- 全量软件 604 PASS / 15 SKIP / 128 subtests PASS；最后修订后定向回归 240 PASS / 14 subtests PASS；隔离 development profile 19 PASS，CI profile 5 PASS；静态门禁通过。
- 下一步：形成本地候选并报告结果；远端发布须取得独立授权。
- 实时状态见 Git 公共目录 `harness/work-items/unified-bootstrap/status.md`。
- 路线图同步已验证的初始化 / 装配完成事实，不改变优先级或已有 AI Evaluation 待办。

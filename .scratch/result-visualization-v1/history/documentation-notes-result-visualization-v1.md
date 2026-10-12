# 结果解释与可视化：整理前的过程记录

来源：`docs/specs/result-visualization-v1.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# R2：结果解释与可视化

当前 Web 长期状态以 [R3 History Spec](../../../docs/specs/history-results-v1.md) 为准：显式 `/api/v1/histories` 与 `/api/v1/saved-results` 保存私人快照，刷新只读，续聊恢复完整条件；旧 `/api/v1/query` 继续原短期 Contract。本文的 R1 / R2 阶段状态描述保留历史边界，不能用来否定 R3。
用户于2026-10-04确认完整行为及本地实施。R1身份、权限、两模式状态与失败恢复规则继续适用。本Contract对应工作项 `result-visualization-v1`；[规划与确认记录](../spec.md)。

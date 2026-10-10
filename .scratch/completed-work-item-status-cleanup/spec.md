# 已完成工作项状态字段整理

## 目标

修正已完成工作项的 Spec / Design 当前状态字段，避免将已合并的 R3、R4、R7 误读为仍在实施；明确产品 V1 规划记录保留的是历史阶段状态。

## 范围

- 更新 `.scratch/history-results-v1/spec.md`、`.scratch/execution-streaming-v1/design.md`、`.scratch/local-operations-v1/spec.md` 和 `.scratch/local-operations-v1/design.md` 的状态字段，使用已核实的完成与合并事实。
- 将 R3 Spec 的旧分支字段说明为历史分支，避免暗示分支仍存在。
- 在 `.scratch/chatbi-product-v1/spec.md` 说明本文保留历史规划 / 阶段状态，当前路线和交付状态以正式路线图及实时工作记录为准。
- 保留 `.scratch/*/status.md` 历史快照及 Acceptance 中有日期的阶段结论；不改动行为 Contract、产品范围或验收证据。

## Done When

- 当前状态字段与实时工作记录及已合并 PR 事实一致。
- 历史规划和阶段性验收仍可追溯，且不会被误认为当前状态。
- Markdown 链接、Diff 检查、只读 Review 与 Harness 状态检查通过。
- 本地提交仅包含本 Spec 及上述长期记录。

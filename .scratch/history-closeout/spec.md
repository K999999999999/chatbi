# 历史收尾（短 Spec）

Status: confirmed

## 目标与授权

用户于 2026-10-01 确认清理两个旧本地分支、归档独有规划证据、消除历史状态误导并完成本地 Commit。未授权 Push / PR 或远端分支清理。

## 范围

- `codex/admin-password-recovery-cli`：确认 HEAD 为 master 祖先后删除本地分支。
- `feature/codex-harness-feedback-spec`：先保存可恢复的本地 Git bundle，逐字归档独有 Spec / Tickets，再删除本地分支；不恢复旧 AGENTS.md。
- 经营分析旧版本：保留历史原文，补充后续承接说明；依据 Ticket 01 Result 和验收证据纠正 open 状态。
- Harness Ticket 拆分文件：标明历史快照，指向正式 Tickets，补充完成事实。

## 验收与验证

bundle verify 与隔离恢复检查通过，恢复 HEAD 与原分支一致；归档原文与来源提交字节一致。清理前核对 worktree、工作区、HEAD 与依赖。Markdown 链接、Diff 检查和当前上下文 Review 通过。不清理其他分支或仓库，不运行产品测试、AI Evaluation 或 Real E2E。

## Done When

两条旧本地分支已清理，历史证据可恢复，文档修订完成且本地候选已提交。发布与合并后收尾不在本次授权范围内。

## 本地收尾结果

- 基线：`bf7b2de36b0db15b027d36f59fdd4ced9b9a309d`；候选分支：`docs/history-closeout`。
- 已删除本地 `codex/admin-password-recovery-cli`（原 HEAD `08482572a3d610a585ec766df85bdfa4b33ddb3e`，为 master 祖先）和 `feature/codex-harness-feedback-spec`（原 HEAD `05e8fbcb52f96bc85b48ea84b5df9bd769f9c1e8`）。清理前仅一个 worktree、无 open PR；没有其他本地分支依赖后一条独有提交。
- 后一分支的完整历史已写入 Git 公共目录的 `harness/archives/history-closeout/codex-harness-feedback.bundle`。`git bundle verify` PASS；在隔离临时目录 clone 后，HEAD 与原提交相同；4 份归档文档逐字比较 PASS。
- 恢复方式：用 `git rev-parse --path-format=absolute --git-common-dir` 定位公共目录，将上述 bundle 用 `git clone --branch feature/codex-harness-feedback-spec <bundle路径> <独立恢复目录>` 恢复；不覆盖当前工作区。bundle 为本机归档，不纳入 Commit；原 Spec / Tickets 随本次 Commit 长期保留。
- `python3 scripts/check_markdown_links.py` PASS；`git diff --cached --check` PASS；当前上下文 `workflow-code-review` PASS，无发现。曾发现新增链接指向不存在的文件，已改为实际的 Query API Contract 并复验。
- 未运行产品测试、AI Evaluation 或 Real E2E：仅历史文档与本地 Git 分支清理，未改运行时行为或业务 Contract。
- 正式事实源更新不适用：本次只澄清历史状态与归档证据，当前正式 Contract 不变。
- Harness 反馈：历史快照与正式 Ticket 状态不同步，已有共享实时记录 / 历史快照职责规则覆盖；本次落实标注，不另建重复改进项。
- 后续：本地 Commit 后仍需发布授权，经 PR 合入及正常收尾，才能让本次记录进入 master 并删除收尾候选分支。

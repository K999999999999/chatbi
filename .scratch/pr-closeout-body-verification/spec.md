# PR 正文复盘字段远端核对（短 Spec）

## 目标
避免本机工作记录已完成 Harness 复盘、远端 PR 正文却仍保留模板或旧字段的情况。

## 预期行为与范围
- 新 PR 合并复盘时，更新本机实时记录和 PR 正文中的 `Harness review`、`Harness evidence`、`Harness follow-up work item`。
- 完成复盘前，使用目标仓库与 PR 身份明确的 `gh pr view --json body` 读回 GitHub 当前保存的完整正文；逐项确认字段存在、值与本机实时记录一致且没有模板占位内容。
- 任一字段缺失、值不一致、模板残留或无法读回时，不能报告复盘完成；修正后重新读回核对。
- 检查器继续只读本机状态，不增加远端访问；不批量补写历史 PR；不改变发布授权规则。

## 验收与验证
- 文档明确规定远端正文完整读回、字段一致性和模板残留检查，以及失败时不得完成的处理。
- Markdown 本地链接与 `git diff --check` 通过；Code Review PASS。
- 不需要产品测试、Evaluation 或新增自动化。

## 授权
用户于 2026-10-11 明确确认按该流程改进执行；授权本地 Spec / Harness 文档更新、Review 和本地 Commit，不包含 Push / PR 发布。

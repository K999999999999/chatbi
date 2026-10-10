# R6 发布前质量检查覆盖

## 目标

让本地发布前的 Python 格式与 lint 检查覆盖 CI 中相同的代码目录和固定 Ruff 版本，避免将局部检查误报为全量质量检查通过。

## 范围

- 增加唯一的 Python 格式 / lint 检查脚本，固定使用 CI 当前的 Python 与 Ruff 版本，并覆盖 `src`、`evaluation`、`tests`。
- GitHub Actions 的 Code quality job 调用同一脚本，本地可直接运行同一命令。
- 更新 Runbook 与 PR candidate 流程，说明该命令的覆盖范围，局部检查需明确标为 targeted，不能代替全量门禁。
- 不变更其他 CI job、测试范围、Ruff 规则、产品代码或 R6 行为。

## 验收条件

- 本地脚本成功时，全量格式和 lint 命令与 CI 实际执行保持相同。
- CI Code quality job 调用该脚本，不重复维护另一份命令。
- 临时加入 `tests/` 下格式错误的 Python 文件时，该脚本非零退出并指出该文件；移除临时文件后完整检查通过。
- 文档准确区分局部检查与全量检查。

## 验证方式

- 在干净基线分支验证正常脚本通过。
- 使用仅在验证过程中创建并删除的临时格式错误文件，验证覆盖检测失败路径。
- 检查 CI YAML、Markdown 链接、`git diff --check`，并 Review 最终 Diff。

## 授权

用户于 2026-10-11 明确要求按顺序处理此前列出的两个独立 Harness 改进；本 Spec 只覆盖第一项 R6 发布前质量检查覆盖。仅本地实施和 Commit，不包含 Push 或创建 PR。

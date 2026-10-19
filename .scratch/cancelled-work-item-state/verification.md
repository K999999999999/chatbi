# 验证与 Review

日期：2026-10-19。已 Review 并提交的本地候选：ChatBI `5f4dd55`（基线 `99e5c73`），Plugin `67cfb13`（基线 `140f2ef`）。

## Review

结果：PASS，无未解决发现。Review 覆盖了工作项与 Ticket 状态枚举隔离、取消元数据校验、迁移 / PR / 当前 SHA 门禁、取消后写入拒绝、关闭收尾语义，以及 ChatBI 容器适配器仅挂载目标工作项目录可写。

## 验证

- Plugin：`uv run --no-project --python 3.11 python -m unittest discover -s tests -v`，57/57 通过。
- ChatBI：`uv run --no-project --python 3.11 --with pytest pytest tests/scripts/test_harness_adapter.py tests/scripts/test_check_harness_state.py -q`，48/48 通过。
- ChatBI 文档链接与结构：`uv run --python 3.11 --locked python -m scripts.check_documentation`，通过。
- `git diff --check`，两仓通过。
- 通过 `./dev harness control --plugin-source /home/jojo/Projects/agent-plugins-cancelled-work-items` 逐项读回、迁移并取消目标工作项；两项均为 `cancelled`，原 Stage 保持，`Next: None`，`legacy_read_only: false`，Plugin 报告取消工作项无需交付收尾。两份迁移前 `.bak` 备份存在。
- 最终 `python3 -m scripts.check_harness_state --json`：无 ERROR；唯一 REVIEW 是本工作项 `cancelled-work-item-state` 正等待发布授权。没有推送、创建 PR 或安装 / 同步 Plugin。

## 文档与路线图

更新位置：`docs/agents/issue-tracker.md`、`docs/runbook.md`、Plugin README 与 Harness integration reference。`docs/roadmap.md` 不更新：本次没有调整产品目标、依赖、验收方式或优先级；工作流 Contract 变更保存在本 Spec。

指定关闭的记录：

- `harness-candidate-preflight`：`Spec 待确认` → `cancelled`；迁移前摘要 `e675f54e9b27097c6e6eb864d4db830eb45ef3f5d90f65bc190e7b60c8744251`。
- `long-task-progress-clarity`：`需求发现` → `cancelled`；迁移前摘要 `46d675bf24b98f5b072030a427abef1dcc259ecff39907486dfcf4263b6a8fa1`。

## 发布准备补充

2026-10-19，用户确认 Plugin 当前记录的 Skill 来源与改写范围可公开分发，并保留 `engineering-workflow` manifest 的 `Local Workflow Maintainer` / `Proprietary` 元数据。Plugin 提交 `7773325` 仅更新 `PROVENANCE.md` 记录此决定，不改运行行为；既有 57/57 Plugin 测试仍对应代码提交 `67cfb13`，未因纯文档更新重跑。该确认不构成 Push 或创建 PR 的授权。

# 本地验收与 Review

基线：`3f24bbf2ac90da6d568053553bff67d916cfb6d0`。范围为同提交的检查脚本、确定性测试、Harness 入口 / 文档及 R3 历史补记；最终候选 SHA 和提交后 clean 核实保存在本工作项的 Git 公共目录实时记录。软件证据不构成产品 Evaluation 或生产验收。

## 验证结果

- TDD Red：两项核心行为测试在占位入口上失败，实际为预期退出 1、实际退出 0（汇总 active 指向 done；工作项 done / Ticket in-progress）；不是导入或环境故障。
- Green / 相关回归：`uv run --python 3.11 --locked --with pytest python -m pytest -q tests/scripts tests/architecture`，**73 passed**，包含本工具 20 个确定性案例。临时真实 Git 仓库覆盖 linked worktree、Squash 不可达、历史 / fenced 示例、缺少本机记录、非法字段、引用缺失 / 多值、Ticket 路径 / symlink 越界、只读性、文本 / JSON 和 Git 失败。
- `uv run --locked --with ruff ruff check --select E4,E7,E9,F scripts/check_harness_state.py tests/scripts/test_check_harness_state.py`：PASS；同范围 Ruff format 完成。
- `uv run --locked python -m scripts.check_markdown_links`：PASS。
- `uv run --locked python -m scripts.check_module_boundaries`：PASS。
- `git diff --check`：PASS。
- 真实本机检查：18 份当前记录；在旧汇总 / Ticket 增加显式关联后，实际检出 `ACTIVE_COMPLETED`、`TICKET_NOT_DONE` 两项 ERROR；补账后 **0 ERROR**。记录与 Git 引用未由检查工具修改。
- PR54 只读核验：MERGED、head `6512091`、merge `2019443`、8 项 required checks SUCCESS；`9f24a85..6512091` 只有 history.py 安全扫描注释 / 边界说明差异。原 R3 浏览器报告与 Evaluation summary 文件仍存在；旧报告保持原身份，不重标为当前通过。
- 首次尝试系统 `python3 -m pytest` 因未安装 pytest 未执行；改用仓库锁定 uv / Python 入口后完成上述验证。

## REVIEW 处置

| 发现 | 处置 |
| --- | --- |
| 产品 V1 in-progress | 总体目标未完成，R6 / R7 待细化；active 指向本修复，功能证据引用子记录 |
| 本修复 in-progress | 本地候选就绪后等独立发布授权；没有远端 PR，不标整个目标 done |
| R3 文档收尾 in-progress | 明确由本修复接手；短 Spec 原文已归档，旧路线图内容被后续交付替代，待替代交付后关闭 |
| docs/r3-delivery-closeout 有不可达提交 | 已核实 d93e7a7 为未发布旧文档候选；保留至替代 PR 合并及归档核实，不直接发布或删除 |
| 当前工作区修改（提交前） | 全部属于本修复；提交后需再次核实 clean，最终结果记录于本机实时状态 |

## 事实源核对与 Review

当前上下文 `engineering-workflow:workflow-code-review`：**PASS**。已逐项读取脚本、测试、文档 Diff、短 Spec、旧候选归档及关联状态。读写边界明确；Git 可选写锁关闭；无网络、自动发布、自动删除和授权继承；显式关联检查避免靠自然语言 / 日期猜测状态。正常 / 失败证据对应公开 CLI；测试使用临时真实 Git，不修改用户仓库。新 clone / linked worktree / Squash 的限制已写明。当前字段冲突已消除，旧细节按历史保存，未将历史成绩改称新候选成绩。

正式事实源更新：AGENTS、Harness 说明、Issue Tracker、Git / PR 流程适用并已更新。业务 Spec、Design、Runbook、日期化 Acceptance 不适用：产品行为与运行入口不变。已复核 Roadmap R1–R5 完成、R6→R7 及作品交付顺序；本修复不改变产品目标、依赖或完成事实，路线图无需改动。R3 历史 Ticket 与状态补记不重新建立产品验收候选。

未运行全量产品软件测试、AI Evaluation、浏览器与数据库验收：改动仅工具 / 文档，无产品运行代码、依赖或 Contract 变化。托管 CI 尚未运行，未发布。

Harness 反馈：本目标已处理同类重复的状态 / 交付漏检；沉淀于本机只读入口、关联字段及恢复 / 收尾检查。不增加无证据的 Plugin 或架构改动。Remaining：独立发布、替代交付后旧 R3 分支处置与记录关闭。

# R3 验收入口与候选身份

此文件定义可复现门禁、候选身份与证据边界；最终候选及真实验收 / Evaluation 的状态和报告身份记录在 Git 公共目录的本机实时工作状态中。本文不预填 PASS，也不代表已发布或合并。

基线为 `afad5ac18452566199bfcfdcceb1585115576a77`，工作项 `history-results-v1`，branch `feat/history-results-v1`。已确认 Contract 见 [Spec](../specs/history-results-v1.md)，实现见 [Design](../designs/history-results-v1.md) 与 [恢复语义](../designs/history-query-restoration.md)。后续报告必须核对自己的 commit 与资源身份，不继承基线或 R1 / R2 的通过身份。

## 确定性验证

- 全量：`uv run --python 3.11 --locked python -m pytest -q`。
- 真实隔离 PG：`uv run --python 3.11 --locked python scripts/run_database_tests.py --profile development`。包含历史事务、owner 隔离、幂等、stale、保存失败回滚、重启 fencing、独立副本、列表游标、升级与重复迁移、基线 Schema verifier 保留数据回滚兼容。软件替身不代替该证据。
- 网页：`cd frontend` 后 `npm ci`、`npm run build`、`npm test`。Chrome 路径可通过 `CHATBI_CHROME_PATH` 指定，环境依赖需事先就绪。确定性浏览器用实际 HTTP / Cookie 身份和下游替身，覆盖 URL 快照、断连、权限、模式隔离、R2 展示及成果管理。
- `uv lock --check`、模块依赖检查、Markdown 链接检查与 `git diff --check`；人工 Code Review 记录于 `.scratch/history-results-v1/code-review.md`。

## 真实链路与报告

固定所有代码和文档的 clean commit 后，运行 `scripts/verify_container_dev.sh real`。实际 Compose / Vite / Chrome /模型 / RAG /业务只读库与独立 SQL 参考核对单值、月份多指标、分类、Top-N、续聊、刷新、重登录、成果副本、独立删除、重查和 API 停止重启后的继续查询。完成分析检查点过期后仍读取已提交报告；未完成分析的 TTL / 同一 run 恢复另由 PG 与 Application 验证。热更新实验单独标记 `experiment_dirty=true`，恢复源码后检查 clean；不得把实验改动当成最终代码。

报告输出到 ignored `reports/browser-real/`，包含候选 SHA、`git_dirty`、Chrome、独立参考、RAG / 模型身份、步骤和账号清理；临时账号禁用、Session 撤销，原用户、开发卷、业务数据与 RAG 保留。失败保留原报告，修复后形成新候选。`CHATBI_CONTAINER_ALLOW_DIRTY=1` 仅用于开发诊断，不能充当正式验收。

三套正式 Evaluation 及三次完整多轮诊断按 [Runbook §9.2](../runbook.md#92-正式三套基线与稳定性诊断) 执行，统一身份入口要求正式报告同一最终 clean HEAD、RAG 版本和 `0 FAIL / 0 INVALID_CASE`。三套旧入口回归不替代 R3 history profile 的真实验收。

最终报告不通过修改本文件来回填新的 commit。Git 公共目录的 `harness/work-items/history-results-v1/status.md` 记录最终候选、报告目录、成绩与剩余事项；可用 `git rev-parse --path-format=absolute --git-common-dir` 定位。日期化原报告保持自己的身份，关联规划记录同步主工作项。此文件是新 clone 可用的验收入口，本机 ignored 报告不保证随 clone 存在。

## 事实源维护

R3 Spec / Design、Query API 的显式命名空间、Web 的刷新边界、共享 query bindings、Product Scope、Architecture、Runbook、README 和 Roadmap 同步维护。原 R1 / R2 Acceptance 保持历史身份。业务指标、领域名词、Sales Mart DDL 与 Evaluation 案例集未扩大；既有事实源无需重写业务含义。R4 执行状态与流式反馈由独立的 [R4 Spec](../specs/execution-streaming-v1.md)、[Design](../designs/execution-streaming-v1.md) 和 [Acceptance](execution-streaming-v1.md) 定义；R5 / R6 / R7 仍待实施。本地候选不自动授权 Push / PR。

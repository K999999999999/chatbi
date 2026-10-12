# Ticket 04 实现 Review

Review: PASS
Scope: BASE `6a50b84`，Ticket 04 改动文件；遵守已确认的文档维护 Spec、设计和 `04-documentation-gates.md`。
Change Description: What：增加文档链接与结构组合门禁、共享 Markdown 行解析、Agent 文档维护规范和 PR Review 记录。Why：让当前文档规范有唯一入口，并由本地 / CI 执行一致的确定性检查。Risk：围栏解析调整可能影响旧锚点与链接解析；通过既有测试、围栏边界回归和临时 Git fixture 核对。Verification：见下方实际结果。

## 结果

- 保留 `scripts.check_markdown_links` 原命令及 `--root`；新增 `scripts.check_documentation`，组合链接检查与正式文档结构检查。
- 标题跳级覆盖 ATX / Setext，错误定位到文件及行；正文章节符号引用忽略行内代码和围栏示例。历史 `.scratch/` 不受结构规则约束，仍受全仓链接检查。
- 临时 Git fixture 覆盖已跟踪、未跟踪、ignored 文件、文档作用域、有效/违规文档、代码示例、缺少 Git、读取失败、CLI 退出码与旧入口 `--root`。
- 旧 `agent-harness.md` 完整原文已在 `.scratch/current-documentation/history/documentation--agent-harness.md` 保留；通过与规划基线文件逐字节比较。当前规则归入 AGENTS、Tracker、Git/PR 与新文档维护规范，所有受影响导航和历史引用已更新。
- 修复迁移后仍指向已移除 `docs/acceptance/` 的当前说明；日期化验收继续链接至所属 `.scratch/` 历史。
- CI `Deterministic tests` job 名称保持不变，检查步骤使用同一组合入口；没有验证或修改远端 required checks 配置。

## 验证

- Red：新增行为测试在空实现阶段失败；Green：定向测试通过。
- `CHATBI_WEB_ORIGIN=https://example.invalid uv run --python 3.11 --locked python -m pytest -q tests/scripts/test_check_markdown_links.py tests/scripts/test_check_documentation.py`：17 passed。
- `uv run --python 3.11 --locked python -m scripts.check_documentation`：通过。
- `uv run --python 3.11 --locked python -m scripts.check_module_boundaries`：通过。
- `bash scripts/check_python_quality.sh`：通过。
- 固定 Ruff 0.16.8 对受影响脚本和测试的 format / `E4,E7,E9,F` 检查：通过。
- `git diff --check`：通过。
- 真实 LLM Evaluation、PostgreSQL integration、Business Acceptance、生产就绪未在本 Ticket 验证；本次变更不触及产品行为或这些验收范围。

## Findings

无。确定性门禁只检查标题层级、章节引用和本地 Markdown 链接；业务含义、事实是否过期与跨文档语义一致性仍由 Review 按正式事实源核对。

Next: Ticket 04 已本地提交并在 PR #77 中交付；CI 跟进见下节。

## PR #77 CI 跟进

- 初次托管 CI 的 `Deterministic tests` 在文档链接检查步骤失败：`.scratch/project-navigation/history/documentation-docs--project-guide.md` 仍链接到已移除的 `docs/acceptance/`。本机残留空目录导致此前本地文件系统检查没有复现。
- 已修正该历史导航，指向当前 Runbook 测试说明；搜索确认没有其他指向该目录的 Markdown 链接。
- 在由已提交 Git 文件组成、没有本机 ignored 文件的临时 clone 中运行组合文档检查，以复现 CI checkout 条件；后续 CI 对新 head 重跑。
- 已启用仓库 active ruleset 的 8 个 required status checks；PR automation 将在检查通过后按 squash 方式自动合并。

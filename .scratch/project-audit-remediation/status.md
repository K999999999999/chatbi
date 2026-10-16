# 审计修复规划状态

Status: in-progress
Stage: 实施中

目标：修复2026-10-16全仓审计的22项问题，并完成软件回归、真实LLM评测与隔离容器业务验收。AUD014不属于缺陷。

用户已确认修复需求方向、真实模型调用验收范围、完整[Spec](spec.md)、12项拆分及整体本地实施/验证/Review/Commit授权。[设计审查](design-review.md)为PASS WITH MINOR FIXES，修订已落实并逐项核对；[Readiness](ticket-readiness.md)为READY；12项正式Ticket已写入[issues](issues/)。Ticket 01 已本地Commit（`e68009d`），Ticket 02 已本地Commit（`606c626`），Ticket 03 已本地Commit（`7a46415`）；三个切片均通过各自确定性验证与Review；远端发布未授权。

当前行为依据是[已确认Spec](spec.md)，缺陷来源为[原审计报告](../../docs/audits/project-audit-20261016.md)。当前阶段、授权和下一步以Git公共目录中的`project-audit-remediation`实时记录为准。

Ticket 03验证：候选 `7a46415` 上 `./dev test database` 为CI 5 passed、isolated development PostgreSQL 59 passed（run `20261016T181403Z-7a46415-test-database-3cf13e780edf`）；`./dev check python` 307 files already formatted / all checks passed（run `20261016T181403Z-7a46415-check-python-1e64d0a951bf`）；`./dev check docs` PASS（run `20261016T181403Z-7a46415-check-docs-b7775d9ab860`）。

Ticket 04已完成并Commit `0b3755c`。候选上 `./dev test web` 71 passed（run `20261016T183628Z-0b3755c-test-web-c2ae9ae720f9`）、`./dev test renderer` 2 passed（run `20261016T183817Z-0b3755c-test-renderer-759f41e475fb`）、`./dev check python` 307 files / all checks passed（run `20261016T183835Z-0b3755c-check-python-4a1b2cdf5d09`）、`./dev check docs` PASS（run `20261016T183853Z-0b3755c-check-docs-1d8d592af71c`）；候选报告 provenance 均 stable；Review PASS。Ticket 04未运行全项目数据库回归、真实LLM评测或隔离Compose业务验收，这些由后续Ticket处理。

Ticket 05已完成并Commit `51d8f48`。定向 `./dev test web frontend/tests/history.spec.ts` 12 passed（run `20261016T185132Z-6f69b47-test-web-47706fa566bb`）；完整 `./dev test web` 79 passed（run `20261016T185258Z-51d8f48-test-web-cad932127fe9`）；候选报告 provenance stable，Review PASS。完整回归包含问数/分析历史、保存成果重查、原操作ID复用、迟到受理的同一执行观察、确定拒绝后的显式新操作、401/403和账号生命周期清理。

Ticket 06已完成并Commit `066e2b2`。候选定向 Python 32 passed、0 skipped（run `20261016T190428Z-066e2b2-test-python-fdc989378278`）；完整 Python 测试 1052 passed、57 条件性 skipped、0 failed（run `20261016T190445Z-066e2b2-test-python-1e82a5932aae`，因 skip 报告状态为 `incomplete`）；`./dev check python` 307 files / all checks passed（run `20261016T190456Z-066e2b2-check-python-709e21ef4410`）；`./dev check docs` PASS（run `20261016T190456Z-066e2b2-check-docs-f40baad43b90`）。各报告 provenance stable，Diff 检查与Review PASS。未在此Ticket加载真实模型，按计划留给后续隔离评测验证。

Ticket 07已完成并Commit `1b40dbf`。候选完整 Python 为1071 passed、58条件性 skipped、155 subtests、0 failed（run `20261016T192654Z-1b40dbf-test-python-d9a0546fce35`；报告因 skip 为incomplete）；数据库CI 5 passed、development PostgreSQL 60 passed、cleanup passed（run `20261016T192900Z-1b40dbf-test-database-3a81bee9c622`）；Python质量307文件、文档检查、Diff及Review均PASS（runs `20261016T193023Z-1b40dbf-check-python-04d97d1246ca`、`20261016T193040Z-1b40dbf-check-docs-083cac6a646b`）。报告provenance均stable。实现递归审计details校验、持久化前安全快照及历史公开 DTO 嵌套校验；覆盖合法旧分类、metadata缺省、Query SQL文本、重开/另存/导出和真实隔离PostgreSQL，未扫描或改写日常数据库。

Ticket 08已完成并Commit `cb434d9`。候选完整 Python 为1081 passed、58条件性 skipped、0 failed（run `20261016T194109Z-cb434d9-test-python-24425a44e317`；报告因 skip 为incomplete）；Python质量307文件、文档检查及Diff均PASS（runs `20261016T194313Z-cb434d9-check-python-a4783cdba32c`、`20261016T194330Z-cb434d9-check-docs-d5c2762751d7`），报告provenance stable，Review PASS。Linux配置读取及Compose调用前执行文件属主/模式检查，涵盖开发、容器验证、Qdrant、metadata导出及数据库测试入口；本机 `.env` 元数据为当前用户所有、mode 600，未读取或改动内容。未运行隔离容器业务验收和真实LLM评测，留待后续Ticket。

Ticket 08完成时下一步为Ticket 09首个管理员事务并发互斥，现已完成；远端发布未授权。

Ticket 09已完成并Commit `2eb1aa3`。候选完整Python为1081 passed、61条件性 skipped、155 subtests、0 failed（run `20261016T195538Z-2eb1aa3-test-python-7ecbbc7cd978`；报告因skip为incomplete）；隔离数据库CI 5 passed、development PostgreSQL 63 passed、cleanup passed（run `20261016T195743Z-2eb1aa3-test-database-fe96c3eb91b1`）；Python质量307文件与Bootstrap文档链接检查PASS（runs `20261016T195911Z-2eb1aa3-check-python-4d39efe7f3f2`、`20261016T195931Z-2eb1aa3-check-docs-0db4dc376256`）。报告provenance stable，Review与Diff检查PASS。真实PG并发覆盖预置角色及首次seed、受控拒绝、回滚释放锁；无Schema变化。真实LLM评测与隔离容器业务验收尚未运行。

Ticket 09完成时下一步为Ticket 10真实评测入口与基线验证，现已完成；远端发布未授权。

Ticket 10已完成并Commit `7ff3399`。候选完整Python为1085 passed、61条件性 skipped、155 subtests、0 failed（run `20261016T201322Z-7ff3399-test-python-420a3a5ddba3`；报告因skip为incomplete）；隔离数据库CI 5 passed、development 63 passed、cleanup passed（run `20261016T201525Z-7ff3399-test-database-65fddca4ba3e`）；Web 81 passed（run `20261016T201647Z-7ff3399-test-web-7cc036188bb0`）；旧兼容PostgreSQL development profile 56 passed；Python质量307文件及Runbook文档链接检查PASS（runs `20261016T201837Z-7ff3399-check-python-6bc5fb280aa1`、`20261016T201853Z-7ff3399-check-docs-6542290a7060`）。报告provenance stable，Review与Diff检查PASS。真实 GitHub runner、Windows 和模型/LLM执行未在本机运行；正式评测由T12 clean candidate完成。

Ticket 11已完成并Commit `0c4be10`。隔离热更新限定到临时单文件副本并核对恢复Hash；验收账号身份在事务提交前持久化，失败清理按精确ID+用户名执行；isolated模型准备显式先于build-rag且RAG输出隔离。staged候选定向Python 52 passed、Web 81 passed、Python质量309 files、Docs、Diff与Review均PASS，报告provenance stable（runs `20261016T203505Z-c2a3d92-test-python-465ba47ff3b6`、`20261016T203533Z-c2a3d92-test-web-8c18f3093293`、`20261016T203505Z-c2a3d92-check-python-d4e9002dd543`、`20261016T203505Z-c2a3d92-check-docs-2f6fb0a1eca9`）。INT/TERM、恢复失败和账号提交前后故障注入通过。完整isolated Compose验收与三套真实LLM评测仍由最终Ticket执行，不将其预先标为通过。

下一步：实施Ticket 12文档状态修正并完成最终候选验收；远端发布未授权。

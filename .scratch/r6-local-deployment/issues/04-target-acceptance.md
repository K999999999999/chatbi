# Ticket 04：目标环境完整验收与交付证据

Status: open
Owner: 当前主Agent
Blocked by: 03
Result: 未开始
Comments: 本地实施授权于2026-10-07取得；发布授权未取得。


Change Profile: 本轮验收+持续维护文档入口 / 中 / 证据身份与清理影响风险 / 软件回归+真实浏览器+运行验收 / 本地Commit。
Owner: 当前主Agent；后续验收脚本与Runbook维护者。
Blocked by: Ticket 03。
What to build: 可重复隔离验收入口、完整业务与失败场景证据、目标机重启验收计划、正式Acceptance与文档状态收尾。前述Tickets的测试不推迟到本项。
Owned files: scripts/verify_local_deployment*、受影响tests、docs/specs/local-deployment-v1.md、docs/designs/local-deployment-v1.md、docs/acceptance/local-deployment-v1.md、docs/runbook.md、docs/product-scope.md、docs/roadmap.md及本目标scratch记录。
Acceptance Criteria:
- 同一最终clean候选完成空环境安装与Windows浏览器登录/问数/追问/经营分析/历史/保存成果/XLSX PNG PDF下载并独立检查内容。
- 停止/重启/手动恢复后账号、历史和成果可用，Seed不重播；电脑或Docker重启验证安排维护窗口，不擅自重启共享服务。
- 真实升级回滚与不兼容拒绝、配置/端口/索引/启动失败、资源隔离/安全日志均有证据；清理仅限身份已确认验收资源。
- 记录候选commit、dirty状态、镜像与模型/Seed/RAG身份，历史R1–R5报告保持原身份。根据最终Diff说明AI Evaluation复用适用性或重跑受影响正式套件。
Evidence: 最终受影响软件回归、容器集成、真实模型Windows浏览器/Business Acceptance、目标机运行证据及资源清理核对；报告绑定最终候选，无结果预填。
Migration / Rollback: 只在专用验收资源构造失败状态，不写开发数据；稳定环境重启需维护窗口。已有长期记录保留，验收结束只清理临时项目。
Done When: 正式Contract/Design/Runbook/Acceptance/产品范围/路线图全部一致，最终Code Review与Diff检查完成，未运行项与限制明确；产品/R6实时状态同步，无远端发布。发布另需明确授权。

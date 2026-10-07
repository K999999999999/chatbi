# R3 交付状态与历史规划快照

当前功能交付事实（2026-10-07 历史补记）：六项 Ticket 已完成；最终行为候选 `9f24a85` 的真实浏览器、三套正式 Evaluation 与三次多轮诊断通过。最终 head `6512091` 仅增加安全扫描注释；PR #54 已合并为 `2019443`，8 项必需 CI 通过，分支清理与复盘完成。证据身份见 [Ticket 06](issues/06-runtime-acceptance.md)，不改标为本次文档提交成绩。实时状态以 Git 公共目录记录为准。产品 R4 / R5 已交付，下一项 R6 待需求与技术澄清，见 docs/roadmap.md。本次文档补记由 harness-delivery-consistency 承接，本地整理尚未发布。

## 历史快照：Candidate A 后、Candidate B 验收前

以下正文保留当时计划和授权状态，不代表当前未完成或未获 R3 发布授权。

工作项：`history-results-v1`。基线 `afad5ac18452566199bfcfdcceb1585115576a77`，branch `feat/history-results-v1`；本仓库唯一 worktree。当前全部代码、Contract、验收入口和路线图改动均属于 R3。

[完整 Spec](spec.md)、恢复语义、[实施设计](design.md)、[最终 Design Review](design-review-final.md) 和 [六项 Ticket Readiness](ticket-readiness.md) 均已确认；用户已授权连续实施全部六项、适用真实验收、Review 和本地 Commit。Push / PR 未获授权。

六项实现已接入。最近全量确定性证据：Python **685 passed, 29 skipped, 139 subtests passed**；隔离 PostgreSQL **33 passed**；桌面浏览器 **36 passed**；前端 TypeScript / production build、Ruff、锁文件、模块边界、Markdown 本地链接、compileall 和 diff whitespace 检查通过。Vite 提示 ECharts chunk 大于 500 kB，构建成功。

记录时点：Candidate A `d6041af45bf4f69bb7b60053e0a404d754dc23fc` 已本地提交且工作区 clean。Code Review PASS；Python 685 passed / 29 skipped / 139 subtests、隔离 PostgreSQL 33 passed、桌面 Playwright 36 passed，构建 / 类型 / 静态 / 文档检查通过。

Candidate A 的 Compose R3 真实闭环、三套正式 AI Evaluation、统一身份验收和三次多轮诊断全部通过，报告及当前运行身份以 Git 公共目录实时状态为准。六项 Ticket Result 与 Roadmap 已准备同步；此 tracked 同步产生 Candidate B，Candidate A 报告不得冒称 Candidate B 成绩。

本记录保留 Candidate A 后、Candidate B 验收前的计划快照。下一步按 Ticket 06 对同步后的最终 clean Candidate B 重跑 Compose R3 真实闭环、三套正式 Evaluation、统一身份验收和三次诊断，然后把结果原子写入 Git 公共目录实时状态；不 Push / 不创建 PR。

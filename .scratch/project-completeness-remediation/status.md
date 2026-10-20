# 项目完整性修复状态

Status: complete
Stage: 本地交付完成

目标是修复全仓检查发现的 API 旧挂载、过期 RAG 资产、doctor 探针误报和完成状态文档不一致四项问题。用户于 2026-10-20 授权完整修复、真实 AI Evaluation、隔离业务验收和本地 Commit；未授权 Push / PR。

实现候选：`1b94c1a3ac1c1a909a17bbf45f5c7b3a5a3a1a7d`，基于 `b330e75d69849c8ffe6a2014a1a415549cbd5b67`。修复提交 `fix(dev): 修复完整性检查发现的问题`；实现 Diff Review PASS，提交后工作区干净。

## 修复结果

- 当前 `chatbi-engine` API/Web 容器已挂载到此仓库；PostgreSQL 原数据卷保留，API / Web 健康。
- RAG 资产 `20261020T051257Z-4b95ed4fcf00` 按当前已确认语义与结构重建并发布：7 tables、69 columns、7 metrics、9 relationships、0 failures；readiness ready。
- `doctor` Web 探针通过内部网络连接并使用 Vite 接受的 HTTP Host；maintenance 模型挂载匹配发布 manifest 的宿主模型路径。覆盖错误 Host 和路径身份的回归测试已通过。
- Roadmap、审计修复 Spec 与 Ticket 12 的状态和 PR #88 合并事实已对齐，保留原历史证据。

## 验收证据

- `./dev check`：报告 `20261020T052549Z-1b94c1a-check-all-e26bf3b58434`，通过。
- `./dev test all`：报告 `20261020T052612Z-1b94c1a-test-all-e6cc4d24d329`，1274/1274 passed、0 failed、0 skipped，cleanup passed；起止均绑定该 clean SHA，provenance stable。
- `./dev doctor dev`：control database、business database、Qdrant、assets、Qdrant health、API health / ready、Web、model 全部 ready；LLM 为 not probed。
- 三套 AI Evaluation 均使用模型 `deepseek-flash`、RAG `20261020T051257Z-4b95ed4fcf00`，绑定上述 clean SHA，provenance stable，并经官方 validator 校验：
  - Single-turn：`20261020T053104Z-1b94c1a-single-turn-cb993324fd7a`，29/29 passed，Execution / Expected Outcome / Case Accuracy 均 100%。
  - Multi-turn：`20261020T053858Z-1b94c1a-multi-turn-bd532deaf49a`，7/7 对话、15/15 轮 passed；Conversation / Execution / Expected Outcome Accuracy 均 100%。
  - Business analysis：`20261020T054204Z-1b94c1a-business-analysis-4ae37d707871`，10/10 passed，端到端准确率 100%。
- 隔离业务验收：`20261020T054545Z-1b94c1a-business-acceptance-container-dev-dad1a54cdc37`，3/3 passed、0 skipped，provenance stable，business acceptance 与 cleanup 均 passed。网页登录问数、追问、API 重启后续聊 / 显式重查、身份与状态隔离、XLSX / PNG / PDF 下载核验均通过；测试账号已禁用、活跃 Session 为 0，热更新源码恢复，临时 worker、Compose 容器 / 网络 / 卷均清理。
- AI 报告与浏览器验收原始 JSON / 产物位于被 Git 忽略的 `reports/evaluation/`、`reports/browser-real/` 和 `reports/browser-real-artifacts/`，保留完整 provenance 与资产 / 案例 / 模型身份。

本机 API 的外部 OTLP Trace 收件未作远端查询，因此收件状态仍未确认；这不影响本次业务与软件验收结果。没有执行 Push、PR 或远端操作。

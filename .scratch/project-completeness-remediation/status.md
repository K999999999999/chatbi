# 项目完整性修复状态

Status: in-progress
Stage: PR CI 跟进

目标是修复全仓检查发现的 API 旧挂载、过期 RAG 资产、doctor 探针误报和完成状态文档不一致四项问题，并解决 PR 必需依赖审计发现的 aiohttp 安全公告。用户于 2026-10-20 授权完整修复、真实 AI Evaluation、隔离业务验收、本地 Commit、发布 PR 与同目标 CI / Auto-merge 跟进；用户随后确认将 aiohttp 从 3.14.3 更新为 3.14.4 并纳入当前 PR。因 3.14.4 的依赖元数据要求 yarl >=1.25.1，锁文件仅同步这一必要传递依赖。

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

本机 API 的外部 OTLP Trace 收件未作远端查询，因此收件状态仍未确认；这不影响已完成的本地业务与软件验收。PR #96 已发布至 `master`，原候选 head `64af44a972b851f13b3225a8a00ef90e5abdae72`；原 GitHub 必需 CI 7/8 通过，Dependency audit 因 `aiohttp 3.14.3` 的 CVE-2026-111064、CVE-2026-111063 与 GHSA-2g87-pp6c-29x5 失败。用户确认按审计建议更新；当前 `uv.lock` 锁定 `aiohttp 3.14.4` 与其所需 `yarl 1.25.1`，依赖范围未变。验证：`uv lock --check` PASS；`uv run --python 3.11 --locked --with pip-audit pip-audit` PASS（未发现已知漏洞；`torch 2.14.1+cpu` 因 PyPI 无匹配发行包而跳过审计）；开发镜像按锁重建通过；`./dev check` 报告 `20261020T100848Z-64af44a-check-all-e0cf0ebf74f8` PASS；`./dev test all` 报告 `20261020T100917Z-64af44a-test-all-4ee56648401e` 为 1274/1274、0 skip、provenance stable、cleanup passed；`./dev check docs` 报告 `20261020T101414Z-64af44a-check-docs-40dc77e8809d` PASS。前一次使用旧本地镜像的 `./dev check` 因 `/opt/venv` 不可写失败；按 Runbook 重建镜像后全量检查通过。依赖修复已完成最终 Diff Review 和本地 Commit；待更新 PR #96 并确认新 GitHub CI。Squash Auto-merge 已启用，Agent 不人工 Merge。

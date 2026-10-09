# Ticket 07 — 服务明确拒绝的网页处理修复 Review

Review: PASS
Scope: baseline `59e1e34`；`frontend/src/Chat.tsx`、`frontend/tests/operations.spec.ts` 及当前 Ticket/Acceptance/Roadmap 事实更新。

Change Description: HTTP 503 / SERVICE_NOT_READY 由受理前就绪门禁明确拒绝，网页直接显示安全原因并保留上次成功上下文；问数、分析和重新查询不再将其转为受理未知。其他 5xx 与断连仍沿原幂等回查，不自动重发。手动重试已有未知请求时保留原未知状态的恢复语义。

Findings: 无未处理 Findings。后端 `_reserve()` 的门禁位于持久 `begin_execution_attempt()` 前；未扩大到 EXECUTION_UNAVAILABLE / HISTORY_STORAGE_UNAVAILABLE 等不能证明未受理的 5xx。没有修改公共 API、权限、状态不变量、Prompt、模型配置或 SQL Guard。

Verification:
- Red：新增追问、经营分析、重新查询三项 Windows Edge 回归均因未显示安全拒绝原因失败；`.local/r7-readiness-red-windows.log`。此前 Linux 尝试缺少 libnspr4、浏览器未启动，不计入 Red 证据。
- Green：Windows Edge 的 operations/auth/query/analysis 受影响回归共 18 passed，21.5 秒；包括三个新拒绝用例与未知503已受理请求恢复、断连明确重试、上下文和隐私边界。`.local/r7-readiness-green-windows.log`。
- `npm run build --prefix frontend`、`npm run typecheck --prefix frontend`、Markdown links、`git diff --check` PASS。
- 真实候选 `59e1e34` 的 Windows Edge 追问本轮成功、经营分析修复验证通过；此运行在本修复之前，不作为本修复的真实候选证据。PDF 客户端下载失败，完整 Ticket 07 未完成。

Review Dimensions: Correctness / Comprehension / Consistency / Testability / Architecture / Security PASS。测试通过用户可见结果、再次提交及公开受理恢复行为验证，不检查私有实现。Diff 不含 Secret 或原始运行报告。

AI Evaluation: 本次只改前端对既有明确拒绝的处理，不触及模型/Prompt/业务算法；复用原候选的适用行为基线，不重标当前候选为新正式 Evaluation 基线。

Harness Feedback: 真实验收重复受本机下载接管影响，而隔离 Windows Chromium 的合成 PDF 对照成功；当前 Ticket 07 拥有最小验收入口和浏览器条件核验，后续在该入口显式记录浏览器身份与下载条件，保留 Edge 日常使用限制。它属于已有 Ticket 的验收可观测性范围，不增加独立 Harness 目标。

Next: 本地提交该修复；继续在不改 IDM 的 Windows 隔离浏览器中补齐 PDF / 历史 / 成果 / 重启验收，再完成容量和运行保障矩阵。真实 stable 切换、密钥初始化和远端发布仍不在本次授权中。

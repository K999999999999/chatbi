# Ticket 02：网页真实阶段、SSE观察与快照重连

ID: execution-streaming-v1/02
Status: complete
Authorization: 用户于 2026-10-05 确认六项拆分及连续完成整个 R4 的本地实施，包含编码、适用测试与真实验收、Review 和本地 Commit；不含远端发布。

Change Profile: 持续维护 /中 /高风险身份与传输 /软件+HTTP浏览器 /本地candidate。
Owner: 当前主Agent。
Blocked by: 01

### What to build / Scope

- 在实际语义理解 /retrieval /生成 /Guard /DB /存储与analysis节点添加可选阶段反馈Port；旧调用默认行为保持，不把阶段从Trace exporter推断。
- 当前执行快照 /计数 /序号、SSE订阅 /心跳 /有界ring与慢订阅重同步，fetch保留X-user-ID /Cookie，版本化DTO /decoder /reducer。
- 网页发送 /恢复 /重查改为受理→GET/SSE观察→读取正式turn；刷新 /关闭 /断连重开原执行，网络重连只GET；当前阶段与实际task count可见。
- 原Session只读鉴权能力与每帧 /心跳检查，新路径来源校验 /CSRF /no-store /Trace，失败关闭观察并清私有内容；不把请求对象交给worker、不续期。

Out of Scope: 报告文字草稿 /流式、用户取消按钮与执行停止策略（03）；真实Provider验收（04）。

Owned files: 01的execution Application /runtime /API与所需history DTO；`src/authorization/auth_service.py`、browser.py /app.py；`src/online_query/contracts.py` /service.py /service_execution.py /`src/authorization/query_entry.py` 的可选Control传递；`src/business_analysis/application.py` /contracts.py /execution.py；`frontend/src/execution.ts` /executionStream.ts /Chat.tsx /api.ts /history.ts /App.tsx /style.css；对应Python、授权、前端纯函数 /浏览器tests；Web /Query API /R4传输事实文档。

### Acceptance criteria / Evidence

1. 实际阶段 /恢复跳步 /真实唯一task计数正确，不模拟百分比 /计数；表格图表只展示正式有效结果，内部Prompt /JSON /分析SQL不泄漏。
2. HTTP /浏览器刷新、断连、重复事件、乱序 /缺口、终态事件丢失、多页与用户切换不会重执行、串任务、状态倒退或复用旧身份。
3. 首snapshot与增量无丢失窗口；ring64帧 /1MiB、每execution8订阅、文字帧16KiB与浏览器6MiB边界有确定性证据；慢读恢复snapshot，无无界队列或worker阻塞。
4. read鉴权不改变Session的idle /absolute期限；401/403或无法验证时停止推送 /清私有内容；缺X-user-ID /跨owner /跨来源 /CSRF /cache策略一致。
5. legacy正常同步输出与R2/R3最终结果组件回归通过；无stream订阅也能查询原执行终态，取消观察只断连接。

验证：执行observer /runtime /SSE解析与reducer定向测试、真实HTTP/Cookie桌面浏览器；必要PG授权 /Session测试；types /build /静态 /links /Diff；不以Mock chunk证明实际模型流式。
Migration / Rollback: 无新技术产品 /Schema决定，复用01存储；网页新流程与旧API兼容回归，保留数据回滚按04 /06执行。
Done When: 1–5与适用检查通过、Review PASS、文档同步、本地Commit完成。
Result: Ticket 02 已完成。真实 Query / Analysis 阶段通过可选 `ExecutionProgressObserver` 发布；Runtime 提供有界事件通道与原子 snapshot / SSE 增量；网页通过异步受理、GET/SSE 重连和正式执行读取恢复原任务，权限失效时清理私有状态，不重复提交。
Comments: 最终回归：后端目标范围 406 passed、6 skipped、105 subtests passed；最新 SSE / HTTP 定向用例 14 passed；全套 Playwright 41 passed；`npm run build`、新增执行模块 Ruff、模块边界、Markdown 链接和 `git diff --check` 均通过。R3 查询 / 历史 / 分析 / 安全 / 可视化浏览器回归包含在全套 Playwright 中。真实 Provider 验收不属于本 Ticket，留待 Ticket 04 / 06。保存成果重查后的旧视图状态与 reducer 回退边界已在实现中修复。

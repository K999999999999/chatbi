# Ticket 07 — 隔离 Windows 浏览器条件 Review

Review: PASS
Scope: baseline `c9bb998`；隔离验收入口、Playwright local-deployment 配置、相应测试及 Ticket/Runbook。

Change Description: 为真实 Windows 验收提供可选浏览器 EXE 参数，默认仍为 Edge；使用专属临时 Profile，报告保留实际版本和启动类型。解决验收只能复现本机下载接管条件、无法在不改用户设置的条件下做完整对照的问题；不修改 IDM、不安装浏览器、不改变产品 API 或权限。

Findings: 无。Windows 路径要求绝对 EXE 且不含控制字符；进入 PowerShell 参数时沿既有 `_ps_quote` 处理，不进行 shell 拼接执行路径内容。该字段在清除 Compose 环境之前单独读取，仅传给浏览器进程，不带入 Docker 运行配置。默认空值会显式覆盖 Windows 继承环境，防止隐式选用其他浏览器。配置无效在创建资源前退出。

Verification:
- 独立 Windows Chromium `149.0.7827.55` 合成 PDF 对照 HTTP 200 / 431 bytes，与服务器一致；未使用业务内容或模型调用，未改用户配置。不是完整候选验收。
- `tests/scripts/test_local_acceptance.py`：14 passed，含原有资源隔离和四类非法浏览器路径拒绝；最后新增的 CLI 错误包装不改变参数校验行为。
- Ruff、TypeScript typecheck、Markdown links、diff check PASS。
- 固定候选的实际 PDF / 历史 / 成果 / 重启及文件解析留下一步真实运行，不将本 Review 冒称整项目完成。

Review Dimensions: Correctness / Comprehension / Consistency / Testability / Architecture / Security PASS。
Harness Feedback: 属于现有 Ticket 07 的验收入口与可观测性范围；没有新增独立 Harness 目标。
Next: 本地提交参数支持，构建 clean image，以明确记录的 Windows Chromium 条件执行完整隔离验收；保留日常 Edge 的 IDM 使用限制。

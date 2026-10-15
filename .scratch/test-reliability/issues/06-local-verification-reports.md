# 06 本地软件检查与保留的业务验收补齐运行证据

Status: open
Canonical Source: [Spec](../spec.md)、[Design](../design.md)、[草案](../tickets-draft.md#06-本地软件检查与保留的业务验收补齐运行证据)
Owner: 当前主 Agent
Change Profile: 中等入口 / 报告适配；失败与退出语义风险中等；复用现有执行器。
Blocked by: 01, 05

## What to build

让 `dev test` 四类与 `dev check` 生成命令级 summary，读取 pytest JUnit / Playwright 机器结果与现有构建检查结果，不从控制台文字推算成绩。记录起止源码身份、作用范围、安全参数、退出 / 清理结果以及 skipped / 未执行；失败、报告冲突或中断不能假报完整通过。保留 dev 验收和旧宿主真实浏览器验收的独立身份；业务验收中间态可更新，最终结果唯一且不可覆盖；RAG 身份从真实配置路径采集。

Owned files: `dev`、`scripts/container_tasks.sh`、共享报告工具、dev 验收 / 数据库测试 / 浏览器 smoke 证据适配、容器与浏览器测试支持、Playwright 配置与适用测试、Runbook / 容器开发 Spec。

Out of Scope: 添加新测试平台；宿主新增 Python / Node 要求；真实 LLM / 日常环境验收自动执行；重新增加 APP 路线。

## Acceptance criteria

- 四类 `dev test` 与代表性 `dev check` 输出真实 summary；计数不可得 / 不适用时为 null；失败 / skipped / 未执行不能算通过。
- 参数与环境采用白名单且不泄漏凭据；只读源码挂载、无 Docker socket 测试容器、临时资源归属保护不变；缺工具 / 配置 / 写入失败有明确失败证据或未确认状态。
- all / check 子步骤失败、进程中断、清理失败及报告冲突均不报告完整成功；故障注入仅用伪命令 / 隔离资源。
- `browser.json` 中间态仍可更新；最终报告排他发布；缺少 RAG 身份明确标记，safe-reporter 不重写最终证据。
- 普通 clone / linked worktree / Dev Container 路径确定性回归以及完整本地软件 test / check 通过；真实业务验收未执行时明确标记。

Migration / Rollback: 新证据写入隔离路径，保留旧报告和兼容入口独有能力；不修改日常数据卷。

## Result

Pending.

## Comments

实现依赖 Ticket 01 的 dev-only 路线及 Ticket 05 的通用 provenance / 原子发布机制。

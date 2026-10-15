# 06 本地软件检查与保留的业务验收补齐运行证据

Status: done
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

已让所有 `dev test` / `dev check` 入口生成不覆盖既有结果的本地 JSON 摘要。摘要读取 JUnit / Playwright 机器结果，记录源码起止身份、执行范围、各步骤状态、适用计数、退出与清理结果、锁文件指纹和实际容器镜像 ID；敏感参数与环境采用白名单。跳过、缺少证据、来源变化或环境身份无法核实不会被标为完整通过。`dev test all` 现在是单个汇总运行；业务验收仍独立运行，最终报告排他发布，RAG 身份从实际配置路径采集。

未新增测试平台、宿主 Python / Node 前置要求或 APP 镜像路线；未运行真实 LLM / 业务验收。

Review：PASS；基线 `f88045666b3e3d614c8969d0068b242579b6c1b1`；范围为本 Ticket 的 `dev test` / `dev check` 执行与摘要、独立业务验收报告、测试和适用文档。What：统一本地命令级机器可读验证证据；Why：准确呈现计数、跳过、未运行步骤、来源和环境身份，防止退出码掩盖不完整结果；Risk：完整 `test all` 含既有 skipped 时报告为 `incomplete`，要求读取摘要而不只看退出码；Verification：下列完整软件测试 / 检查、定向报告测试及 Diff 检查通过。Findings：审查发现并修复了最终报告发布后的暂存链接清理异常可能造成报告与命令结论不一致、PostgreSQL 临时初始化实例可能被误判 ready，以及环境身份未完整进入摘要的问题；最终复审无遗留发现。Review Dimensions：Correctness / Comprehension / Consistency / Testability / Architecture / Security 均通过。

Verification：`./dev test all`（退出码 0；1201 total：1147 passed、54 skipped、0 failed、0 errors；摘要因 skipped 标为 `incomplete`，清理通过、源码 stable，记录 Python / Node / Browser / PostgreSQL 镜像身份及锁文件指纹；报告 `20261015T144428Z-f880456-test-all-33ac20736e4e`）；最终 `./dev check`（通过，锁文件、文档、模块边界、Python 质量、Web / Export 构建均通过；报告 `20261015T145534Z-f880456-check-all-ac88fe71e365`）；`./dev check docs`（通过；报告 `20261015T145359Z-f880456-check-docs-22453a1de0f4`）；`uv run --locked pytest -q tests/scripts/test_verification_report.py tests/scripts/test_container_dev.py tests/scripts/test_dev_maintenance.py`（71 passed）；定向浏览器报告测试及数据库验证通过；`bash -n scripts/container_tasks.sh scripts/verify_container_dev.sh`、Ruff 格式检查、`git diff --check` 通过。完整 `check` 仅有现存 Vite 大 chunk 提示，无构建失败。

Roadmap：不修改 `docs/roadmap.md`；Ticket 06 属已确认测试可靠性目标内的实施，未改变范围、依赖、验收或优先级。

Commit：`5add0ec43fcb56f45c288631db453eb3f093bf6e`（本地）；没有 Push / PR。

## Comments

实现依赖 Ticket 01 的 dev-only 路线及 Ticket 05 的通用 provenance / 原子发布机制。

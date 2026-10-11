# Ticket 03：验证隔离新 clone 的新人启动与确定性检查路径

Status: done
Owner: 当前主 Agent
Blocked by: 02-current-doc-facts
Change Profile: Lifetime S；Size M；Risk Medium（隔离环境会启动容器并下载依赖 / 模型）；Evidence 隔离启动、健康检查、确定性测试与新人走查；Delivery 本地文档 / 验收记录，无运行时发布。
Canonical Source: 初始化 / 配置 / 健康命令以 `docs/runbook.md` 和 `./dev` 实际行为为准；测试入口以 Runbook、`pyproject.toml`、前端 package scripts 与 CI 为准；本次证据写入当前工作项，不覆盖历史 Acceptance。

## What to build

在与当前 Dev / Active Stable 隔离的新 clone 或等效隔离开发环境中，按推荐路径核对配置前提、初始化顺序、服务启动、健康检查和确定性测试命令；核实文档是否会误导新人复用现有 `.env`、卷、模型或 Qdrant 资产；形成简洁走查清单和复现记录，并从导航链接到 Runbook。

真实浏览器业务验收和真实 LLM Evaluation 只列进阶路径，不是首次上手门槛。

## Acceptance criteria

1. 使用新 clone / 全新隔离容器、卷、数据库、Qdrant 和配置；不连接、挂载或复用现有 Dev / Active Stable 数据、`.env`、管理员或外部云凭据。
2. 按文档可完成配置、显式初始化、启动和 HTTP 健康检查；说明健康检查与真实业务验收的边界。
3. 运行 Runbook 标记的确定性纯软件测试入口；环境满足时记录适用的隔离集成或前端测试结果，未运行项不得写成通过。
4. 非导航作者按清单能找到启动、健康和测试命令；阻塞或外部依赖限制如实记录。
5. 仅清理本 Ticket 创建且身份明确的隔离资源；清理失败时保留资源并记录恢复指引，不碰未知资源。

## Owned files

- 必要时小范围修改 `docs/runbook.md` 或 `docs/project-guide.md`
- `.scratch/project-navigation/` 下的验收记录

禁止读取、复制、覆盖、清理或迁移当前 Stable / 用户数据、配置和运行资产。

## Verification evidence

- 隔离环境身份与创建方式
- 实际命令、退出结果和 HTTP 健康响应
- 测试范围 / 结果、新人走查记录及资源清理核对
- 真实 LLM Evaluation / 完整浏览器 Acceptance 不属于默认证据

## Migration / Rollback

无持久产品迁移或运行时发布。只移除本 Ticket 明确创建的隔离资源；身份不明确时停止清理并保留证据。

## Result

推荐容器初始化、健康和测试路径已在隔离 Compose 项目实际运行；详细命令、边界、结果和清理证据见 `.scratch/project-navigation/onboarding-acceptance.md`。API / Web HTTP 200，全量 Python 测试与 PostgreSQL 集成测试、前端类型检查通过；已有主机镜像被用于绕过 Debian 系统包源 HTTP 502 的冷构建障碍。隔离资源已清理。导航作者两次模拟走读和一位非作者独立走查均已完成。独立走查发现产品范围内导出交付状态易误读，以及当前 Online Retrieval 契约不易定位；已修正文案 / 导航链接并由该审阅者复核通过。Markdown 本地链接检查通过。独立走查未执行隔离新 clone 操作；隔离启动 / 健康 / 测试证据来自本 Ticket 前述记录。以上范围完成，未声明冷镜像构建、完整浏览器业务 Acceptance 或 LLM Evaluation 已通过。

## Comments

- 来源：用户确认的 `.scratch/project-navigation/spec.md` 与 `ticket-drafts.md`。
- Ticket Readiness：READY（当前上下文只读检查）。

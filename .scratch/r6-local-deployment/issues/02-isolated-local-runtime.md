# Ticket 02：独立环境安装与日常启停闭环

Status: in-progress
Owner: 当前主Agent
Blocked by: 01（done）
Result: 已实现独立 Compose、`.env.local` 模板、`./local` 操作入口与运行前置检查；Runbook 安装 / 启停章节及正式 Contract 初稿已同步。静态 Review 和确定性检查通过；clean 候选构建、真实空卷安装、模型 / RAG 初始化及管理员 / Windows 浏览器问数和持久性验收仍待完成。
Comments: 本地实施授权于2026-10-07取得；发布授权未取得。


Change Profile: 持续维护 / 中 / 初始化、资源归属与Secret风险 / 命令软件测试+空卷集成+浏览器 / 本地Commit。
Owner: 当前主Agent；后续交付/bootstrap维护者。
Blocked by: Ticket 01。
What to build: 独立docker-compose.local.yml、安全配置模板、./local安装/初始化/启动/停止/状态/日志入口；配置和卷/项目labels隔离、API/工具/migrator最小权限、模型缓存与独立RAG资产装配；交付启动显式复用既有catalog/RAG门禁。
Owned files: docker-compose.local.yml、.env.local.example、local、scripts/local_release.py、必要bootstrap装配适配及对应tests；部署正式Spec初稿/Runbook安装配置启停章节。若需改变bootstrap公共行为返回审查。
Acceptance Criteria:
- 空验收环境显式完成基础初始化→migrate→模型/索引→隐藏密码创建管理员→up；up缺少条件拒绝且不自动初始化。
- 仅API发布回环端口；无开发代码bind/迁移凭据进入API，所有服务手动启动；secret与静态身份检查生效。
- Windows浏览器同源登录并完成至少一次真实问数；关闭终端继续运行，down保留数据，再up历史可读。
- 索引指纹不匹配/配置缺失/端口冲突给出阶段诊断与非零结果；不杀进程/重置数据/影响开发环境。
Evidence: 命令分支/权限/挂载确定性检查，独立真实PG/Qdrant初始化与重试集成，真实LLM浏览器登录问数；记录环境/提交/镜像/资产身份。
Migration / Rollback: 只在新独立实例应用现有migration，不导入开发数据；失败保留稳定数据，恢复按显式初始化步骤重试。工具锁阻止并发写操作。
Done When: 已确认安装/启停边界全部有证据，正式行为说明与Runbook同步，Code Review完成；形成可用于后续真实升级对的clean release候选。

Review: PASS（base `eba02b0251c00cfcf169bf09bae63e8d02c9bd42`；Ticket 02 owned files）。复审修复了遗漏的写操作锁，并收紧 Qdrant 检查 URL；当前无未解决实现发现。Correctness / Comprehension / Consistency / Testability / Architecture / Security 均通过。20 个本地发布入口确定性测试通过；Ruff、Bash 语法、Markdown 本地链接、Compose 隔离约束与 `git diff --check` 通过。该 Review 不代表真实容器安装、LLM 浏览器验收或 Ticket 完成。

Verification: `uv run --frozen pytest tests/scripts/test_local_release.py -q`（20 passed）；`uv run --frozen ruff check scripts/local_release.py tests/scripts/test_local_release.py`；`bash -n local`；`python3 -m scripts.check_markdown_links`；Compose JSON 检查仅有 API 回环端口、数据库 / Qdrant 无宿主端口、API 无 migrator 环境变量、应用资产只读、所有服务手动 restart、Qdrant 固定 digest；`git diff --check`。clean 镜像构建与真实隔离运行待本地 Commit 后执行。

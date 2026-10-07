# Ticket 02：独立环境安装与日常启停闭环

Status: in-progress
Owner: 当前主Agent
Blocked by: 01（done）
Result: 已实现独立 Compose、`.env.local` 模板、`./local` 操作入口与运行前置检查；Runbook 安装 / 启停章节及正式 Contract 初稿已同步。空卷安装、迁移、模型 / RAG、管理员创建、Windows Edge真实问数和down-up历史持久性已通过。随后发现端口冲突会被内部健康检查误报成功；修复已实现并通过工作区集成检查，待clean候选重建与复验后完成Ticket。
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

Review: PASS（follow-up base `5ffe0b2e9512fdd64797c58e888847a53b3e73ab`；Ticket 02 owned files）。首次 Review 中的写操作锁和 Qdrant URL 问题已修复。构建失败暴露出的缓存 / release 身份耦合也已拆开：祖先镜像只提供可复用的 Docker layer cache key，最终标签和 `/opt/chatbi-release.json` 始终写当前 clean source commit；无祖先镜像时仍执行完整构建。当前无未解决实现发现。Correctness / Comprehension / Consistency / Testability / Architecture / Security 均通过。该 Review 不代表镜像构建或真实容器验收成功。

Verification: `uv run --frozen pytest tests/scripts/test_local_release.py -q`（20 passed）；`uv run --frozen ruff check scripts/local_release.py tests/scripts/test_local_release.py`；`bash -n local`；API / database Dockerfile `docker build --check` 无告警；`python3 -m scripts.check_markdown_links`；Compose JSON 检查仅有 API 回环端口、数据库 / Qdrant 无宿主端口、API 无 migrator 环境变量、应用资产只读、所有服务手动 restart、Qdrant 固定 digest；`git diff --check`。clean build `0a9f5aa287d87f648cb71ab31b234d77d07fc15b`成功，API / PostgreSQL image ID分别为`sha256:211550d04ab2524cf329fb5eb9bef341108a61314ba11e7a6b1ecaeba7cb6637` / `sha256:77379c207ef8345a2d5430cf6b283bcfd072cc4f7fb7308193632ec79bae3c78`，OCI revision与release JSON匹配。空卷Sales初始化、RBAC / 应用迁移、固定BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181`和RAG build `20261007T153620Z-52a4cdfae6ea`（7 tables / 69 columns / 7 metrics / 9 relationships，0 failures）通过。Linux Chromium真实问数与独立SQL匹配；down/up后历史可读、页面刷新未重新执行；Windows Edge 154.0.4258.53同源登录和真实问数与独立SQL匹配。端口冲突在修复前确认为实际缺陷；TDD Red为新增测试1失败/1通过。修复后`tests/scripts/test_local_port.py`与`tests/scripts/test_local_release.py`共24 passed，Ruff / Bash语法 / Diff检查通过；真实端口占用时`./local up`非零诊断且临时占用进程HTTP 200未被停止，释放后新`up`及重复`up`通过。端口修复尚未Commit和clean build，需绑定下一候选重跑启动 / Edge问数 / down-up；开发PostgreSQL / Qdrant未修改。

# Ticket 02：独立环境安装与日常启停闭环

Status: done
Owner: 当前主Agent
Blocked by: 01（done）
Result: 独立安装、配置、初始化、Runbook / Contract、隔离与启停闭环完成。空稳定PG/Qdrant卷、Sales Seed、migration、固定模型、RAG和管理员验收绑定clean候选`0a9f5aa`；端口冲突修复和缓存键修复绑定`9050258` / `df5c9e1`。最终clean候选`733b074`构建时复用依赖层缓存，镜像身份校验通过；同候选启动后，端口冲突保护、Windows Edge真实问数、down/up后的登录、历史快照和刷新持久性均通过。本地Stable与开发PG/Qdrant保持隔离，无远端发布。
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

Review补充（2026-10-08）：复核缓存选择helper、`./local`调用点、API / PostgreSQL镜像label和回归测试；显式缓存键按当前提交可达祖先选择，legacy镜像仅按最早可达revision回退，最终release身份仍由当前clean commit写入。未发现阻断问题；候选构建及目标运行证据见下。

Verification:
- clean候选`0a9f5aa287d87f648cb71ab31b234d77d07fc15b`完成隔离空PG/Qdrant卷初始化、合成Sales Seed、应用/RBAC migration、固定BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181`准备及RAG build `20261007T153620Z-52a4cdfae6ea`（7 tables / 69 columns / 7 metrics / 9 relationships，0 failures）；管理员创建与首轮浏览器问数完成，开发PG/Qdrant未修改。该候选API / PostgreSQL image ID为`sha256:211550d04ab2524cf329fb5eb9bef341108a61314ba11e7a6b1ecaeba7cb6637` / `sha256:77379c207ef8345a2d5430cf6b283bcfd072cc4f7fb7308193632ec79bae3c78`。
- 端口修复TDD Red覆盖旧误报；修复后`tests/scripts/test_local_port.py`与`tests/scripts/test_local_release.py`共24 passed。真实占用回环8080时`./local up`非零退出并保留外部HTTP服务；释放后启动和重复`up`通过。
- 缓存选择TDD先在旧revision-only逻辑下2项失败，修复后构建缓存 / 端口 / release测试合计26 passed。Ruff、`bash -n`、Markdown本地链接、`git diff --check`和API / database Dockerfile `docker build --check`通过。候选`733b074f2417460bc3a41e00815059bbdd6b2d26` clean build使用cache source `4d4732b7896a46b231a4a3437c703e74b5ae513f`；APT、Python依赖、Playwright、前端及PostgreSQL内容层显示`CACHED`。API / PostgreSQL image ID为`sha256:7c7631b1a1f1346a0d15bbfd4b775c65a7190456b3d6e63fe56d6b873d1032e2` / `sha256:43536bcacdb89892419a2bbc73aacdb4b4038472347c3283f7b2649a5561d130`；两镜像OCI revision、`com.chatbi.build-cache-commit`和`/opt/chatbi-release.json`均核实正确，API `/health`和启动前置检查通过。
- 最终候选上的回环8080冲突验收返回非零，临时占用进程仍HTTP 200且稳定API保持停止；释放后候选恢复healthy。Windows Edge `154.0.4258.53`在稳定URL同源登录问数；2025年2月已完成订单人民币净销售额`171010.14355`与独立只读SQL一致。`./local down`后`./local up`，PG/Qdrant Volume CreatedAt均保持`2026-10-07T15:35:24Z`；重登录后读取历史及快照、页面刷新通过，未创建新执行。报告：ignored `reports/browser-real/r6-ticket02-candidate-733b074.json`（权限600）。临时账号已禁用且0 active session，临时凭据与隔离Edge profile已删除；开发PG/Qdrant保持运行且未改动。

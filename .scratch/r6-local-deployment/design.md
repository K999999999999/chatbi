# R6 本地稳定交付实现设计

Status: 基于2026-10-07已确认[Spec](spec.md)；Design Review PASS，可按四项Ticket实施。
Owner: 当前主Agent；后续维护由交付配置、bootstrap和所属模块维护者承接。

## 事实与方案选择

- `src/query_api/browser.py:BrowserSettings.from_environment`仅对development/dev/test/testing放行回环HTTP，production/staging均要求Secure Cookie / HTTPS。首版本地交付显式设置development，固定构建与隔离通过交付入口保障；不放宽production或浏览器安全Contract，不增加新环境枚举。
- development不触发`src/bootstrap/readiness.py`的production RAG来源检查。交付入口必须额外显式调用既有`RagRuntime.verify_production_ready`和catalog检查，强制启用RAG并校验管理员密钥至少32字符及拒绝旧静态身份配置；作为交付前置检查，不改变默认开发入口。每次启动/升级/回滚都执行，检查成功不代表动态readiness。
- `docker-compose.yml`与dev overlay有源码bind、固定Qdrant端口和unless-stopped。新增独立`docker-compose.local.yml`，不叠加开发Compose：api、postgres、qdrant常驻，tools/migrator使用profiles。所有服务restart=no，手动完整启动；仅API发布回环端口，数据库与Qdrant只在项目私有网络可达。
- 数据库账号沿用既有固定角色名，但在独立PostgreSQL实例/独立凭据下创建，不修改Sales Mart grants。两套数据库仍在同一独立PostgreSQL服务中。项目资源由Compose项目名/labels和显式数据路径归属，不使用开发卷或默认全局资源名。

替代方案：复用dev overlay后逐项覆盖挂载和端口，虽然文件少但易残留源码、凭据或端口继承；独立Compose成本局部且隔离可直接核对。production + 新增HTTP例外会改变安全边界，因此不采用。

## 固定版本打包

- CPU镜像的Python锁文件须从官方PyTorch CPU wheel index解析torch，显式来源仅绑定torch；将torch写成明确运行依赖，`uv.lock`记录CPU wheel哈希且不锁定CUDA/Triton依赖。PyTorch官方安装选择器提供CPU计算平台；uv sources支持指定索引并以`explicit=true`限制其他包不从该索引解析。来源：[PyTorch安装选择器](https://pytorch.org/get-started/locally/)、[uv依赖源](https://docs.astral.sh/uv/concepts/dependencies/)。重新核验RAG离线构建/检索和evaluation用的FlagEmbedding链路。
- `docker/local.Dockerfile`多阶段构建前端网页与R5导出bundle，再安装Python锁定依赖/Chromium/已锁定字体，并复制src、所需scripts、结构/语义资产及数据库初始化/migration文件。运行用户非root，单worker、无reload；运行服务不依赖宿主源码。
- 数据库初始化文件进入专用PostgreSQL镜像或同一Dockerfile的postgres目标，不运行时bind仓库database；沿用PostgreSQL16与既有初始化流程。依赖基础镜像使用固定digest，沿用现有锁文件与字体版本；构建证据记录实际镜像ID，不承诺镜像字节级完全可重现。
- `.dockerignore`以允许列表扩展必要源文件，不包含.env、.git、.scratch、reports、模型缓存或真实数据；构建入口检查clean commit和构建输入归属。导出bundle/字体manifest继续复用既有生成及验证机制，不设置开发`CHATBI_EXPORT_SOURCE_DIR`。
- 每个发布描述包含格式版本、源commit、API/PostgreSQL实际image ID、构建依赖身份和兼容性描述；运行按image ID选择，不把可变标签作为发布身份。

## 操作入口与资源

新增根入口`./local`，Bash只负责定位/Compose调用；确定性输入、归属和兼容性检查放在`scripts/local_release.py`，在容器中运行涉及Python的操作。预期命令族：build、infra、migrate、create-admin、prepare-model、build-rag、up、down、status、logs、upgrade、rollback。配置以独立安全模板开始，必须用户显式填写，不自动复制开发.env或生成管理员。

- 持久目录/卷、端口、项目名及配置互不共用；API只有运行账号，无迁移账号/.env挂载。migration仅一次性工具可用，密码不回显。
- 模型缓存允许读取固定revision；工具准备模型可写指定缓存，API只读。索引是稳定环境独立目录/卷与独立Qdrant实例；保持manifest所需模型路径身份，不能靠改写manifest绕过校验。
- 首次infra不等待migration依赖的完整health；migrate等待基础初始化，再显式运行bootstrap migrate；管理员/模型/索引分别显式完成。up不替代这些命令。
- up检查发布描述、环境身份、配置和资产后后台启动；超时失败报告阶段与恢复命令，不自动删除已创建资源。down只stop当前项目服务，不提供隐式down -v或reset。
- 状态/日志输出脱敏；不输出Compose完整配置。port冲突保留未知进程。所有写操作按环境加本地锁，升级/回滚与初始化不能并发。

### Ticket 02 实施选择（验收仍进行中）

- `./local init-config` 只从 `.env.local.example` 创建独立 `.env.local`，另行生成 `.env.local.secrets`；两文件权限要求为 `600`，已存在时拒绝覆盖。数据库、Control DB、管理员签名及 Qdrant 密钥由 `openssl` 生成；LLM Key 保持空值，需用户自行填入。命令不读取开发 `.env`。
- `./local build` 仅接受 clean worktree，以完整 source commit 构建 API / PostgreSQL 目标，并记录 commit、tag 与实际 image ID 到 ignored `.local/release.env`。Compose 使用固定 `chatbi-stable` project；数据卷显式命名为 `chatbi_stable_postgres_data` 和 `chatbi_stable_qdrant_data`，Qdrant 使用固定版本 digest。
- 为复用本机 Docker layer cache，构建从当前 source commit 的最近祖先镜像 commit 作为早期依赖层的 cache key；API / PostgreSQL 最终层重新写入当前 clean source commit 的 OCI revision 和 `/opt/chatbi-release.json`。无祖先镜像时以当前 commit 完整构建；缓存不改变发布身份或运行资产。
- 镜像额外记录`com.chatbi.build-cache-commit`，构建时按该标签选择最近可达祖先；旧镜像没有此标签时才按最早的可达OCI revision回退，避免把旧发布的source身份误当成它实际使用的依赖层缓存键。
- `docker-compose.local.yml` 将 API、PostgreSQL、Qdrant 与 `tools` profile 下的一次性工具分开。API 只发布 `127.0.0.1`，单进程、无迁移凭据；数据库与 Qdrant 不发布宿主端口。API 对已准备的模型缓存和 `.local/rag` 只读，准备工具按宿主 UID/GID 写入；RAG 资产不共用 `data/rag`。
- 空稳定 PostgreSQL 卷沿用镜像内初始化脚本建立专用数据库、角色、Sales Mart 结构和确定性合成 Seed；后续 `migrate`、创建管理员、准备模型、构建索引均由用户显式执行，`up` 不代替这些操作。启动前执行既有导出 manifest、管理员、Control DB、catalog 和生产来源 RAG 检查，并额外要求 LLM、CPU/FP32、回环 Origin、固定镜像身份。
- `down`、`status` 和 `logs` 直接按 `com.docker.compose.project=chatbi-stable` 及服务标签定位容器，因此配置 / 发布文件损坏时仍可诊断或停止本项目；它们不删除数据卷。该行为已有本地无容器路径检查，真实隔离环境安装和运行验收尚待本 Ticket 完成。

## 兼容性与失败恢复

兼容性不是仅检查某个v2 marker存在：现有migration采用加法marker，旧marker保留不能证明旧版本支持新表/快照。每个发布显式声明已验证的兼容状态：Control migration marker集合、关键catalog结构投影、checkpoint migration版本、业务Schema/Seed版本、历史快照版本与RAG manifest格式/来源输入。范围从本目标验证过的状态开始；未知状态默认拒绝，不创建通用迁移平台。

- 初始发布描述从当前权威DDL、锁定checkpoint依赖和合同确定所需状态，不能“现场观测是什么就接受什么”。集成验收对照实际catalog。运行角色只读读取必要状态。
- 检查目标镜像真实存在、内嵌commit与发布描述一致，迁移状态符合该目标接受列表，资产指纹符合目标内嵌结构/语义事实及catalog。RAG变更可能使旧版本无法回滚，保持拒绝语义，不承诺恢复旧索引。
- upgrade先检查目标和资源身份、获取锁、停止API，再明确执行指定目标的migrate/必要的显式资产准备与检查，最后启动新API；下游数据服务保持项目身份。成功后原子更新active发布记录，失败保留前一成功记录和本次失败阶段，不将旧active记录伪称为服务仍在运行。
- rollback不执行迁移；在停API前只读检查目标兼容性，不兼容或描述缺失直接拒绝。允许后停新API并启旧API，启动失败保留数据，报告实际状态和手动恢复入口。
- 不增加业务migration，不反向DROP，不清理旧镜像，不改变既有运行中execution恢复语义。备份恢复与动态监控仍归R7。

## 验证与切片

每个切片包含软件/集成检查和相应文档，不把测试全部留到最后。最终在隔离验收项目以clean candidate验证，指定Windows浏览器完成核心链路；重启验收在目标机安排明确维护窗口，不擅自重启整个Docker/电脑影响其他项目。

兼容升级/回滚使用本目标两个真实clean release提交构建的镜像（例如安装闭环候选与后续版本管理候选），保持同一业务Schema；记录其具体SHA。它证明已声明状态的兼容升级，不等于新增Schema migration跨版本能力。额外不兼容状态在隔离验收实例构造，只读拒绝后证明数据未改。

## 边界与重新审查触发

Domain/Application业务行为不变；部署脚本复用bootstrap、catalog及RAG既有边界。不得把发布兼容逻辑塞入Domain或新增业务Service层。若必须改变Cookie规则、production启动策略、migration语义、manifest格式或新增依赖，返回Spec/Design审查。预期维护寿命为持续维护的本地交付入口。

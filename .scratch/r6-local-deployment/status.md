# R6 本地稳定部署规划记录

- 2026-10-07：首版范围、目标环境、安装 / 初始化、启停、升级回滚、运行边界与验收标准逐项确认，需求澄清完成。
- [完整 Spec](spec.md) 已整体确认，Design Review PASS，四项Ticket拆分与完整本地实施已获用户确认和授权。
- 当前实施分支 `feature/r6-local-deployment`，起始于已同步的 `master` / `origin/master` `2a7600d`；Ticket 01、02、03已完成，稳定API候选`995440b`，Ticket 04完整隔离验收实施中；未发布。
- 本机实时状态位于 Git 公共目录 `harness/work-items/r6-local-deployment/status.md`，本文件为规划历史，不作为实时状态副本。
- R1–R5 历史证据不改写；R6 Ticket 02安装与Ticket 03版本往返验收已完成，Ticket 04完整目标环境验收实施中。R7完整运行保障不纳入本地首版部署范围。

## 需求澄清完成记录

状态: 澄清完成
事实源与已确认事实: Architecture、产品范围、bootstrap / RAG / 开发环境Contract、Runbook及R1–R5历史Acceptance；当前WSL2 x86_64与Docker Compose可用，原Compose为开发入口。
用户已确认的决定: 见完整Spec；逐项确认本地首版范围、目标设备、启停、升级回滚、安装、配置初始化、运行边界与验收标准。
范围与关键边界: 合成销售数据、当前电脑、独立固定版本稳定运行；仅本机同源HTTP、单进程CPU/FP32；云部署和R7全面运行保障不在首版范围。
验收与验证方向: 空环境安装、真实浏览器业务闭环、重启持久化、升级与兼容回滚、安全失败与环境隔离；候选和资源身份需关联。
假设: None
未决 / 阻塞项: None
留给Ticket / 实施阶段的决定: 在Design中确定Compose/命令组织、固定版本标识、兼容性检查、缓存与发布资产路径、验收版本对；不得改变已确认边界。
下一步: Ticket 01–03已完成；完成Ticket 04同一clean候选的完整Windows Edge隔离验收与文档收尾。

## 本次文档整理检查

- 四份规划文件的Markdown本地链接PASS，tracked Diff的`git diff --check` PASS；人工核对完整Spec与逐项确认一致。
- 路线图当前阶段、需求细化状态、R6需求表、目标环境、授权门禁与后续生产范围同步；产品长期记录补充R6决定。
- 本机19份记录检查0ERROR；REVIEW为产品/R6尚未完成以及本目标已归属的文档修改，不代表已完成运行验收。
- 未运行软件测试、容器验收或AI Evaluation；未修改运行代码、Commit或PR。

## 完整Spec确认后的规划结果（2026-10-07）

用户整体确认Spec；实现设计经当前主Agent只读Design Review PASS。四项Ticket Readiness READY；用户随后确认Ticket拆分并授权完整本地实施和验证。设计保留production/Cookie安全规则，本地development配置通过独立交付入口追加资产校验；不构成放宽安全Contract。

## R6 Ticket 01 完成记录（2026-10-07）

- clean source commit：`4d4732b7896a46b231a4a3437c703e74b5ae513f`。
- API镜像：`sha256:dfe36e7aa5927bd2334f2fd406a257837e7079ef8e07f168dd2ffca9aa01961b`，1,909,212,440 bytes。
- PostgreSQL镜像：`sha256:e9605804df9016d702ee575220cd27ab7a40441a07f44846931fe9ca952fdbfc`，116,049,593 bytes。
- 两镜像OCI revision label与`/opt/chatbi-release.json`均匹配source commit。Dockerfile check、构建、前端build/typecheck、锁文件、CPU模型、网页及导出资源、PostgreSQL初始化脚本/DDL/合成Seed定向检查通过。
- 未完成完整稳定环境、Embedding/RAG构建实测或浏览器业务验收；这些仍在Ticket 02 / 04范围。

## R6 Ticket 02 实施记录（2026-10-07）

- 独立`chatbi-stable` Compose、配置模板、`./local`操作入口、环境前置检查、写操作锁及Runbook安装 / 启停章节已实现；正式本地稳定部署Contract初稿已建立。
- 基于`eba02b0251c00cfcf169bf09bae63e8d02c9bd42`的实现Review PASS；本地发布入口20项测试通过，Ruff、Bash语法、Markdown本地链接、Compose资源隔离约束和Diff检查通过。
- `5ffe0b2e9512fdd64797c58e888847a53b3e73ab`的首次`./local build`约111分钟后因锁定`pyarrow==25.0.1`从`files.pythonhosted.org`下载超时而失败；未生成可用新镜像或release记录，未启动稳定容器，开发PostgreSQL / Qdrant未改动。锁文件保持不变。
- 为复用已有干净祖先镜像的Docker依赖层、同时将最终镜像revision和release JSON绑定当前clean commit，已加入末层release身份覆盖与祖先缓存选择；该修复的定向测试和Dockerfile检查通过，尚待本地提交及重新构建。
- 尚未完成空卷真实初始化、稳定RAG构建、隐藏密码管理员创建、真实LLM浏览器问数、关闭终端 / down-up持久性验收；不能据此标记Ticket完成。

## R6 Ticket 02 集成进度（2026-10-07）

- 缓存修复已提交为clean source commit `0a9f5aa287d87f648cb71ab31b234d77d07fc15b`，本地API / PostgreSQL镜像构建成功，ID分别为 `sha256:211550d04ab2524cf329fb5eb9bef341108a61314ba11e7a6b1ecaeba7cb6637` / `sha256:77379c207ef8345a2d5430cf6b283bcfd072cc4f7fb7308193632ec79bae3c78`；OCI revision与镜像内release JSON均匹配该提交。
- 独立稳定PostgreSQL / Qdrant空卷启动、Sales初始化与应用/RBAC migration通过；固定BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181`准备完成。RAG build `20261007T153620Z-52a4cdfae6ea`已发布，包含7个table、69个column、7个metric文档和9条relationship edges，failure_count=0。
- 开发PostgreSQL / Qdrant持续运行且未修改。稳定PG / Qdrant运行中；管理员尚未创建，`.env.local` 的 `LLM_API_KEY` 当前为空，因此API未启动。下一步由用户在本机交互创建隐藏密码管理员、填写本地LLM密钥；随后继续up、Windows浏览器真实问数与down-up历史持久性验收。

## R6 Ticket 02 端口冲突修复进度（2026-10-08）

- 用户本机已完成管理员创建和LLM密钥配置。Linux Chromium真实登录 / 问数结果与独立只读SQL一致；稳定环境down/up后，同一测试账号的历史和快照可重新打开、刷新，未触发新执行。Windows Edge 154.0.4258.53也完成同源登录和真实问数，返回值与只读SQL一致；临时账号已禁用并撤销会话，临时凭据与Edge profile已清理。
- 为验证Ticket02的端口冲突边界，先用隔离回环HTTP进程占用8080。复现`./local up`误报成功：容器内健康检查通过，但HTTP请求实际落到占用进程；稳定API没有有效发布映射。已按TDD记录Red（占用端口探测测试1失败/1通过），修复增加host回环端口探测、运行API映射识别、`/health`外部路由检查和失败时只停止本稳定API的恢复路径。
- 修复后定向测试24项通过；端口冲突集成验收返回非零和明确诊断，临时占用进程仍返回HTTP 200且未被停止；释放端口后`./local up`成功，API回环HTTP健康，重复`up`也通过。
- 当前端口修复代码尚待本地Commit与clean镜像重建；因此Ticket02仍in-progress，需在新候选上复验浏览器和持久性，再收尾文档。稳定环境服务现已恢复运行。

## R6 Ticket 02 构建缓存选择修复（2026-10-08）

- 端口修复提交后尝试clean build时发现，旧选择器只读最终镜像`org.opencontainers.image.revision`，会把发布提交误当成依赖层实际缓存键，导致apt及后续昂贵层重新构建；在apt下载阶段中止，未改写release记录或容器。
- 新增`com.chatbi.build-cache-commit`镜像标签，仍由当前source commit构建发布身份，同时记录早期依赖层实际cache commit；选择器先按该身份取最近可达祖先，旧镜像无该标签时才选择最早可达OCI revision。针对新标签和legacy回退新增TDD，旧实现2项失败，修复后与端口 / release测试合计26项通过；Ruff、Bash语法、API / database Dockerfile check和Diff检查通过。现有本机镜像上选择器实测返回`4d4732b`。
- 端口与缓存选择修复及进度证据已本地提交为`df5c9e1`；本机稳定Stack仍运行旧候选`0a9f5aa`，开发PostgreSQL / Qdrant保持运行。下一步从clean提交构建新候选，确认昂贵依赖层命中缓存，并在新候选复验端口保护、Windows Edge问数和down-up持久性，再完成Ticket02并连续实施03→04。


## R6 Ticket 02 最终候选验收完成（2026-10-08）

- 候选`733b074f2417460bc3a41e00815059bbdd6b2d26` clean build成功，cache source=`4d4732b7896a46b231a4a3437c703e74b5ae513f`；APT、Python依赖、Playwright、前端与PostgreSQL内容层显示`CACHED`。API / PostgreSQL image ID及OCI revision、cache label、内嵌release JSON见Ticket 02记录；`.local/release.env`和镜像均仅在本机。
- 该候选下8080占用测试非零拒绝、未停止外部HTTP服务，随后候选启动健康；Windows Edge真实查询为`171010.14355`，与稳定Sales库只读SQL一致。`down/up`后两持久卷`CreatedAt`不变，重新登录可打开历史与快照，刷新不触发新execution。
- 空卷Seed、migration、模型及RAG初始化证据绑定先前clean候选`0a9f5aa`；其后的候选改动限于回环启动冲突保护和缓存/镜像身份元数据，并已在`733b074`复验受影响链路。最终ignored浏览器报告为`reports/browser-real/r6-ticket02-candidate-733b074.json`，mode 600。
- 验收临时账号已禁用且会话全部撤销，临时凭据和隔离Windows Edge profile已删除。Stable API/PG/Qdrant运行于`733b074`；开发PG/Qdrant仍运行未修改。Ticket 02完成；依赖满足，下一步Ticket 03。

## R6 Ticket 03 真实版本对验收完成（2026-10-08）

- 实现 Review PASS；候选 C `9ae32ef6900030af15c38ac9a059e3086b5dde1c`、D `995440bfd448f6057f5152431d17dff012f8bd5c` clean build，并在稳定资源完成 `733b074 → C upgrade → D upgrade → C rollback → D re-upgrade`。所有兼容预检、migration、API健康与部署状态记录通过；回滚未运行migration。
- 往返前后只读数据指纹一致：4个用户、1个管理员；3条历史、3个turn、3个成功快照；saved_results为空集。Control DB用户与历史 / 快照指纹见Ticket 03记录。PostgreSQL容器`cb18b903d8bd`（原733b074运行镜像）与Qdrant容器`f54cf28e0543`、命名卷均未重建。
- 最终Stable API运行候选D；`.local/deployment-state.json`为`running/succeeded`，权限600。开发PG/Qdrant未修改。无Push/PR/云部署。Ticket03已完成，进入Ticket04。

## R6 Ticket 04 目标环境完整验收实施中（2026-10-08）

- 起始BASE为clean candidate `995440bfd448f6057f5152431d17dff012f8bd5c`；工作区仅有Ticket03验收关闭、正式Contract与路线图状态同步改动，Stable API仍运行该候选，部署配置 / Secret仅留本机。
- 下一步：为最终clean候选建立独立空卷验收资源，完成Windows浏览器问数 / 追问 / 经营分析 / 历史 / 保存成果 / XLSX、PNG、PDF内容验收，服务恢复与Ticket04失败场景检查，随后形成Acceptance / Design / Runbook / Product Scope / Roadmap最终证据；电脑或Docker重启安排维护窗口，不擅自重启共享服务。

## Ticket 04 验收入口候选准备

隔离配置、资源归属保护、Windows Edge配置及报告目录已实现。TDD记录：报告模块缺失和隔离配置模块缺失均先产生Red；Compose真实解析发现project名称大写不合法后修复。定向软件63项与报告路径3项通过；随后新增容器身份拒绝回归，目前隔离配置/Compose/身份10项通过。类型、Ruff与Diff检查通过。完整真实验收尚未运行；下一步形成clean candidate构建固定镜像。

## Ticket 04 PDF传输诊断停点（2026-10-08）

9f01de2正式运行已通过sandbox、问数 / 追问 / 多指标 / XLSX / PNG、经营分析参考值，但PDF在Edge收到204空响应；完整验收失败。诊断与有效PDF最小对照确认API/Linux/Windows PowerShell200，Edge204。IDM运行且监控PDF，接管原因待暂停后的对照确认。用户已收到临时调整 / 恢复IDM的确认请求，尚未修改本机配置。失败资源已清理，Stable仍995440b；Ticket04未完成，无发布授权。详见正式Acceptance当前失败记录。

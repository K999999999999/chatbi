# 现有脚本与 dev 入口盘点

## 结论与证据范围

建议让所有当前支持的人工操作都能从`./dev help`找到，并通过dev执行；一个操作可调用多个脚本，内部模块继续由调用链使用。存在旧宿主执行方式和重复runner，接入前须适配或明确退出支持。

前半部分保留master@38e1302盘点时的事实与建议，属于基线记录；当前目标已确认并进入实现/验证，最终处置见文末。本阶段测试只用专属隔离资源，没有真实LLM或日常数据操作。

- 基线：`master@38e1302ce33d999dc908419067bc5d39195f86cf`；盘点工作区`feat/dev-command-entrypoints`。
- 基线`scripts/`共24个Git跟踪文件：17个Python、6个Shell、1个PowerShell。其中16个文件提供可执行入口，8个为内部模块/库；有CLI并不代表要公开为独立dev命令。
- 逐项读取用途、入口、依赖、副作用，并核对[dev](../../dev)、[Runbook](../../docs/runbook.md)、README、CI、Dockerfile、Compose、Dev Container及相关Tests的调用方。
- 补充覆盖根dev、数据库容器脚本、Git Hook、Bootstrap/Evaluation入口、导出内部进程和前端npm scripts；不把ignored本机临时诊断脚本或历史归档当作现行支持入口。
- 独立待发布候选`container-auto-restart@fd9be30`新增的`scripts/start_dev_api.py`另列，不把它称为已合入master。该候选和原运行工作区保留。

## scripts 逐文件清单

“只读”只描述目标业务数据；安装Hook、写源文件、报告、索引、测试临时资源等副作用另行列明。处理建议均待范围确认。

| 文件 | 当前用途与调用方 | 依赖与副作用 | 处理建议 / dev映射 |
| --- | --- | --- | --- |
| [scripts/__init__.py](../../scripts/__init__.py) | Python包入口；测试及模块导入 | 无独立操作 | 内部保留，不公开命令 |
| [check_dev_qdrant.py](../../scripts/check_dev_qdrant.py) | Qdrant健康检查；对应软件测试，未接dev | Python/dotenv、网络、配置；只读，不打印Key；当前使用宿主回环地址 | 容器/项目地址适配后纳入`./dev doctor`，无需要求用户记文件名 |
| [check_documentation.py](../../scripts/check_documentation.py) | 组合文档结构/链接检查；CI和dev check调用 | Python/Git、源码只读 | 保留`./dev check`覆盖；可提供`./dev check docs`定向检查 |
| [check_harness_state.py](../../scripts/check_harness_state.py) | 本机实时进度与Git一致性；AGENTS指定会话入口 | Python/Git、worktree及共享Git公共目录；只读，不访问远端 | 建议`./dev harness check`，容器适配需保持linked worktree和公共目录身份 |
| [check_markdown_links.py](../../scripts/check_markdown_links.py) | 链接校验；组合文档检查导入，旧独立CLI仍存在 | Python/Git、源码只读 | 保留内部/兼容入口，由`check docs`覆盖，无需再加一个公开命令 |
| [check_module_boundaries.py](../../scripts/check_module_boundaries.py) | 特定稳定模块导入边界；CI和dev check调用 | Python AST，源码只读 | 保留`./dev check`覆盖；可提供`./dev check boundaries`定向检查 |
| [check_python_quality.sh](../../scripts/check_python_quality.sh) | 固定Ruff0.16.8全量格式/lint；CI调用 | uv/Python、缓存和可能的工具下载；格式check不修改源码 | 由`./dev check`/`./dev check python`在容器复用同一入口，保持工具版本和覆盖范围一致 |
| [compose_volume_reset.py](../../scripts/compose_volume_reset.py) | PostgreSQL/Qdrant重置共享实现；无独立CLI | Docker/Compose、标签校验、确认；删除并重建指定数据卷 | 内部保留，接入重置命令时先适配当前Compose上下文 |
| [container_tasks.sh](../../scripts/container_tasks.sh) | 容器测试/check/evaluate编排；dev委派 | Docker；测试临时网络/数据库、临时构建输出与报告；evaluate可调用LLM | 继续作为dev内部执行器，不公开`container-tasks`命令 |
| [install_git_hooks.sh](../../scripts/install_git_hooks.sh) | 首次clone安装Hook；Runbook/AGENTS和测试引用 | Bash/Git；写local core.hooksPath，拒绝覆盖其他Hook | 直接复用为`./dev hooks install`；不依赖.env或Docker |
| [loopback_probe.sh](../../scripts/loopback_probe.sh) | 端口与回环HTTP探测函数；dev up source及测试 | Bash、网络探测；不停止占用进程 | 内部保留，由up/doctor使用 |
| [markdown_content.py](../../scripts/markdown_content.py) | Markdown行解析；文档/链接检查共享库 | Python，无独立操作 | 内部保留 |
| [metadata/export_schema.py](../../scripts/metadata/export_schema.py) | mart_sales物理结构导出CLI；Architecture和测试引用 | Python/psycopg、DB配置；数据库只SELECT，但写tables/columns/relationships JSON；当前连接配置使用migrator | 建议`./dev metadata export`，适配容器内连接、宿主输出路径和源文件权限；输出变化后索引另行显式重建 |
| [metadata/export_schema_database.py](../../scripts/metadata/export_schema_database.py) | catalog读取与结构对象组装；导出CLI导入 | psycopg、只读系统目录查询 | 内部保留，无独立命令 |
| [metadata/export_schema_input.py](../../scripts/metadata/export_schema_input.py) | 读取本地配置和已有字段示例；导出CLI导入 | Python、文件只读；配置含连接凭据不输出 | 内部保留；容器适配需保持正确配置来源 |
| [metadata/export_schema_models.py](../../scripts/metadata/export_schema_models.py) | 结构投影数据模型、固定输出名；导出CLI/测试导入 | Python，无独立操作 | 内部保留 |
| [metadata/export_schema_output.py](../../scripts/metadata/export_schema_output.py) | 生成并写结构JSON；导出CLI导入 | Python，写派生源文件 | 内部保留，由metadata export调用 |
| [reset_dev_postgres.py](../../scripts/reset_dev_postgres.py) | 删除并重新初始化开发PG卷；软件测试引用，未接dev | 当前由宿主Python调用Docker；删除Sales与Control数据，再以sys.executable执行迁移；无管理员自动创建 | 需适配后才可接`./dev reset postgres`；限定开发项目，保留确认、卷归属校验，协调API停止与显式重新初始化 |
| [reset_dev_qdrant.py](../../scripts/reset_dev_qdrant.py) | 删除并重建开发Qdrant卷；软件测试引用，未接dev | 当前宿主Python调用Docker；删除索引与集合，默认交互确认，支持显式--confirm | 需适配后接`./dev reset qdrant`；仅开发项目，保留确认与标签校验，索引另行显式重建 |
| [run_database_tests.py](../../scripts/run_database_tests.py) | 老独立CI/development PG测试runner；相关测试和skip提示仍引用 | Python/Docker；隔离DB/清理；通过宿主sys.executable执行migration/pytest | 日常统一使用现有`./dev test database`；先核对独有profile/Windows路径能力与引用，再决定归档或兼容，不公开第二套同名runner |
| [smoke_web.py](../../scripts/smoke_web.py) | 打包网页/API登录Smoke；CI专用账号调用 | Python/httpx、显式测试凭据；登录/登出，必要时给测试账号生成随机密码并改密；不调用LLM | 保留CI专用；若纳入`./dev test smoke`，必须配套隔离资源/专用账号和清理，不直接接受日常管理员凭据 |
| [start-dev.ps1](../../scripts/start-dev.ps1) | 旧Windows宿主启动器；当前Runbook未推荐 | PowerShell/Docker/宿主uv/npm；开两个终端，宿主启动API/Vite，npm ci；只检查HTTP存活 | 与现行容器统一入口冲突。建议退出现行支持；若要Windows快捷入口，只能另行确认薄WSL/dev委派，不恢复第二套宿主流程 |
| [verify_container_app.sh](../../scripts/verify_container_app.sh) | 标准应用空卷、真实业务、导出/重启/清理验收；Runbook调用 | Docker、工具/应用/浏览器镜像、.env；真实LLM；独立PG/Qdrant/model/RAG卷与账号，按project清理；读取配置路径固定root/.env | 复用为`./dev verify app`；显示费用/耗时，核对配置选择与镜像准备前提；保留原脚本直接调用 |
| [verify_container_dev.sh](../../scripts/verify_container_dev.sh) | 源码容器实际运行验收isolated/real；Runbook调用 | Docker、Git、模型缓存、配置；构建/迁移、真实LLM、专用账号；热更新临时改源码并恢复；isolated清理临时卷，real重启日常服务 | 复用为`./dev verify dev [isolated\|real]`；默认isolated，real需显式选；保留资源与凭据清理及报告身份 |

## scripts 外的实际操作入口

| 入口 | 当前用途与副作用 | dev接入建议 |
| --- | --- | --- |
| 根[dev](../../dev) | 环境、初始化、测试/check/evaluate薄路由；隐藏evaluate-tools为内部委派 | 保持既有命令兼容，分类帮助；内部委派不作为用户操作列出 |
| [Bootstrap CLI](../../src/bootstrap/commands.py) / [__main__](../../src/bootstrap/__main__.py) | migrate、create-admin、prepare-model、build-rag、verify；显式写Schema/账号/模型/索引或只读验初始化 | 开发前四项已有dev入口；标准应用初始化与只读verify可由app分组委派。新增recover-admin另有已确认信任边界 |
| [Evaluation CLI](../../evaluation/__main__.py) | 单轮、多轮、分析、辅助理解；正式链路真实LLM，读取业务数据、写报告 | 保持`./dev evaluate [参数]`，费用说明与报告身份保留 |
| [real_e2e_acceptance](../../evaluation/common/real_e2e_acceptance.py) | 确定性报告身份/案例/分数校验；CI调用；无LLM/DB业务执行 | 建议`./dev evaluate validate [原参数]`；只读报告，不能替代真实评测或容器验收 |
| [bootstrap/readiness.py](../../src/bootstrap/readiness.py) | 应用监控子进程，真实依赖/资产只读探测 | 保留应用内部入口；doctor可复用适用检查，不复制就绪判定 |
| [export_assets.py](../../src/query_api/export_assets.py) | Dockerfile构建时写字体/浏览器/导出资源manifest | 保持构建内部，由build/check覆盖，不公开独立导出资产命令 |
| [export_worker.py](../../src/query_api/export_worker.py) | Application管理的受限导出子进程，写文件，依赖父进程存活与资源限制 | 保持应用内部，不能提供绕过授权/快照/额度的dev入口 |
| [10_chatbi_dev_environment.sh](../../database/init/10_chatbi_dev_environment.sh) | 空卷PG初始化、角色、Seed、Control DB基础Schema | 数据库容器内部，由infra/初始化链执行；不得普通启动重复重播Seed |
| [wait_for_base_initialization.sh](../../database/init/wait_for_base_initialization.sh) | PG基础初始化有界等待 | 内部保留，由migrate/验收委派 |
| [healthcheck.sh](../../database/init/healthcheck.sh) | PG角色、Seed、checkpoint与权限只读检查 | Compose健康检查内部保留；status/doctor展示必要状态 |
| [.githooks/pre-commit](../../.githooks/pre-commit) | Git自动调用的分支护栏 | Git自动运行；只公开hooks install，不新增手动pre-commit命令 |
| [frontend npm scripts](../../frontend/package.json) | dev、typecheck、build、build:export、test、test:dev、test:real | 容器up/build/check/test web已覆盖主链；保持Node内部命令，避免额外暴露每个npm脚本 |
| [playwright.real.config.ts](../../frontend/playwright.real.config.ts)及test:real | 旧真实浏览器链：宿主uv启动测试应用，真实LLM、专用账号/报告 | 现行完整容器验收已有替代主入口；先检查独有断言/兼容需求，再决定迁移/归档，不直接包装旧宿主路径 |
| [.devcontainer配置](../../.devcontainer/devcontainer.json) | 编辑环境/工具装配与postCreate依赖安装 | 保持可选编辑环境；dev仍是运行入口，不新增另一套启动命令 |
| [CI workflow](../../.github/workflows/ci.yml) | 质量、软件/数据库/浏览器/renderer、Smoke与依赖审计 | 保留CI编排和脚本复用；dev统一本机操作不意味着本机模拟所有GitHub任务 |
| [Real E2E workflow](../../.github/workflows/real-e2e.yml) | 专用CI环境真实模型/RAG/三套基线与诊断 | 本机已有evaluate/报告校验；CI可继续直接调用同一Python能力 |
| [Auto-merge workflow](../../.github/workflows/enable-auto-merge.yml) | 已授权PR的远端自动合并 | 属于交付流程，不纳入开发工具命令或自动发布 |
| container-auto-restart候选`scripts/start_dev_api.py` | `fd9be30`开发API控制库等待/exec热重载入口 | 内部保留，由dev up启动；待其独立交付后合并事实，当前基线没有该文件 |

## 已发现的接入前差异

1. **旧宿主执行路径**：start-dev.ps1、run_database_tests.py、reset_dev_postgres.py和前端test:real中仍有宿主uv/npm/sys.executable调用。直接包一层dev并不能满足当前“宿主只需Git/Bash/Docker”的Contract。
2. **Compose上下文分散**：dev使用指定env-file及两份Compose，并可追加override；旧重置库只调用默认docker compose，不能保证跟随dev选中的环境和覆盖配置。必须统一解析目标与卷身份后才能公开删除操作。
3. **标准应用缺dev日常入口**：Runbook仍通过长Compose命令构建、启动、迁移、准备资产、创建账号和停止。若目标是统一所有现行人工操作，app分组也需纳入，不能只添加app验收/密码恢复。
4. **质量入口版本差异**：CI通过check_python_quality.sh固定Ruff0.16.8；container_tasks.sh直接调用镜像内python -m ruff，没有在该路径固定同一版本。统一时应复用CI约定入口，不把两条路径混称完全相同。
5. **Smoke有账号写入**：smoke_web在must_change_password时生成随机新密码并改密，CI对专用账号使用是现有事实；直接让用户传日常管理员账号会改变真实密码，不适合作普通健康检查。
6. **linked worktree身份**：dev evaluate-tools当前挂载root/.git；linked worktree的.git是指向公共目录的文件。评测身份和新增harness命令的容器适配必须按git-common-dir核实，不能仅凭挂载.git宣称Git证据有效。
7. **配置来源不完全统一**：verify_container_dev支持CHATBI_DEV_ENV_FILE，verify_container_app直接读取root/.env；check_dev_qdrant和metadata export也有各自的文件/地址规则。统一入口需要明确每项命令实际读取的配置，避免同名命令检查错环境。

这些是源码可核实的接入差异，不是本轮已运行得出的故障或完整测试结论。除已确认的管理员恢复边界外，适配、归档及新增命令范围仍需用户决定。

## 建议命令地图

以下新增语法是讨论方案，尚未实现；保持现有根命令默认作用于开发环境，app使用独立分组，内部辅助模块不逐文件暴露。

| 分组 | 命令 | 当前状态 / 建议 |
| --- | --- | --- |
| 帮助 | `./dev help` | 已有简短帮助；改为分类说明、用途和副作用 |
| 开发环境 | `./dev build/up/down/status/logs/infra` | 已有，保留兼容 |
| 开发初始化 | `./dev migrate/create-admin/prepare-model/build-rag` | 已有，保持显式初始化 |
| 标准应用 | `./dev app build/up/down/status/logs/infra/migrate/create-admin/prepare-model/build-rag/check` | 建议新增；复用标准Compose，check为只读初始化检查，明确与完整验收不同 |
| 质量检查 | `./dev check`；`./dev check docs/python/boundaries` | 总检查已有；定向分组建议新增，复用原能力和固定工具版本 |
| 软件测试 | `./dev test python/database/web/renderer/all` | 已有，不公开第二套同用途runner |
| AI评测 | `./dev evaluate [原参数]`；`./dev evaluate validate [报告参数]` | 运行已有；只读报告校验建议新增 |
| 容器验收 | `./dev verify dev [isolated\|real]`；`./dev verify app` | 已有实现，建议加路由；真实LLM/资源修改说明 |
| 运行诊断 | `./dev doctor` | 建议新增；复用就绪/Qdrant等检查，不改密、不收费探测LLM |
| 结构维护 | `./dev metadata export [参数]` | 建议新增并适配；数据库只读、写结构文件，索引另行重建 |
| 开发重置 | `./dev reset postgres/qdrant` | 建议纳入高级维护；先适配环境身份，只限开发资源、保留删除确认 |
| 协作维护 | `./dev hooks install`；`./dev harness check [参数]` | 建议新增；分别修改local Git配置与只读检查，不要求业务配置 |
| 管理员恢复 | `./dev recover-admin dev/app --username NAME` | 新能力，信任边界/环境范围已确认，完整Spec仍待确认 |
| CI专用Smoke | 无普通doctor/smoke入口 | 保留专用账号链；以后若需要本机Smoke，先确认隔离测试模式 |

## 下一步与范围决定

推荐范围：统一现行人工操作入口，包含开发与标准应用、质量/测试/评测/验收、诊断/结构维护、Hook/Harness，以及管理员恢复。开发数据重置只有在目标解析与删除确认适配后接入；旧宿主启动/重复runner先明确独有能力与历史去向，再退出现行支持。

盘点完成时原三项Spec尚未覆盖本表建议；用户随后确认分类统一方向，已将具体范围和行为写入[更新后的完整Spec](spec.md)，原草案归入[历史](history/spec-three-entrypoints.md)。完整Spec与七项拆分已由用户确认，Design Review PASS、Readiness READY；当前完整本地实现已授权。以下原检查描述仅指初始盘点，不冒称当前实现结果。

## 覆盖与本轮检查

- scripts表包含基线Git跟踪的全部24个文件；外围实际执行入口与待发布候选分别列明。
- 文件内容、AST可执行入口、命令参数、源码引用及当前Runbook/CI消费者已核对；“无现行调用方”仅指已查当前源码/文档/CI，不否定外部个人调用。
- 只做文档/本地链接与Diff检查；没有运行产品测试、真实容器验收、LLM、重置或管理员恢复，不声明这些工具本轮运行通过。
- Harness REVIEW归属：本工作区修改是已授权盘点记录；container-auto-restart保留分支及待发布授权属于前一独立目标，不混入本次范围。


## 最终处置台账（当前候选）

| 基线文件/能力 | 最终入口或归属 | 兼容与独有能力去向 |
| --- | --- | --- |
| __init__.py | Python内部包 | 保留，无独立命令 |
| check_dev_qdrant.py | doctor复用原安全HTTP探针；原脚本兼容保留 | 5秒安全健康探针保持；doctor新增总预算与项目地址，不改密 |
| check_documentation.py、check_markdown_links.py、markdown_content.py | check docs及完整check内部 | 原组合检查与链接能力，CI直调保留 |
| check_harness_state.py | harness check | 普通clone/linked worktree/common-dir、指定repo和json参数保持；只读 |
| check_module_boundaries.py | check boundaries及完整check | 原AST范围与CI直调保持 |
| check_python_quality.sh | check python及完整check | 同一CI入口固定Ruff0.16.8；缓存置于容器/tmp |
| compose_volume_reset.py | 纯配置/归属校验复用，旧内部编排兼容保留 | 不公开；新重置宿主编排正确传递dev上下文、停API/Web及二次校验 |
| container_tasks.sh | test/check/evaluate/Harness内部执行器 | Git/宿主路径适配，普通工具不挂socket |
| install_git_hooks.sh | hooks install | 当前命令clone本机安装，拒绝其他Hook；直接脚本保留 |
| loopback_probe.sh | up内部端口/HTTP探针 | 原端口占用保护保持，不公开 |
| metadata/export_schema.py及四个export_schema_*内部模块 | metadata export | 原参数/直调保留，容器runtime配置显式扩展，catalog仅SELECT；宿主UID输出 |
| reset_dev_postgres.py、reset_dev_qdrant.py | reset postgres/qdrant；旧main委派同一dev编排 | 保留可导入纯helper和旧内部能力；直接CLI不再使用默认Compose错误上下文 |
| run_database_tests.py | 非推荐旧宿主兼容runner | 当前test database覆盖ci/development及清理；旧单profile选择、Windows路径映射独有能力未证明完全替代，保留源码/测试；skip提示改为dev |
| smoke_web.py | CI专用账号Smoke | 未公开为doctor，保留可能改密的CI链 |
| start-dev.ps1 | 仅提示WSL/dev，退出2 | 旧uv/npm实现保存history/start-dev.ps1.md；当前不另建Windows启动流 |
| verify_container_dev.sh、verify_container_app.sh | verify dev默认isolated/显式real；verify app | 原脚本/报告/退出/清理/LLM链保留；app源配置支持CHATBI_APP_ENV_FILE |
| frontend test:real及real.spec.ts | 非推荐旧宿主兼容验证 | 独立SQL真值、同历史追问及两期分析全部断言保留；未用入口统一删除独有覆盖，当前推荐容器验收 |
| Bootstrap/Evaluation/数据库初始化/导出worker/CI | 所属流程内部或现有dev入口 | 不新增任意内部模块公开命令，不新增GitHub发布/合并命令 |

新实现文件：dev_environment.sh集中目标/Git/宿主路径和共享临时目录；dev_maintenance.sh维护宿主编排；dev_compose.py纯JSON筛选/校验/路径映射；python_quality.py容器复用CI质量入口；docker/dev-project-name.yml只维持Dev Container宿主项目身份。均为内部能力，没有逐文件公开命令。

Source of Truth：当前行为见正式Runbook、容器/Bootstrap及admin-recovery Contract；本表记录迁移去向，验证结论见本工作项acceptance与Review，不使用基线建议冒充结果。24/24基线文件均有处置，旧独有验证保留有明确理由；用户未授权远端发布。

## 发布基线补充

前一自动重启目标已由PR #83合入master@11ff5d2；其start_dev_api.py为API容器内部启动入口，由Compose调用，不新增日常dev命令。本文前半部的fd9候选身份仍是初始盘点时的历史事实，当前基线以发布记录为准。本目标新增dev_environment.sh（目标/路径）、dev_maintenance.sh（宿主维护编排）、dev_compose.py（纯配置/归属校验）与python_quality.py（CI质量委派）四个内部辅助文件，均由公开命令链调用，不按文件名公开独立日常操作。

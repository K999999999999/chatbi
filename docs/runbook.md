# ChatBI Runbook（运行手册）

## 1. 前提与配置

所有命令从仓库根目录的WSL / Linux Bash执行。宿主只需Git、Docker Engine、Compose（隔离验收要求至少2.24.4）；不需要宿主Python、uv、Node、`.venv`或`node_modules`。开发镜像准备依赖，Compose组织服务，`dev`提供统一开发入口。

```bash
test -e .env || install -m 600 .env.example .env
./dev hooks install
```

已有配置不要覆盖。`.env` 必须由当前 Linux 用户拥有且仅当前用户可读；建议权限为 `600`。开发入口在把配置交给 Compose 前、直接读取配置的脚本在读取前都会检查属主和权限，不安全时拒绝且不显示配置内容；按提示检查属主并执行 `chmod 600 .env`。`./dev help` 不读取配置。Git Hook脚本只修改当前clone的local hooksPath，遇到已有其他有效Hook会拒绝覆盖；按[Git流程](agents/git-pr-workflow.md)保留并处理。

填写 `.env` 的 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`、数据库密码、Qdrant Key和随机 `CHATBI_ADMIN_SECRET_KEY`。模板中的本地演示密码仅用于回环环境；真实配置不进入Git、镜像或报告。构建前可以用以下基础容器命令生成签名Key，再自行填写到本地配置：

```bash
python_base=$(sed -n 's/^ARG PYTHON_BASE=//p' docker/python-dev.Dockerfile)
docker run --rm --entrypoint python "$python_base" -c 'import secrets; print(secrets.token_hex(32))'
```

默认Web5173、API8000、PostgreSQL5433、Qdrant6333/6334只绑定回环。`CHATBI_DEV_WEB_PORT`、`CHATBI_DEV_API_PORT`、`POSTGRES_PUBLISHED_PORT`可以调整端口；`CHATBI_DEV_ENV_FILE`选择独立配置，`CHATBI_DEV_COMPOSE_OVERRIDE`用于隔离验收。首次build前完成必需配置，启动API前确保LLM配置有效。

业务库 `chatbi_mvp` 的 `mart_sales` 由 `chatbi_app` 只读访问；控制库 `chatbi_control` 使用独立账号，保存用户、权限、Session、历史、执行和checkpoint。迁移身份只提供给初始化工具，API不挂载 `.env`。

## 2. 开发与本地体验

### 首次启动

```bash
./dev build
./dev infra
./dev migrate
./dev create-admin --username admin-1
./dev prepare-model
./dev build-rag
./dev up
```

打开 `http://127.0.0.1:5173`，首次管理员登录后按要求修改密码，再创建使用账号。管理员密码隐藏交互输入，不作为命令参数或Seed。

`infra`先启动PG/Qdrant；`migrate`等待基础初始化、迁移Control DB和checkpoint，再等待完整PG健康。新空卷创建合成Sales Mart演示数据；日常启动不重播Seed。`prepare-model`下载固定revision BGE-M3，复用 `.model-cache`；`build-rag`校验并原子发布索引，失败保持已有发布资产。首次下载/CPU构建可能较慢。

### 日常使用

```bash
./dev up
./dev status
./dev logs --follow
./dev down
```

四个常驻服务统一使用`restart: unless-stopped`。首次通过`./dev up`启动后，运行中的服务在Docker重启时自动恢复；电脑重启后仍需Docker Engine / Desktop先启动。`./dev down`主动停止后保持停止，直到再次执行`./dev up`；停止保留数据库/Qdrant卷、模型与RAG资产。禁止将删除volume当作常规停止方法。

自动恢复只启动已有容器，不执行构建、迁移、管理员创建、模型下载或索引重建；一次性tools/migrator保持不自动重启。配置变化后执行`./dev up`应用新配置，依赖变化后先build。自动恢复后可用`./dev status`和`/ready`确认就绪。

Docker自动恢复时依赖可能晚于API启动；开发API先有界等待控制库，再启动热重载进程，超时退出后由Docker重试。网页容器启动不代表后端已经可用，仍以`/ready`为准；缺少migration或索引时按首次准备步骤显式处理。

源码从宿主挂载，Python自动重载、Vite热更新。依赖/锁文件或根配置变化后build再up；环境配置变化后up重建容器。重载不保证进程内会话持久，历史按正式Contract只读恢复，不自动重发请求。不要同时运行两个写同一Control DB的history runtime。

API的模型与RAG挂载只读，初始化工具可写。容器保持当前宿主UID/GID与模型路径身份，不重写已有数据所有权。本地Embedding沿用CPU/FP32，不承诺GPU或性能。

### 容器调试

```bash
docker run --rm -it --user "$(id -u):$(id -g)" -v "$PWD:$PWD:ro" -w "$PWD" --entrypoint python chatbi-python-dev:local -m pdb -m pytest tests/query_api/test_operations_state.py
```

用容器内pdb查看断点和变量；调试运行中的应用时先停止原API，再以同一Compose配置交互运行单个API，避免第二个history runtime。项目不再提供 VS Code Dev Container 编辑配置；从 WSL / Linux Bash 使用统一 `./dev` 入口。

## 3. 验证与CI

```bash
./dev check
./dev test python
./dev test database
./dev test web
./dev test renderer
# 汇总执行以上四套测试，不调用真实LLM
./dev test all
```

`./dev check docs`、`./dev check python`、`./dev check boundaries`仅执行所选检查；Python与CI共用固定Ruff0.16.8入口，format与lint覆盖`src/`、`evaluation/`、`tests/`和`scripts/`，定向通过不等于完整check通过。帮助`./dev help`不读取.env或访问Docker。

check包含锁文件、文档/链接/模块边界、Python质量和网页/导出构建。Python全量回归不等于数据库或renderer验证；database分别启动独立CI/development fixture，覆盖真实权限、迁移、checkpoint、history和execution。并发History用例只观察自己 worker 的 PostgreSQL backend PID；失败时先释放本用例锁，再限时取消 / 回收自己创建的连接，故障路径也由有时限的子进程验证。web使用隔离mock API和浏览器；首次改密用例由`tests.browser_support`按用例创建独立测试账号，并清理其Session / 账号，管理路由不进入生产App。renderer启用真实Chromium/PDF与字体。失败返回非零，汇报skip和未执行范围。

CI保留`PostgreSQL integration` job及其临时PostgreSQL服务，依次运行与本地相同的CI / development数据库fixture、migration、测试选择和开关，再用`docker/python-dev.Dockerfile`构建测试依赖镜像运行真实PDF renderer（不是业务APP镜像）。pytest JUnit、renderer本地摘要和安全环境身份分开保存在`reports/ci/`、`reports/tests/`；artifact步骤在前置测试失败后仍尝试上传可得证据，绝不写入`reports/evaluation/`。CI实际结果以对应GitHub Actions运行记录及artifact为准；本地提交不会代替托管CI执行。

该job在上传artifact前强制核验`postgres-ci.xml`、`postgres-development.xml`及renderer JSON / JUnit：三个报告都必须存在、可解析、至少包含一个实际通过的测试且零失败 / 错误 / 跳过；renderer摘要计数必须与JUnit一致，源码提交、`uv.lock`摘要和测试镜像身份必须与CI环境记录一致。任何报告缺失、损坏或不完整都会使该job失败；原始报告仍会在失败后尝试上传以便诊断。

每次`dev test` / `dev check`都会创建`reports/tests/<run_id>.json`摘要，不覆盖既有运行；JUnit / Playwright原始机器结果按同一Run ID保存。摘要显示源码起止身份、命令范围、各步骤状态、退出 / 清理结果、测试计数，以及适用的`uv.lock` / `package-lock.json` SHA-256和实际Python / Node / Browser / PostgreSQL容器镜像ID；环境身份无法核实也不会显示完整通过。check的构建 / lint步骤计数为null（不适用）。测试计数缺失、存在skip、来源身份变化 / 无法核实或后续步骤未运行时，摘要不会显示完整通过；因此命令退出码为0不等于所有测试均已通过。目录本地ignored；一般本地验证不上传CI或写入Git，CI仅按上段规则选择性上传测试证据。

宿主Bash负责Docker资源创建与清理，测试程序在容器执行。结构测试可只读挂载Compose CLI解析配置，测试容器无Docker socket，业务API无Docker权限。临时数据库/网络按本次标签清理，不能修改日常数据。CI仍可以内部使用uv/npm，不要求开发者在宿主安装它们。

软件测试直接验证容器中挂载的当前源码，不需要构建独立业务APP镜像。旧`app`、`verify app`等命令以状态码2拒绝；已有APP容器、镜像、卷、配置和资产不会自动删除或迁移，开发维护入口也不会把旧APP资源当作dev目标。

真实容器业务验收显式执行，会产生少量LLM调用费用；只使用独立临时资源和专用账号：

```bash
./dev verify dev # 默认isolated；也可显式传isolated
```

`./dev verify dev real`显式验收日常开发环境，会重启服务并执行专用账号操作；热更新写入仅在默认isolated阶段执行，real阶段跳过该隔离专用用例。默认isolated使用独立Compose project、专用卷、临时RAG输出和当前worktree私有的固定revision模型缓存。原scripts/verify_container_*.sh仍可直接调用，退出码、报告、clean要求与清理规则保持。

`verify dev`的业务验收与`dev test`软件测试身份分开。运行中可变的`browser.json`留在私有暂存目录；完成账号 / 临时资源清理后，排他发布唯一摘要到`reports/browser-real/<run_id>.json`，相关证据位于`reports/browser-real-artifacts/<run_id>/`。摘要关联浏览器机器计数、源码起止身份、清理状态和`runtime.json`；该文件的模型身份由应用内实际`RAG_MODEL_DIR/config.json`生成。宿主`npm run test:real`也使用独立run目录与不可覆盖最终JSON；它不是日常软件回归入口。真实业务验收需要远端模型调用，不由`./dev test all`自动触发。

isolated热更新把`src/query_api/app.py`和`frontend/src/style.css`覆盖挂载为本次临时目录中的可写副本，其余源码目录保持只读；Playwright只改写这两份副本。退出清理从私有备份恢复副本并核对SHA-256，恢复失败会使验收失败并保留备份。INT/TERM进入清理路径；SIGKILL不可捕获，精确Compose project、覆盖文件和恢复备份保存在输出的`/tmp/chatbi-container-verify.*`目录中，可按其中`hot-reload/recovery-manifest.txt`恢复。验收账号身份在事务提交前写入私有pending记录；异常时按精确用户ID和用户名禁用账号并撤销Session，不按用户名片段批量处理。运行记录绑定候选、镜像、模型、Seed、RAG和资源身份。历史验收不能重标为当前候选。

## 4. AI Evaluation

```bash
./dev evaluate --help
./dev evaluate --online-retrieval
./dev evaluate --query-understanding
./dev evaluate --business-analysis --online-retrieval
./dev evaluate --multi-turn --online-retrieval
```

初始化并启动对应开发基础设施，使用真实LLM配置和现有固定案例；不自动重建RAG、不修改评测案例。报告写入ignored `reports/evaluation/`，只适用于记录的提交、案例与模型/数据/资产身份。基线对比可以继续传递评测原参数，容器路径统一使用 `/workspace/reports/evaluation/`。Secret和原始敏感内容不得进入报告。

评测工具容器沿用本地 `CHATBI_OBSERVABILITY_ENABLED`、OTLP trace endpoint 和 headers；内容采集在评测容器中固定关闭。需要本地查看 Span 时，在本地 `.env` 显式设置 `CHATBI_TRACE_CONSOLE_EXPORT_ENABLED=true`，重建并重启 API 后可通过 `docker compose logs --since 10m api` 查看；Evaluation tools 自身的 Span 通过其容器日志查看。该开关只在 local/dev/test 生效，并把同一批经过安全属性过滤的 Span 同时发送到配置的 OTLP 后端。Trace 导出失败不阻断评测。

每次运行先记录起点 Git / 案例 / 上下文指纹，在评测与必要清理后再记录终点；报告 `provenance.consistency` 为 `stable`、`changed` 或 `unverified`。运行中源码或输入变化仍可生成诊断报告，但不能用于正式 clean 验收；Git 或输入身份无法读取时不得按 stable 处理。Run ID 含时间、短提交、套件和随机部分，同名 JSON / Markdown 通过排他创建防覆盖；保存冲突或部分写入会失败，不会覆盖旧证据。历史报告仍可读取和参与既有 Baseline 比较，但缺少新 provenance 的旧报告不能通过新的正式验收。

报告仅记录非敏感的有效模型配置：temperature、max_tokens、有效 timeout、Endpoint Hash 及其规范化配置 Hash，不写 API Key 或完整 Endpoint。经营分析另记 Judge 配置和 Hash；Judge temperature 为 `0`，与业务模型 temperature 分开。辅助 Query Understanding 报告记录实际语义题集 Hash；该套件不适用的数据库指纹保持缺省，不造值。

评测报告的确定性校验（无LLM、无业务查询）：

```bash
./dev evaluate validate --report-dir reports/evaluation/BASELINE --expected-commit FULL_SHA --expected-rag-version RAG_VERSION
```

保留原验收器的report/cases/suite参数与完整提交、RAG、案例身份检查。普通clone和linked worktree均使用真实Git公共目录；WSL/Linux直接映射；已有容器调用方可通过LOCAL_WORKSPACE_FOLDER映射宿主源路径及默认开发项目名，临时测试挂载保存在共享工作区的ignored .local/dev-tools并按宿主路径传递；COMPOSE_PROJECT_NAME及用户override保持优先。Git公共目录在工作区外且宿主路径不同的linked worktree，可用CHATBI_GIT_COMMON_DIR_HOST显式提供同一公共目录的宿主位置；挂载必须匹配，Git检查失败不能当作clean。

托管 Real E2E 在构建 RAG 前运行 `prepare-model`，并把固定 revision 对应的本地模型目录用于索引构建和后续在线评测；模型准备失败会阻断构建与正式评测。旧 PostgreSQL 兼容测试入口的 readiness 探测和开发 fixture 查询均通过容器内 `127.0.0.1` TCP 服务，不以初始化期间的 Unix socket 实例作为就绪信号。

## 5. 健康与故障处理

`/health`只表示HTTP存活，`/ready`才反映应用依赖就绪；模型状态来自近期真实调用，不做定时收费探测。管理员可以查看依赖、模型和执行额度，网页不显示备份状态；刷新不延长登录期限。应用保护见[就绪Contract](specs/application-readiness.md)。

- 缺少配置：检查 `.env` 必需字段；权限拒绝时检查属主并执行 `chmod 600 <配置文件>`；不要输出完整Compose配置或Secret定位。
- 首次PG不healthy：先执行migrate，不等待未迁移的checkpoint健康状态。
- 模型/索引未准备：显式prepare-model/build-rag；来源校验失败不能通过删校验或静态回退解决。
- 端口占用：调整本项目端口后重试，不杀未知进程；确认实际网页Origin随端口更新。
- 业务拒绝或执行繁忙：按API安全提示处理，不绕过权限、SQL Guard或共享额度。
- 导出失败：检查镜像中的Chromium、字体、导出manifest与seccomp；保持sandbox，不以关闭保护换取成功。
- 停止后找不到历史：检查是否使用同一Compose项目/数据卷，不能用重播Seed或删除卷修复。

OTel/OTLP诊断可选，默认关闭；端点/认证配置只在本地，内容采集关闭。诊断不可用不能改变业务结果。详见[Observability](specs/observability.md)。

## 6. 诊断、结构维护与开发重置

```bash
./dev doctor          # 默认dev，只读、有界，不启动或修复服务
./dev metadata export --output-dir /path/to/structure
./dev reset postgres
./dev reset qdrant
./dev harness check
./dev harness check --work-item WORK_ITEM --json
./dev harness check --closeout WORK_ITEM --json
python -m scripts.check_harness_state --json
./dev harness control --plugin-source /path/to/agent-plugins state --work-item WORK_ITEM --json
```

doctor检查选中项目的依赖、health/ready、网页与必要资产；缺失/未知不报告就绪，LLM标记not_probed，不收费探测、不改密。需要已有工具镜像；缺服务或资产时安全失败，不自动补齐。

metadata使用开发项目已配置的既有结构导出权限，只执行catalog SELECT，写tables/columns/relationships JSON；默认输出src/structure/generated，也可用--env-file选择配置。保持宿主UID，不改Semantic或业务数据；源结构变化后的build-rag仍需显式执行。

reset仅支持明确选中的开发项目。PG删除Sales Mart及Control DB账号、Session、历史和成果；Qdrant删除集合和索引。核实项目/卷并输入DELETE POSTGRES DATA或DELETE QDRANT DATA；自动化可显式--confirm。取消/EOF、外部卷、标签不符或停止失败均不删除。命令先停止本项目API/Web和目标服务，再验证卷身份后删除；其他卷、模型缓存、旧APP与Stable资源保持。PG重建Seed并迁移但不创建管理员；Qdrant仅重建，需显式build-rag。结束后API/Web保持停止，按初始化步骤显式up。删除不可回滚，不能作为普通故障修复。

Hook入口修改当前clone的本机hooksPath。`./dev harness check` 与 `python -m scripts.check_harness_state` 仍只读本机Git和公共目录记录，不访问远端，也不修改进度或分支；检查全部登记工作树，容器入口将其源码只读挂载。显式归属 / 收尾参数及旧记录兼容边界见[工作树归属与收尾](agents/issue-tracker.md#工作树归属与收尾)。

源码、配置、Plugin 和 Git 的 Docker bind mount 使用 `--mount` 或 Compose `create_host_path: false`，并在调用 Docker 前验证宿主源存在。本机 Docker Desktop 的真实验证发现仅靠 `--mount` 仍可能创建缺失路径，因此必须保留调用前校验。已有容器调用方若看不到 `LOCAL_WORKSPACE_FOLDER` 指定的宿主路径，会明确失败，应从可验证该路径的宿主环境调用。报告等显式输出目录由命令有意创建；缺失源码目录不得自动补成空目录。旧 worktree 删除后出现 `package.json` 等同名空目录时，核对旧命令的挂载源与映射，不要反复删除后继续运行旧路径。

### Harness Task Control

`./dev harness control` 是独立的 Plugin Harness 入口，不改变旧 `harness check`。`--plugin-source` 可指向包含 `plugins/engineering-workflow` 的只读源码仓库根目录，也可直接指向含 `.codex-plugin/plugin.json` 和 `tools/harness.py` 的 Plugin 包根目录；也可通过 `CHATBI_ENGINEERING_WORKFLOW_SOURCE_ROOT` 指定。第一次使用时需确认路径来源与版本；路径可读不代表该版本已安装或已加载到当前 Codex 会话。

```bash
./dev harness control --plugin-source /path/to/agent-plugins state --work-item WORK_ITEM
./dev harness control --plugin-source /path/to/agent-plugins diff --work-item WORK_ITEM
./dev harness control --plugin-source /path/to/agent-plugins diagnostic report --work-item WORK_ITEM
./dev harness control --plugin-source /path/to/agent-plugins closeout check --work-item WORK_ITEM
./dev harness control --plugin-source /path/to/agent-plugins cancel --work-item WORK_ITEM --reason '停止原因' --confirmed-by '确认来源' --expected-sha RECORD_SHA256
```

适配使用已有 `chatbi-python-dev:local` 容器和宿主 Docker CLI，不要求宿主 Python / uv / Node；不构建或拉取镜像，不读 `.env`，不联网，不挂载 Docker socket。项目源码、Plugin 包、Git 公共目录只读；显式状态写命令仅将 `.git/harness/work-items/<work-item-id>/` 对应目录作为可写挂载。它不会创建状态记录，不批量迁移旧记录；读取旧记录时会标记 `legacy_read_only`，需要先由用户明确目标后显式执行 `migrate`。`cancel` 仅接受已迁移记录、`PRs: None`、非终态工作项和当前 SHA，并要求记录取消原因与确认来源；它保留 Stage 和历史，不完成交付收尾，也不删除分支 / worktree、关闭 PR 或级联修改 Ticket / 关联工作项。`done` 仍要求原有整体收尾证据。`onboard apply` 会修改项目文件，因此不通过此状态写入适配器执行。

容器内 `scripts.harness_control` 在调用 Plugin 前核验当前任务归属。state 在未绑定、checkout 不匹配或记录仍为 legacy read-only 时仍可读进度，但返回 `record_only: true`，candidate / closeout 等当前 checkout 派生字段为空；候选相关操作拒绝不匹配，且不执行状态写入。migrate、cancel、运行状态、诊断记录，以及 adapter 声明不需要 candidate 的早期阶段转换，继续按明确工作项与 Plugin 原有语义门禁执行，不要求创建无意义的开发分支。此 preflight 不替代 Plugin 的证据、阶段或授权门禁。

遇到取消状态或扩展格式不兼容时，先核实实际 marketplace、已发布源码及安装包内容。获准更新后使用 `codex plugin add engineering-workflow@MARKETPLACE` 等当前官方入口刷新，再验证受影响记录和源 / 安装摘要；不手改缓存。相同版本号不能证明文件一致，CLI 验证成功也不证明当前会话已重载，需按客户端支持方式在新会话确认。

缺少 Plugin 路径、包内 CLI、容器镜像或状态目录时命令以非零退出；它不会回退到 `harness check` 并声称新 Harness 已运行。GitHub CI 使用仓库内合成 Plugin fixture 检查调用参数和挂载边界；该测试只证明 ChatBI adapter 命令组装，不证明真实 Plugin 已安装、同步、加载或可在托管 CI 运行。旧 `run_database_tests.py` 和 `npm test:real` 保留独有 profile / Windows 路径及 SQL 真值 / 追问 / 分析断言的兼容能力，属非推荐旧宿主入口；统一推荐 `test database` 和 `verify dev`。旧 `start-dev.ps1` 只提示使用 WSL/dev，不再启动宿主 uv/npm。CI 专用 `smoke_web.py` 可能改专用测试账号密码，不作为 doctor 或日常账号检查入口。

## 7. 管理员忘记密码

```bash
./dev recover-admin dev --username admin-1
```

本机Docker操作能力和开发Control DB运行账号配置的持有者是可信运维操作者。显式指定dev和账号，终端隐藏输入临时新密码两次；不接受密码参数、环境变量或流水线。至少12位。只恢复现有启用admin，不创建账号、不授予角色、不启用禁用账号。

目标Control DB必须已运行且初始化，工具镜像必须包含恢复代码；缺镜像先显式build。恢复不依赖API/Web/LLM/Qdrant/RAG，不自动构建、启动或迁移。旧`app`目标在读取密码、连接数据库或修改账号前拒绝；不会搜索其他项目或旧Stable。

成功原子更新密码Hash、必须改密、清除登录锁/失败计数、撤销全部旧Session并写独立审计；审计失败全回滚，本机操作者不冒充被恢复账号。成功后用临时密码登录并立即改密。参数/非终端/两次输入不一致退出2，资源/账号/事务失败退出1，成功0，中断非零；提交不确定时不自动重试。详见[恢复Contract](specs/admin-recovery.md)。首次安装仍用create-admin，Web普通用户管理保持原职责。

## 8. 当前支持边界

本机Windows+WSL/Linux，单API进程与电脑端访问。业务定义、权限、数据结构、AI链路和评测案例不因部署精简变化。公网生产、多worker/副本、企业编排和备份恢复不在项目支持范围。

当前规则见[容器开发](specs/container-dev-environment.md)、[源码运行边界](specs/container-deployment.md)、[Bootstrap](specs/bootstrap.md)、[Evaluation](specs/evaluation.md)；历次部署与运行验收保存在所属 `.scratch` 历史记录。

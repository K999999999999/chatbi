# dev 分类统一入口与管理员紧急恢复

Status: 完整Spec、Design Review和七项Ticket拆分已确认；全部本地实现与适用验证获授权，已授权Push/PR及CI/自动合并收尾；当前对齐PR #83后的master基线。

## Problem Statement

当前开发、初始化、测试、评测已经由`./dev`组织，但帮助信息只有一行命令列表；标准应用、真实容器验收、结构维护、重置、诊断和协作检查仍使用分散入口，部分脚本还依赖旧宿主执行方式。唯一管理员忘记密码时，首次管理员创建不能重复执行，Web管理后台也无法登录，缺少受控的本机恢复入口。

需要让开发者记住一个工具入口，同时保留已有实现与CI复用；管理员恢复必须明确本机信任边界、目标环境、账号范围、事务与审计。

## 仓库事实与已确认决定

- [dev](../../dev)已经组织环境、初始化、测试、质量检查和评测；[Runbook](../../docs/runbook.md)区分软件验证与真实容器验收。
- `./dev test all`包含真实隔离PostgreSQL、mock API浏览器和真实Chromium/PDF/字体验证。容器验收额外覆盖完整装配、初始化、真实RAG/LLM、网页业务、持久性和恢复，二者不是互不重叠的验证层。
- [开发验收脚本](../../scripts/verify_container_dev.sh)支持isolated/real，默认isolated；[标准应用验收脚本](../../scripts/verify_container_app.sh)使用独立临时项目。两者实际业务验收均调用真实LLM。
- [首次管理员初始化](../../src/chatbi_control/bootstrap.py)在已有管理员时拒绝；当前Web密码重置与用户改密能力已经存在，保持其职责。
- 用户已确认：本机Docker操作权限与目标Control DB配置的持有者是可信恢复操作者，无需Web登录；恢复同时支持当前开发环境与标准应用，必须显式选择目标。
- 两套环境使用独立账号/历史数据库；环境名表示运行方式，不表示两种产品。旧Stable/Restore不属于当前支持入口。
- 用户在完整盘点后确认按环境管理、系统初始化、代码验证、AI评测、容器验收、诊断维护、账号恢复、开发协作组织操作；每个现行手动操作都有dev入口，内部模块由调用链使用，重复或过时入口需整理。
- [完整盘点](script-inventory.md)覆盖基线`scripts/`全部24个文件及外围实际操作入口；包含旧宿主路径、Compose目标解析、质量版本、Smoke账号写入、linked worktree身份等接入差异。

## Solution 与范围

同一个工程目标统一所有现行人工操作：分类帮助、开发与标准应用管理/初始化、检查与测试、AI评测与报告校验、容器验收、诊断与结构维护、开发数据重置、Hook/Harness，以及本机管理员恢复。`dev`保持薄命令路由；Compose负责容器，Bootstrap负责CLI装配，账号模块负责恢复规则，原验收脚本负责完整运行验收。

不把已有脚本重写进dev，不把Web用户管理或角色分配搬入CLI，不新增HTTP恢复端点。

## User Stories

1. 开发者运行`./dev help`，能找到环境、初始化、测试评测、容器验收和管理员恢复命令，知道真实验收会调用LLM。
2. 开发者运行`./dev verify dev`或`./dev verify app`，无需记住脚本路径即可获得现有完整验收结果、报告位置和清理行为。
3. 唯一管理员忘记密码时，可信本机操作者指定环境与管理员用户名，隐藏输入临时新密码，使管理员重新登录并改密，旧Session立即失效。
4. 指定错误环境、普通用户、禁用用户、不存在用户或不合格密码时，命令受控失败，不改变账号、角色或Session。
5. 使用标准打包应用时，开发者同样从dev执行构建、初始化和启停，不需要记忆长Compose命令，也不操作开发环境的数据。
6. 维护者从dev诊断当前依赖、导出结构、安装Hook和检查本机记录；每个命令清楚说明只读、写源文件或删除数据的边界。
7. 开发者显式重置开发数据库或向量库时，能核实项目和数据卷、确认删除范围；未确认或身份不匹配时不删除资源。

## Observable Behavior

### 分类与兼容

| 帮助分类 | 命令范围 |
| --- | --- |
| 环境管理 | 现有开发build/up/down/status/logs/infra；标准应用app分组 |
| 系统初始化 | migrate/create-admin/prepare-model/build-rag；标准应用相同操作与只读初始化check |
| 代码验证 | check及定向docs/python/boundaries；test python/database/web/renderer/all |
| AI评测 | evaluate原参数；evaluate validate报告校验 |
| 容器验收 | verify dev/app；默认开发隔离模式 |
| 诊断与维护 | doctor、metadata export、开发reset postgres/qdrant |
| 账号恢复 | recover-admin dev/app，显式指定账号 |
| 开发协作 | hooks install、harness check |

分类是帮助组织，不强制把每个分类变成额外命令层级。现有根命令与参数保持兼容，默认开发环境；新增标准应用使用app分组，写账号/删除数据的操作必须清楚定位目标。不公开内部辅助模块、导出worker、数据库容器自动脚本或内部evaluate-tools为日常操作。

根帮助与新增分组帮助不要求.env或Docker；帮助不触发构建、初始化、验收或账号变更。委派给既有工具的参数仍按其解析规则处理；用户能从帮助找到目标操作和参数说明。未知命令、缺少必填参数或不支持的目标在产生写入副作用前返回用法错误。

### 环境管理与系统初始化

- 开发根命令保持现有生命周期、就绪、热更新、初始化、数据保留和失败退出语义；本目标不重新定义restart策略或接手前一独立自动恢复候选。
- 标准应用提供`./dev app build/up/down/status/logs/infra/migrate/create-admin/prepare-model/build-rag/check`；子命令分别复用标准Compose的现有操作。app check调用Bootstrap只读verify，区别于`./dev verify app`完整运行验收。
- app up不隐式迁移、创建管理员、下载模型或重建索引；app down与开发down一样停止服务并保留卷。显式build负责镜像构建，初始化继续显式执行。
- app migrate沿用“PG基础初始化→Control/checkpoint迁移→完整健康”顺序；create-admin保持交互隐藏输入和重复拒绝；模型/索引使用目标项目资产卷，不引用开发或旧Stable资产。
- 项目身份、env-file、端口、用户UID/GID、宿主路径和override通过同一目标解析规则传递到实际操作；现有CHATBI_DEV_ENV_FILE/CHATBI_DEV_COMPOSE_OVERRIDE等开发配置保持有效。标准应用默认同一配置文件与其独立Compose项目，实际选中身份在相关命令中可核实。
- 兼容WSL/Linux与现有Dev Container的宿主路径映射，不新增宿主Python/uv/npm要求。工具需要已有匹配镜像时明确说明，不能因包装脚本而静默安装宿主依赖。

### 代码验证与AI评测

- `./dev check`保持完整锁文件、文档/链接、模块边界、Python质量和网页/导出构建范围；新增`check docs/python/boundaries`供定向执行。定向通过不能汇报为完整检查通过。
- Python质量在容器复用CI固定Ruff0.16.8入口和覆盖范围；文档组合检查继续包含链接，不增加一个与其竞争的默认文档检查链。
- `./dev test python/database/web/renderer/all`保持当前确定性/隔离验证边界，禁止隐式调用真实LLM。数据库runner统一为当前容器执行能力，保留CI/development fixture覆盖、失败/清理和适用配置能力。
- `./dev evaluate [原参数]`沿用现有标准套件、案例、运行资源和收费说明；新增`./dev evaluate validate [原报告校验参数]`调用确定性验收器，不调用LLM或数据库查询。expected commit/RAG与完整案例身份校验不弱化。
- 评测及Harness的Git元信息须兼容普通clone和linked worktree，通过真实git-common-dir保持提交/dirty/本机记录身份，不把容器内不可见Git路径解释为有效clean证据。

### 分类帮助与验收

| 命令 | 行为 |
| --- | --- |
| `./dev`、`./dev help`、`./dev --help` | 展示上述八类操作及实际用法；不要求.env或Docker，不初始化资源 |
| `./dev verify dev` | 调用现有开发验收的isolated模式，使用独立临时资源和专用账号 |
| `./dev verify dev isolated` | 与默认开发验收相同 |
| `./dev verify dev real` | 显式使用现有日常开发环境验收模式，保持原有行为与清理规则；帮助清楚说明会触及现有环境 |
| `./dev verify app` | 调用现有标准应用空卷验收，不操作日常开发或旧Stable/Restore |

验收路由不改变现有报告、clean候选要求、显式诊断选项、专用账号清理、退出码或实际LLM调用。未知目标、模式、额外参数和缺少目标先返回用法错误，不启动资源；各命令帮助不触发验收。验收耗时与真实LLM费用在帮助和Runbook说明。

原脚本保留原位置与直接调用能力，CI可继续复用。Python Bootstrap中已有的`verify`只读初始化检查保持原语义，与`./dev verify dev/app`的完整容器验收明确区分。

### 诊断、结构维护与开发重置

- `./dev doctor [dev|app]`默认开发目标；只读、有界检查所选环境的依赖、应用HTTP存活/就绪和必要资产，复用既有检查。失败/超时/未知不报告ready，不启动或修复服务、不改密、不收费探测LLM，不输出配置/凭据/原始异常。
- `./dev metadata export [原参数]`复用认证范围内的结构导出：数据库只执行既有catalog SELECT，显式写tables/columns/relationships结构投影。沿用固定Sales Mart范围，不修改业务Schema、数据或指标定义；输出路径和文件权限适配容器/宿主，来源变化后的RAG重建仍需显式执行。
- `./dev reset postgres`、`./dev reset qdrant`只接受当前明确解析的开发项目，保留已有交互删除短语和显式--confirm能力。显示目标项目、卷及删除范围；取消/输入结束不删除，外部卷、标签不符或配置解析失败时拒绝。
- PostgreSQL重置删除该开发卷内Sales Mart与Control DB数据，包括账号/Session/历史/成果；Qdrant重置删除对应集合和索引。另一基础设施卷、模型缓存、其他项目和旧Stable/Restore保持不变。
- 删除前停止本目标API/Web和待重置服务，核实相关容器停止；删除/重建只针对已验证归属的卷。PG按既有流程准备Seed和迁移，不自动创建管理员；Qdrant仅重建服务，索引需显式build-rag。重置后API/Web保持停止，用户按初始化步骤显式up。
- 重置使用宿主编排和容器内Python/迁移，不给业务API或普通测试容器Docker socket权限。执行失败非零退出、报告安全阶段，不扩大清理范围或自动继续删除其他资源。

### 开发协作与旧入口处置

- `./dev hooks install`直接复用现有安装器，不依赖.env/Docker；只写当前clone的local hooksPath，保留对其他有效Hook配置的拒绝覆盖规则。
- `./dev harness check [原参数]`只读检查当前/指定worktree、本机实时记录和共享Git公共目录；不访问远端、不更改记录/分支/PR，原ERROR/REVIEW/INFO和退出语义保持。
- 内部端口、Markdown、metadata辅助模块、卷身份校验、数据库自动初始化/healthcheck、导出资产构建/worker继续由所属流程调用，不逐文件新增独立dev命令。
- 旧start-dev.ps1宿主启动流程退出当前支持；旧run_database_tests.py与前端test:real的独有验证/路径能力先核对并由现行容器链覆盖，再迁移或归档旧入口和引用。不能丢弃独有验收断言换取表面单一入口；无法证明覆盖的内容保留并明确不作为现行推荐操作。
- scripts/smoke_web.py保留CI专用账号链，不提供面向日常账号的公开Smoke命令；不得因健康检查重置或生成真实管理员密码。
- CI继续直接复用适用脚本和Python能力；不要求通过dev触发GitHub自动合并、远端部署或所有CI专属任务。

### 管理员恢复

```text
./dev recover-admin dev --username NAME
./dev recover-admin app --username NAME
```

- 环境和用户名都必须显式指定；不默认选择环境、不默认选择第一个或唯一管理员。成功前显示目标运行环境/Compose项目及规范用户名，密码不显示。
- 可信边界为本机Docker操作能力与目标Control DB运行账号配置；不要求旧密码或Web Session，不通过网络暴露恢复入口，不把本机操作者冒充为被恢复账号。
- 目标按相应Compose项目与本地配置选择；保留现有环境选择配置方式，不跨环境搜索或fallback。默认开发资源与标准应用资源隔离；旧Stable/Restore不接受为目标。
- 需要目标Control DB已运行且已初始化、相应本地配置及可执行恢复代码的工具镜像。恢复不依赖API/Web/LLM/Qdrant/RAG在线；不调用真实LLM，不自动启动整个应用、不构建镜像、不迁移、不重建索引。
- 宿主不要求Python；宿主Bash路由到一次性容器，Python账号恢复Service裁决目标与状态；Bash不直接更新数据库。
- 必须在交互终端隐藏输入临时新密码两次；不接受密码命令参数、环境变量或流水线stdin，不允许getpass退化成回显。沿用现有至少12位密码策略与Argon2id。
- 只恢复规范用户名匹配的、当前启用且拥有固定admin角色的现有账号；普通用户、禁用账号、不存在账号均拒绝。多个管理员存在时也必须指定其中一个账号，不修改其他账号。
- 保留账号ID、用户名、启用状态、角色、历史、成果和数据访问范围；不创建账号、不授予角色、不启用禁用账号。
- 成功原子完成：写入新密码Hash、设置首次登录必须改密、清除失败计数与临时登录锁定、撤销该账号所有旧Session、追加独立恢复审计。
- 恢复使用Control DB运行身份，不使用业务只读身份或迁移身份。账户校验和变更在同一事务内完成，使用适用锁保护并发，不在CLI外层先判断管理员再无条件按ID重置。
- 审计记录目标、环境、本机CLI恢复来源和结果；不记录密码、Hash、Token、数据库凭据或原始异常，也不声称本机标识可以证明自然人身份。成功恢复的审计写入失败时，密码和Session修改全部回滚。
- 无权限、缺配置、目标不符、密码不合格、输入中断、数据库失败或审计失败时非零退出，安全提示原因/阶段，不输出异常堆栈或连接信息。事务失败不自动重试账号修改；只有提交确定成功才报告恢复成功。
- 参数/非交互输入/两次密码不一致返回2；资源、账号或事务失败返回1；成功返回0。Ctrl-C不报告成功，未提交变更不保留。

## Implementation Decisions 与边界

- 命令入口新增行为是明确的本机账号恢复Contract，Web认证与普通管理员重置不变。
- 恢复Service复用既有密码策略、用户规范化、Control DB、Session与事务内审计能力，保持已有模块归属与依赖方向。
- 不改变Semantic、SQL Guard、业务数据库结构、模型/Prompt、业务API、执行恢复或历史归属；不新增Schema迁移或独立用户身份平台。
- 具体命令路由组织、目标解析复用、容器工具调用、连接装配、锁实现、模块迁移和兼容包装留给设计审查，在上述信任与状态Contract内选择最小方案。dev中保留路由，不复制成熟的业务/验收实现。

## Testing Decisions 与验收

- 帮助无需配置/Docker；路由覆盖正确脚本/默认隔离模式、显式real、退出码传播、未知/多余参数不产生副作用。
- 所有24个scripts文件及外围入口都有最终处置和dev操作映射；“内部保留/CI专用/历史归档”也明确说明原因、调用方及独有能力去向，不只验证新增两个快捷命令。
- 开发/app目标解析与初始化/启停通过实际Compose解析和隔离资源验证，覆盖自定义配置、override、宿主路径、错误参数、数据保留及环境互不影响。
- 诊断覆盖成功、依赖故障、超时/未知与脱敏；metadata覆盖现有导出Contract、容器输出权限及只读DB行为；报告校验覆盖提交/RAG/案例身份和无真实调用。
- 重置在独立临时开发项目验证拒绝、取消、确认删除范围、标签不符/外部卷、停止失败保护、PG重新迁移、Qdrant索引失效及其他资源身份不变；不删除真实日常数据或旧Stable卷。
- Hook/Harness覆盖无业务配置、已有Hook保护、普通clone/linked worktree与共享记录；不写真实其他项目配置。
- 恢复参数与TTY覆盖必填环境/用户名、禁止密码参数、非交互/回显拒绝、两次不一致、弱密码和输入中断；失败前不写账号。
- 软件回归通过真实账号Service与数据库状态观察：成功、旧密码失效、全部旧Session撤销、登录锁解除、必须改密、非admin/禁用/未知拒绝、角色与其他用户不变。
- 审计成功事务与审计失败回滚都有测试；失败提示和审计不含敏感输入，不伪造Web actor。
- 隔离PostgreSQL与专用账号验证真实权限/事务/锁及并发登录、改密/恢复的Session撤销边界；以隔离dev/app目标验证显式环境路由和互不影响，不重置真实管理员。
- 依风险运行受影响回归、Compose实际解析、Bootstrap导入/命令兼容、Python质量、文档/链接与Diff检查；完成当前上下文Code Review后形成本地候选。
- 快捷入口不改变验收实现，路由回归不调用真实LLM；完整真实容器验收/AI Evaluation不因本次整理而隐式执行。不使用历史验收冒称当前候选结果。

## Compatibility、Documentation 与交付

现行支持命令参数和脚本调用保持兼容；旧入口的退出、独有能力迁移和历史去向单独列明。create-admin仍只初始化首个管理员，测试和评测保持现有边界。更新README/Runbook和正式Bootstrap/容器工具Contract，说明八类操作、环境选择、读写/删除范围、恢复权限、首次改密与验收费用；当前行为不只留在.scratch。

检查Product Scope、Architecture及Roadmap是否受已确认恢复能力影响：适用时仅补充本机账号恢复边界，不改路线优先级，不把旧交付和运行身份重标为新结果。历史记录保留原位置。

用户已整体确认这版完整Spec，包括分类统一目标、操作范围，以及管理员恢复信任/环境边界；随后按仓库规则完成Design Review、Ticket草案、当前上下文Readiness与拆分确认，再连续实施完整获准范围。最初仅授权本地Commit；用户现已明确授权两个目标依次Push/PR、CI修复、Auto-merge跟进及安全清理。

本轮此前未确认的三项草案保存在[历史草案](history/spec-three-entrypoints.md)，不作为当前授权或行为事实源。

## Out of Scope

公众注册、邮件/短信找回、Web无认证恢复API、SSO、多租户、任意用户CLI管理、管理员角色修复、启用禁用账号、数据库直改教程、标准应用数据重置、旧Stable/Restore清理或接管、Docker Desktop设置、重新建设自研发布/备份恢复、完整脚本重写、业务功能扩展、真实日常数据重置/管理员密码修改及远端发布。

## 基线与工作区

基线`master@38e1302ce33d999dc908419067bc5d39195f86cf`，GitHub master已只读核实同SHA。独立工作区`/home/jojo/Projects/chatbi-dev-tools`，分支`feat/dev-command-entrypoints`。前一目标`container-auto-restart`的`fd9be30`候选和原工作区保留，尚未授权发布；本目标不混入其配置或收尾。

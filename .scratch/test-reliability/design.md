# 测试可靠性与运行路线精简：实现设计

## 依据与边界

行为依据为用户已确认的 [Spec](spec.md)。本设计只细化实现与验证选择；不授权实施或发布，不修改业务模型、首次改密、安全规则、SQL Guard 或数据。

## 1. APP 退役与公共消费者

- dev CLI、环境装配、维护、doctor、Bootstrap / Authorization 的新恢复请求只支持 dev；旧 app 调用在实际资源操作前返回用法 / 目标错误，不重定向到开发库。
- 删除根 Dockerfile、`docker-compose.app.yml`、`scripts/verify_container_app.sh` 和仅为这些入口存在的测试 / 配置。开发 Python / Node Dockerfile 是保留的依赖环境；其 Chromium、字体和导出 assets 构建继续保留。
- `scripts/dev_compose.py` 中拒绝旧 APP 容器的检查与回归测试保留，避免相同项目名或 override 把旧资源误当 dev。已有审计中的 app 字段是历史事实，不改写、不迁移数据库。
- `src.query_api.app`、数据库角色 `chatbi_app`、前端构建出的网页静态文件和普通 API startup smoke 都是共享能力，不随 APP 镜像删除。浏览器测试中的 packaged 网页表示前端 build 产物，不表示独立 APP 镜像，相关覆盖保留。
- 活动文档只推荐 dev；独有旧 Contract 归档到当前工作记录 history，受删除路径影响的历史本地链接修复。基线 Git 是源码删除的恢复依据。
- 比较方案：仅隐藏 help 会留下可执行的第二条路线；新增兼容别名会使调用者继续依赖旧目标。因此采用完整删除正向支持并明确拒绝旧目标，不保留迁移数据或自动清理资源的功能。

## 2. 数据库锁测试

- 保持真实 PostgreSQL 验证，worker 通过独立连接报告其 backend PID；observer 只查询该 PID / 测试库的等待状态，不用其他会话代替。
- 锁拥有者的释放位于线程池 join 之前的 finally 中；observer 查询、连接、worker 语句及 join 使用明确预算，SQL 限时只作用于测试连接。
- 任何失败路径先释放持有锁；worker 仍未退出时，只取消 / 关闭本测试拥有的连接。不能取消任意会话或接触日常开发库。
- 超时 / 故障注入在有进程上限的隔离子运行中验证，防止测试线程阻止解释器退出。原始断言错误是主失败，清理失败另行附加，不用后续错误覆盖。
- 不把首次未观察到等待归咎于已否定或未证实的 PostgreSQL 缓存假说；需按实际调度和连接证据验证同步方式。

## 3. 浏览器账号生命周期

- 在隔离 `tests.browser_support` 应用的 fixture 管理中，按每次用例生成唯一用户名并创建初始账号；测试通过现有真实登录 / 改密接口观察行为。
- 账号准备 / 清理只存在于测试装配，限制测试命名空间与该测试进程的 SQLite 数据，不向生产 `create_app` 注册测试路由或管理能力。
- Playwright fixture 在 finally 中清理账号与会话，失败也执行；应用进程退出释放隔离数据库。固定 analyst / other-user 的既有用例保持原用途。
- 连续重复验证仍使用同一个浏览器支持服务，以证明账号隔离，而不是靠每次重启整个服务隐藏残留。

## 4. 无序数值匹配

- 复用现有 `_rows_match` / 数值容差，不改变值比较语义。
- actual / expected 行作为二分图两侧，满足逐列比较的行之间建立边；通过确定性的增广路径寻找完整匹配。复杂度有多项式上限，不采用全排列或指数回溯。
- 每一行至多匹配一次，因此重复行数量仍受约束；有序模式继续走原逐行比较。NULL、数字字符串的可选归一化和截断检查保持。
- 通过容差重叠、不同排列、不存在完整配对、多列、重复行、有序 / 无序以及接近最大结果行数的密集候选验证，不用脆弱的毫秒级性能断言。

## 5. 运行身份与报告最小结构

### 公共实现位置

在 `scripts/verification_report.py` 放置使用标准库的运行身份 / 独立编号 / 排他保存小工具，供工程命令与 Evaluation 边缘使用；不新增 `src` 一级业务模块、Port 或 Framework。模型、数据库和 RAG 的事实仍由现有对应 collector 提供，公共工具不加载这些依赖。

选择一份纯工具实现，避免 Python、Shell 和四套评测各自重写 Git / 文件保存规则；与新增统一测试平台相比，仅共享必要的数据收集和保存机制。报告渲染继续由各套件拥有。

### 起止身份

- 起点在加载并执行待评测行为之前采集；终点在工作及必要清理完成后采集。`git_commit` / `git_dirty` 的旧字段表示起点，不再借终点覆盖起点。
- 新增 `provenance.version = 1`、`started_at`、`finished_at`、`source_start`、`source_end`、`inputs_start`、`inputs_end`、`consistency`。source 至少含完整 SHA、dirty 和 tracked worktree 变更指纹；输入使用实际加载的案例 / 上下文内容指纹，不记录文件内容。
- `consistency` 只取 `stable`、`changed`、`unverified`。输入或源码可观察身份不同为 changed；读取失败为 unverified，不能默认为 stable。
- dirty 但起止一致的软件运行可保留正常诊断成绩；正式 clean AI 验收还必须满足起点 clean、终点 clean、consistency stable 及已有资源身份要求。新生成报告缺字段属于未确认，不能正式通过。
- 持续变化后恢复和 ignored 的运行依赖不是起止检查能完全证明的事项；不宣称完整不可变环境。Docker 镜像身份 / 锁文件指纹作为环境信息另记，不能用宿主源码 SHA 代替镜像身份。
- 不读取或输出真实 .env 内容 / 密钥，不把 Git diff 正文写入报告；仅存 Hash。无法识别的任意 CLI 参数按安全字段白名单保留，不把任意 argv 或环境整体倒入报告。

### 软件与质量报告

- 以 dev test / check 子任务或 CI 实际检查为记录单位，JSON summary 含 `schema_version: 1`、独立 `run_id`、`kind`、`scope`、安全参数、起止时间、provenance、`environment`、`status`、`exit_code`、`counts` 和相对 `artifacts`。
- `status` 为 passed / failed / interrupted / incomplete；成功要求命令、适用清理和报告保存均成功。观察到源码变化单独由 consistency 表示，不能当正式固定候选通过。
- pytest 使用现成 JUnit，Playwright 使用现成机器可读 reporter；counts 使用真实产物。构建 / lint 等没有用例计数时 counts 为 null，且说明不适用或未取得，不解析随语言变化的控制台文字来伪造计数。
- `test all` / `check` 保持原失败退出策略；各步骤分别列已运行、失败和未运行，不能因为最后一个命令成功而掩盖前面失败。
- CI JUnit / summary / 日志使用独立 artifact，失败时也上传可得证据；取消导致 runner 无法执行后续步骤时，CI 自身 cancelled 状态是事实，不能生成虚假的 completed / cleanup 成功。

### AI 报告与正式验收

- 四套 AI 报告保留原 suite 名称、case / turn ID、summary 和既有 metadata，并增量加入 provenance 与有效模型配置；语义套件也记录实际题集 Hash、端点 Hash、temperature、max_tokens、适用 timeout。
- 经营分析额外记录 Judge 的实际配置；当前 Judge 使用 temperature 0，这一事实不能被业务模型 temperature 覆盖。模型 API Key、完整服务地址不落盘。
- 数据 / RAG / 上下文收集沿用现有职责，仅在实际依赖时适用；开始和结束核对该次使用的案例与上下文。若无法证明中途输入保持一致，报告 changed / unverified，不作为正式 clean 证据。
- 老 JSON / Markdown 可读，旧 baseline 比较规则继续适用；缺少新身份字段的历史报告不被补造为符合新正式验收。正式验收器拒绝新要求未确认的报告，不改变三套业务验收的成绩门槛。

### 唯一性与保存

- run ID 使用 UTC 时间、短提交及足够随机的 UUID；每次运行独立目录或现有套件后缀，保持三套正式报告目录恰好三份 JSON 的既有消费约束，summary 辅助 JSON 不混入该目录。
- 排他创建确保目标已存在时失败且旧内容不变；JSON / Markdown 一对报告先准备内容、预留各自新路径，均成功才报告保存完成。部分产物保留可诊断的 incomplete 状态，不删除或覆盖任何历史文件。
- dev 业务验收的 `browser.json` 在本次私有目录中是可变运行状态；重启阶段和清理可更新它。最终发布到新 run 路径的报告 / manifest 不可覆盖，并包含阶段、资源与清理结论。
- 既有 safe-reporter 等读取后补写的流程改为在最终发布前汇总，不把最终证据当状态文件继续修改。独立目录保留安全权限；临时凭据按原规则清理，不进入 artifact。

## 6. CI 与运行入口

- 复用现有 `PostgreSQL integration` job，补齐 development fixture 与 renderer 步骤，尽量共用一次 Python 开发测试镜像构建；保留原 job 名称，不引入需要修改远端必需检查配置的新门禁身份。
- 数据库沿用本地同一 profile / 套件选择，renderer 沿用 Python 开发镜像中的真实 Chromium、字体及 seccomp。构建开发测试环境与打包业务 APP 是不同操作；不构建 / 推送业务应用镜像。
- 保留现有来源码 application startup smoke、前端静态 build、Python / SQL Guard / 浏览器 / 安全检查。CI 中的依赖安装、锁文件和固定工具版本继续约束环境。
- CI 结构验证核对实际命令、开关、目标套件、失败退出、始终上传可得报告和超时；本地运行同一实际命令。未授权发布时只报告托管 CI 未执行。

## 7. 迁移、回退与实施顺序

- APP 退役、锁测试、账号隔离、比较器可各自独立验证和恢复；共享报告工具及 AI 适配完成后，软件 / 业务验收接入，再补 CI。每个切片同时更新受影响正式文档，最终做交叉核对。
- 只涉及源码 / 配置和新报告格式，不迁移真实数据库或重写旧证据。恢复使用本目标切片前的 Git 版本；不能用自动清理真实数据作为回退。
- 发现需要新增业务 API、放宽安全、不兼容现有报告消费者、修改旧目标提交或需要收费运行时，停止该依赖路径，返回已确认 Spec 与授权核对。
- 实施 Owner 为当前主 Agent；用户拥有范围与公共 Contract 的裁决权。仅本地候选，发布仍需单独授权。

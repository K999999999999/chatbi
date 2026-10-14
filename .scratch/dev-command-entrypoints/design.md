# dev 分类入口实现设计

Status: 设计方案；行为以[已确认 Spec](spec.md)为准。基线 master@38e1302。
Owner: 当前主 Agent；设计、实施和维护同属本工作项。涉及 Contract 改变时返回用户确认；仅实现细节调整由主 Agent处理。

## 1. 命令与容器边界

`dev`只解析命令、提供帮助并委派。新增一个共享 Bash 环境辅助文件，集中隐藏项目、env-file、override、宿主路径、UID/GID及 Compose 参数数组；现有 container_tasks.sh、验收脚本和 Bootstrap 保持实际执行职责。不建设注册表、插件机制或每个命令一套类。

帮助先于配置读取；未知参数先于任何写操作拒绝。Hook直接调用宿主 Bash/Git；其他 Python/Node能力使用镜像，不增加宿主运行时要求。现有根命令默认dev，app分组明确使用标准Compose。app新增 CHATBI_APP_ENV_FILE / CHATBI_APP_COMPOSE_OVERRIDE，与现有开发变量对称；默认均为当前工作区.env，数据归属仍按独立项目。

共享解析分别提供完整操作配置和受限诊断/恢复配置。完整操作沿用Compose优先级；受限配置从同一Compose文件集的未插值结构提取，禁止另一套手写项目名推断。临时项目、服务、卷、镜像必须以Docker标签和实际配置双重核实，不能只匹配名称前缀。LOCAL_WORKSPACE_FOLDER负责Docker宿主源路径，工作区和Git身份独立处理。歧义、重复目标、外部卷或不支持的配置形状安全失败，不fallback到默认项目。

app生命周期依照现有Runbook：build镜像、infra基础设施、migrate等待基础初始化后迁移再检查完整健康；其余初始化显式。up保留完整健康/就绪检查，不隐式创建账号或资产；down使用stop保留卷。app check为Bootstrap verify。

## 2. 检查、评测和Git身份

扩展container_tasks.sh分发docs/python/boundaries与evaluate validate。完整check继续覆盖原范围，Python质量统一调用现有固定Ruff0.16.8脚本，不直接调用镜像中漂移的ruff。软件测试继续使用ci/development两种私有PG fixture、mock浏览器和真实renderer，不连接日常项目。

Git在宿主通过git rev-parse获得worktree git-dir与common-dir；容器只读挂载真实元数据及工作树，并确保.git引用与commondir可解析。禁止通过伪造HEAD或忽略Git错误声称clean；safe.directory仅限已选择工作树。Harness所需公共目录包括本机记录，按其原规则只读，报告校验保留expected commit/RAG/cases检查。无.env场景可执行检查/帮助/协作命令；工具镜像缺失时明确提示，不暗中下载宿主依赖。

## 3. 诊断与结构导出

doctor组合现有安全探针：选中容器状态、Control DB、Qdrant、所选模型/RAG及网页资产、HTTP health/ready。容器不存在就报告缺失；不得先启动再诊断。每次网络检查有超时与总预算；统一结构状态及安全原因，不转发完整配置、原始异常或连接串。LLM只说明配置/未探测，不发送请求；资产存在不能直接等同业务ready。

metadata export复用scripts/metadata能力，开发目标数据库配置与已授权结构范围保持；源目录/output显式挂载，宿主UID写入。通过已有catalog SELECT产生结构JSON，不调用RAG构建；错误输出和权限失败保持安全。需要的数据库权限由既有导出Contract决定，不把运行账号换成更宽权限来掩盖失败。

## 4. 开发重置

Docker操作仍在宿主Bash，Python镜像承担配置/卷校验和现有迁移；compose_volume_reset.py保留可复用的纯校验能力。旧宿主Python CLI在调用方迁移完成前可保留兼容委派，不给普通工具挂Docker socket。

顺序：解析并展示目标及删除范围→校验所有卷归属与外部标志→确认短语或--confirm→停止API/Web及目标服务→核实停止→移除仅目标服务容器→再次校验卷归属与使用者→删除目标卷→重建基础服务。每一步失败停止，其他项目卷不进入候选集合。两次校验之间发生变化视为失败，不能扩展清理。

PG重建继续基础Seed和完整迁移，不创建管理员；Qdrant仅重建，不build-rag。API/Web保持停止。数据删除不可回滚；命令不承诺恢复删除数据。本目标只在新建且带专属标签的测试项目演练，记录其他卷的身份/内容未变。

## 5. 管理员恢复

### 装配与独立依赖

恢复使用独立一次性Python容器，dev绑定当前代码，app使用选中标准应用镜像中的打包代码。要求已有镜像，不build、不启动基础设施。选择已运行且唯一匹配Compose project/service=postgres的容器，再核实归属与数据卷；连接使用该PG容器的network namespace，容器内127.0.0.1:5432，无须PG宿主端口、API网络或Qdrant。

完整Compose会对无关LLM/管理员Key/Qdrant字段强制插值，不能用于此处的最终配置展开。从`config --no-interpolate`取得同一文件集的项目身份和tools定义，用镜像内Python提取最小恢复服务模板，再由Compose处理选中env-file及宿主变量优先级。只保留Control DB必需配置、镜像/工作目录/运行用户及dev代码绑定，删除build、restart、depends_on、普通资产卷和无关environment；受限服务固定network_mode到已核实PG容器。不得继承额外env_file/env_from、entrypoint、网络、特权或socket；支持的override配置由显式测试覆盖，未知形状拒绝并提示安全原因。

临时模板只含变量表达式和非Secret结构，不打印完整配置；如需暂存已展开的最小环境，使用0700临时目录/0600文件、EXIT清理，不能进入仓库或日志。凭据不出现在命令参数；不从运行PG的超级用户配置取得更高权限。连接由ControlDatabaseConfig运行身份检查和verify_control_schema核实，不进行迁移。必需配置缺失在修改账号前失败。

### 账号规则与事务

Bootstrap新增恢复CLI，按操作懒加载，不创建Web、LLM或RAG资源。TTY两端校验，getpass回显警告转错误；密码两次隐藏输入，仅驻留进程内存。参数与异常映射遵循Spec的0/1/2，Ctrl-C不报告成功；提交结果不确定时不自动重试。

AuthService新增专用recover_admin能力，复用规范用户名、密码策略、Argon2id及Session撤销；保持账号规则在authorization，不导入Docker/CLI模块。审计Sink必须具备事务内write，缺失即失败；actor_user_id=None，记录独立恢复事件与环境/项目/local_cli来源。

事务读取目标User并FOR UPDATE，取得锁后重新读取active及admin成员关系，再更新Hash、must_change_password、失败次数/锁与所有Session，写审计，提交后才报告成功。login/change_password已锁同一User；对既有密码重置、启停及角色修改写路径仅补齐相同User锁和锁后刷新，以防角色/状态在恢复校验后变动。不改变其权限、最后管理员或普通审计Contract，不建立通用账号仓储。

锁顺序统一为User→现有必要的admin Role锁，恢复本身不新增全局Role锁。SQLAdmin所有已有用户修改与set_user_roles先锁User；最后管理员保护继续原Role锁规则。真实PG双连接屏障测试覆盖登录、改密、禁用和角色撤销与恢复交错；若发现无法满足一致顺序或原行为需要变化，暂停该切片并返回设计审查，不在实现中猜测。

### 方案比较

直接借用reset_password成本较低，但没有目标admin校验、行锁和强制审计，CLI外围检查存在竞争窗口。选用专用恢复事务并复用已有低层能力，把不同信任来源与审核规则局部化。完整tools Compose运行包装简单，但迫使恢复依赖无关业务配置；选用最小一次性装配，增加少量配置校验但满足已确认离线依赖边界。Owner为本工作项；未来账号模块替换、支持远端恢复或复杂Compose override时重新审查。

## 6. 旧入口迁移与文档

以script-inventory为迁移台账，逐项记录消费者、独有能力、新入口、最终归属和删除证据。先提供新入口，再迁移文档/测试/调用者，覆盖证明后删除或归档。start-dev.ps1退出宿主运行推荐；run_database_tests.py的profile/退出清理/路径由T02负责；前端test:real及real.spec.ts的独立SQL真值、追问与分析断言由T07核对。证明不足则保留并明确非推荐，禁止为了删除而弱化断言。

每个切片同时更新所属正式Spec、Runbook和适用测试。最终README和盘点覆盖所有24个脚本；记录内部模块/CI专用/兼容历史。Roadmap仅记录已确认工程目标与完成事实；产品范围/架构仅补充实际恢复边界，不改变优先级。实现后的Code Review再次搜索旧消费者，防止重新引入。

## 7. 验证与回滚

各切片先建立确定性路由/失败回归，再真实隔离Compose/PG测试；Docker替身用于参数和拒绝分支，不能替代实际目标/权限/事务证据。新CLI行为不改变模型，AI Evaluation不适用；真实LLM验收路由以替身测试，未运行真实业务验收要明确记录。文档检查不等于软件验收。

本地候选，不部署日常环境、不恢复真实管理员、不删除真实卷、不Push/PR。无Schema迁移或常驻新服务，不需要Feature Flag。代码可按切片回滚；已经执行的密码恢复不能靠回滚代码复原旧密码/Session，重置删除的数据也无法恢复；该不可逆操作仅限授权测试资源。发现跨项目资源变化、Secret泄漏、账号非原子写入或旧独有验证缺失，停止后续切片，修复并重跑对应证据。

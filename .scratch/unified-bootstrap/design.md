# 统一初始化实现设计

Status: reviewed（Contract 内局部设计，已完成设计审查补充核对）
Canonical Source: `spec.md`
Baseline: `08c632e01baae62e161f3eec69993d56a3f441c3`

## 组织与依赖

采用 `src/bootstrap/`，明确命令为 migrate、create-admin、prepare-model、build-rag。目录内分为运行资源装配、就绪检查、命令分发和按操作划分的命令装配；无需创建资源注册框架、DI 容器或每种资源的透传包装。

统一入口可依赖现有 Adapter、模块工厂和应用接口，业务模块不依赖 bootstrap。Query API 的 HTTP Adapter 接受内部资源工厂 / 生命周期回调，通过已有接口绑定资源；该注入约定位于 Adapter 边界，不导入具体 bootstrap runtime，也不让 Domain 了解 FastAPI 或资源容器。

旧 CLI 文件中的命令解析、操作装配迁入 bootstrap；Control DB 初始化实现、RAG builder 和模型适配实现仍留在所属模块。Embedding 下载操作从现有脚本迁入统一命令，无兼容脚本。四类命令按选择加载依赖；统一帮助不装配服务或加载模型。

## 应用生命周期

创建 FastAPI 应用时建立 HTTP 路由、验证处理器和根 Middleware，仅保存工厂，不创建真实资源。启动时加载配置、校验运行模式与 Secret，装配当前应用需要的资源，执行既有就绪门禁，将服务绑定到 Adapter 请求边界，完成 SQLAdmin 挂载后才 yield。

现有 app.py 的处理器捕获局部服务引用，迁移必须统一改为启动时可更新的绑定；不能只更新 app.state 而遗留旧闭包。保留直接注入服务的测试调用方式，直接注入不强制通过真实生产配置。

SQLAdmin 在就绪后挂载 / 绑定。当前锁定安装源码中 SQLAdmin 在独立 Starlette 子应用构造 Middleware，不要求在启动后修改根 Middleware。不能在 lifespan 启动时给已经构建 Middleware stack 的根应用添加 Middleware。首次启动挂载一次；后续进入同一应用 lifespan 时更新绑定或替换旧 mount，避免重复路由或使用已释放 engine；更新 OpenAPI 缓存如路由发生变化。

相同应用生命周期重复进入必须创建新一轮资源、绑定当前资源并在结束时清理；失败一轮不留下后台线程、过期 app.state 或可服务的旧资源。真实请求只在 lifespan 正常启动后服务；无需增加新的 readiness HTTP API。

运行生命周期使用 AsyncExitStack 等待异步 HTTP client 关闭；模型 Adapter 接收应用持有的同步 / 异步 HTTP clients，避免隐式 SDK 缓存所有权。沿用已锁定 SDK，不修改模型、Prompt、参数或依赖版本。经营分析 pool 先以 open=False 创建并登记，再显式 open，避免启动线程后尚未登记清理。

## 所有权和失败清理

- bootstrap 创建的 Tracing recorder、Control DB engine、RAG Runtime 和经营分析资源由这一轮运行生命周期拥有。
- Query Executor 使用逐查询 context manager，不持有长期连接池；Session factory、授权策略等非资源对象不需要假造 close。
- Control DB 运行 engine、经营分析 run store engine、checkpoint pool 明确分别登记，保持原有配置和身份；本目标不合并池或改变容量。
- 对外资源获取成功后立即登记 cleanup。若 builder 内第二步失败，builder 必须清理第一步成功获取的资源，不能等根入口接收到未返回对象。
- BusinessAnalysisApplication 自己持有的线程、run store 和 checkpoint pool 的关闭依赖关系保留；清理不能在 run store close 异常时跳过 checkpoint pool。根生命周期只登记一个完整 application close；构造完成前的局部登记在成功时转移，避免双重释放。
- RAG Runtime 继续拥有快照和 Qdrant clients；close 尝试全部快照，单个 client close 失败不能遗漏其余。模型对象仅按现有 SDK 明确提供的资源释放能力处理，不臆造接口。
- Tracing 使用现有 recorder.shutdown，最后关闭，以覆盖此前阶段的处理；仍保持 Observability 的 Fail-open Contract。
- 使用标准 context manager / ExitStack 或等价的最小实现登记逆序清理。清理异常只输出安全的资源阶段 / 异常类型，继续释放剩余资源；启动失败重新抛出原始启动原因，正常关闭保留可定位的清理失败信息。
- 现有直接注入测试方式不自动接管调用者的 engine、RAG 或 recorder；保留既有 analysis_service close 约定。统一创建路径与注入路径不能对同一对象各调用一次 close。

## 方案比较

1. 只移动 main.py 和 CLI 文件：改动小，但仍有导入时资源创建、闭包和失败清理问题，不满足已确认生命周期 Contract。
2. 根 FastAPI shell 加运行时挂载的第二个完整 FastAPI：可延迟创建，但额外引入两个应用、OpenAPI 和 Middleware / State 衔接；当前需求不值得这层复杂度。
3. 单一 FastAPI + 启动时注入资源绑定：保留现有路由和测试 seam，集中生命周期，局部修改 Adapter；选择此方案。

Owner: 当前主 Agent。若单一应用绑定无法保持路由、权限或测试注入 Contract，暂停实现返回设计审查，不自行增加第二条应用链路。

## 命令迁移与回滚

迁移分两组：数据库命令及其所有调用、模型 / RAG 命令及其所有调用。各组在同一切片内新增统一入口、迁移消费者并删除旧入口，不存在已交付兼容窗口。

README、Runbook、当前 Spec / Design / Architecture、CI、脚本和测试为消费者发现范围；历史 .scratch、日期化 Acceptance 和报告保持原始候选身份。消费者搜索结合命令执行检查，允许旧字符串仅出现在历史证据及明确记录删除行为的规划文本中。

无 Schema、数据或配置格式迁移。尚未发布时，通过本目标相关提交的 Git revert 可恢复既有代码与命令，不能 reset / 清理用户修改；若部分切片已完成，停止后续切片并恢复整组入口及调用。没有真实部署，不新增 Feature Flag 或 rollout 平台。

## 验证

以 Spec 的测试与验收项为准，补充 Tracing shutdown、清理抛错后继续、重复 lifespan、SQLAdmin 实际挂载和闭包绑定测试。数据库命令和权限使用隔离 PostgreSQL；模型 / RAG 命令使用现有替身验证分发及资源释放，并复用 builder 软件测试。锁文件和依赖版本保持不变，不需安装新依赖。

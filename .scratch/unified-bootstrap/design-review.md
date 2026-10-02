# Design Review

Review: PASS WITH MINOR FIXES → 补充落实并核对完成，可进入 Ticket 草案
Review Target: 用户已确认的 `spec.md`
Baseline: `08c632e01baae62e161f3eec69993d56a3f441c3`
Reviewer: 当前主 Agent（只读审查，无独立 Agent）

## Findings

### 1. 启动绑定和 SQLAdmin 挂载

- Signal: HTTP 处理器持有创建时的资源，移动创建时机不能只迁移 main.py。
- Evidence: app.py create_app 捕获 authorized_service、auth_service、recorder、active_analysis_service；现有 lifespan 仅关闭分析服务。SQLAdmin 使用独立 Starlette 子应用，根 Middleware 启动后不可追加。
- Impact: 只更新 app.state 可能让请求继续使用空对象；重复 lifespan 可能重复挂载或使用已经关闭的 engine。
- Recommendation: 单一 FastAPI，根路由与 Middleware 提前定义，lifespan 创建并绑定服务，SQLAdmin 就绪后挂载且支持重复启动；保留直接注入 seam。
- Resolution: 已写入 Spec 局部约束和 design.md，明确闭包、重复挂载和测试要求；不改变外部 HTTP Contract。

### 2. 部分创建与清理异常

- Signal: 根入口不能清理尚未从构造函数返回的资源；多个 close 串行调用可能中途停止。
- Evidence: business_analysis/runtime.py 依次创建 engine、ConnectionPool、application；application.py close 依次关闭 run store 和 pool。RagRuntime.close 遍历 Qdrant clients。
- Impact: 构造失败或第一个 close 异常可能遗漏连接池、线程或其他 clients。
- Recommendation: 局部构造先登记清理，成功时转移所有权；逆序尝试全部 cleanup，保留原始启动失败，避免根与 Adapter 双重释放。
- Resolution: Spec 和 design.md 已明确所有权、局部失败、继续清理和重复关闭；验证纳入草案。

### 3. 资源清单需要按真实持有关系确定

- Signal: Tracing 生命周期容易遗漏，数据库 Query Executor 则没有长期连接池。
- Evidence: recorder.shutdown 已存在；PsycopgQueryExecutor.execute 为每次查询使用连接 context manager。
- Impact: 遗漏 Tracing 可能残留 exporter 线程；虚构 Query Executor pool 增加无关变化。
- Recommendation: 登记 Tracing shutdown，保留逐查询连接行为；不改变 SDK 或池容量。
- Resolution: Spec 和 design.md 已补齐；无依赖版本和业务行为变化。

## 核对结果

- Business / Contract: 初始化入口与生命周期调整明确；Semantic、SQL Guard、Authorization、管理员交互和原子发布受现有 Contract 保护。
- Dependency: bootstrap 仅在边缘装配；模块不反向依赖 bootstrap，不新增业务层或通用注册框架。
- Alternative: 对比仅移动文件、第二个 FastAPI shell、单一应用启动绑定，选择第三项，详见 design.md。
- Migration: 已发现 README、Runbook、CI、reset 脚本和数据库测试 runner 的调用，按命令组原子迁移并删除旧入口；历史证据保留。
- Testing: 正常、失败、部分创建、cleanup 抛错、重复生命周期、命令参数 / 退出码、数据库权限与 startup smoke 均有对应验证方向。
- Scope: 修订为已确认 Contract 内局部设计，不增加一键初始化、环境操作或生产部署。

Reference: 已读取 Architecture Knowledge Core 的复杂度、依赖方向、可观察行为、失败与状态、Design Twice、迁移与过度工程章节。
Evidence Sources: Spec；Architecture；Query API / RAG Spec 与 Design；main.py、app.py、Control DB admin / CLI、Business Analysis runtime / application、RagRuntime、Tracing、Query Executor、相关测试、CI；本机锁定安装的 SQLAdmin / Starlette 源码。没有运行实验或产品测试。
Next: workflow-to-tickets；当前主 Agent 执行 workflow-ticket-readiness 后请求用户确认拆分及整体实施范围。

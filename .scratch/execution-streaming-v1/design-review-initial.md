# R4 设计首轮只读 Review

Review: NEED FIX
Review Target: [已确认 Spec](spec.md)、[设计候选](design.md)
Baseline: `2019443020bb7a20a8c3d1a578a613544ad8148b`
Mode: 当前主 Agent 只读审查；未启动独立 Agent，未改代码 / 测试 / 配置。

## Findings

### F1 分析 Guard 的受理交接窗口

Signal: 后台受理与 worker 进入共享分析 Guard 之间缺少具体的所有权交接。
Evidence: `HistoryApplication._execute_attempt()` 现在在同步调用内获取 `AnalysisExecutionGuard`；Design §4 只要求 HistoryRuntime 活跃登记覆盖受理窗口，旧 `/api/v1/query` 分析仍可能在 worker 开始前取得同 run Guard。
Impact: 新执行已受理后可能与旧入口争夺原 run，checkpoint /取消 registry 竞争结果难预测，违反同 run 唯一执行与可恢复性。
Recommendation: 在 admission 内先取得共享 run 的可转交 lease，再受理；同步 /后台入口统一获取方式，worker实际结束才释放，重复受理不再获取。失败与进程关闭覆盖 lease回收。

### F2 shutdown 的真实嵌套顺序

Signal: “先 drain 再释放”尚未映射 API lifespan 的实际嵌套顺序。
Evidence: `app.py` 的直接注入分支先 `analysis_guard.drain()`，生产分支退出其 runtime context 后按 ExitStack回调释放资源；后台 worker新增后若停止signal晚于 Guard drain，会等待至原分析超时。
Impact: 停止监视器 /业务资源的先后顺序不明，可能令尚在执行的worker访问关闭的checkpointer /HTTP /DB，增加恢复未知项。
Recommendation: 明确 API finally 先 close_admission / signal / stop_observers / drain_execution，再原 HistoryRuntime /AnalysisGuard drain，再退出业务资源context；将正常和部分装配失败纳入测试。

### F3 有界 SSE 的常量与回滚 FK

Signal: 设计将订阅 /事件缓存上限和回滚删除兼容条件留给实施，尚不能客观验收。
Evidence: Design §8 要求有界但无明确ring /订阅数；§10 “若v3删除不兼容”仍是分支方案。原v3删除turn不知道新execution表，默认restrict FK会阻断正常历史删除。
Impact: Reader内存资源和兼容验证缺少边界，Ticket不能确定设计完成条件。
Recommendation: 明确共享有界ring /每执行订阅上限、慢读重同步 /资源拒绝以及解析大小；新增FK明确ON DELETE CASCADE，只删执行元数据，不影响独立成果；真实v3保留数据删除回归。

### F4 新API的浏览器校验与公共错误 Contract

Signal: 新 `/executions` 未纳入当前 middleware前缀；新202 /查回 /取消 /超限错误未形成唯一映射。
Evidence: app observability middleware只匹配query /histories /saved-results；BrowserIdentityProvider强制X-user-ID。Design选择fetch正确，但所有新路由的no-store /CSRF /Trace /受控错误要有确定路径。
Impact: 实施可能有安全Header或错误处理不一致，前端重连把鉴权失败误当普通断连。
Recommendation: 显式扩展middleware前缀或在新Adapter统一等价行为，补错误状态与业务payload边界；按X-user-ID /Cookie写校验 /Cache-Control回归。

## Reference / Evidence

已读取 Architecture Knowledge Core 全文，按业务 /变化轴 /依赖方向 /信息隐藏 /失败 /可测试性 /替代方案和迁移规则审查。事实源为 Spec、Architecture /Product Scope /Domain、实际 history /auth /sharedGuard /API lifespan /Control migration与SDK源码；没有运行软件 /PG /模型 /浏览器，未声称实现证据通过。

上述修订均可在已确认 Contract 内完成，不需要重新决定用户目标、单进程边界或取消语义。返回设计准备，修订后再次只读审查；本轮不进入 Tickets 或编码。

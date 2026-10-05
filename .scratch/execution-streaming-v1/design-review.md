# R4 最终 Design Review

Review: PASS
Review Target: [已整体确认 Spec](spec.md)、[修订实施设计](design.md)
Baseline: `2019443020bb7a20a8c3d1a578a613544ad8148b`
Mode: 当前主 Agent 只读 Review；未启动独立 Agent，Review期间未修改目标 / 代码 / 测试 / 配置。

## 结论与边界

设计在已确认 Contract 内可实施：同一查询 /分析业务链、历史成功事务与执行状态、单进程worker、SSE快照 /增量、停止 /授权、checkpoint封锁及回滚有明确所有权、输入输出与验证seam。没有需要用户重新裁决的业务、模块一级职责、技术产品或授权不变量变化。

PASS 表示设计门禁通过，不代表 Provider、数据库、浏览器、容量或实现已经验收，也不授权编码 / Commit /发布。首轮 NEED FIX 保留于 [历史审查](design-review-initial.md)。

## 首轮发现闭环

| 发现 | 设计修订 /复核 |
| --- | --- |
| F1 run Guard交接 | §4：受理前获取共享分析lease，worker接管而非二次获取，busy受理前拒绝、失败回收，旧同步入口共享同一Guard |
| F2 shutdown顺序 | §10：API finally先停止受理 /观察并signal + drain worker；monitor保留至worker退出；随后Guard drain与资源context释放；直接注入 /部分装配失败同序 |
| F3资源 /回滚 | §3/§8/§10：execution FK级联清元数据，旧历史删除不被restrict；共享ring64帧 /1MiB、每执行8订阅、文字帧16KiB、草稿 /raw JSON5MiB、浏览器帧6MiB；溢出重同步，真实v3保留数据回滚必须验证 |
| F4接口安全 /错误 | §6/§7：无续期Session检查、fetch保留X-user-ID；新增middleware前缀 /no-store /CSRF /Trace；202受理、409冲突、429资源保护、404查不到、401/403失效、503未确认映射明确 |

## 继续实施必须兑现的约束

- 取消与成功在同一PG裁决边界：停止已确认受理后不能成功回写；取消分析registry封锁在请求停止事务内成立，不能先ACK后再封锁。
- 受理登记先于任何GET reconcile可见的窗口；Store同operation去重在额度 /revision拒绝之前识别原执行。DB提交结果未知不得删除幂等键重执行。
- 停止信号不能被已有 broad catch /Graph /retry吞掉；当前不可立即中断的Provider调用保持占用，Future取消或SQL cancel回执不是执行结束证据。
- 读鉴权不续Session，也不依赖浏览器在线；无文字时仍检查授权，worker提交前再验证当前原Session /权限。
- LangGraph state不持久化Control /Observer /凭证，停止路径与mark_completed /checkpoint写入保持协调；旧Bearer正常响应保持，取消run不能被旧入口复活。
- 严格JSON增量解码和最终校验共用事实；未知结构 /重复key /escape /Unicode /generation缺口不能静默拼接；Provider不支持流式时受控失败，不能伪造打字。
- 最终PG /真实浏览器 /Evaluation证据分别绑定实际candidate；rollback、故障注入与模型真实stream不能仅以软件替身冒充。

这些是明确的实施 /验收义务，不是额外未决方案。若实现无法兑现，应返回设计审查，不能放宽断言或改用户决定。

## Review Dimensions

Business /Contract：当前已确认R4范围与逐项确认覆盖成功、停止、授权、恢复、草稿与资源边界；Domain /SQL Guard /业务数据只读不变。

Boundaries /Change Axes：HTTP观察、执行生命周期、PG事务与Provider中断 /流式各归既有边界；没有队列 /Redis /分布式协调 /通用任务框架，新增Runtime隐藏生命周期而非透传包装。

Repository Reality：实际BrowserIdentityProvider强制X-user-ID、AuthService滑动TTL、sharedGuard与history事务、Control v3验证 /旧CHECK、SDK stream /cancel接口都已逐项核对。真实Provider支持仍待已确认验收，不推定本机SDK能力等于线上中断保证。

Testability /Migration：可控clock /worker /barrier及纯decoder /reducer支持确定性行为；真实PG证明事务和fencing，浏览器证明网络 /Cookie，真实模型与业务参考证明真实流式和结果；v4增量迁移保留旧markers /数据，cancelled run采用旧版已能拒绝的expired登记。

Reference: Architecture Knowledge Core全文；尤其Business /变化轴、依赖方向 /信息隐藏、跨边界状态与可观察行为、Failure /Testability、Design Twice、Migration与Overengineering Guard。

Evidence Sources: AGENTS /Architecture /Product Scope /Domain /Roadmap；已确认Spec；actual history Application /Store /runtime、auth /browser /RBAC、API lifespan /middleware、analysis Graph /registry /Guard /summarizer、bootstrap /Control migration /verifier；前端Chat /api及现有测试入口；uv.lock与锁定SDK源码；Design列出的协议主来源。

Verification: 未运行软件测试、PG、浏览器或模型；文档链接检查通过仅证明引用存在。没有新实验 /依赖变更。

Next（Review 当时）：当前主 Agent 使用 workflow-to-tickets形成草案，再只读 workflow-ticket-readiness；READY后请求拆分与整体本地实施授权。未创建正式Tickets /业务代码 /Commit /PR。

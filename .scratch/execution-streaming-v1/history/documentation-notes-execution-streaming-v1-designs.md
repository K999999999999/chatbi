# 执行状态、worker与事件衔接：整理前的过程记录

来源：`docs/designs/execution-streaming-v1.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# R4 实施设计

Status: Design Review PASS；设计及确认记录见 [最终 Design Review](../design-review.md)；本地实现已完成，最终候选验证状态见 R4 Acceptance 与本机实时工作状态。
Owner: 当前主 Agent
Baseline: `2019443020bb7a20a8c3d1a578a613544ad8148b`
Canonical Contract: [R4 Spec](../../../docs/specs/execution-streaming-v1.md)；设计只细化其行为；实施授权依据保留于 Spec Decision Record 与本机实时工作状态。

## 1. 当前事实与方案比较

当前 `HistoryApplication` 在 `HistoryRuntime.executing()` 中同步受理 / 执行 / 提交。`PostgresHistoryStore` 以 history 行锁、active turn、epoch / generation 和成功快照事务保证单一成功上下文；`AnalysisExecutionGuard` 已供旧 API 与历史共享。保持这些机制，增加执行尝试的可观察状态。

| 方案 | 成本与边界 | 选择 |
| --- | --- | --- |
| 请求内生成 SSE 并同时执行 | 接入较短，但连接取消可能取消生成器，无法证明关闭页面后继续；受理丢失与跨页查看难协调 | 不采用 |
| 独立队列 / 执行进程与持久事件流水 | 可支持分布式，但增加队列、调度、故障恢复与部署 Contract，超出单进程目标 | 不采用 |
| 单进程受控 worker + 原历史事务 + 共享当前快照 | HTTP 受理后与连接解耦，明确占用 / 取消 / 提交，重连恢复当前快照；资源生命周期在 bootstrap 统一持有 | 采用 |

没有新数据库、框架、SDK 或一级业务模块。现有 `src/query_api/` Application 隐藏执行生命周期，Infrastructure 仍只实现 Port。模型 / SQL 业务不进入 HTTP / worker 调度器。

## 11. 验证 seam、文档与交付

- Runtime独立时钟 /可阻塞worker /可控停止适配器验证受理交接、stop /success先后、真正结束才释放额度；不以真实sleep或Future.cancel推断安全。
- Store真实PG双连接 /可控barrier验证同operation并发、跨账号、revision、停止提交事务、registry封锁、初始化 /升级 /重复、旧版保留数据回滚和迟到CAS。
- 字符串解码与reducer按实际不同chunk拆分、escape /Unicode /字段 /重试 /旧generation /序号缺口验证，断言可观察文字与最终对象，不测试私有调用次数代替行为。
- HTTP /浏览器模拟真实网络、响应丢失、并发页面、断连 /重连、无token时撤权、终态丢失；验证X-user-ID、Cookie /CSRF与只读Session期限不变化。各Profile真实/替身证据分别记录。
- 最终clean候选跑已确认全部Python /真实PG /桌面浏览器 /静态检查、R4真实模型和业务参考闭环、三套正式Evaluation统一身份与三次诊断；不增加生产容量或多副本结果。
- 维护正式R4 Spec /Design /Acceptance、Web /Query API /History受影响说明、Architecture /Product Scope /Runbook /README /Roadmap；移除与已交付R4矛盾的未来描述，R5–R7保持真实未交付。
- 一目标一active branch /worktree；当前R3文档候选独立保留，R4从master基线设计，不合入无关Commit。发布仍需独立授权，未准备真实生产rollout，无额外feature flag流程。

## 12. 证据与重审触发

设计阶段读取了本机锁定 SDK 源码、API /browser /auth、history 受理 /finish /runtime、analysis graph /run_store /shared guard、bootstrap 生命周期、Control DB migration / verifier、frontend api /Chat 与现有测试入口。实施和验收结果按适用候选记录在 [R4 Acceptance](../../../docs/acceptance/execution-streaming-v1.md) 及 Git 公共目录的本机实时工作状态中；设计阶段调查不替代当前候选验证。

协议和API能力参考：[SSE 标准](https://html.spec.whatwg.org/multipage/server-sent-events.html)、[Fetch response streaming](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch#streaming_the_response_body)、[Psycopg cancel_safe](https://www.psycopg.org/psycopg3/docs/api/connections.html#psycopg.Connection.cancel_safe)、[PostgreSQL 行锁](https://www.postgresql.org/docs/16/explicit-locking.html)。实际Provider /libpq中断能力以验收为准。

Owner为当前主Agent；需要新依赖、改变旧API响应、将历史成功与execution成功拆成两次提交、扩大单进程边界、修改取消 /恢复或授权策略时返回Spec /Design Review。内部文件划分、纯函数命名和测试辅助属于既有Contract内局部选择。

## 首轮修订核对

[首轮 Review](../design-review-initial.md) F1：§4明确admission获取可转交分析run lease；F2：§10明确实际API finally→worker drain→Guard drain→资源context顺序；F3：§3/§8/§10明确级联FK、ring/订阅/帧上限及回滚验证；F4：§7明确middleware前缀、Header与统一错误映射。未改变已确认行为、范围或单进程边界，最终只读复审已 PASS。

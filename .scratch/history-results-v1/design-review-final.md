# R3 修订设计最终 Review

Review: PASS
Review Target: [Spec](spec.md)、[实施设计](design.md)、[完整结构化恢复Contract /设计](restoration-semantics.md)
Baseline: `afad5ac18452566199bfcfdcceb1585115576a77`；当前未提交规划候选。
Mode: 当前主Agent只读Review；未启动独立Agent，审查期间未修改目标或实现代码。

## 结论与适用边界

已确认Spec及用户本轮F7补齐方向范围唯一。修订设计能够安排实施：历史持久状态、完整恢复语义、并发 /重启、checkpoint协调、接口兼容、迁移与验证都有明确约束和seam。无待裁决的业务口径、一级模块、数据库 /Provider选择或权限不变量。PASS表示设计门禁通过，不代表实现、PG竞争实验、真实浏览器或Evaluation通过，也不授权Commit /Push /PR。

## 原发现核对

| 发现 | 修订证据 /闭环 |
| --- | --- |
| F1 双状态提交 | Design§2 /§4：网页只以PG历史为权威，受理前持久化、执行后序列化与5MiB检查、快照 /成功指针同事务；明确commit未知与响应丢失区别，不经过旧内存commit |
| F2 生命周期 /所有权 | Design§4 /§5：active turn、revision、generation /epoch条件、NOWAIT竞争、进程内执行登记；重启必须停止原进程，guard失效不自动接管或提前放行，迟到提交0行拒绝 |
| F3 checkpoint完成协调 | Design§6：原ID与attempt区分，completed路径仅读结果，24h原期限、旧Web共享Guard、删除run登记expired；历史 /成果不靠checkpoint保存 |
| F4 新旧API选择 | Design§7 /§8：显式新命名空间、严格参数 /owner /CSRF、版本 /错误 /分页 /URL身份清理，旧query入口及默认短期行为保留；重查受理的operation ID和来源副本确定 |
| F5 codec /来源 | Design§3与Restoration§2 /§3 /§5：独立版本化envelope /认证state、精度 /绝对时间 /相关定义比较 /未知版本拒绝，展示说明不作为恢复证书 |
| F6 migration | Design§9：005新增对象与v3标记、显式幂等入口 /启动检查 /资源逆序释放，保留v2 /数据，旧版回滚不删除新数据 |
| F7 完整语义表达 | 用户本轮确认；Restoration§1–§5：排序 /数量 /实体选择与distinct /既有聚合过滤，独立history profile，首轮 /delta /认证binding，SQL执行前全条件核对；网页成功必须持有完整经认证state，不使用“成功但不可恢复”降级 |

## Findings

无阻断或需要先修订的发现。以下为必须在实施与证据中兑现的约束，不冒充实际结果：

- Signal: 新profile触及现有理解 /Prompt /Guard /Retrieval，默认值传播与R2映射迁移可能导致兼容回归。
  Evidence: Restoration§1 /§3 /§6，现有QueryRequest /QuerySuccess及QueryContext为不可变DTO，旧API与分析任务共用Online Query。
  Impact: 默认值丢失或旧接口意外启用新检查会放大影响到旧API /正式Evaluation。
  Recommendation: 保留末尾可选默认、在AuthorizedQueryService内部复制请求时传递标记；旧profile严格回归并记录启用入口，R2只引用同一权威mapping且保留显示行为。
- Signal: PG guard与CAS只在明确单API停止后重启边界内保护checkpoint，不能证明多副本故障切换。
  Evidence: Design§5 /§6及Spec明确排除多worker；现有分析RunStore与checkpointer独立事务。
  Impact: 错误扩张为多进程会留下旧checkpointwriter竞争。
  Recommendation: 实施真实PG /进程停止恢复检查，guard断连停止新受理；改变运行拓扑必须返回Spec /设计，不用任意TTL回收。

## Architecture / Evidence Sources

已读取Architecture Knowledge Core完整参考，应用业务优先、变化轴 /信息隐藏、依赖方向、可观察兼容、状态 /失败 /可测试性、替代方案和迁移规则。HistoryApplication /Store隐藏持久生命周期，Online Query认证规则隐藏业务语义映射，SQL Guard裁决候选，HTTP与PG技术不泄漏入业务DTO。短事务方案已与双truth /模型期间长事务比较；不新增队列、Redis、多进程协议、通用工作流或第二执行链。

实际核对事实源：AGENTS.md、Architecture /产品范围 /Roadmap /Domain与相关已确认Spec；现有query_understanding /semantic_revision /Prompt /service_execution /contracts /RetrievalContext、SQL Guard及测试、R2展示 /binding、Control DB /bootstrap /analysis生命周期与API /Web边界；沿用首轮的checkpoint /RunStore核查。三套正式Evaluation入口、Software /PG /Chrome入口来自当前Runbook与package.json，无新依赖 /lockfile版本选择。

未运行R3代码、模型、数据库或浏览器；验证计划不能写成测试PASS。历史NEED FIX报告保留：[首轮](design-review.md)、[F7复审](design-review-followup.md)，本报告是其修订后的当前设计结论。

## Next

进入workflow-to-tickets草案，然后当前主Agent执行workflow-ticket-readiness；用户确认拆分与整体实施范围后才能写正式Tickets并连续实施。远端发布仍须独立明确授权。

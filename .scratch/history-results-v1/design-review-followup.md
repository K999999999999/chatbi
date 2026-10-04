# R3 实施设计复审

Review: NEED FIX
Review Target: [实施设计候选](design.md)，行为上位依据为[已确认Spec](spec.md)
Baseline: `afad5ac18452566199bfcfdcceb1585115576a77`；未提交规划候选。
Mode: 当前主 Agent 只读审查；未启动独立 Agent、未自动修改审查目标、未执行功能测试。

## 结论

首轮F1 / F2 / F3 / F4 / F6已有明确设计机制：PG历史为网页唯一状态真相、短事务受理 /完成、epoch /generation条件提交、单进程停止后重启、共享分析Guard与completed checkpoint读取、新API命名空间、增加型迁移与保留数据回滚。以上是设计覆盖，不是运行验证通过。

F5仍有关键缺口：当前已校验语义不能表达现有查询链允许的全部条件。设计§3用“无法证明完整恢复则标为不可恢复”收口，会在业务定义未变化时拒绝已有合法结果的续聊 /重查，不能直接等同于Spec已确认的“旧定义不兼容时拒绝”。不得把这一范围收缩隐藏在实现细节中。

## Finding F7：持久恢复所需语义超出现有状态表达（高，阻断）

Signal: 完整条件恢复与复用现有ValidatedSemanticQuery之间存在表达缺口；设计中不可恢复降级尚未获得行为确认。
Evidence: `src/online_query/query_understanding.py:93` 的Candidate及`:131` 的ValidatedSemanticQuery仅有query_type / subjects / metrics / dimensions / time / filters（已验证对象另有original_question），无排序、Top-N / limit。`docs/specs/multi-metric-retrieval.md:178`允许ORDER BY与LIMIT；`tests/online_query/test_sql_guard.py:59`已有带排序的既有查询示例。Spec§普通问数续聊 /显式重查要求服务端完整条件，不允许依赖短追问、旧SQL或聊天全文恢复。Design§3尚未明确完整认证状态的字段、来源及所有现有合法形态的覆盖，现有展示result_metadata的complete不能代替这一证明。
Impact: 保存成功的查询重查可能丢排序 /排名限制，或口径与映射完全未变仍被拒绝。若靠解析旧SQL补业务含义，会使实现反向定义业务真相；若直接扩大SemanticQuery对象，又触及稳定对象语义、查询理解 /修订 /Guard Contract，需要用户确认。
Recommendation: 推荐补齐服务端结构化恢复条件：对现有已支持的排序 /排名数量等明确业务条件，在Business Semantic Resolution阶段产生Untrusted Candidate，再由程序与当前发布资产认证；持久化完整经认证条件并让语义修订 /当前SQL Guard共同保持。旧Bearer请求 /响应 /默认短期行为保持。不新增任意SQL功能，不以旧SQL作为恢复真相。先确认该稳定对象 /公共语义Contract补齐方向，固化受支持字段与兼容规则，再复审；不能在Ticket或编码中猜测。不建议直接缩减已确认“完整条件恢复”的承诺。

## Reference / Evidence

已读取workflow-design-review及Architecture Knowledge Core：变化轴、依赖方向、跨边界Contract /可观察行为、信息隐藏、可测试性 /状态、Design Twice、迁移和Overengineering Guard。沿用首轮读取的Architecture /产品范围 /领域 /API /Web /多轮 /R2 /Evaluation事实源，并重新核对Spec、Design、QuerySuccess /Request、Query Understanding、Online Query Service、result_metadata、SQL Guard测试与多指标Spec。

未运行R3 Software Test、PG实验、浏览器、Evaluation、真实模型 /数据库验收；不能输出PASS / READY或声称实现已完成。

## Next

就F7补齐方向取得一次关键确认，返回Spec /设计作者阶段；不重问已确认的持久化、保留、删除、身份和恢复目标。完成语义字段 /来源 /兼容设计后复审，PASS才形成Ticket草案。当前仅规划授权，无功能实施 /Commit /Push /PR授权。

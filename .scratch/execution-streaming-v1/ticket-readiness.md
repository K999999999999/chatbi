# R4 Ticket Readiness Review

Ticket Readiness: READY
Scope: [已确认 Spec](spec.md)、[修订 Design](design.md)、[Design Review PASS](design-review.md)、[六项 Ticket 草案](tickets-draft.md)
Baseline: `2019443020bb7a20a8c3d1a578a613544ad8148b`
Mode: 当前主 Agent 只读检查；未调用独立 Agent，Review期间不修改Ticket /Spec /代码 /测试。
Owner: 当前主Agent统一维护六项与跨切片共享Contract；不新增跨团队Owner或Backup组织。

## 结论

六项粒度形成可验证纵向闭环。01提供后台受理 /查回 /正式结果，02网页可观察真实阶段，03取消 /超时 /授权停止，04在文字改动前真实验收该闭环，05接入模型文字增量，06统一完整候选与正式事实源 /Evaluation。可在授权后按依赖连续实施。

READY本身不提供编码或交付授权。用户于 2026-10-05 已确认六项拆分与整体本地实施范围；正式 Ticket 文件已建立，Ticket 01 开始实施。该确认不包含 Push / PR 或生产验收。

## 覆盖检查

| 维度 | 证据与判断 |
| --- | --- |
| Scope /Out of Scope | 各切片明确纵向交付与排除范围，全部属于R4，旧API /单进程 /业务指标不扩张 |
| Change Profile /Owner | 每项持续维护或收敛验收、规模、风险、Evidence与本地Delivery明确；迁移 /Runtime /decoder由对应切片负责 |
| Contract /Canonical Source | Spec为用户已确认行为，Design为实现机制，最终Review PASS；各草案引用同一来源，无竞争事实副本 |
| Dependencies | 01→02→03→04→05→06，各项只列直接前置；04实现已确认的先状态后文字验收，没有隐含独立目标依赖 |
| Owned files /边界 | 受理 /PG /auth /online-query /analysis /frontend /bootstrap位置按真实源码定位，新增文件清楚；跨切片复用owned files时按已确认先后修改，不并行writer |
| 正常 /边界 /失败 | 幂等 /受理丢失、额度、阶段、序号 /snapshot /generation、停止提交竞态、存储未知、旧epoch、撤权、草稿失败和Unicode /结构异常均有可观察断言 |
| 授权 /状态 /SQL安全 | owner /Session /CSRF、只读不续期、非在线鉴权、共享run lease、Guard /fencing /原run封锁、成功事务与只读Sales数据均明确 |
| 软件与真实证据 | Runtime可控clock /worker /barrier，PG双连接事务，HTTP/Cookie浏览器，真实模型 /RAG /DB与参考值分工明确，失败报告保留 |
| Migration /Rollback | 01新增v4 /保留markers /旧CHECK；04实际停止进程后的v3保留数据回滚 /删除cascade /成果保留，取消run用旧版可识别expired封锁，06基线变化按需复验 |
| Dependency /Lockfile | 复用uv.lock的langchain-openai1.6.0 /psycopg3.3.4及当前框架，未计划新依赖；需要新版本时返回设计，不实施中偷换 |
| Runtime Delivery | 当前本地开发 /隔离验收，不进行真实用户部署；无需虚构feature flag /生产rollout门禁，正式发布另授权 |
| Done When /事实源 | 各项targeted验证 /Review /Commit，06所有适用事实文档 /Roadmap /完整clean身份 /统一Evaluation均明确；无以代码测试通过替代交付文档 |

## 设计发现落实与风险归属

首轮F1/F2由01的run lease、受理登记 /shutdown验证覆盖；F3由01迁移与02有界ring /subscriber、04回滚覆盖；F4由01/02接口安全 /错误与浏览器覆盖，最终06兼容回归。未知Provider立即中断能力没有被偷写成承诺，03/04/06分别验证可控停止、真实现象与最终证据。

无阻断发现，未遗留需在Ticket中猜测的目标、领域、权限、公共行为或关键技术决定。纯函数命名、文件内组织与test helper属于已明确的局部实现选择。

## Evidence /未运行项目

已核对真实仓库的query_api /history /Control migration /auth /bootstrap、online_query /analysis /sharedGuard、frontend与测试目录、Runbook真实PG /Compose /Evaluation入口，Design及实际锁定SDK事实。

Markdown本地链接与行尾空白检查适用于本批文档；不运行软件测试、真实PG、浏览器或模型，因为没有实施Diff。所有验收均是计划，未改称PASS。

Post-review transition (2026-10-05): 用户确认六项拆分及整体本地实施范围（编码、适用测试 /真实验收、当前上下文Code Review与本地Commit）；正式 Tickets 写入 issues/，Ticket 01 开始实施。Push / PR /部署仍未授权。

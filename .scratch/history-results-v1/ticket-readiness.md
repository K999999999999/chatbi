# R3 Ticket Readiness Review

Ticket Readiness: READY
Scope: [已确认Spec](spec.md)、[实施设计](design.md)、[完整恢复语义](restoration-semantics.md)、[六项Ticket草案](tickets-draft.md)
Baseline: `afad5ac18452566199bfcfdcceb1585115576a77`；未提交规划候选。
Mode: 当前主Agent只读审查；未启动独立Agent，未修改Ticket /Spec /代码 /测试；未正式写issues。
Design prerequisite: [最终Design Review PASS](design-review-final.md)；F7补齐方向有用户本轮确认，旧NEED FIX报告仅作历史。

## Change Profile / Owner

整体持续维护、跨模块较大、高风险；01是最小完整持久成功闭环，需要同时覆盖完整语义 /受理 /认证 /结果 /state /页面恢复，因此较大且允许多个逻辑Commit，但不按DB /服务 /UI水平拆成不能验收成功语义的Ticket。02–05分别有可独立核验用户行为与直接依赖；06为整体证据收敛，不能代替各项自身检查。

Owner当前主Agent覆盖本目标代码、Migration、Tests、Contract和证据维护；当前没有跨仓库 /跨团队或独立Agent，Backup不适用。触及新业务口径、技术 /Provider、公共状态或运行拓扑时升级用户 /Design Review，不在代码猜测。一个branch /worktree、按依赖连续本地交付；用户尚未确认拆分 /授权实施，无发布授权。

## Findings

无阻断项，无未决Architecture、Domain、公开Contract、权限或状态决定。以下风险已在草案明确验收和停止条件：

- 01新增Schema与history profile触及核心执行链，旧API /三套Evaluation必须保持，AuthorizedQueryService内部标记传播、R2 mapping移至统一语义来源必须回归。
- restart /guard失效的安全性基于单API停止旧执行后再启动；不承诺自动failover /多worker；迟到history CAS不能冒称保护独立checkpointwriter。
- 用户主动删除不可回滚内容；代码回滚只保留未删数据 /版本，不能让tombstone复活。来源复制 /删除、active /begin互斥依真实PG事务证据，不能只测UI禁用。
- 06正式报告必须等于最终clean HEAD；tracked证据回填形成新提交后再次固定最终候选验收，最终结果记录于Git公共目录，不能靠A→B“只加文档”改写报告身份。

## Dependencies /覆盖

直接依赖：01无前置；02←01；03←01；04←03；05←02、04；06←05。无循环，不列不必要传递依赖；编号顺序可在同一主Agent连续实施，未要求并行Agent。02并不阻塞03的独立analysis。

| Spec行为 | Ticket与验收 |
| --- | --- |
| 自动问数history /失败记录 /成功一致提交 /完整状态 /刷新登录 | 01、02；含5MiB、精度、当前身份、state /snapshot原子性 |
| 完整条件跨TTL /restart续聊、当前定义比较、显式requery | 01完整首轮认证；02修订 /重查；05成果来源完整副本 |
| independent analysis /原ID /completed读结果 /24h /报告长期快照 | 03；04删除防重放；06真实checkpoint /模型闭环 |
| 多页面 /stale /busy /断连 /restart /late /guard失效 | 01基础受理 /finish /runtime；02交互 /多轮；03共享分析Guard；04、05竞争 |
| 列表20 /100、分类 /字面标题搜索 /重命名 /删除 /URL /隐私 | 01基础分页 /打开；04完整两类管理；05独立成果管理 |
| independent named results /不成功拒绝 /来源删除仍读与重查 | 05，复用02、03、04的执行 /删除行为 |
| 旧API /权限 /SQL Safety /CSRF /false success拒绝 | 每项各自失败 /安全AC；06全目标适用回归 |
| Migration /startup /关闭 /fresh /upgrade /repeat /回滚保留 | 01实现即验证；03、04必要协调；06实际整体恢复 |
| 正式文档 /三套Evaluation与诊断 /真实R3 /clean候选 | 每项同步所影响Contract /Review；06最终身份与全部事实源一致性 |

## Migration / Rollback

005增加对象、v3标记但保留v2，显式migrate、当前运行权限 /启动完整性检查；不伪造旧历史，不破坏RBAC /用户 /审计 /checkpoint /RAG /业务数据。旧版回滚停止新API、保留新表与内容，恢复升级可再读；用户主动删除不承诺还原。新profile Expand、网页Migrate，旧Bearer保留，无未经确认Deprecation或删除旧Contract。

无新增依赖 /lockfile版本，SQLGlot /PG /FastAPI /现有模型沿用；`npm ci`与锁定Python入口仍验证可复现构建。没有真实生产Rollout，因此不新增Feature Flag /分批发布 /生产恢复门禁；如果实际部署范围改变则返回用户授权与R6。

## Evidence

实际检查：当前Agent规则、issue tracker /Git流程、Architecture /产品范围 /Roadmap、Spec /Design /恢复语义 /Review、六项草案、当前Query Understanding /revision /执行 /Guard /Retrieval /R2 /Control DB /analysis /bootstrap /API /前端文件与测试seam；真实验证入口按当前Runbook、Evaluation Contract、frontend/package.json与.gitignore核对。

本阶段自动规划检查：六项必需字段、本地Markdown链接、直接依赖无环PASS；git diff --check PASS。它们仅验证文档结构，READINESS结论另基于上述行为 /边界 /风险 /验收的人工核对。

未运行R3 Software Test、PG实验、浏览器、模型、三套Evaluation或真实业务验收；所有Ticket Result均未实施，PASS /READY仅表示规划门禁通过。

## Next

用户确认六项粒度 /依赖，并明确完整本地实施范围（编码、适用验证含已确认真实验收、Code Review与本地Commit）。可一次回复确认拆分和完整实施，两种授权分别记录；确认后才生成正式issues并连续按依赖完成，不逐Ticket询问。Push /PR仍须独立发布授权。

# 05 具名独立成果与来源删除后的重查

Change Profile: 持续维护 /中 /高风险（独立生命周期与来源 /内容防变）；Evidence为快照 /API /PG /Chrome；Delivery本地逻辑提交。
Owner: 当前主Agent。
Blocked by: 02、04（02提供完整条件requery；04提供两类管理组件与来源删除语义，03为传递依赖）。

### What to build / Scope

- 从成功query turn /完成有效analysis report命名另存，保存相同versioned envelope的独立副本与必要来源说明；名称允许重复、只可改名不能改结果。
- 成果列表 /kind /字面标题搜索 /分页 /懒详情 /重命名 /删除，复用04的输入 /分页和页面规则，保留新的独立owner核验。
- 来源删除不级联、成果删除不影响历史；成果显式requery从自己私有完整条件 /原分析问题受理新history /run，operation去重保持来源独立。
- 正在执行时可另存来源既有成功turn，copy /delete短事务先后裁决；失败 /澄清 /未确认 /无效报告不能另存。

Out of Scope: 分享 /公开链接 /导出 /编辑数据 /图表配置保存 /仪表板；不以来源引用替代必要条件副本。

### Owned files

history与saved-results Application /API /contracts /snapshot codec /PG Adapter、frontend SavedResults /History /Chat /api /解码与样式、相关query_api /PG /Chrome测试、正式成果 /独立生命周期 /重查Contract与Design。

### Acceptance criteria /验证证据

1. 保存成功query和analysis成果内容与所选成功轮次一致、保留原始值 /说明 /截断 /图表 /完成证据；追问、来源改名 /删除、checkpoint清理均不改变成果。
2. 来源删除后从成果完整条件query重查 /原问题新analysis run仍可当前认证执行，新record不覆盖原成果；定义不兼容明确拒绝不改原内容。
3. 不成功turn /未知损坏snapshot /未完成报告拒绝；成果名1–120、同名允许、恶意名文本、跨owner /撤权 /CSRF /revision拒绝保持。
4. active时另存之前成功turn允许且不清busy；copy先完成则删来源仍读，delete先完成则保存404，真实PG两连接无半份成果。
5. 删成果原history仍读，重复 /跨owner统一不可用；详情只公开result不暴露私有state、执行token、AuthContext或checkpoint对象；Chrome双向独立删除 /重查闭环通过。

Evidence: 快照字节 /语义相等、API调用边界、PG copy /delete /dedup竞争、Chrome流程；当前模型 /业务数据验收在06。
Migration / Rollback: 使用01saved_results独立副本Schema，无来源级联FK；回滚保留表 /字节，用户主动删成果不可还原。外部分享 /公开scope变更需重新确认。
Done When: 全部适用检查 /Review /Diff、本地逻辑Commit及正式成果 /历史 /API /Web文档、证据 /roadmap事实同步完成。
Result: 未实施。
Comments: 来源标识只作说明，删除来源不使成果变为失效引用。

Status: open
Canonical Source: ../spec.md、../design.md、../restoration-semantics.md
Authorization: 用户本轮确认六项拆分及整体本地实施（编码、适用真实验收、Review、本地Commit）；未授权Push /PR

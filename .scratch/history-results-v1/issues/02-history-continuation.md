# 02 历史续聊与完整条件重新查询

Change Profile: 持续维护 /中 /高风险（条件继承、当前定义与多页面冲突）；Evidence为delta /API、真实PG /桌面Chrome；Delivery本地逻辑提交。
Owner: 当前主Agent。
Blocked by: 01（使用持久成功state与当前认证执行 /受理机制）。

### What to build / Scope

- 接入历史追问与Restoration§4严格delta keep /set /clear，基础同槽位替换 /不同槽位叠加 /明确维度替换 /歧义澄清；排序 /业务数量 /聚合过滤 /selection保留或明确更改，不存最新短delta当完整state。
- 先当前相关定义认证比较，再合并 /重新认证。定义真实变更拒绝，相关RAG读取技术失败与定义不兼容区分，无关资产 /显示格式 /build ID变化不误拒。
- 接入所选成功turn的显式requery：同一事务复制来源私有条件并受理新header /turn；创建operation唯一性定位同一目标，生成当前SQL并Guard，原快照不改；不再次理解旧问题 /执行旧SQL。
- stale context提示刷新且不排队、active busy、断连期间占用保持；刷新新revision与对应结果同时加载才可续聊，无自动重发。

Out of Scope: 跨查询比较 /经营分析路由、成果来源重查（05）、新的指标 /SQL功能。

### Owned files

`src/query_api/semantic_revision.py`及history Application /Store /API /codec /runtime、`src/chatbi_control/history.py`、Online Query语义profile /认证 /Prompt /Guard /相关权威mapping、frontend Chat /History /api /解码与状态；`tests/query_api/test_multi_turn_revision.py`及新增history /state /PG测试、`frontend/tests`。不修改旧Bearer默认处理。

### Acceptance criteria /验证证据

1. 过短期TTL /API进程停止后重启，“按销售额降序前10产品”再“改成毛利”保留绝对时期 /筛选 /分组 /direction /10，唯一排序指标同步替换；歧义多目标澄清不推进。
2. keep /set /clear、取消Top-N、维度替换导致悬空排序、聚合筛选指标更换歧义有确定性证据；失败 /拒绝 /澄清后从最后成功继续。
3. 相关口径 /映射 /类型 /Join变化拒绝，无自动指标替换；无关定义、build ID、R2显示修改不误拒；技术不可用CONTEXT_ERROR安全提示。
4. 显式重查产生新history /新真实执行，完整条件同源、旧记录 /快照固定；重复相同operation不多建 /执行，hash不符409，来源删除竞争按受理事务先后裁决。
5. 同context两个页面只一个成功，另一个busy或stale且下游调用0次；未确认页面必须读取新事实，迟到旧请求不能覆盖。API与桌面Chrome验证刷新无执行 /不默默换上下文。

Evidence: 纯delta /认证、API invoke计数、PG竞争与operation /sourcecopy事务、Chrome两页面 /恢复用例；真实当前数据对照在06。
Migration / Rollback: 使用01新增对象，无破坏迁移；失败保持原context，回滚保留快照 /state版本，未知版本不能执行。不改变旧接口生命周期。
Done When: 所有适用检查 /Code Review /Diff通过；同步正式恢复条件 /续聊 /requery Contract和Acceptance证据 /roadmap事实；本地Commit完成，Result记录候选与未验证范围。
Result:
- Candidate A `d6041af45bf4f69bb7b60053e0a404d754dc23fc` 上，Python 全量、隔离 PostgreSQL、桌面 Playwright 分别为 685 passed / 29 skipped / 139 subtests、33 passed、36 passed；代码 Review PASS。
- Compose 真实报告 `reports/browser-real/container-1791144563-real.json` 验证完整条件追问、API 重启后的快照读取 / 续聊和显式重查新建历史，独立参考一致；`status=passed`、`suite_status=passed`，绑定 clean commit。
- 正式 single-turn / multi-turn / business-analysis 在此候选分别 29/29、7/7（15/15 轮）、10/10，均 0 FAIL / 0 INVALID_CASE；统一身份验收通过。候选 B 的最终身份重验由 Ticket 06 执行并记录在 Git 公共目录实时状态。
Comments: 当前数据重查是明确的新执行，原记录始终只读历史事实。

Status: done
Canonical Source: ../spec.md、../design.md、../restoration-semantics.md
Authorization: 用户本轮确认六项拆分及整体本地实施（编码、适用真实验收、Review、本地Commit）；未授权Push /PR

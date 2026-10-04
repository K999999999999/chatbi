# 04 历史分类管理、搜索、重命名与删除

Change Profile: 持续维护 /中 /高风险（删除防重放、并发 /隐私）；Evidence为API /PG /Chrome；Delivery本地逻辑提交。
Owner: 当前主Agent。
Blocked by: 03（需要两类完整history和analysis run失效能力；01为传递依赖）。

### What to build / Scope

- 统一两类列表按最近更新排序，默认20最多100、kind筛选、字面标题搜索、keyset分页 /筛选hash、详情懒加载；默认首问题截取标题不调用模型。
- PATCH标题 /record revision；DELETE期望revision、active拒绝；清敏感轮次 /state、保留最小tombstone，analysis run登记同Control事务expired，无checkpoint恢复入口复活。
- UI列表 /管理、刷新URL记录删除 /无权访问退回新问数，已打开其他页面迟到响应不重填。

Out of Scope: 全文问题搜索 /文件夹 /分享 /年龄清理 /移动端；独立成果UI在05。

### Owned files

history API /Application /contracts /PG Adapter /必要约束、Business Analysis RunStore同事务失效协作、frontend History /App /api /样式与状态，相关API /PG竞争 /Chrome测试；正式历史管理 /隐私 /删除文档。

### Acceptance criteria /验证证据

1. 两类混合 /分类、默认标题、literal % / _ /反斜杠搜索、排序与分页界限、非法cursor /筛选不符 /长度 /UUID /unknown字段一致错误；无列表下载全量快照。
2. 重命名只影响标题，不改变state /快照 /context revision；旧record revision拒绝，不静默覆盖另一页面修改；恶意标题以文本呈现。
3. begin /delete竞争锁定明确，只能一方先成立；active不能删除，结束后删除旧ID详情 /续聊 /resume全404，原analysis ID旧入口不能复活。
4. 跨owner存在 /不存在 /deleted统一404，撤权 /禁用 /CSRF保持；成功删除后迟到finish或UI响应不能恢复数据。
5. 真实PG删除 /runexpired事务、Chrome两页面 /被删URL /退出换号管理闭环通过。

Evidence: 严格API、真实PG两连接竞争 /同事务回滚、桌面Chrome；无随机sleep作为竞争正确证据。
Migration / Rollback: 沿用01Schema，必要约束只增加。用户主动删除内容不可还原，保留原有独立数据 /业务卷；代码回滚不能复活tombstone。不通过批量删除开发数据验证。
Done When: 正常 /失败 /安全证据、Code Review /Diff、本地提交、正式Contract /隐私边界 /Runbook及roadmap适用事实同步完成。
Result: 未实施。
Comments: 删除历史与删除analysis checkpoint不是同一行为，checkpoint仅沿用既有期限清理。

Status: open
Canonical Source: ../spec.md、../design.md、../restoration-semantics.md
Authorization: 用户本轮确认六项拆分及整体本地实施（编码、适用真实验收、Review、本地Commit）；未授权Push /PR

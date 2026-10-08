# 05 — 隔离恢复与可回退的显式切换

Status: in-progress
Authorization: 用户2026-10-08确认七项拆分与全部本地实施、验证、Review和Commit；无Push/PR或实际stable切换授权。
Canonical Source: [Spec](../spec.md)、[Design](../design.md)；共同约束见 [已确认拆分](../tickets-draft.md)。


Change Profile: 持续维护 / 恢复并可安全激活的完整闭环 / 高风险（数据/权限/单写者）/ Software+真实隔离资源故障集成 / 本地Commit。
Owner: 当前目标实施维护者。
Blocked by: 03。
What to build: 本地binding兼容原固定资源；所有local操作统一解析资源归属；restore只建隔离环境；核验数据/角色/资产与登录成果；restore-activate与restore-recover按Design journal逐步切换，保留原卷/config/RAG。
Acceptance Criteria:
- 损坏/wrong key/版本不兼容/陌生归属拒绝；仅空专属卷恢复，原stable/dev数据不变；批准roles/grants恢复，无任意陌生owner/超级用户。
- 全量原指纹先验证，再撤销旧Session/epoch处理未完成执行；重新登录、已完成历史/成果可读；checkpoint原到期不延长，未完成不自动重跑。
- 固定model与业务来源重建Qdrant/RAG；完整readiness通过才candidate verified；未verified不能activate。
- 切换停止所有旧/候选writer，单PG卷仅一个PG容器附着；原子binding与journal可追溯；各阶段中断显示未完成，显式选择previous/candidate恢复，不删除/覆盖原卷或反向迁移。
- up/down/status/upgrade/rollback/backup都识别新binding；缺文件使用原R6资源，未知卷/路径拒绝；7天清理不触及原环境。
owned files: local、scripts/local_*、docker-compose.local.yml资源binding；既有bootstrap/control/init接口；tests/scripts及隔离restore验收。仅需要接入既有epoch/授权，不改Domain或业务schema。
验证证据: 真实已加密副本到空PG/Qdrant；全表指纹与权限/session/历史/checkpoint；隔离stable clone进行逐阶段故障、单写者、激活/previous回退及所有local命令兼容；原stable/dev资源前后核对。
Migration / Rollback: binding格式version1、缺失兼容旧资源；journal保留previous/candidate；操作者显式recover选择；真实stable切换需该次授权，不作为代码实施的隐含动作。
Done When: 恢复/切换/中断矩阵及Review通过；正式资源/恢复Design、Runbook和Acceptance入口完成；30分钟目标及全链路实测由07汇总，不删除原环境。


Result: 待实施。
Comments: 无。

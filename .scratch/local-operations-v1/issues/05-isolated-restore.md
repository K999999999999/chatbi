# 05 — 隔离恢复与可回退的显式切换

Status: complete
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


Result: 本地实现与Review通过。隔离恢复、显式candidate切换和previous回退已在专属真实Compose资源中运行；118项本地R7测试、Ruff和diff检查通过。实际stable/dev容器、镜像和健康状态前后未变；实际stable key初始化和stable切换未执行。完整RTO / 故障矩阵归Ticket 07。
Verification: 2026-10-08真实密文副本恢复至空专属PG/Qdrant卷；全表指纹、角色/grants、Session撤销与epoch fence、固定RAG readiness、临时登录、历史及成果详情核验通过。独立stable clone执行candidate activation及previous recovery；另强制恢复解密后preflight失败，确认明文payload清理、候选记录与受限配置保留。软件回归 `tests/scripts/test_local_*.py`：118 passed；Ruff及`git diff --check`通过。复核结论与范围见 [Review](../review-05.md)。
Comments: 测试使用临时age密钥、测试副本和本机工具镜像；不构成实际stable服务切换或R7整体运行验收。实际stable备份私钥未初始化，云端/真实运行数据未修改。

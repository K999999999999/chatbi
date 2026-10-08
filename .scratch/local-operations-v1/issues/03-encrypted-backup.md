# 03 — 固定工具镜像与可恢复的手工加密备份

Status: in-progress
Authorization: 用户2026-10-08确认七项拆分与全部本地实施、验证、Review和Commit；无Push/PR或实际stable切换授权。
Canonical Source: [Spec](../spec.md)、[Design](../design.md)；共同约束见 [已确认拆分](../tickets-draft.md)。


Change Profile: 持续维护 / 手工备份完整闭环 / 高风险（Secret与数据）/ Software+真实PG/age隔离集成 / 本地Commit。
Owner: 当前目标实施维护者。
Blocked by: 01。
What to build: 固定age1.3.2/官方SHA-256与PG16客户端工具镜像；显式init-backup、backup、backup-list。保留所有Control状态与只读业务DB一致性快照、批准角色身份、固定发布/model/资产及必要敏感配置；tool内加密/完整解密校验，原子登记known catalog与安全状态。共享operation lock、最小权限、受限临时文件、固定成员/容量/超时边界。
Acceptance Criteria:
- 私钥/Secret从不进入Git、argv、日志、业务API或公开投影；重复init不覆盖key，文件/目录权限符合Design；API只能读安全public子目录。
- 正常业务写Control时dump和指纹同exported snapshot，业务只读身份前后核对；备份不中断业务，无跨库共享snapshot假承诺。
- 密文/manifest/dump损坏、磁盘不足、wrong key、锁冲突、工具超时/中断失败不登记、不删除旧副本，清除受限临时明文；解密/TOC/成员校验通过才发布。
- 登记只接受本机known id/hash/归属，拒绝任意路径/陌生archive；记录实际active版本，不把最新build代称当前运行。
owned files: local；scripts/local_*及最小backup工具；新增固定工具Dockerfile；docker-compose.local.yml仅工具/安全projection挂载；.gitignore/.env.example安全模板（如适用）；tests/scripts与隔离集成入口。
验证证据: age固定包摘要/镜像来源与PG版本记录；真实双库并发Control写入snapshot一致性；解密恢复前指纹/TOC；故障注入与权限/secret扫描；public投影原子替换可见。
Migration / Rollback: 新backup format1/catalog，不迁移原业务数据；现有R6缺keys显示未初始化。镜像/模板变化不自动初始化真实stable；停止工具不会影响原API，既有副本保留。
Done When: 可校验副本完整证据、Review与工具供应链核验；正式备份Contract、密钥保管/丢失/失败处理Runbook完成；真实空库恢复能力在05验证，当前不冒称已演练。


Result: 待实施。
Comments: 无。

# 04 — 自动备份、保留期和升级失败保护

Status: open
Authorization: 用户2026-10-08确认七项拆分与全部本地实施、验证、Review和Commit；无Push/PR或实际stable切换授权。
Canonical Source: [Spec](../spec.md)、[Design](../design.md)；共同约束见 [已确认拆分](../tickets-draft.md)。


Change Profile: 持续维护 / 定时与升级两个触发的同一备份政策 / 高风险（升级数据安全）/ Software+容器生命周期集成 / 本地Commit。
Owner: 当前目标实施维护者。
Blocked by: 03。
What to build: stable独立工具服务随up/down启停，运行期间每6小时备份，超过24小时/无副本启动立即补备份；7天保留与失败/逾期提醒；升级在旧API停止前备份旧active，失败拒绝升级。
Acceptance Criteria:
- 不持Docker socket、不自动重启API；电脑/Docker停止不虚报已执行；调度失败有界重试、无热循环；锁冲突不与恢复/升级并行写。
- 最近成功时间/安全失败原因可见；超过24小时持续警告，不假承诺RPO；管理员显示详细状态，普通无备份细节。
- 只有新副本校验并登记成功才清理已知过期副本；失败保留旧副本和服务；不清理陌生文件/密钥/回退卷。
- 升级备份读取旧active release/binding，目标镜像已构建也不改变源版本；备份失败原API继续可用，成功后仍执行R6兼容门禁。
owned files: local、scripts/local_*、docker-compose.local.yml与backup scheduler；01安全状态投影展示；tests/scripts、容器隔离验收。
验证证据: clock驱动6h/24h/7d边界和重试；服务up/down、锁竞争；两真实发布版本升级前失败/成功与旧数据指纹；过期提醒权限及API不停服。
Migration / Rollback: 无DB migration；增量工具服务restart:no；升级故障在停止旧服务前退出。停止调度保留keys/catalog/已有副本并显示不再有新成功证据。
Done When: 全部时序与升级保护证据、Review、Runbook备份与升级步骤及roadmap事实核对完成。


Result: 待实施。
Comments: 无。

# 01 — 动态就绪、近期模型结果及安全状态入口

Status: done（本地实现与切片验证；最终clean运行验收见07）
Authorization: 用户2026-10-08确认七项拆分与全部本地实施、验证、Review和Commit；无Push/PR或实际stable切换授权。
Canonical Source: [Spec](../spec.md)、[Design](../design.md)；共同约束见 [已确认拆分](../tickets-draft.md)。


Change Profile: 持续维护 / API+bootstrap+前端+CLI的单一状态闭环 / 高风险（权限与就绪）/ Software+隔离依赖+浏览器 / 本地Commit。
Owner: 当前目标实施维护者。
Blocked by: 无。
What to build: 复用启动资产门禁，增加有界15秒周期探测、10秒周期上限、30秒过期规则与近期15分钟真实模型结果；/health保持兼容，/ready与operations/status按Design DTO；网页普通/管理员投影、./local status实时容器事实及安全状态。提供备份状态projection的受限读取边界，03再提供真实写方；缺证据显示未初始化/未知。
Acceptance Criteria:
- 依赖成功/故障/恢复/超时/资产变化/过期有确定性状态；运行且网页打开时故障和恢复60秒内显示；挂住探测不阻塞后续恢复，关停无无界worker。
- 定时检查不调用LLM；模型Adapter实际结果更新，过15分钟或重启unknown；后续SQL失败不改变模型结果。
- 未登录401；普通无details；管理员仅安全详情；Control身份核验失败不泄露；Cookie来源/expected-user/混用Bearer规则保持。
- 状态轮询不触碰last_seen、30分钟Idle/8小时Absolute、Cookie；禁用/撤销及时拒绝，HTTP/网络失败不显示旧正常。
owned files: src/query_api/app.py、browser.py和新增最小运行状态文件；src/bootstrap/readiness.py及装配；实际模型Adapter的结果观察；frontend/src/api.ts、App.tsx和最小状态组件；local/scripts本机状态读取；对应tests/query_api、tests/bootstrap、tests/scripts、frontend/tests。
验证证据: 注入clock/probe的状态矩阵；真实HTTP权限/TTL数据库读写断言；隔离PG/Qdrant故障计时；浏览器两种role与断网恢复；./local status读取不到证据用unknown。
Migration / Rollback: 无业务schema migration；缺新projection兼容显示未初始化；缺stable必要装配fail closed。新资产/状态格式version1；撤回代码仅能在兼容既有配置时回原候选，不改数据。
Done When: 上述证据、Review、Spec/API/Runbook/Design相关章节与状态提示说明完成；60秒真实证据若依赖最终整体验收，明确暂不宣称总目标完成。


Result: 动态状态/只读HTTP/前端/CLI/真实模型结果观察已实现；软件、Windows Edge确定性浏览器、真实资源只读probe、静态/链接检查通过，见 [Review与证据](../review-01.md)。当前stable未部署新候选，60秒故障/完整运行目标由07验证。
Comments: 无。

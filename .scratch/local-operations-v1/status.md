# R7 长期规划记录

当前：01–04已本地实现/Review；完整跨版本与恢复/运行验收未完成，继续05–07。无Push/PR或实际stable切换授权。以下按时间保留规划与实施历史，实时阶段见Git公共目录记录。

## 初始规划快照（拆分确认前）

2026-10-08：用户已整体确认 [Spec](spec.md)。首轮Design Review NEED FIX后在既有Contract内补齐 [Design](design.md)，[复审PASS](design-review-2.md)。[七项Ticket草案](tickets-draft.md)经当前主Agent [Readiness READY](ticket-readiness.md)，待确认拆分与完整本地实施范围。

尚无工程实现、Commit或本目标Push/PR授权；当前只是规划文档。Baseline `0c77d80`，Stable历史runtime `2b4a8c8`。真实stable升级/密钥初始化/恢复切换不隐含在本地实施授权内。

正式Ticket确认后按01–07依赖连续推进。新验收由候选建立，既有R6/Evaluation/云接入报告不重标。roadmap仅更新确认及准备事实，不重排优先级。

实时阶段/授权/阻碍/下一步以Git common-dir的harness/work-items/local-operations-v1/status.md为准；产品总目标引用该子工作项。

2026-10-08：用户确认七项拆分和全部本地实施、验证与Commit；正式issues/已生成，按依赖连续推进。无Push/PR或实际stable资源切换授权。

Ticket 01本地实现、软件及Windows Edge确定性入口验证/Review PASS；probe在原stable资源只读核验PASS（4.624秒）。完整clean候选运行验收留07，未发布或修改stable。开始02共享受理保护。

Ticket 02共享受理保护已完成本地实现与Review，205+14subtests、追加37/14、WindowsEdge12项PASS；2项依赖真实renderer条件SKIP，07完整验证补齐。开始03手工加密备份。

Ticket 03手工备份本地实现/Review PASS；固定age工具、真实PG并发snapshot到空库恢复指纹、wrongkey/损坏/unknownrole/明文清理PASS，24新增与87相关回归PASS；原stable仅只读来源核验，未初始化真实key或备份。继续04自动调度/升级前保护。

Ticket04本地实现/Review PASS：6h/24h/7d、失败冷却/锁/已知清理/升级保护软件验证，真实PG/age scheduler产物与0.016s停止、WindowsEdge14项PASS。来源处理已回归Spec宿主无新依赖，原R6仅只读核验，未修改实际服务/key/data。跨版本完整矩阵留07。继续05隔离恢复与显式资源切换。

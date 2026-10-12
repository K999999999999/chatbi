# 历史持久化与恢复一致性：整理前的过程记录

来源：`docs/designs/history-results-v1.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# R3 历史与成果实施设计

Contract：[History Spec](../../../docs/specs/history-results-v1.md)。已确认设计的本地实现；验收见 [Acceptance](../../../docs/acceptance/history-results-v1.md)。

## 1. 方案与边界

网页长期状态由PostgreSQL历史记录唯一裁决，旧Bearer `/api/v1/query` 保持原请求 / 响应和默认短期状态。新增历史接口不调用旧 `_authorized_query` 的内存create / commit：复用现有授权服务、语义修订、OnlineQueryService及BusinessAnalysisApplication，只把网页状态提交替换为历史事务。

| 边界 | 职责 / owned files |
| --- | --- |
| History Application / Contract | `src/query_api/history.py`、`history_contracts.py`、`history_codec.py`：当前身份、受理、成功 /失败提交、来源及恢复策略；独立DTO与一个HistoryStore Port，不依赖FastAPI / ORM |
| History API Adapter | `src/query_api/history_api.py`、现有app / browser / response：HTTP、当前Cookie或显式Bearer身份、CSRF、输入 /响应；不生成SQL或定义指标 |
| PostgreSQL Adapter | `src/chatbi_control/history.py`：事务、行锁、约束、版本 /占用及快照存取；没有业务公式或权限策略 |
| 当前语义认证 | `src/online_query/semantic_state.py`、query_understanding / revision / prompt / Guard及必要contracts / service_execution / RetrievalContext改动：结构化语义的严格codec和当前业务定义 /认证映射比较；不存储历史、不依赖Control DB |
| 执行资源 | `src/query_api/history_runtime.py`、bootstrap runtime / lifecycle：单API进程启动归属、在执行请求登记、重启恢复和资源释放 |
| 分析运行互斥 | `src/business_analysis/run_execution.py`：当前进程同owner / analysis_run_id执行互斥；旧analysis入口与历史入口共享Guard，保持原图与checkpoint类型 |
| Web | 新History / SavedResults组件与解码器，修改Chat / App / api / styles；复用ResultView / AnalysisReport，清除身份私有状态 |

这些是现有Application与Adapter职责内的文件，不新增一级业务模块、第二条执行链路、数据库产品或依赖。HistoryStore的方法围绕完整操作（begin_attempt / finish_attempt / copy_result / delete_history等），不暴露任意SQL、ORM Row或“先调用A再B”的隐式事务。

### 方案比较

| 方案 | 成本与问题 | 决定 |
| --- | --- | --- |
| 保留网页内存状态，执行后另写历史 | 改动少，但保存失败时内存已前进；重启后需协调两个真相；不能满足F1 | 不采用 |
| 长事务从受理到模型结束，锁整段对话 | 数据提交直观，但模型执行期间持有PG事务 /锁，断连恢复难，读取 /另存 /关闭成本增大 | 不采用 |
| 持久历史真相，短事务受理与完成，条件提交 | 一次明确的Store边界管理版本与执行身份；模型期间释放行锁；可确定性证明失败 /删除 /迟到行为 | 采用 |

并发控制依赖PG实际事务和行锁：[PostgreSQL 16 Explicit Locking](https://www.postgresql.org/docs/16/explicit-locking.html)、[Transaction Isolation](https://www.postgresql.org/docs/16/transaction-iso.html)。选择已确认的现有数据库；不引入Redis、后台队列、分布式锁服务或通用工作流引擎。

## 10. 可测试性与受影响边界

| F项 | 确定性seam /实际证据 |
| --- | --- |
| F1 | HistoryApplication注入Store与下游：begin失败无execute、finish回滚旧state、commit后响应丢失只读成功、大小 /编码失败、无双重truth |
| F2 | 真实PG两个连接竞争begin /delete /copy、epoch /generation旧token拒绝；注入本地Registry仍running /已结束 /guard失效；实际单API进程停止再启动 |
| F3 | 同run旧API /Web Guard竞争、completed→无graph.invoke、未完成原ID恢复、删除标expired、过期拒绝、checkpoint清理后成果仍读 |
| F4 | httpx公开API：严格字段、状态版本、统一跨账号404、permission撤销 /CSRF、分页 /字面搜索 /操作ID复用、旧API字段与默认行为 |
| F5 / F7 | 完整恢复语义的字段 /delta /当前资产 /SQL条件一致性及排序 /Top-N /entity /既有聚合筛选；原始数值 /绝对时区 /相对时间跨天codec roundtrip；来源定义变化拒绝、无关定义不误拒、未知version不执行，未知展示说明原表格降级 |
| F6 | fresh PG与v2已有库升级、重复migration、权限 /缺对象启动拒绝、回滚旧版保留数据、关闭guard连接 |

每个ticket包含纵向API /UI或状态行为，不先完成所有DB再接所有业务。无新依赖 /lockfile版本，无新增真实业务指标。最终按Spec完成桌面Chrome、真实模型 /数据库R3闭环、三套正式Evaluation与统一身份验收；设计复审不代替这些实际结果。

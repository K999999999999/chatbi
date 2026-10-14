# ChatBI产品范围

本文说明当前可用能力、支持场景和限制。具体功能规则见 [Spec](specs)，技术结构见 [架构](architecture.md)，后续方向见 [Roadmap](roadmap.md)。

## 产品定位

面向销售业务数据的领域AI引擎，采用模块化单体。模型提出候选，程序裁决业务口径、权限、SQL安全和状态。

## 当前能力

| 能力 | 支持范围 | 行为规则 |
| --- | --- | --- |
| 自然语言问数 | 实体查询、明确指标、时间 / 分类分组、筛选；单次最多5个指标、一条安全SQL、有界结果 | [查询](specs/online-query.md)、[检索](specs/online-retrieval.md) |
| 多轮追问 | 基于最后成功的结构化条件修订；失败不污染状态，歧义先澄清 | [API](specs/query-api.md)、[恢复](specs/query-restoration.md) |
| 经营分析 | 两个明确时期的人民币净销售额 / 毛利变化，以产品及单价 / 数量 / 成本因素归因 | [分析](specs/business-analysis.md) |
| 电脑端Web | 指定账号登录、首次改密、问数与分析独立模式、当前Session权限 | [Web](specs/web-dialogue-v1.md) |
| 结果展示 | 可信指标 / 单位 / 范围、表格、适用折线 / 柱图、归因证据、安全降级 | [可视化](specs/result-visualization-v1.md) |
| 私人历史与成果 | 自动历史、快照重开、完整条件续聊、显式重查、独立保存 / 删除 | [历史](specs/history-results-v1.md) |
| 执行状态 | 后台受理、真实阶段、SSE、未经校验草稿、取消、断连重连与恢复 | [执行](specs/execution-streaming-v1.md) |
| 文件导出 | 成功查询XLSX、适用单图PNG、正式分析PDF；从有权访问的快照生成 | [导出](specs/result-export-v1.md) |
| 本机运行 | 容器开发与标准本地构建、显式初始化、资源隔离、动态就绪与诊断 | [部署](specs/container-deployment.md)、[保障](specs/application-readiness.md) |

## 数据与用户边界

- 单一PostgreSQL `mart_sales` 数据源，使用Sales Mart合成数据；当前指标以Semantic目录的登记定义为准。
- 指定用户共享同一套业务数据；历史与成果按账号隔离。固定RBAC不代表行列级数据隔离。
- 管理员创建账号，无公众自助注册；账号、Session与业务访问每次由程序验证。
- 查询只读、关系由认证直接FK→PK提供，不让模型自由跨表或改业务定义。
- 模型、索引与结构记录都有来源与发布身份；业务定义不由模型或旧快照重新解释。

## 运行与验证边界

当前支持Windows + WSL2 + Docker的本机单API进程和电脑端同源访问。统一使用dev容器开发，标准应用Compose与开发资源分开；启动、迁移、模型 / 索引和管理员初始化都是显式操作。

确定性软件测试、真实AI评测、业务与运行验收提供不同证据；报告只对记录的提交、案例集与资源有效。可复现入口见 [Runbook](runbook.md)。

## 当前不支持

多数据库 / 多Schema、多租户、部门 / 区域行列级隔离；任意复杂Agent、自动SQL修复、自由多查询分析；全量分页或扩展导出查询；手机适配、公开分享与仪表板编辑。

公网 / 云生产部署、多worker / 多副本协调、网关流量治理、多用户容量 / 延迟承诺、整机或磁盘损坏后的异机灾备不在当前支持范围。项目不提供自研发布、升级回滚、备份恢复或企业编排能力。

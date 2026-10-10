# ChatBI 产品 V1 作品交付入口

本文汇总产品 V1 已确认的作品交付内容：演示、架构说明、可复现评测和运行证据。它是导航入口；各项行为 Contract、验收结论和报告身份仍以所链接的事实源为准。

## 演示

- 本机稳定环境启动、状态检查、停止和限制见[Runbook](../runbook.md) 的“本机稳定环境”章节。
- 默认网页地址为`http://127.0.0.1:8080/`。演示数据为合成 Sales Mart；Stable当前发布源为R7候选`6d764ac`，不是云端或公网部署。
- 环境初始化、账号管理和固定版本运行方式见[R6本地部署验收](local-deployment-v1.md)；R7运行保障、备份和恢复方式见[R7本地运行保障验收](local-operations-v1.md)。

## 架构与产品边界

- [Architecture](../architecture.md)说明模块化单体、依赖方向和核心查询链路。
- [Product Scope](../product-scope.md)与[Roadmap](../roadmap.md)说明当前产品边界及V1需求顺序。
- 每项行为的权威Contract见`docs/specs/`对应文档；本文不重复定义业务语义。

## 交付与验收证据

| 范围 | 交付内容与验收入口 |
| --- | --- |
| R1 Web 对话 | [Web 对话验收](web-dialogue-v1-20261003.md) |
| R2 结果解释与可视化 | [结果可视化验收](result-visualization-v1-20261004.md) |
| R3 历史与成果 | [历史与成果验收](history-results-v1.md) |
| R4 执行状态与流式反馈 | [执行与流式验收](execution-streaming-v1.md) |
| R5 成果导出 | [导出验收](result-export-v1.md) |
| R6 本地部署交付 | [本地部署验收](local-deployment-v1.md) |
| R7 本地运行保障 | [本地运行保障验收](local-operations-v1.md) |

路线图中记录的每个候选及其 Evaluation、Acceptance 证据必须保持各自的提交、案例集和运行资源身份；历史报告不会自动成为新候选的通过证据。

## 可复现评测

- 评测分类、案例集和身份约束见[Evaluation Spec](../specs/evaluation.md)。
- 环境准备、单项命令、三套正式基线和身份核验见[Runbook 第 9 节](../runbook.md)。正式交付检查按第 9.2 节在同一干净候选运行单轮、多轮和经营分析评测，并验证`git_dirty=false`、提交、RAG版本及案例集身份；只有全部案例有效且通过时才接受该候选为正式基线。
- 原始 JSON / Markdown 报告位于本机 ignored `reports/evaluation/`，不会随 Git clone 分发，也不得把 Secret 或本机运行凭据放入文档。新环境按Runbook准备授权的`.env`后重新运行即可获得绑定新候选的报告。

## 运行边界

- 当前交付面向指定 Windows + WSL2 + Docker 本机使用与演示；不代表公网 / 云部署或多用户容量承诺。
- 当前备份覆盖本机误删、数据卷损坏和升级失败；不承诺整台电脑或磁盘损坏后的异机恢复。
- 模型状态根据最近真实请求显示；没有近期调用时`unknown`是未确认状态，不等同于服务未就绪。

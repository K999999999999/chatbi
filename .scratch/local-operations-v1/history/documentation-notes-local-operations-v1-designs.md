# 就绪、备份与恢复机制：整理前的过程记录

来源：`docs/designs/local-operations-v1.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# R7 本机运行保障实现设计

Status: 已确认Spec的Contract内实现设计；Design复审PASS，见 [复审](../design-review-2.md)；01–04已本地实现，完整运行验收未完成。Canonical Source: 行为以 [Spec](../../deployment-simplification/history/docs--specs--local-operations-v1.md) 为准；本文仅固化Contract内实施机制。Owner: 本目标实施维护者。Baseline: 0c77d80。

## 1. 边界与变更轴

不新增一级业务模块。运行状态快照与共享额度属于现有query_api Application；HTTP/前端展示留在Adapter；依赖探测与模型调用观察在bootstrap/Infrastructure装配。业务Domain、模型Prompt、SemanticQuery、Certified Physical Mapping与SQL Guard不变。

备份/恢复属于scripts和local运维边界，用独立工具容器承载age/PostgreSQL客户端。工具具有受限主机目录和必要数据库管理权限；业务API只读安全状态投影，无迁移凭据/私钥/Docker socket。阿里云通过现有TraceRecorder/OTLP Adapter，不在业务Core引用云SDK。

不为每个状态创建Service/Repository层。最低边界是一个可注入clock/probe的状态快照、一个现有runtime内共享额度租约，以及运维文件/进程Adapter。真实网络/数据库/文件交由Adapter，纯状态规则用确定性测试。

## 8. 验证与交付边界

沿Spec测试矩阵，每个纵向切片都有对应软件/隔离集成/文档门禁，不能把所有安全验证留到尾部。clock/probe/snapshot/transporter/资源命令提供真实边界可注入seam，避免测试专用业务分支。

最后clean image执行Windows真实入口、备份/恢复/切换/回退、60秒故障/恢复、权限与无保活、Secret与资源归属、阿里云Trace及单用户容量/RTO报告；选择多个代表用例记逐次耗时和CPU/内存峰值，不在少量样本上声称可靠p95/SLA。

正式Spec/Design/API/Architecture/Runbook/Observability/Acceptance/Product Scope/roadmap按适用范围同步；最初只保留scratch规划，不提前改正式Contract。未授权主机重启/永久IDM/稳定数据切换，不在验收中执行。

无需新增业务migration即可保存运行/备份绑定状态到本机受限文件。若实施证据要求改变schema/权限或稳定一级边界，返回Spec/Design审查。实验若需要真实资源/配置变更，先定义实验及授权，不以Design写入代替验证。

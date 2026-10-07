# R6 本地固定版本部署验收

Status: Ticket 01 / 02 / 03 适用验收完成；Ticket 04 完整隔离环境验收进行中。尚未确认 R6 完整通过。

范围以 [Contract](../specs/local-deployment-v1.md)、[实现设计](../designs/local-deployment-v1.md) 和 [R6 Spec](../../.scratch/r6-local-deployment/spec.md) 为准。

## 已有证据

- 固定版本镜像：Ticket 01 clean commit `4d4732b7896a46b231a4a3437c703e74b5ae513f`，API / PostgreSQL revision、内嵌 release JSON、实际 image ID、CPU 依赖及网页 / 导出资产检查通过；见 [Ticket 01](../../.scratch/r6-local-deployment/issues/01-fixed-release-image.md)。
- 独立稳定环境：空卷安装证据绑定 `0a9f5aa`，Ticket 02 最终候选 `733b074` 完成 Windows Edge 真实问数、端口冲突保护、手动启停和历史持久性；见 [Ticket 02](../../.scratch/r6-local-deployment/issues/02-isolated-local-runtime.md)。
- 真实版本往返：`733b074 → 9ae32ef → 995440b → 9ae32ef → 995440b`；升级执行 migration，回滚没有运行 migrator。账号、历史、快照指纹一致，稳定 PostgreSQL / Qdrant 容器和卷身份保持；当时保存成果为空，完整成果持久性由 Ticket 04 验证；见 [Ticket 03](../../.scratch/r6-local-deployment/issues/03-compatible-upgrade-rollback.md)。

## 完整目标环境验收入口

`uv run --frozen python -m scripts.verify_local_deployment` 要求当前 clean candidate 已由 `./local build` 构建固定镜像；使用 run ID 隔离 Compose project、随机数据库 / Qdrant 凭据、空命名卷和临时 RAG 目录。固定 revision 模型缓存只读复用，外部 LLM 配置仅从 `.env.local` 读取。

Windows Node 在临时目录安装锁定的浏览器测试依赖，Microsoft Edge 完成真实问数、追问、经营分析、历史、保存成果与 XLSX / PNG / PDF 下载；独立解析器核验导出内容。验收项目停止 / 手动恢复后，检查账号 / 历史 / 成果 / Seed 状态及未完成执行恢复。额外构造配置、缺少索引、未知 migration、回环端口占用和容器退出失败。

每次证据保存到 ignored `reports/browser-real-artifacts/r6-local-deployment/<commit>-<run-id>/`，记录 source commit、dirty 状态、镜像 / 模型 / Seed / RAG 身份及其他项目容器前后状态。账号禁用、Session 撤销、临时凭证删除与资源身份校验完成后才归档通过结果。失败诊断留在权限受限的 ignored `.local/acceptance/`；不能把诊断重跑冒称原运行通过。

## 维护窗口与验证限制

完整脚本只停止专用验收项目。电脑 / Docker daemon 重启需要无其他项目活动的维护窗口，尚未执行；窗口中先记录账号、历史、成果和 Seed / 卷身份，再重启，显式执行 `./local up` 并重新读取和导出已有成果。未预定具体时间，也不以容器 stop / up 替代电脑重启证据。

R1–R5 原 Acceptance 和 Evaluation 报告保留原候选身份。R6 部署及验收代码没有改变模型、Prompt、Domain、SQL Guard、业务资产或查询 / 分析应用行为，因此已有正式 AI Evaluation 作为原候选行为基线复用；完整 Edge 业务验收提供新运行环境证据，不等于重跑三套正式 AI Evaluation。动态 readiness、备份恢复、容量 / 可用性及监控告警归后续 R7。

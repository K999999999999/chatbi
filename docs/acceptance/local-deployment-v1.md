# R6 本地固定版本部署验收

Status: Ticket 01–04 本地实施与适用验收完成；最终 clean runtime candidate `2b4a8c8` 的完整隔离入口通过，稳定环境已升级到该候选。PR60 已合并（`9a70601`），required CI 全部通过，交付与分支清理完成，见 [PR60](https://github.com/K999999999999/chatbi/pull/60)；电脑 / Docker daemon 重启未执行，仍按维护窗口计划验证。

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

## Ticket 04 失败历史与诊断（2026-10-08）

clean candidate `9f01de29ca12094c4447bbe241672d6260927725` 的正式 run `20261007T191015Z-8582c456` 已通过空环境初始化、RAG / 兼容前置、五项失败检查、Windows Edge 真实问数 / 追问、多指标、XLSX 与 PNG；经营分析的任务及程序归因与独立参考值一致。PDF 下载时 Edge 收到 204 空响应，完整验收失败，重启 / 保存成果及最终导出内容检查尚未执行，不能标记 Ticket 04 完成。

诊断 run `20261007T191852Z-9ffb13b7` 在临时浏览器测试副本增加安全响应字段，**不是正式验收**。PDF 服务端访问日志返回 200，Edge 收到 204、无文件内容；独立最小复现对同一份有效 PDF，Linux / Windows PowerShell 均返回 200 和 78,427 bytes，Edge 返回 204 / 0 bytes。headed / headless 和关闭浏览器代理的复现结果一致。本机确认运行 IDMan，IDM advanced integration 开启且监控 PDF；该次诊断时接管原因尚未通过暂停对照确认。后续用户授权临时调整，确认 IDM 为原因，见下文最终结果；未修改本机代理或用户浏览器配置。

两次 run 的临时账号、Session、配置凭据、Windows workspace 和专用 Compose 容器 / 卷 / 网络均已清理；失败报告保留于 ignored `.local/acceptance/<run-id>/`。当次失败结束时稳定 API 仍运行 `995440b`，未因此被替换；开发环境保持运行。

AI Evaluation 的复用边界还包括运行依赖变化：R6 将 PyPI `torch 2.14.0` 改为 CPU 索引 `torch 2.14.1+cpu`（非 Darwin）。已有正式报告只提供原候选的软件行为基线，不证明本次 CPU runtime 已取得新的正式 Evaluation 基线。新环境 RAG 构建和真实业务参考值检查已有证据，最终部署运行验收已通过，见下文；三套正式 AI Evaluation 未在本次候选重新执行。

## Ticket 04 最终通过（2026-10-08）

- 最终运行候选：`2b4a8c811713adb663d22cdac4108e13e731165f`，`git_dirty=false`。API image ID：`sha256:a01769af61f448b2597a5994dfb5dcfb1a9ed3a0a896135cd42d4649e7d9cd97`；本次空卷 PostgreSQL image ID：`sha256:fe35dc2bbd3aa62057c22aea10361ccf9b3e168f76193db97de11f33dbbbc2ec`。两镜像 revision 与发布描述一致；后续证据文档提交不冒称新的运行候选。
- 正式 run：`20261007T200251Z-e8ea09aa`，Compose project `chatbi-r6-accept-20261007t200251z-e8ea09aa`。空卷初始化 / migration / 管理员 / RAG / 兼容前置 / Chromium sandbox 与完整入口全部通过。Windows Edge `154.0.4258.53`；LLM `deepseek-flash` / `api.deepseek.com`；BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181`，CPU / FP32。model config SHA-256：`26159e7ad065073448460117eb24b7a4572f6f4e78eadff65dc0a11c052449fa`；RAG current SHA-256：`c2851c0f79cbf8d8b58271fc2f6bc83ca2954e10a5220a1018334bc016d24f6b`，manifest / provenance 详见 runtime.json。
- 真实登录、问数、追问、多指标 / 多单位、经营分析、历史 / 成果、来源历史删除后成果保留通过，业务值与独立只读 SQL 参考一致。共 12 份浏览器实际下载：4 XLSX、3 PNG、5 PDF；独立解析器核验 hash / 大小、工作表 / 精度 / 公式安全、PNG 解码和 PDF 多页可选取文本 / 完整正文与证据 / 私有标识排除。每类格式均覆盖历史与保存成果，导出不提交新执行。
- API 强制停止后，专用 API / PostgreSQL / Qdrant stop / up，恢复前后 `users=2`、`histories=5`、`turns=8`、`saved_results=2`、`business_fact_rows=1166`、Seed `chatbi-sales-mart-dev-v3` 完全一致。重新登录、续聊、过期分析的已提交报告、显式重查产生新历史、删除成果保留历史通过；中断执行恢复为 unconfirmed，无伪成功快照，旧成功结果可继续使用。
- 配置错误、缺失索引、未知 migration、回环端口冲突与容器启动失败均明确非零拒绝，持久状态未变。API 两个资产挂载均只读、无 migrator 身份；导出临时文件 / worker 已回收，已知 Secret 未出现在日志 / JSON 报告。其他项目容器身份、镜像和运行状态前后一致。
- 验收账号已禁用、active sessions=0；临时配置凭据、Windows workspace、专用容器 / 卷 / 网络清理通过。原始报告保存于 ignored `reports/browser-real-artifacts/r6-local-deployment/2b4a8c811713-20261007T200251Z-e8ea09aa/`，新 clone 不自带报告。`runtime.json`、`browser.json`、`export-verification.json`、`failure-checks.json`、`recovery.json`、前后快照和清理记录共同构成证据；继承的 r5-* 下载文件名不改变本次 R6 身份。

### 本机 IDM 条件与失败修复

用户授权后，通过 IDM 原生设置临时取消 PDF 文件类型接管；同一有效 PDF 从 Edge 204 / 0 bytes 恢复为 200 / 78,427 bytes，确认外部接管为原因。完整验收期间保持此条件，结束后原设置已恢复并核实，未留下永久配置修改；`browser-download-environment.json` 记录条件及恢复。日常使用网页 PDF 下载时，需要用户暂停 IDM 接管，或明确设置本机站点例外；恢复 IDM 后不能承诺其不会再次接管。

本项另外修复两处验收缺陷：保存成果读取期间等待旧页面可见不足，现等待 saved URL 与专属标题；独立文件解析使用宿主锁定 dev 环境，并在创建 Docker 资源前检查 openpyxl / pypdf，生产镜像不加入测试依赖。此前 `1bebea5` 的成果导航失败、`7c5a5fa` 的解析环境失败均保留原运行结果；后者浏览器 / 恢复通过及补充文件解析通过不冒称原 runner 通过。

### 稳定环境升级与验证边界

完整验收通过后，`./local upgrade 2b4a8c811713adb663d22cdac4108e13e731165f` 成功，稳定地址 `http://127.0.0.1:8080/`。4 个用户、3 条历史、3 个 turn、0 个成果的前后完整行指纹一致；PostgreSQL 容器 / 运行镜像（733b074）与 Qdrant 容器 / 两命名卷身份不变。API `/health` 为 ok、容器 healthy；实际 seccomp JSON 与仓库 profile 一致，Chromium sandbox 启动实测通过；部署状态 running/succeeded、权限600。指纹及资源身份详见 `stable-upgrade.json`。

定向软件回归 66 passed；Windows Edge 的历史 / 成果确定性回归 3 passed，报告路径测试此前 3 passed；TypeScript、Ruff、Bash、Compose、Markdown local links 与 Diff 检查适用证据通过。宿主 Linux Chrome 启动曾因缺安装与 libnspr4 失败，改在已有目标 Windows Edge 完成确定性回归，没有安装宿主浏览器依赖。最终证据变更为纯文档，复用未受影响软件证据。电脑 / Docker daemon 重启没有执行，维护步骤与待选窗口仍如上；三套正式 AI Evaluation 没有重跑。R6 远端交付已完成（PR60）；R7 运行保障仍待澄清，不以 R6 通过宣称整个产品或生产就绪。

## 稳定服务恢复核验（2026-10-08）

17时检查发现稳定 API / PostgreSQL / Qdrant 均已退出（exit 255），三容器记录的结束时间为当日16:53:41 +08:00；具体停止原因未确认，不能由此推定整机或 Docker 重启验收通过。部署状态文件仍保留此前 running 记录，实际可用性以容器与 HTTP 核验为准。

用户授权后执行既有 `./local up`。启动前置校验通过，API仍为 `2b4a8c8`（image ID `sha256:a01769af61f448b2597a5994dfb5dcfb1a9ed3a0a896135cd42d4649e7d9cd97`）；PostgreSQL按发布记录重建容器，运行镜像从此前733b074改为2b4a8c8（image ID `sha256:fe35dc2bbd3aa62057c22aea10361ccf9b3e168f76193db97de11f33dbbbc2ec`），数据库命名卷保留。Qdrant容器、镜像及其卷保持不变。

恢复后 API / PostgreSQL healthy，Qdrant running；网页 HTTP 200、`/health`返回ok；部署状态原子更新为running/succeeded。只读完整行指纹与此前stable-upgrade.json的after一致：4账号、3历史、3turn、0成果；Seed v3、1,166业务行。开发等其他项目的容器身份、镜像、运行状态、启动时间及卷均未变化。证据见 ignored `reports/browser-real-artifacts/r6-runtime-recovery-20261008/` 和 [长期恢复记录](../../.scratch/r6-runtime-document-closeout/verification.md)。

本次仅核验服务恢复、启动门禁、HTTP及持久状态，不重跑登录 / 问数 / 下载的完整浏览器验收或正式AI Evaluation；不修改IDM、不执行整机 / Docker重启，既有维护窗口与下载条件仍适用。

## 稳定服务重启核验（2026-10-09）

当日检查发现稳定 API、PostgreSQL、Qdrant 容器均已退出（exit 255）。停止原因未确认；没有证据表明这是整机或 Docker daemon 重启。运行绑定仍为 `legacy`，活动发布仍是 R6 `2b4a8c811713adb663d22cdac4108e13e731165f`，没有未完成的恢复切换日志。

为恢复已授权的原稳定服务，执行 `./local rollback 2b4a8c811713adb663d22cdac4108e13e731165f`，命令与启动核验成功。恢复前后 API / PostgreSQL 镜像身份与原发布记录相同；PostgreSQL 和 Qdrant 使用原稳定命名卷，未运行 migration、初始化密钥或激活恢复候选。恢复后 API、PostgreSQL healthy，Qdrant running；`/` 和 `/health` 返回 HTTP 200，PostgreSQL 接受连接。最后复核仍为该 R6 发布且服务健康。

R6 当前不实现 R7 readiness 入口，因此 `/ready` 返回 404，`./local status` 的运行就绪证据显示未确认；这不改变 `/health` 和容器健康结果，也不构成 R7 readiness 验收。此处只记录恢复和当前 R6 服务核验，不代表整机 / Docker 重启测试通过。停止原因仍待查明。

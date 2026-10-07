# R6 本地稳定部署规划记录

- 2026-10-07：首版范围、目标环境、安装 / 初始化、启停、升级回滚、运行边界与验收标准逐项确认，需求澄清完成。
- [完整 Spec](spec.md) 已整体确认，Design Review PASS，四项Ticket拆分与完整本地实施已获用户确认和授权。
- 当前实施分支 `feature/r6-local-deployment`，起始于已同步的 `master` / `origin/master` `2a7600d`；Ticket 01实现提交至`4d4732b`、证据收尾文档提交`eba02b0`，Ticket 02改动实施中，未发布。
- 本机实时状态位于 Git 公共目录 `harness/work-items/r6-local-deployment/status.md`，本文件为规划历史，不作为实时状态副本。
- R1–R5 历史证据不改写；R6 尚无完整稳定环境验收。R7 完整运行保障不纳入本地首版部署范围。

## 需求澄清完成记录

状态: 澄清完成
事实源与已确认事实: Architecture、产品范围、bootstrap / RAG / 开发环境Contract、Runbook及R1–R5历史Acceptance；当前WSL2 x86_64与Docker Compose可用，原Compose为开发入口。
用户已确认的决定: 见完整Spec；逐项确认本地首版范围、目标设备、启停、升级回滚、安装、配置初始化、运行边界与验收标准。
范围与关键边界: 合成销售数据、当前电脑、独立固定版本稳定运行；仅本机同源HTTP、单进程CPU/FP32；云部署和R7全面运行保障不在首版范围。
验收与验证方向: 空环境安装、真实浏览器业务闭环、重启持久化、升级与兼容回滚、安全失败与环境隔离；候选和资源身份需关联。
假设: None
未决 / 阻塞项: None
留给Ticket / 实施阶段的决定: 在Design中确定Compose/命令组织、固定版本标识、兼容性检查、缓存与发布资产路径、验收版本对；不得改变已确认边界。
下一步: 本地提交已通过Review与确定性检查的Ticket 02实现，以clean commit构建固定镜像；随后完成空卷数据库、模型与RAG集成，再进入管理员 / LLM 浏览器验收。

## 本次文档整理检查

- 四份规划文件的Markdown本地链接PASS，tracked Diff的`git diff --check` PASS；人工核对完整Spec与逐项确认一致。
- 路线图当前阶段、需求细化状态、R6需求表、目标环境、授权门禁与后续生产范围同步；产品长期记录补充R6决定。
- 本机19份记录检查0ERROR；REVIEW为产品/R6尚未完成以及本目标已归属的文档修改，不代表已完成运行验收。
- 未运行软件测试、容器验收或AI Evaluation；未修改运行代码、Commit或PR。

## 完整Spec确认后的规划结果（2026-10-07）

用户整体确认Spec；实现设计经当前主Agent只读Design Review PASS。四项Ticket Readiness READY；用户随后确认Ticket拆分并授权完整本地实施和验证。设计保留production/Cookie安全规则，本地development配置通过独立交付入口追加资产校验；不构成放宽安全Contract。

## R6 Ticket 01 完成记录（2026-10-07）

- clean source commit：`4d4732b7896a46b231a4a3437c703e74b5ae513f`。
- API镜像：`sha256:dfe36e7aa5927bd2334f2fd406a257837e7079ef8e07f168dd2ffca9aa01961b`，1,909,212,440 bytes。
- PostgreSQL镜像：`sha256:e9605804df9016d702ee575220cd27ab7a40441a07f44846931fe9ca952fdbfc`，116,049,593 bytes。
- 两镜像OCI revision label与`/opt/chatbi-release.json`均匹配source commit。Dockerfile check、构建、前端build/typecheck、锁文件、CPU模型、网页及导出资源、PostgreSQL初始化脚本/DDL/合成Seed定向检查通过。
- 未完成完整稳定环境、Embedding/RAG构建实测或浏览器业务验收；这些仍在Ticket 02 / 04范围。

## R6 Ticket 02 实施记录（2026-10-07）

- 独立`chatbi-stable` Compose、配置模板、`./local`操作入口、环境前置检查、写操作锁及Runbook安装 / 启停章节已实现；正式本地稳定部署Contract初稿已建立。
- 基于`eba02b0251c00cfcf169bf09bae63e8d02c9bd42`的实现Review PASS；本地发布入口20项测试通过，Ruff、Bash语法、Markdown本地链接、Compose资源隔离约束和Diff检查通过。
- 尚未以当前Ticket 02 clean commit构建镜像，也未完成空卷真实初始化、稳定RAG构建、隐藏密码管理员创建、真实LLM浏览器问数、关闭终端 / down-up持久性验收；不能据此标记Ticket完成。

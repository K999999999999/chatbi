# R6 本地稳定部署规划记录

- 2026-10-07：首版范围、目标环境、安装 / 初始化、启停、升级回滚、运行边界与验收标准逐项确认，需求澄清完成。
- [完整 Spec](spec.md) 已整理，待用户整体确认；尚未设计审查、拆 Ticket 或实施。
- 当前分支 `docs/r6-local-deployment-spec` 基于已 fetch 且同步的 `master` / `origin/master` `2a7600d`，仅整理 Spec 与规划事实；无提交或发布。
- 本机实时状态位于 Git 公共目录 `harness/work-items/r6-local-deployment/status.md`，本文件为规划历史，不作为实时状态副本。
- R1–R5 历史证据不改写；R6 当前无运行验收结果。R7 完整运行保障不纳入本地首版部署范围。

## 需求澄清完成记录

状态: 澄清完成
事实源与已确认事实: Architecture、产品范围、bootstrap / RAG / 开发环境Contract、Runbook及R1–R5历史Acceptance；当前WSL2 x86_64与Docker Compose可用，原Compose为开发入口。
用户已确认的决定: 见完整Spec；逐项确认本地首版范围、目标设备、启停、升级回滚、安装、配置初始化、运行边界与验收标准。
范围与关键边界: 合成销售数据、当前电脑、独立固定版本稳定运行；仅本机同源HTTP、单进程CPU/FP32；云部署和R7全面运行保障不在首版范围。
验收与验证方向: 空环境安装、真实浏览器业务闭环、重启持久化、升级与兼容回滚、安全失败与环境隔离；候选和资源身份需关联。
假设: None
未决 / 阻塞项: None（完整Spec整体确认及后续设计审查仍是阶段门禁）
留给Ticket / 实施阶段的决定: 在Design中确定Compose/命令组织、固定版本标识、兼容性检查、缓存与发布资产路径、验收版本对；不得改变已确认边界。
下一步: 用户确认完整Spec后进入Design Review；通过后整理Ticket草案、当前上下文Readiness并取得拆分与实施范围确认。

## 本次文档整理检查

- 四份规划文件的Markdown本地链接PASS，tracked Diff的`git diff --check` PASS；人工核对完整Spec与逐项确认一致。
- 路线图当前阶段、需求细化状态、R6需求表、目标环境、授权门禁与后续生产范围同步；产品长期记录补充R6决定。
- 本机19份记录检查0ERROR；REVIEW为产品/R6尚未完成以及本目标已归属的文档修改，不代表已完成运行验收。
- 未运行软件测试、容器验收或AI Evaluation；未修改运行代码、Commit或PR。

## 完整Spec确认后的规划结果（2026-10-07）

用户整体确认Spec；实现设计已整理并经当前主Agent只读Design Review PASS。四项Ticket草案已生成，当前上下文只读Readiness READY；待用户确认拆分及整体本地实施范围，尚未正式写Ticket或编码。设计保留production/Cookie安全规则，本地development配置通过独立交付入口追加资产校验；不构成放宽安全Contract。

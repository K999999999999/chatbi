# Design Review

Review: PASS
Review Target: [Spec](spec.md)、[Design](design.md)

- Signal: 任意 checkout 生成任务 candidate 会污染交付事实。
  Evidence: PR #100 的 Roadmap 描述与其 master 不一致；旧 CLI 为 CI ID 返回文档分支 candidate。
  Impact: 无法确认验证与工作项对应。
  Recommendation: state 保留跨目录发现能力，未绑定时仅输出记录；候选相关操作要求明确归属。
- Signal: 主目录可能承载另一个未发布任务。
  Evidence: 文档分支 e598533 与 CI 工作分离。
  Impact: 强制回主分支或删除分支会打断其他任务。
  Recommendation: 以 parked 明确保留候选；仅处理已授权临时目录，收尾按角色核验。
- Signal: 本机缓存远端引用不等同于实时 PR。
  Evidence: 本机检查器明确不联网；Plugin 远端依据为独立声明。
  Impact: 退出码可能被误读为远端完成。
  Recommendation: 本机 gate 与 GitHub 读回分开，记录同一候选上的真实证据。

Reference: 已读取 Architecture Knowledge Core 的复杂性、边界、Contract、失败与生命周期原则，以及项目架构 / 产品范围；产品边界不变。
Evidence Sources: 工作项记录、Git reflog、PR #100 正文、检查器 / adapter 源码、真实 Plugin state 与安装结果。
Next: 按用户已确认四步方案执行原四个切片，当前上下文 Ticket Readiness READY。

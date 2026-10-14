# 应用就绪与执行保护

本文定义单API进程的应用健康、状态投影与请求保护；操作见[Runbook](../runbook.md)。不提供发布、备份或恢复能力。

## 存活与就绪

- `/health`保持HTTP存活语义。`/ready`根据Control DB、业务数据库、Qdrant和业务/RAG资产的真实校验返回200或503，使用no-store。
- 依赖检查有界且可终止；检查过期或超时显示unknown，不能继续使用旧的成功证据。服务运行期间依赖故障或恢复在60秒内反映。
- 模型状态取最近15分钟真实调用的成功/失败结果；没有近期证据显示unknown，不做定时收费LLM探测。
- 就绪未通过时拒绝新的问数/经营分析；恢复检查通过后重新受理，不伪造已受理任务的终态。

## 请求与资源保护

- 同步Query API和后台问数/分析共用每账号1、单API4的默认业务额度；不足立即拒绝，不排队或自动重试。
- 导出仍使用独立每账号1、单API2额度。问数180秒、分析1200秒、导出60秒的保护时限保持；不构成容量或延迟承诺。
- 幂等重放和观察不重复占额度；取消/超时直到真实工作结束才释放资源。历史运行锁、epoch/generation和导出进程锁保留。
- 就绪失败503 SERVICE_NOT_READY、额度不足429 EXECUTION_LIMIT_REACHED保持既有响应外壳；会话冲突仍返回409 CONVERSATION_CONFLICT。

## 状态与权限

- `/api/v1/operations/status`保持version、status、checked_at、query_available和message；管理员details包含dependencies、model、capacity，不再包含backup。
- 普通账号仅见必要可用性提示；详情按当前权限`admin.audit`裁决，首次必须改密的用户不取得详情。
- Cookie/Bearer/Origin/身份撤销继续生效；只读状态刷新不延长Idle/Absolute期限，不成为登录保活。
- 状态和日志不显示原始问题、SQL、结果、Secret或敏感异常。无运维Unix socket或备份状态文件依赖。

## 验证

软件回归覆盖就绪成功/失败/超时/过期/恢复、模型证据期限、状态权限与无保活、同步与后台容量共享、取消/异常释放及生命周期。浏览器验证故障提示和恢复、登录过期、管理员应用状态。实际依赖故障与真实业务属于容器验收，历史结果不代表新候选通过。

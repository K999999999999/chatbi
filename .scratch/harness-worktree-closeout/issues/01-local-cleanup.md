# 本机目录收尾

Status: done
Owner: 当前主 Agent
Blocked by: None (can start immediately)
What to build: 校验归档 CI 报告，移除已授权临时目录，主目录同步 master，保留文档分支。
Acceptance criteria: 仅一个 ChatBI 登记 worktree；文档候选仍为 e598533；5 份报告逐文件哈希一致；旧空审计目录不存在。
Owned files: Git common-dir 归档和相关本机进度；不提交 Git 内部文件。
Result: 5份CI报告逐文件归档校验；临时CI目录与旧审计空目录已清理；文档候选e598533保留；主目录已同步master后开始本修复目标。
Comments: 用户已确认四步方案的第一项。

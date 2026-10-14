# T03 Hook与Harness协作入口

Status: done
Spec: [已确认行为](../spec.md)；[设计](../design.md)；[共用完成规则](../tickets-draft.md#共用done-when与证据要求)。
Authorization: 用户确认七项拆分及全部本地实现、验证与提交；远端未授权。

- Change Profile: 短期CLI扩展；小切片；Git本机身份风险；临时clone/worktree；本地交付。
- Owner: 当前主 Agent；长期归本机Harness/Hook工具。
- Blocked by: T01。
- What to build: hooks install直接委派既有安装器；harness check容器内只读执行，真实Git目录挂载复用T01目标/路径能力；报告本机ERROR/REVIEW原语义。
- owned files: dev、scripts/container_tasks.sh或共享辅助文件、tests/scripts Hook/Harness路由测试；Runbook。既有Python检查规则尽量不修改。
- Acceptance Criteria: 无业务.env；Hook无需Docker并拒绝其他有效hooksPath；Harness不访问远端或写状态；共享common-dir/指定repo及普通clone/linked worktree正确；退出码原样。
- 验证证据: 临时clone和linked worktree的测试记录，不改日常其他clone配置；只读元数据前后对比、未知参数及缺镜像分支。
- Migration / Rollback: 保留既有脚本直调；回滚入口不自动回写hooksPath，本切片仅测试临时clone。
- Done When: 两个协作操作无业务环境依赖，真实Git身份与只读边界有证据。


## Result

hooks/harness接入完成。临时clone验证Hook归属及拒绝覆盖；真实普通clone和linked worktree验证clean/dirty、外部repo与公共目录身份。

证据范围、故障修复及未运行验证见[整体验收记录](../acceptance.md)，[Code Review](../code-review.md)结论适用于本地候选；提交身份见Git公共目录实时记录。

## Comments

从草案正式写入，适用基线master@38e1302。

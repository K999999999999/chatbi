# 文档状态修正与完整候选验收


- Change Profile: 中高风险；收尾文档和本目标有界完整验收；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD022、AUD023。
- Blocked by: 01–11；需全部完成
- owned files: .scratch/chatbi-product-v1/r1-spec.md；.scratch/project-navigation/spec.md；docs/roadmap.md；README.md（仅本目标入口）；docs/audits/project-audit-20261016.md（与原始报告逐字一致，供路线图和README链接在clean clone中有效）；.gitignore（排除验收器自己的运行状态文件，确保clean candidate provenance）；scripts/start_dev_api.py、src/bootstrap/readiness.py及对应确定性回归测试（修复隔离验收发现的冷启动就绪探针超时，不改变用户行为）；本工作项记录及路线图引用的Spec/设计审查/Ticket草案/Readiness材料；必要现有验证编排入口（仅运行，不新增通用平台）。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

按历史证据修正两份Spec首部；完成22项映射台账、全量软件检查与三套真实AI评测/隔离业务验收，形成一个本地candidate。

### Acceptance criteria

1. R1和导航Spec首部与已有交付/非作者走查证据一致，保留原日期和历史记录；路线图准确记录本目标，适用正式文档已由各Ticket更新。
2. 22项均有修复、regression、候选SHA和结果，不漏AUD002，不把AUD014作为缺陷；审计报告副本与原件一致。
3. dev check及python/database/web/renderer完整执行，记录真实计数/skip/未运行；Code Review与Diff Review通过；形成clean代码candidate后才做正式真实验收。
4. 同candidate与资源身份的三套正式Evaluation完成并按现有标准校验；首轮失败保留、不挑选成功替换；隔离业务报告依Contract判定，skipped仍incomplete。
5. 验证之后源码、专用账号和临时资源已恢复/清理；任何失败或环境限制保留未完成项。仅本地Commit，不Push/PR、不直接Merge；原工作区修改保持。

### 验证证据

完整./dev check、./dev test all；三套./dev evaluate与evaluate validate；./dev verify dev isolated；安全验收摘要、provenance与清理结果；不触发远端workflow。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

Status: open
Result: 文档回填已开始；最终软件回归、三套真实AI评测和隔离业务验收仍待执行。
Comments: 按已确认Spec、设计审查和READY拆分登记。审计报告副本、README入口与路线图链接所需的本工作项记录一并纳入最终候选，原始审计文件不改写。最终验收首次暴露冷启动下完整readiness探针耗时超过其10秒子进程超时，以及验收器自身`.verification-state`导致dirty provenance；已增加定向修正与回归，整体验收重跑绑定修正后的新候选。

# T04 只读诊断与结构导出

Status: done
Spec: [已确认行为](../spec.md)；[设计](../design.md)；[共用完成规则](../tickets-draft.md#共用done-when与证据要求)。
Authorization: 用户确认七项拆分及全部本地实现、验证与提交；远端未授权。

- Change Profile: 短期维护CLI；中等；诊断误报/源文件权限风险；安全探针+隔离catalog；本地交付。
- Owner: 当前主 Agent；长期归operations和metadata。
- Blocked by: T01。
- What to build: doctor dev/app安全状态汇总与超时；metadata export容器执行，继承现有结构范围/参数/输出。
- owned files: dev、scripts诊断装配/现有check_dev_qdrant及metadata入口适配、tests/scripts及metadata测试；Runbook、所属正式Contract。
- Acceptance Criteria: doctor不启动/修复、无LLM调用、不改账号；失败/未知不ready、不泄密；两目标资产路径准确；export只catalog SELECT、宿主UID输出三份结构投影、不修改Semantic或隐式build-rag。
- 验证证据: 成功/缺失/故障/超时/脱敏回归；临时项目只读检查前后状态；隔离catalog与临时输出目录权限、结构Contract回归。
- Migration / Rollback: 保留metadata内部模块调用；原Qdrant脚本适用直调能力先兼容；回滚CLI不能替用户恢复已经导出的源文件，测试只写临时目录。
- Done When: 正确诊断与导出闭环，包括只读和显式源文件写入边界。


## Result

只读有界doctor与容器metadata导出完成。纯软件覆盖ready/失败/脱敏；隔离dev/app诊断不创建资产卷、不改账号，catalog导出三文件及宿主UID正确。

证据范围、故障修复及未运行验证见[整体验收记录](../acceptance.md)，[Code Review](../code-review.md)结论适用于本地候选；提交身份见Git公共目录实时记录。

## Comments

从草案正式写入，适用基线master@38e1302。

# 实现 Code Review

Review: PASS
Scope: BASE_SHA=38e1302ce33d999dc908419067bc5d39195f86cf；本工作项全部owned files与T01–T07。主Agent当前上下文只读审查，无独立Agent或额外用户Review阶段。

## Change Description

What / Why：基线全部脚本盘点，现行人工操作统一到dev八类帮助；实际执行继续由Compose、Bootstrap、账号Service和成熟验收/评测工具负责。补唯一管理员本机恢复及目标安全维护。

Risk：目标配置与宿主路径、维护资源归属、不可逆重置、认证并发事务。本次仅专属隔离资源验证；paid真实验收留作明确后续范围。Verification见[验收记录](acceptance.md)。

## Findings与修复复验

- 干净worktree的网页嵌套只读挂载缺少dist目录：先创建挂载点，不覆盖产物；完整web 68项重跑通过。
- 维护Compose expanded config重复转义美元符号：保留Compose的规范序列化；实际含$密码连接/恢复及纯配置roundtrip通过。
- 标准应用维护误要求开发镜像：仅从目标tools配置解析已有镜像、pull never；专属标准应用镜像真实恢复及doctor通过。
- 旧Stable/Restore标签可能被误认dev：核验受支持Compose文件族；app源码overlay也拒绝；补确定性拒绝回归。
- PG测试teardown尝试运行身份无权DELETE：按真实权限禁用专用账号/撤销Session，未扩大授权；完整两profile PG及7项并发/回滚通过。

没有未解决的范围内阻断项。上述问题均在实现中修复，并对受影响范围复验。

## Review Dimensions

- Correctness：帮助与无效参数先退出；目标解析共享、app独立、up不初始化；CLI退出码与成熟入口保留。doctor失败/未知不报ready，不启动依赖。
- Security：恢复显式目标/账号、TTY隐藏输入、既有密码策略；只用Control运行身份，User锁后重读admin/active，Session及强制审计同事务。并发修改遵循User→Role锁顺序，审计提交失败回滚。配置私有临时目录、不输出原始异常；业务/普通测试无socket扩权。
- Architecture：Bash只做宿主编排；Bootstrap装配；Authorization拥有账号规则；业务模块不依赖Docker或Bootstrap。Semantic/SQL Guard、业务数据、模型/Prompt、依赖与Schema无变化。
- Comprehension / Consistency：dev薄路由，维护配置纯函数与编排分离；Python质量复用CI固定入口。原卷校验及旧importable辅助行为保留兼容，避免为入口迁移重写成熟能力。
- Testability：软件状态断言、实际Compose规范化、真实PG锁等待/回滚、真实TTY及隔离双项目对照；非真实LLM证据与付费验收明确区分。
- Migration / Documentation：24/24最终处置及外围消费者核对；独有验收断言不删除；正式Contract/Runbook/README/Product Scope/Architecture/Roadmap同步。回滚代码不承诺恢复已删卷/已恢复密码。

Next: 最终受影响回归、完整check及Diff检查通过后本地Commit；远端仍需发布授权。本结论不代表真实LLM、生产就绪或远端合并完成。

## 发布前修复Review

PASS：私有临时缓存生命周期由标准库管理，保持CI命令、返回码及只读源文件；doctor仅允许HTTP(S)，标准重定向处理拒绝其他协议。4项新增/受影响回归、完整固定质量及全src/scripts Bandit通过；精确扫描说明不豁免其他检查。无Contract、Schema、权限或依赖扩展。

## master@11ff5d2对齐Review

PASS：无冲突rebase，复核重叠正式文档与入口测试，两个目标语义均保留；未把restart变更计入本PR新增范围。账户事务、维护配置及网页实现未因对齐改变；补跑软件/启动入口/check并由最终PR CI绑定新head。发布授权已明确取得，早期“远端未授权”描述为当时历史状态。

# 本机管理员紧急恢复

## 范围与信任

本机Docker操作者持有开发Control DB运行账号配置时，可显式执行`./dev recover-admin dev --username NAME`。当前只支持dev；旧`app`目标在连接数据库、读取密码或触及账号前拒绝。无HTTP端点，不要求旧密码或Web Session，不提供任意用户管理。不默认选择账号，不搜索其他项目或旧Stable。

只恢复现有、启用且具有固定admin角色的规范用户名；普通/禁用/未知账号拒绝。多管理员也只操作指定用户。不创建账号、授予角色、启用账号或改变ID、历史、成果、数据范围。create-admin与Web普通重置职责保持。

目标PG须已运行并完成Control/checkpoint初始化，已有工具镜像须包含恢复代码。无隐式build/start/migrate或索引构建；不依赖API/Web/LLM/Qdrant/RAG，不进行模型调用。

## 输入与事务

交互终端隐藏输入临时密码两次，getpass回显退化必须拒绝。不接受密码参数、环境变量或流水线；至少12位及Argon2id。

一个运行身份事务：FOR UPDATE锁User，锁后重读active与admin成员关系，更新Hash、must_change_password、失败次数和登录锁，撤销全部旧Session并写审计。与登录、改密、重置、启停及角色变更统一User锁；最后管理员保护需要的Role锁在User之后获取。不改变普通认证权限规则。

审计Sink必须支持事务内write；事件auth.admin_recovery，目标user，actor_user_id为空，details仅environment/project/source=local_cli。审计写入或提交失败全部回滚；不记录密码、Hash、Token、连接凭据或原始异常，不声称CLI来源能证明自然人身份。

Compose项目、PG容器及卷需核实归属，不fallback；不能使用业务账号、迁移账号或数据库创建/角色管理等高权限身份。宿主编排Docker，Bootstrap装配，Authorization裁决；账号规则不依赖Docker/Bootstrap，普通业务和测试容器不新增socket权限。

## 结果与验证

参数、非终端及两次输入不一致退出2；资源、账号、密码策略或事务失败1；成功0；Ctrl-C非零且不报告成功。只报告安全阶段，不输出原始异常或凭据。提交确定成功后才提示登录并立即改密；提交不确定不自动重试。已恢复密码和已撤销Session不能靠代码回滚复原。

软件测试覆盖状态、账号范围及审计回滚；隔离PostgreSQL验证运行权限、行锁及并发登录/改密/禁用/撤权。dev容器与伪终端验证环境隔离、不依赖无关配置和不回显，仅操作专用测试账号。见[Runbook](../runbook.md#7-管理员忘记密码)。

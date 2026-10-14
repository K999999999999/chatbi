# 本地候选验收记录

## 身份与范围

- 基线：master@38e1302ce33d999dc908419067bc5d39195f86cf。
- 候选：feat/dev-command-entrypoints本目标提交；精确SHA在共享Git公共目录实时记录。正式实现与测试由同一候选交付。
- 目标：已确认Spec及T01–T07；八类入口、标准应用管理、维护、管理员恢复，保持成熟实现及独有断言。
- 标准应用测试镜像：chatbi-app-dev-entrypoints:local，sha256:4ece6a7331bed849cd2561a73296bd1ce4ab24e81645bbb8f4fca14f1e41e0c7；未覆盖日常应用tag。
- 验证仅用带专属身份的临时项目、账号和合成密码；未修改日常管理员，未删除日常卷，无真实LLM调用。

## 软件与构建证据

| 检查 | 结果及适用边界 |
| --- | --- |
| ./dev check | 完整锁文件155依赖、文档/链接、模块边界、固定Ruff0.16.8（305文件）、前端与export构建通过；最终完整check退出0，最终文档状态定向复验也退出0 |
| 全量Python | 968 passed、51 skipped、142 subtests passed；新增最后两项拒绝校验再由受影响定向回归补证，不把历史全量数量改称当前重跑 |
| 隔离PostgreSQL | ci 5 + development 53 = 58 passed；含7项真实恢复锁/提交回滚验证 |
| 浏览器 | 打包网页67 + Vite真实代理1 = 68 passed；登录、模式、结果等确定性浏览器流程 |
| PDF renderer | 2 passed；真实Chromium/PDF/font/sandbox |
| 最终定向回归 | 维护配置/路由/旧重置/恢复输入/doctor/账号Service；68 passed，包含最后两项legacy目标与app源码覆盖拒绝 |
| Shell | dev及受影响Shell的bash -n通过 |
| 标准应用构建 | Docker api目标成功，恢复代码与doctor探针打包完成 |

原./dev test all在Python及PG通过后，因干净worktree缺少frontend/dist嵌套挂载点而失败。已修复先创建目录、保留现有产物，随后完整重跑web通过，并独立完成renderer。因此证据为完整suite逐项通过，不声称原test all进程退出0。最终复验只涉及共享维护脚本、拒绝测试和文档；未改变已验证的软件主体/数据库/网页/PDF逻辑。

本机原始日志位于/tmp/chatbi-entry-{all,check-final,docs-final,web,renderer,app-build-final,targeted-complete,runtime-final,git}.log，仅为本次运行辅助，非产品长期依赖；此表与下面状态观察为长期证据摘要。

## 隔离运行与失败路径

1. 真实专属app生命周期：migrate/infra、up/down/up/status，卷保留；HTTP就绪使用显式替身，不冒称真实问数就绪。
2. 普通clone与linked worktree：容器读取准确HEAD/clean/dirty；外部--repo Harness及公共目录可见，均通过。只读Git挂载不赋予socket。
3. dev/app均独立初始化PG和Qdrant。专用runtime-admin初始2个Session、失败次数5、登录锁；恢复前移除LLM/Qdrant/签名配置，API/Web未启动，资产未准备。
4. 真实伪终端：dev两次输入不一致退出2、Ctrl-C退出130、dev/app成功退出0；均无密码回显。成功观察新密码、must_change、全部Session撤销、审计、解锁/次数清零、admin角色保持；另一环境不变。
5. Control运行密码含字面$及$$；实际连接/恢复成功，证明维护Compose配置不再次损坏凭据。只保存私有临时配置，不记录真实Secret。
6. dev/app只读doctor在依赖缺失时退出1，不创建缺失asset卷，不改账号。metadata真实catalog导出tables/columns/relationships三文件、宿主UID正确。
7. 重置使用专属项目的API/Web替身进程：错标签及external卷在停止前拒绝，API仍运行；停止故障退出非零且卷/账号保持。取消PG重置不变。
8. 确认PG重置仅删除本dev账号/数据并重新迁移；QD集合标记与app管理员保持。确认QD重置集合清空，PG/app不变，API/Web保持停止。
9. 最终临时项目chatbi-entry-runtime-dev-45734与chatbi-entry-runtime-app-45734均通过；所有专属测试容器/卷/网络按项目身份清理；原chatbi-engine运行服务及原工作区保留。

## Review、迁移及未运行项

[Code Review](code-review.md)检查全部owned files和七项验收；基线24/24脚本及外围入口去向见[盘点](script-inventory.md)。旧数据库runner与前端test:real未能证明等价的能力保留非推荐兼容，PowerShell旧宿主启动归档并指向WSL/dev。

正式事实源：README、Runbook、开发/标准容器Contract、Bootstrap、管理员恢复Contract；Product Scope/Architecture补恢复边界，Roadmap仅更新已确认本地完成事实。

未运行：真实LLM问数/AI Evaluation及verify dev/app完整收费验收；只验证这些入口的参数、目标和退出码委派。本次浏览器测试使用确定性服务，并不能证明当前真实LLM配置或日常网站已ready。未Push/PR，独立restart候选fd9be30未纳入本目标。

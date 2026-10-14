# 02 开发者无需宿主Python/Node即可完成验证

Status: done
Canonical Source: [Spec](../spec.md)、[Design](../design.md)。用户确认四项拆分及完整本地实施、验证、Commit；无发布授权。


Change Profile: 持续维护 / 中等跨dev、测试配置与脚本 / 中风险（临时资源、凭据和测试覆盖）/ 软件、PG、浏览器、renderer / 本地交付。
Owner: 当前实施Agent。
Blocked by: None (can start immediately)

### What to build / Scope

增加Design定义的dev test/check/evaluate入口与容器调试说明；容器执行Python/Node/评测，Bash管理隔离测试数据库。适配Playwright容器fixture并保留CI默认行为，补齐实际浏览器/renderer能力。保留现有dev初始化、热更新和卷名。

Owned files: dev；docker-compose.dev.yml及新增测试Compose override；docker/python-dev.Dockerfile、docker/node-dev.Dockerfile；scripts/run_database_tests.py及必要容器测试Bash入口；frontend/playwright*.config.ts的执行装配；tests/scripts/test_run_database_tests.py、test_container_dev.py及新增入口测试；tests/container_dev_support.py必要工具；docs/specs/container-dev-environment.md和对应Runbook命令章节。

Out of Scope: Docker socket挂业务API、新依赖、修改评测案例/业务断言、日常数据重置、CI全部容器重写。

### Acceptance criteria

- 用不含python/uv/node/npm的宿主执行环境，通过Bash/Docker完成test/check及evaluate帮助/确定性入口验证。
- test python运行全量软件回归；database分别运行CI和development隔离profile，启用相应开关并覆盖history/execution/checkpoint。
- web运行现有确定性浏览器套件，renderer启用实际Chromium/PDF检查；不以缺少浏览器跳过。
- 帮助/未知参数/失败退出码明确，all不调用收费真实LLM；报告可读取，Secret不输出。
- 失败/成功清理仅处理本次标签资源，API无migration身份/Docker socket；已有卷身份不变。
- CI原有Playwright调用仍兼容，评测参数/案例不改变。

Evidence: 入口正/负向软件验证、隔离PG两profile、浏览器与renderer、前端类型/构建、容器工具实际执行；记录适用skip；评测帮助/确定性装配不使用历史AI成绩替代。
Migration / Rollback: 先补新容器入口，后移除宿主教程；旧脚本必要逻辑迁移后才能删除。测试临时凭据/资源按运行标签清理；测试失败不得影响日常服务。
Done When: 容器入口真实可用、未隐藏宿主Python/Node调用，验证/Review PASS，开发Contract/操作入口同步。
Result: 已完成本目标范围；验证与失败处置见[验收](../acceptance.md)，当前上下文Code Review记录见[Review](../code-review.md)。
Comments: 此项技术上不依赖01；同一Agent按编号实施避免共享文件并发写入。

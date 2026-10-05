# Ticket 06：最终clean候选验收、回归与事实源同步

ID: execution-streaming-v1/06
Status: complete
Authorization: 用户于 2026-10-05 确认六项拆分及连续完成整个 R4 的本地实施，包含编码、适用测试与真实验收、Review 和本地 Commit；不含远端发布。

Change Profile: 收敛型交付验收 /中 /高风险证据 /软件+真实PG+桌面Chrome+AI Evaluation /本地最终candidate。
Owner: 当前主Agent。
Blocked by: 05

### What to build / Scope

- 汇总全部Ticket与受影响Regression，完整确定性 /真实PG /浏览器 /安全与静态检查，R4真实模型与DB闭环、独立业务参考。
- 正式R4 Spec /Design /Acceptance、Query API /Web /History受影响说明、Architecture /Product Scope /Runbook /README /Roadmap与各Ticket Result一致更新。
- 固定最终clean候选运行三套正式Evaluation /统一report身份 /三次完整多轮诊断，以及R4真实SSE /文字 /取消恢复链路；完整保留失败报告。
- 在当前上下文Code Review /Diff检查并形成本地最终candidate；报告发布范围 /风险 /验证 /真实auto-merge行为后另行请求发布授权。

Out of Scope: Push /PR /人工Merge /生产部署、R5–R7、扩大模型或业务数据范围。

Owned files: R4真实profile /验收scripts与frontend真实tests、既有Evaluation验收入口（仅必要受影响适配，案例集不无理由改口径）、相关Software /PG tests；`docs/specs/` /`docs/designs/` /`docs/acceptance/`正式R4与受影响Web /Query /History、architecture /product-scope /runbook /roadmap、README；本目录Ticket /Review /规划证据；故障修复仅01–05范围。

### Acceptance criteria / Evidence

1. Python全量、Runbook隔离DB、npm ci /types /build /Playwright、锁 /模块边界 /Ruff /安全 /Markdown /Diff等适用门禁通过；skip /未运行 /环境阻塞明确记录，不能视为通过。
2. R4真实桌面Chrome /Cookie /SSE /模型 /RAG /DB证明真实阶段与模型增量、最终结果 /图表 /报告参考一致、断连重连 /刷新 /多页 /取消 /草稿重试 /重启恢复正确；04只复用仍适用证据，相关行为 /基线改变重跑。
3. 受理幂等、并发 /额度、stop-success竞态、撤权 /保存失败、registry封锁、旧API /R2 /R3、安全 /SQL Guard、初始化 /升级 /重复 /旧版保留数据回滚有适用软件 /真实PG /浏览器证据；报告分清真实与替身范围。
4. 同一最终clean提交的single_turn /multi_turn /business_analysis正式三套均0 FAIL /0 INVALID_CASE，统一身份检查验证commit /git_dirty=false /案例hash /RAG /数据 /模型一致；另三次完整多轮诊断分别保留，不替代正式报告。
5. 临时账号禁用、活跃Session=0、临时凭证清理、原用户 /业务DB /开发卷 /RAG保留；正式事实源 /Roadmap与当前能力一致，R5–R7不假称已交付。
6. Code Review PASS，only相关Diff /Secret /文档检查完成，本地candidate唯一 /clean；未获发布授权不Push /创建PR。

Evidence / Candidate流程：实现、Contract、Review和适用tracked维护先Commit，再固定clean身份运行真实门禁。若回填tracked结果形成新candidate，重跑受影响真实门禁并按本项最终三套身份要求接受新报告；原报告不改SHA。最终即时结果原子写Git公共目录，tracked验收入口保存可复现门禁与历史身份，不循环回填“当前HEAD已通过”。

Migration / Rollback: 复用已确认的v4 /v3保留数据方案与04证据，基线变动重验；无实际生产rollout，发布另授权。
Done When: 1–6全部适用检查达到可报告终态，正式事实源维护完整、最终clean候选与报告可追溯；准确报告未运行 /剩余问题。仅本地交付完成不授权远端发布。
Result: 起始提交 `4443493`（Ticket05）。最终事实源同步新增正式 [R4 Spec](../../../docs/specs/execution-streaming-v1.md) / [Design](../../../docs/designs/execution-streaming-v1.md)，维护 Acceptance、Architecture、Product Scope、Query API / Web / History、Runbook、README 与 Roadmap。浏览器验收揭示并修复了通道清理后的终态 SSE 回退快照漏发 `draft: null` 的 Contract 缺陷；API 回归断言覆盖该快照，最终打包网页 Playwright 47 passed、Vite 开发代理 Playwright 1 passed。提交前 Python 全量 `737 passed, 38 skipped, 139 subtests passed`；隔离 development PostgreSQL `42 passed`；锁、compileall、Markdown links、模块边界、Ruff format / CI lint、Bandit、前端 typecheck / build 和 Diff 检查通过。当前上下文 Code Review PASS。最终 clean candidate 的真实 Compose / 模型 / RAG / PostgreSQL、三套正式 Evaluation、三次多轮诊断及身份检查结果绑定 candidate SHA，原始报告路径与摘要记录于 Git 公共目录的本机实时状态；生产发布仍未授权。
Comments: 19 个 R4 已修改 Python 路径按仓库 CI Ruff 0.16.8 全仓 `format --check` 收敛；完整确定性及隔离数据库门禁在候选前重跑。宿主 Chrome 缺少 `libnspr4.so` 且日常 API / Web 占用默认测试端口，故打包 / Vite Playwright 使用隔离 Docker browser + Python 容器、挂载当前源码并使用临时 Playwright config；两组最终用例均通过，临时配置和容器已清理，日常 Compose 服务保持健康。正式 Evaluation /真实候选门禁按本 Ticket 的 clean candidate 流程在提交后运行，精确身份和结果只写本机 Git 公共目录，避免结果回填改变 SHA。

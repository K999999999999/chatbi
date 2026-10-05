# 06 最终候选真实闭环验收与事实源同步

Change Profile: 收敛型一次验收 /中 /高风险证据与交付；维护报告 /Runbook长期保留；Evidence为clean候选 /真实PG /Chrome /三套正式Evaluation与R3真实链路；Delivery本地candidate，远端另授权。
Owner: 当前主Agent。
Blocked by: 05（其依赖覆盖01–04，不能在全部行为完成前声称整体R3通过）。

### What to build / Scope

- 使用既有真实验收入口及安全临时账号扩展R3模型 /检索 /只读DB桌面Chrome：查询 /追问 /排序Top-N /刷新 /重登录 /历史与成果 /独立删除 /重查 /API停止重启；analysis原任务恢复与过期 /完成快照保持。用独立参考SQL /确定性归因核对业务结果。
- 汇总01–05证据，受影响行为 /基线变动重跑；完成失败注入 /真实PG初始化升级重复、运行资源释放 /旧版保留数据回滚、安全与旧API完整回归。
- 最终clean候选运行三套正式Evaluation与统一real_e2e_acceptance；不以小范围R3浏览器闭环替代三套。正式失败报告保留，修复后形成新候选再验收，不挑选成功报告。
- 正式Spec /Design /适用Architecture /产品范围 /README /Runbook /日期化Acceptance /roadmap完成一致性核对，区分需求状态 /当前能力 /不包含范围；后续R4–R7保持实际未交付。逐一记录维护位置或不适用理由。

Out of Scope: Push /PR /Merge /生产部署、R4流式 /R5导出 /R6–R7容量与多副本；未经授权新技术或真实业务数据写入。

### Owned files

`scripts/verify_container_dev.sh`及其现有helper /真实验收入口、`frontend/tests/container-real.spec.ts` /real配置与必要R3用例、受影响软件 /PG /API tests、`reports/evaluation/` /Acceptance报告、`docs/specs/history-results-v1.md` /Query API /Web /相关恢复语义Contract、`docs/designs/`、`docs/acceptance/`、`docs/runbook.md` /`docs/product-scope.md` /`docs/architecture.md` /`docs/roadmap.md` /README、本目录Ticket与Review证据。若验收发现缺陷，仅修复01–05既定owned files和范围并重新Review /检查，不加新承诺。

### Acceptance criteria /验证证据

1. `uv run --python 3.11 --locked python -m pytest -q`、Runbook数据库测试入口、frontend `npm ci` /typecheck /build /Playwright、适用锁检查 /安全检查 /静态检查通过；环境缺失或未运行明确记录，不能以skip称通过。
2. 实际fresh /v2 upgrade /repeat migration、restart /旧generation /checkpointTTL /回滚保留数据、故障保存 /超限 /多页面 /stale /跨owner /撤权等矩阵有当前适用证据；软件seam与真实PG /浏览器证据类型分清。
3. R3真实浏览器完整行为在最终clean候选通过，真实结果与独立业务参考一致；正式报告关联commit、git_dirty=false、RAG /案例集 /数据库身份 /配置边界，临时账号 /Session /凭证清理不伤原用户 /卷 /业务数据。
4. 三套single_turn /multi_turn /business_analysis正式Evaluation按Runbook§9、同一最终clean候选与资源身份全部通过，并由统一acceptance入口核对；另做三次完整多轮稳定性诊断并保留全部结果，诊断不替代正式基线。R3history profile另有真实闭环证据，旧套件不能代替它。
5. 当前上下文workflow-code-review、Diff /Secret /文档链接及roadmap内容一致性核对通过；所有正式事实源与各Ticket Result同步，有适用范围 /剩余风险 /未运行项目的准确报告。

Evidence /候选流程: 先完成实现、Contract、Review及适用事实文档 /确定性证据提交，再固定clean候选运行真实验收。若预验收后回填tracked Acceptance /Ticket结果形成新提交，必须再次固定最终clean HEAD并运行最终三套正式Evaluation /统一acceptance和R3真实闭环，让最终报告严格绑定该HEAD；原预验收仅保留自己的身份，不冒称新HEAD成绩。生成报告使用既有.gitignore下reports/evaluation与reports/browser-real位置；最终验收后不再修改tracked文件补写“当前通过”，实时结果原子记录于Git公共目录。若代码 /Contract /基线改变则修复、Review并形成新候选后重跑受影响检查。最终commit不因只加证据而绕过正式报告expected-commit核对。
Migration / Rollback: 使用隔离fresh /升级测试库和原有明确入口，保留开发卷 /账号 /RAG；旧版兼容演练停止API后切换版本、保留v3数据，恢复当前候选。无实际生产Rollout /feature flag门禁；一旦需要真实用户部署返回发布授权与R6边界。
Done When: 全部01–05与上述适用门禁 /真实验收通过，正式证据身份 /维护位置完整、所有Ticket结果与当前候选可追溯、Code Review /Diff /本地Commit完成，形成唯一clean本地candidate。报告发布目标 /风险 /验证 /实际Auto-merge规则后才能请求PR发布授权；本Ticket完成不授权发布。
Result:
- Candidate A `d6041af45bf4f69bb7b60053e0a404d754dc23fc` 的 R3 Compose 真实链路通过：`reports/browser-real/container-1791144563-real.json`，`git_dirty=false`，两阶段均通过，独立业务参考一致，临时账号已禁用且活跃 Session 为 0。
- Candidate A 正式报告在 `reports/evaluation/baseline-20261005T041046Z-d6041af/formal/`：single-turn 29/29、multi-turn 7/7（15/15 轮）、business-analysis 10/10，均 0 FAIL / 0 INVALID_CASE；`real_e2e_acceptance` 确认三套报告同一 clean commit 与 RAG 身份。三次独立 multi-turn 诊断均 7/7（15/15 轮），退出码均 0，报告分别位于 `diagnostic-1/`、`diagnostic-2/`、`diagnostic-3/`。
- 本 Result、其他 Ticket Result 与路线图同步将形成 Candidate B，因此 Candidate A 是预验收证据而非最终身份。Candidate B 必须再运行 R3 Compose 真实闭环、三套正式 Evaluation、统一身份验收和三次诊断；最终身份、退出状态与结果由 Git 公共目录实时状态记录，随后不再改 tracked 文件回填“当前通过”。
Comments: 真实API凭证与.env只在本地，报告不得泄露Secret；失败必须保留并修复，不通过回退验收门槛完成。

Status: in-progress
Canonical Source: ../spec.md、../design.md、../restoration-semantics.md
Authorization: 用户本轮确认六项拆分及整体本地实施（编码、适用真实验收、Review、本地Commit）；未授权Push /PR

# CI 与远端合并门禁加固

Status: Scope 按用户决定收窄为三项；Design Review: PASS；Ticket 拆分已确认；本地实现中；尚未发布或修改远端。

## Problem Statement

本目标处理三处CI / 合并门禁不足：必跑数据库 / renderer测试未强制核验完整计数和skip；scripts/不在现有Ruff范围；远端Ruleset没有要求分支包含最新master。用户明确决定不增加AI评测required check；Real E2E继续保留为手动评测入口，不作为PR合并门槛。

基线：github.com/K999999999999/chatbi，master 64d2eae2b4004dc402d006a1a524ded71a9d7304；branch chore/ci-merge-gate-hardening；新worktree /home/jojo/Projects/chatbi-ci-gates，创建前master与fetch结果同步，初始干净。文档删除 / 修复工作项remove-roadmap-and-audit另在原分支保留，不混入本目标。

## 已核实事实

- 远端Ruleset 23564531（main-protection）active，覆盖默认分支；要求PR、防删除 / 强推、线性历史，无bypass actor，当前用户不能bypass。
- required checks为Deterministic tests、SQL Guard tests、PostgreSQL integration、Application startup smoke、Dependency audit、Secret scan、Static security scan、Code quality，均绑定GitHub Actions integration_id=15368。strict_required_status_checks_policy=false，人工批准数0。
- 自动合并workflow请求Squash Auto-merge；PR98曾被前端 / Python依赖审计先后阻止，最终head 43ccd0b的8项通过后才合并。最新数据库产物5+63项、PDF2项均零失败 / 跳过。
- Real E2E目前仅workflow_dispatch；保留的Hosted记录只有2026-09-28旧workflow失败，不证明后续新版失败或成功。其现行代码已先prepare-model再build-rag。
- scripts.verification_report的finish会保存incomplete摘要但返回0；本目标在CI消费侧增加拒绝规则，保持现有报告工具的只读 / 退出码Contract。

## Solution / 用户故事

1. 必跑数据库和renderer套件若未真正执行、发生跳过或证据不完整，CI必须失败，不能仅凭pytest退出0放行。
2. `scripts/` 改动纳入现有固定Ruff检查，普通CI与本地共用同一入口。
3. Real E2E保留当前手动入口，不自动调用付费模型，也不成为PR必需检查。
4. 远端Ruleset要求PR分支更新到最新master；原8项required checks、Auto-merge和Squash行为保持不变。

## Implementation Decisions

### 范围与模块边界

仅工程验证与交付门禁：workflow、scripts中的校验工具、tests、Python质量入口、适用Runbook和本工作项记录。不得改变产品行为、模型Prompt、指标、查询安全、权限或评测准确率要求；不改AI评测规则，不重构业务模块。

### Real E2E 边界

Real E2E workflow与报告validator保持现状；用户仍可按Runbook手动触发评测。本目标不新增AI评测检查、不要求PR报告、不改变Real E2E工作流、评测成本或其权限。

### 必跑软件测试完整性

- PostgreSQL CI和development profile分别校验JUnit：至少一个实际测试、无failure / error / skipped，文件存在且结构有效；不能两个profile之一未运行却通过。
- renderer校验摘要与JUnit：status=passed、exit_code=0、有真实非零计数、零failure / error / skipped、来源稳定、适用环境身份可核实、无缺失artifact，摘要和JUnit计数一致。
- 不全局禁止普通确定性套件中有明确原因且由其他profile承担的skip；不修改既有报告工具“生成报告成功返回0”的Contract。
- 覆盖伪造 / 损坏 / 缺失 / 零计数 / skip / 摘要与XML不一致及有效通过场景；不靠固定当前5 / 63 / 2计数锁死测试增长。

### scripts 质量检查

将scripts/纳入现有固定Ruff版本的format及现有lint规则，与CI / 本地使用同一入口。仅修正该范围为通过所必需的格式 / 明确静态问题，不混入运行逻辑重构，不扩大为全仓新增类型系统。

### 远端配置与兼容 / 回滚

- 现有8项required checks及其GitHub Actions来源绑定完整保留；不新增required context；仅将`strict_required_status_checks_policy`设为`true`。
- 保留Auto-merge、Squash默认、人工批准数0、无bypass、防强推 / 删除与线性历史，不修改其他仓库 / 分支。
- 仓库代码先本地验证并形成候选；按仓库发布规则说明风险 / 检查 / 自动合并行为并取得具体发布授权后Push/PR。当前总体整改授权不等于已执行远端写入。
- CI代码形成并通过本地候选后，先核对Open PR与当前远端规则，再取得具体Ruleset写入授权后启用strict。
- 写前保存完整Ruleset快照，重新读回确认预期基线，只改变strict字段并核对其余字段；并发外部编辑停止覆盖。回滚使用该次核实快照，不能删除整条Ruleset或临时bypass来促成合并。
- 写后只读证明原8项required checks及来源未变、strict字段为true；需要真实阻断 / 恢复验收时使用明确授权的受控PR，不能往master推故意失败代码。

## Testing Decisions / Done When

- PostgreSQL 两个profile的JUnit：有效、缺失、损坏、零计数、failure、error、skip及分别缺profile。
- Renderer JSON / JUnit：有效、缺失、损坏、计数为0、skip、摘要与XML不一致、身份不完整。
- scripts Ruff format / lint覆盖；检查本地与CI是否继续共用同一入口。
- Ruleset写前 / 写后完整快照比较：8个contexts及App来源不变，仅strict变true；检查Open PR影响。
- 软件摘要：有效 / 缺失 / 损坏 / skip / 零计数 / 状态与计数不一致；不修改日常业务数据。
- scripts定向回归、统一Python质量、文档 / 模块边界 / lockfile及受影响确定性全量检查。
- Hosted实际证据与本地替身分别记录；真实评测由用户手动触发，不在测试中暗中调用付费模型。实际Hosted / remote写入仍按已获授权推进。
- 相关正式文档 / Runbook更新及链接检查完成；旧文档分支和其他本机工作记录保留，未运行 / 失败 / 无法核实项明确列出。
- 实施后的当前上下文Code Review、Diff检查与本地Commit完成。远端交付、required检查、Ruleset生效和合并后复盘各自记录，不以本地绿灯代替。

## Out of Scope

新增AI评测required check、自动收费评测、改变Real E2E入口或评测准确率、关闭自动合并、增加人工Review人数、改业务实现、移除安全检查、推送当前文档分支、安装或改写外部Plugin、实现旧harness-candidate-preflight的跨仓库通用平台提案。

## 授权与后续阶段

用户已决定不增加AI评测门禁。本目标限于测试报告完整性、scripts Ruff覆盖和远端严格更新分支规则；Real E2E继续手动可用，但不要求PR触发或通过。用户已确认三项Ticket拆分，按依赖连续实施本地范围。远端Ruleset写入仍需候选形成后的具体授权。

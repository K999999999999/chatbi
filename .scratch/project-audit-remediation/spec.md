# 全仓审计问题修复与回归验证

Status: 已完成；PR #88 已于 2026-10-17 合并至 `master`，merge commit `34867d83049d35ee6567dbcabef8b197c5cfa9ea`，8/8 required checks 通过。Ticket 01–12 的实现、验证、Review 与交付状态见各 Ticket，最终收尾证据见 [Ticket 12](issues/12-final-validation-and-documentation.md)。设计审查为 PASS WITH MINOR FIXES，修订落实情况见[设计审查](design-review.md)。

工作项 ID：`project-audit-remediation`。审计与起始代码基线：`8d01740474b2c727131e54a70a2f186713b306ad`。

## Problem Statement

[全仓审计报告](../../docs/audits/project-audit-20261016.md)记录 22 项问题，覆盖业务结果正确性、请求保护、状态与观测、数据清理、安全边界、模型加载、验证入口及文档状态。AUD014 已根据正式 Contract 排除，不纳入缺陷。

当前代码与审计基线一致。审计证据包括静态分析和部分合成输入复现，不包含完整软件回归、真实 PostgreSQL 并发、真实 LLM 或完整容器业务验收。本目标需要逐项形成修复和回归证据，不能以现有 CI、审计结论或历史成绩替代新候选验证。

原工作区的 README、文档维护规则和审计报告仍为审计归档的未提交改动，保留原样。本工作在独立 worktree 和一个 feature branch 上规划、实施；隔离工作区的报告副本必须与原报告逐字一致，不改写原始发现。

## Solution

在现有 Architecture、产品范围及行为 Contract 内修复全部 22 项。优先保证 SQL 与结果语义、权限与请求保护、数据保留及安全；修通真实验证入口后完成软件、AI 和隔离业务验收。原报告保留为历史证据，新工作记录负责修复映射、验证结果与剩余限制。

### 用户决定与授权

- 用户“可以，按你建议来”确认以全部 22 项建立修复需求。
- 用户在解释真实验收会使用已配置模型并产生 API 费用后回复“可以”，确认纳入真实 LLM 评测和隔离容器业务验收。
- 用户已在当前会话明确回复“确认”批准本完整 Spec、12 项 Ticket 拆分及整体本地实施/验证/Review/Commit。按依赖连续完成全部 Ticket，不逐项等待确认。
- 2026-10-17，用户再次回复“确认”，批准在既有经营分析 Contract 内修复 BA03 首轮失败暴露的总结与 Judge 边界：总结明确“仅未在报告中展开”的产品限制，Judge 以程序归因返回的至多 3 个产品判定贡献，不要求总结重算或补列其余产品；不得更改案例、数据、模型参数或通过门槛，必须保留首轮失败并在修复后新候选上重跑受影响的正式验收。
- 真实调用授权只覆盖本目标的现有合成数据、标准案例、正常模型输入及 Judge 输入；不读取并发送真实私有业务数据或凭证。复用既有模型配置，不更换 Provider、模型或引入新依赖。
- 本 Spec 默认本地交付，不自行授予 Push / PR 授权。用户于 2026-10-18 单独授权向 `master` 提交 PR #88；该 PR 已于 2026-10-17 合并，授权已完成。

### Scope 与正常结果

| AUD | 预期行为与成功条件 | 必须覆盖的失败或边界 |
| --- | --- | --- |
| AUD001 | 多指标 SQL 只允许认证形状支持的普通分组；GROUPING SETS、ROLLUP、CUBE 等额外分组语义不得突破校验；合法多指标查询保持成功 | 覆盖相关 SQLGlot AST 形式及组合；不支持的形状返回 SQL_REJECTED，数据库执行器零调用；合法普通分组和历史条件回归 |
| AUD002 | 授权拒绝测试观察当前真实下游执行方法，证明拒绝发生在任何查询执行或副作用之前 | 无身份、无权限和受控拒绝均断言真实执行路径零调用；合法授权场景证明同一替身可被调用，避免对未使用mock的空断言 |
| AUD003 | 历史 submit、requery、resume 和成果 requery 兼容执行入口纳入同一就绪与账号/API业务额度保护 | 未就绪503、额度不足429、跨 history_id / 同步与后台共享；幂等重放不重复占额；异常、取消和真实工作结束后的释放；保持现有身份、锁、错误外壳和接口 |
| AUD004 | 业务层的 AUTHORIZATION_DENIED / AUTHENTICATION_REQUIRED 与 HTTP401/403 均准确映射既有授权撤销终态 | 授权依赖故障仍归 unavailable；拒绝后不继续执行、不提交成功；不在 Domain 中引入 HTTP依赖 |
| AUD005 | 真实 succeeded 轮次记录 SUCCESS，无错误分类；已有 completed 调用兼容性按实际调用点核对 | 失败、超时和业务拒绝的分类保持；使用真实 Worker/API 状态建立回归，不能只用替身 completed |
| AUD006 | 主动删除分析历史后，相关 checkpoint 数据仍能被既有清理机制回收，已经 expired 的遗留对象也可回收 | checkpoints、checkpoint_blobs、checkpoint_writes 全部覆盖；重复清理幂等；其他有效 run 和独立成果保留；删除后不得恢复原 run |
| AUD007 | PDF 每个证据分块的列名、列序号和单元格值对应同一源列 | 至少覆盖 8 列、奇数列、空行、长中文列名及后续分块；验证实际 PDF 文本/内容对应，不只检查末列存在 |
| AUD008 | 页面、历史重开、图表和 PDF 正确解释后端 continuing / new_product / exited_product 分类 | 新增/退出产品的金额、方向和因素不变；兼容识别已有 new / discontinued 表示；未知分类仍受控处理，不猜产品语义 |
| AUD009 | requery 受理结果不确定时保留原 operation ID 和原请求，用户显式恢复/重试仍指向同一操作 | 提交超时、首次查找失败、迟到受理、确定拒绝、账号切换及401/403；不自动换ID重发，不影响原历史/成果 |
| AUD010 | 同一共享 BGE provider 并发首次调用只成功构造一个模型实例 | 同步多线程首次查询、已加载快速路径、加载异常和后续可恢复；不扩展为全局推理串行化或跨进程协调 |
| AUD011 | 手动 Real E2E 在 build-rag 前显式准备固定 revision 的本地 BGE 快照，构建使用同一快照身份 | 缓存为空、缓存命中和准备失败；失败不进入正式 suites；来源、路径和 manifest 一致；不移除本地快照检查 |
| AUD012 | host Playwright 的报告写入和读取定位本次同一个 run 目录 | 保留容器报告目录与既有优先关系，目录未设置、空值和文件名穿越防护；host start.json 能被实际 helper 读取，不写 /reports 作为错误回退 |
| AUD013 | 隔离容器热更新验收能按受控方式修改本次测试源码、观测 Python/Vite 更新并恢复 | 成功、中途失败和中断均恢复；默认初始阶段实际执行；不对日常源码挂载开放无范围写权限，不以 skip 绕过检查 |
| AUD015 | 当前 Linux 本机 .env 收紧为仅文件所有者可读写；项目说明与 dev 配置加载入口防止宽松权限配置被无提示使用 | 新建文件使用安全权限；已有宽松权限给出明确修复方式并安全拒绝加载；不输出文件内容，不修改值、不提交配置、不递归 chmod；不承诺不支持的文件系统权限语义 |
| AUD016 | AuditRecord 的 dict/list 嵌套结构也受既有敏感字段约束，敏感载荷不能持久化 | 顶层、深层字典、列表内字典及合法嵌套详情；失败提示不回显载荷；复用既有敏感键规则，不声称能识别任意文本里的 Secret |
| AUD017 | 首个管理员初始化在数据库事务中互斥；已有固定 admin 角色但没有管理员时也只允许一个并发请求成功 | 真实 PostgreSQL 上不同用户名同步竞态；恰好一个成功、另一个受控拒绝；失败回滚后可重新初始化；不改变日常创建管理员/恢复管理员语义 |
| AUD018 | Qdrant 构造或连接失败后，公开错误和服务日志不含 URL userinfo、API Key、敏感查询参数或原始敏感异常 | 用合成 canary 覆盖 URL、异常文本和最终日志链；保留安全阶段/错误类别用于排障；不接触真实凭证内容 |
| AUD019 | 持久化分析快照公开前按嵌套公开 Contract 校验，异常旧快照不能通过 task_results/report/metadata 携带内部字段 | 合法现有快照与缺少可选说明的旧快照继续可读；嵌套 SQL、连接信息或 Secret 等非法快照受控拒绝；普通 query 的合法 sql 字段保留；不扫描或重写日常数据库 |
| AUD020 | 保留旧数据库测试入口的兼容能力，连接/探测等待正式 PostgreSQL TCP 服务和初始化条件 | 临时 socket 实例不可被当成正式服务；正式TCP可用、失败、超时和 fixture 初始化条件；新容器入口无回归 |
| AUD021 | 专用验收用户创建与报告写入之间发生异常时，仍可确定本次账号身份并完成既有清理 | 账号提交后 account.json 写入失败、prepare/cleanup 失败与中断；保留正常清理的禁用/Session撤销语义；不得按模糊前缀批量修改账号 |
| AUD022 | R1 Spec 首部反映已交付的历史事实，并指向原有验收证据 | 不把旧结果冒称本次候选通过，不删除原日期/决定/验收记录 |
| AUD023 | 项目导航 Spec 首部与已有非作者走查、Ticket 完成记录一致 | 保留历史状态依据，不重造走查证据；链接与同工作项状态无矛盾 |

## User Stories

1. 作为问数用户，我得到的是通过确定性认证的结果，失败重试不会重复受理；未就绪或超额时获得明确拒绝。
2. 作为经营分析用户，我能查看新增/退出产品，导出的证据列名与数据一致；删除历史后不留下永不清理的 checkpoint。
3. 作为管理员和维护者，我能可靠初始化首个管理员，从日志得到正确状态和安全诊断，凭证不会经新增嵌套结构或故障异常外泄。
4. 作为开发者，我能运行保留的兼容检查和正式容器验证，报告准确绑定代码与资源，异常测试不会留下不可定位的账号或源码修改。

## Implementation Decisions

### 事实源和架构

- [Architecture](../../docs/architecture.md)、[Product Scope](../../docs/product-scope.md)及现有正式 Spec 优先于审计和旧实现。
- 查询仍走 Natural Language → Business Semantic Resolution → SemanticQuery → Certified Physical Mapping → SQL，模型输出仍为不可信候选。
- 使用现有 Port、Adapter、runtime、PostgreSQL 事务、模型 provider 和报告入口；不引入新的服务、平台、队列或依赖。
- 内部互斥手段、锁粒度、递归校验组织、路由共用保护方式与测试 seam 在设计审查中核实；不得反向改变上述可观察结果。发现需要改变公共 Contract 或安全/状态不变量时返回确认。

### 兼容和数据生命周期

- 保留历史兼容 HTTP 路由、旧 run_database_tests.py 和 host Playwright 的现有独有能力；推荐入口继续为 dev。
- 对合法旧数据保持现有兼容；非法分析快照返回既有 HISTORY_SNAPSHOT_UNAVAILABLE，不静默展示、脱敏后假装完整成功或执行旧 SQL。
- checkpoint 清理覆盖已过期遗留数据，但不扩大删除范围至历史、成果或仍有效的其他 run。实现脚本不自动修复日常库。
- 预期不需要破坏性 Schema 迁移；若设计发现必要迁移，先补充迁移/回滚与用户确认，不在代码阶段自行扩大。
- 本机 .env 权限处置只针对原工作区已识别的本地文件；验证环境使用独立配置，不能从 chmod 一项推定 Secret 从未泄露。
- PDF/前端接受已知分类兼容表示，不修改归因算法和权威后端值；不从旧前端 fixture 重定义业务分类。

### 本地资源和工作区

- 一个工作项、一个 active branch、一个隔离 worktree；不 stash、reset、移动或覆盖原工作区已有修改。
- 真实数据库并发测试和业务验收使用独立数据库/Compose project、专用账号、完整合成 Seed；不得操作日常服务或卷。
- 允许按既有 prepare-model/build-rag 流程准备隔离测试所需资产；模型缓存可按既有固定 revision 复用，不覆盖日常已发布 RAG 指针。
- 热更新测试只能写入本次隔离源码副本或明确受控的本次候选文件，且必须在起止源码身份核验前完成恢复；不能扩大容器对原工作区的写权限。

### 设计审查后的实施约束

以下是对既有验收要求的细化，不改变公共接口、目标范围或数据生命周期。

1. **历史兼容受理。** 不能简单在HTTP路由外包一层admit，否则幂等重放也会被就绪/额度阻挡。沿既有begin_*事务，在归属、请求摘要、幂等和revision校验完成后、新attempt或重查history写入前，调用Application提供的可选内部受理回调。回调由Application装配，复用现有就绪与owner额度机制，不把Request/Response/ORM对象传入核心边界。Application用同一退出栈持有租约，直到同步真实工作及必要持久化结束；事务失败也释放。后台已占额路径不再次调用同步受理。复用现有SynchronousExecutionControl并传至下游，保持180秒/1200秒保护。
2. **checkpoint清理。** 仍保留expired tombstone阻止ID重用；仅选择已到期run及其关联checkpoint，可用子表存在性过滤避免每轮无差别更新全部expired记录。不把删除历史变成删除独立成果，不引入新的清理服务或破坏性迁移。用真实PG验证已expired遗留数据和重复清理。
3. **首个管理员。** PostgreSQL使用专用固定事务advisory lock，在查询现有管理员之前取得，直到提交/回滚释放；锁身份不能复用HistoryRuntime等已有锁。比较过锁admin角色行的方案：它依赖角色已存在且不能完整覆盖未seed的原入口，因此不采用。SQLite现有软件测试继续覆盖串行行为，不能据此宣称并发安全。调用者事务、用户与角色写入仍保留在Control DB边界。
4. **公开/审计嵌套数据。** 分析公开快照按report、task、error、attribution、result_metadata既有结构逐层校验，SQL/连接配置等非公开字段受控拒绝；不能只递归删除几个敏感键来冒充完整校验。query合法sql和旧可选字段缺失保持。AuditRecord按现有敏感键规则递归dict/list，非法或不可遍历结构受控拒绝；不把纯文本里的业务词当敏感字段。
5. **隔离验收恢复。** 仅isolated模式将本次受控源码路径提供给测试写入；其余挂载保持只读。保留原内容、失败/信号恢复与恢复后Hash核对，测试失败及可处理的INT/TERM必须执行清理；SIGKILL等不可捕获终止保留源码备份和准确身份供恢复，不能报告清理成功。账号身份记录应在用户提交前安全落盘，或在持有确切身份的prepare异常路径补偿；提交到记录落盘之间不存在唯一身份丢失窗口。最终清理仍精确核对id+username并禁用/撤销Session，不批量扫描删除账号。
6. **模型与报告。** Real E2E显式prepare-model后以同一固定revision本地路径build-rag；host报告helper依次选非空CHATBI_CONTAINER_REPORT_DIR、CHATBI_REAL_E2E_REPORT_DIR、原容器默认/reports。两种显式变量并存时保持容器优先，穿越校验不变。本地隔离验收也在build-rag前显式准备快照或验证同revision可用缓存，不隐式加载远端模型ID。
7. **权限和副本。** Linux配置文件在读取/交给Compose前检查属主和group/other权限；拒绝不安全模式并只给出修复指令，不打印配置。已确认的本机.env处置只chmod该文件，不变更值。真正的配置读入前检查不能仅位于某个后置启动步骤，help无配置无Docker行为保持。

## Testing Decisions

### 确定性验证

1. 为表中每项行为缺陷补充可观察的回归，尽可能证明修复前失败、修复后通过；文档状态修正使用证据核对和链接检查，不编写只镜像文字的测试。
2. 运行 dev 容器内 Python、数据库 CI/development profiles、Web、renderer 套件与完整 dev check；数据库测试包括真实 PostgreSQL 并发初始化、checkpoint 清理和容量/事务相关行为。
3. 检查原始计数、skip、未执行范围和清理结果，命令退出0不等于完整通过。选择性跳过须说明归属，不把 intentional skips 改成成功。
4. AUD011 做工作流步骤/配置回归并在本地隔离环境验证 prepare-model → build-rag → suites 所用资产身份；AUD012、AUD020 对保留旧入口做实际 helper/探测调用验证。没有运行的 Windows 或 GitHub runner 行为明确标注。
5. 代码变更后执行 workflow-code-review、Diff Review、git diff --check；Python质量使用仓库统一脚本，不以局部 lint 冒称全量检查。

### 真实 AI Evaluation

- 在实现与软件回归收敛后的 clean candidate 上，运行现有 single-turn、multi-turn、business-analysis 三套正式评测，启用 online retrieval，不修改案例、Seed、模型参数或比较门槛以换取通过。
- 按[Evaluation Contract](../../docs/specs/evaluation.md)验证三套报告完整性、全部案例/轮次、0 FAIL / 0 INVALID_CASE，以及相同候选 SHA、RAG、数据、有效模型配置和 stable provenance。任何 suite 失败不阻止其余 suite 出报告。
- 保留首轮完整结果。必要故障修复后对受影响的新候选重跑，保留失败历史，不挑选成功轮次或结果替换本次失败。
- 本目标不额外承诺多次完整稳定性研究；辅助 query-understanding 套件按相关链路改动需要补跑，不能替代三套业务评测。
- 报告进入既有 ignored reports 目录；长期记录只保存安全摘要、命令、身份、判定及本机报告位置，不提交原始 Secret 或敏感请求。

### 隔离业务验收

- 执行现有隔离 dev 容器业务验收，覆盖登录、问数/追问、经营分析、历史/成果、执行恢复、导出和热更新等既有场景。
- 新增/退出产品、PDF多列对应、不确定重查及授权撤销等审计 Bad Case 由确定性浏览器/renderer/数据库测试提供必需证据；真实合成数据未触发某种边界时，不冒称真实场景已经覆盖。
- 报告绑定本次候选、镜像、模型、RAG与Seed；验证结束核实专用账号、临时资源与源码恢复。原Contract要求 skip 导致 incomplete 的规则保持；如有 skipped，报告其原因及未完成条件，不宣称全量通过。
- 本地验证不等于远端工作流成功。托管 Real E2E 和 PR CI 只在发布授权后才可触发/跟进，当前保留未执行状态。

### 证据与完成条件

- 建立 AUD → 修复行为 → regression → 候选提交 → 验证结果的22项台账；每项标明正常、失败和边界覆盖及尚未验证部分。
- 测试证据绑定实际运行的 clean candidate；后续若仅追加验收文档，记录证据适用的代码基线及差异，不把旧报告 SHA 改成文档提交 SHA。相关代码、案例、配置或基线改变后重跑受影响检查。
- 全部适用检查、真实评测与业务验收结果有明确判定。环境或模型失败不得通过放宽标准关闭工作项；无法完成时保留未完成项和恢复条件。
- 正式文档、Review、Diff检查完成后才做相关本地 Commit；代码候选与验收记录的提交分别遵守证据规则。

## Documentation

| 更新位置 | 应记录的内容 |
| --- | --- |
| 正式 online-query / application-readiness / execution / query-api / history / business-analysis / bootstrap Specs | 只补充与本次修复有关的既有边界及验收，不扩展功能；公共字段和值以已确认行为为准 |
| result-export / result-visualization 及对应 Design | 分类兼容、PDF数据对应及相关验证机制 |
| Runbook、相关容器与初始化文档 | .env权限、模型准备、隔离验证与清理说明；保留兼容入口定位 |
| R1及项目导航原Spec | 仅修正过期首部状态，保留原交付证据 |
| Roadmap | Spec确认后登记审计修复目标，交付时据证据回填，不重排其他路线优先级、不新增生产承诺 |
| 本工作项记录 | Spec、后续设计/Review/Tickets、22项修复台账和验收摘要 |
| 原审计报告 | 内容保持原样，作为历史发现依据；修复进度引用本工作项，不把原审计改成当前验证报告 |

原工作区审计导航改动不自动纳入修复 Commit；如需归档进入当前交付，在 candidate 前单独核对来源和范围。所有受影响本地 Markdown 链接通过仓库检查。

## Out of Scope

- AUD014、新的全仓审计、无关重构，以及超出22项的新功能。
- 改变指标口径、归因公式、Semantic/RAG权威事实、账号数据范围或SQL安全标准。
- 删除兼容接口、迁移日常数据、批量清理未知账号、轮换真实凭证或读取凭证值。
- 日常环境重启/热更新、公开生产部署、多worker/多副本保护、容量与稳定性承诺。
- 新依赖、替换模型/Provider、远端设置变更、Push/PR、人工Merge；必要范围变化须另行确认。

## Further Notes

- 事实源优先级：正式 Architecture/Product Scope/Specs → 已确认本需求 → 设计与Tickets → 实现；审计只提供缺陷与证据，不能替代业务Contract。
- 当前没有需要用户另选技术方案的未决问题；设计审查补充的是已确认行为的实施约束，不改变范围或公共Contract。
- 完整Spec与拆分均已确认；12项草案经Readiness通过后已写入正式[issues](issues/)。按授权实施修复；不含Push、PR或远端工作流触发。
- BA03 首轮完整报告 9/10，首轮失败原样保留。其 Judge 依据全部原始产品行要求列出超过产品 Spec 上限的贡献，而产品 Spec 明确只展示按整体方向选择的至多 3 个产品；总结提示也未明确区分“本报告未展开”和“数据缺失”。按用户后续确认，只修正总结提示和 Judge 的 Contract 指引，仍核实任务可用性；案例集、Seed、比较门槛和归因计算不变。修复后的 BA 评测必须绑定新 clean candidate，不能覆盖首轮报告。

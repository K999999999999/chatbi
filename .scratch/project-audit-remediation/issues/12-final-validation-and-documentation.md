# 文档状态修正与完整候选验收


- Change Profile: 中高风险；收尾文档和本目标有界完整验收；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD022、AUD023。
- Blocked by: 01–11；需全部完成
- owned files: .scratch/chatbi-product-v1/r1-spec.md；.scratch/project-navigation/spec.md；docs/roadmap.md；README.md（仅本目标入口）；docs/audits/project-audit-20261016.md（与原始报告逐字一致，供路线图和README链接在clean clone中有效）；.gitignore（排除验收器自己的运行状态文件，确保clean candidate provenance）；scripts/start_dev_api.py、src/bootstrap/readiness.py及对应确定性回归测试（修复隔离验收发现的冷启动就绪探针超时，不改变用户行为）；tests/chatbi_control/test_history_postgres.py（修正锁等待故障注入的超时预算，不放宽断言）；scripts/verify_container_dev.sh（让最终验证报告发布不依赖已清理的临时Compose文件）；frontend/tests/helpers.ts、frontend/tests/operations.spec.ts、frontend/tests/container-real.spec.ts（让真实浏览器验收等待公开就绪状态，并在受理被拒绝时立即记录安全状态，不改产品行为）；src/business_analysis/reporting.py、evaluation/suites/business_analysis/business_analysis_judge.py及对应测试（按用户确认的既有 top-3 Contract 修复总结提示和 Judge 判定边界，不更改案例或门槛）；本工作项记录及路线图引用的Spec/设计审查/Ticket草案/Readiness材料；必要现有验证编排入口（仅运行，不新增通用平台）。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

按历史证据修正两份Spec首部；完成22项映射台账、全量软件检查与三套真实AI评测/隔离业务验收，修复 BA03 首轮报告暴露的 Contract 表达和 Judge 边界后绑定新 candidate 重跑，不覆盖首轮失败，形成一个本地candidate。

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

Status: in-progress
Result: 当前最近正式评测候选为 `97268ca67cdba7523de61be7e6acb95f17096410`；之后审计分支新增本地Commit `f67221b`（S02别名）和 `c345827`（验收readiness时序），尚未在新clean candidate上重跑隔离容器验收，正式AI门槛仍未通过，T12保持in-progress。
Comments: 按已确认Spec、设计审查和READY拆分登记。审计报告副本、README入口与路线图链接所需的本工作项记录一并纳入最终候选，原始审计文件不改写。最终验收首次暴露冷启动下完整readiness探针耗时超过其10秒子进程超时，以及验收器自身`.verification-state`导致dirty provenance；已增加定向修正与回归。全量数据库回归又显示，worker-timeout故障注入未能在外层20秒预算内完成资源清理；将6秒`statement_timeout`明确限定在注入查询事务内，保留锁观察、错误诊断和连接清理断言。首轮隔离验收的业务与资源清理步骤均完成，但总结发布器依赖随后已删除的临时Compose文件而返回未确认；验证报告工具现改为独立只读Python容器调用。首轮 BA03 正式经营分析评测 9/10，失败历史保留；用户于2026-10-17确认修复总结对被省略产品的表达及 Judge 对 top-3 Contract 的判定边界，不更改案例/Seed/门槛，修复后须在新候选重跑。

候选 `7ba52e1` 的最终 `./dev check` 通过，run `20261016T225747Z-7ba52e1-check-all-6032420bb987`；`./dev test all` 1245 passed、61 条件性 skipped、0 failed，报告状态 incomplete，provenance stable（run `20261016T225820Z-7ba52e1-test-all-85816718c743`）。提交前经营分析相关定向测试73 passed / 2 subtests（run `20261016T225617Z-bdb4452-test-python-572afe804931`）时 HEAD 为`bdb4452`且`git_dirty=true`，仅作实现迭代证据，不作为clean candidate门禁；代码修改的只读 Review PASS，`git diff --check` PASS。固定BGE revision `5617a9f61b028005a4858fdac845db406aefb181`；新 RAG `audit-7ba52e1` 包含7张表、69列、7个指标和9条关系，构建失败数0。

同一代码SHA、Sales Mart Seed `chatbi-sales-mart-dev-v3`、数据hash `5ecab061588e5084ef1dd13c9d0a969d3c49f8d26bd7418b5341f427abedeafb`、RAG `audit-7ba52e1` 和稳定provenance上的三套正式评测报告：单轮 `20261016T230724Z-7ba52e1-single-turn-ee1b1f1185f7` 为28/29；S02失败阶段`query_understanding`、`LLM_ERROR / PROVIDER_CALL_FAILED`，未生成SQL。经营分析 `20261016T232112Z-7ba52e1-business-analysis-3098287259f6` 为9/10；BA03返回`CANNOT_ANSWER`（`EXPECTED_SUCCESS_MISSING`），评测器未记录内部阶段/原因，总结Judge没有运行，因此本报告不能证明top-3总结修正通过。多轮 `20261016T232613Z-7ba52e1-multi-turn-4e35b4453cc6` 为7/7、100%。官方 `./dev evaluate validate --report-dir reports/evaluation/audit-7ba52e1 --expected-commit 7ba52e1fcf9cc3140700982b77085dfabe1bacef --expected-rag-version audit-7ba52e1` 返回1；单轮与经营分析准确率/零失败门槛未满足。三份完整报告和原候选 `bdb4452` 的首轮报告均保留，没有重跑或挑选结果覆盖失败。

隔离容器业务验收 `20261016T233215Z-7ba52e1-business-acceptance-container-dev-21d860ab876f` 的源码起止SHA均为`7ba52e1`、dirty=false、provenance stable；浏览器问数/追问、重启恢复、长期快照与重查、导出解析、账号精确清理和Compose资源清理均通过；3项设计性browser skip保留，报告为3 passed / 3 skipped、`cleanup_status=passed`、`business_acceptance_status=incomplete`。验收使用独立 `/tmp` 模型/RAG缓存及新detached candidate worktree；活动修复worktree `.model-cache` 指向原工作区的符号链接未被写入。每日 Compose 项目未操作。

2026-10-17诊断（非正式Evaluation，不覆盖正式报告）：比较`bdb4452`与`7ba52e1`的S02报告，模型配置Hash相同、超时均为30秒；前者PASS、耗时44,901ms，后者`PROVIDER_CALL_FAILED`、耗时60,564ms。使用原模型配置直接调用S02 Query Understanding 一次成功，耗时29,665ms；旧失败报告未保存底层异常类型/HTTP状态，因此“慢响应/超时”只是强推断，具体Provider根因未证实。BA03正式报告只记录`CANNOT_ANSWER`，不能据此说失败发生在规划阶段；本地OTel关闭，也无既有Trace可还原。当前候选上，直接语义提取返回“销售额”、2025年2月/3月，确定性计划生成4个Task；随后在新隔离Compose项目、仓库标准seed及`audit-7ba52e1` RAG上运行单案例诊断，应用返回成功、4个Task全部完成并生成总结，未观察到QueryFailure，所有Provider调用成功（提取1,428ms；SQL生成2,200/2,333/3,658/3,823ms；总结10,330ms）。该诊断注入应用工厂以捕获内部错误，因此未运行正式LLM Judge，不能作为BA03通过或首轮失败被纠正的证据；官方报告仍保留9/10失败。临时Compose项目、volume和RAG目录已清理，日常Compose未操作。

上述证据未复现稳定代码缺陷，当前没有可在已确认范围内实施且有证据支持的修复；未改变案例、Seed、门槛、模型配置或重试策略，也未重跑/覆盖正式报告。BA03评测器未把`QueryFailure.internal_reason`写入报告，是此次无法定位首轮失败阶段的具体原因；为报告安全错误阶段/原因及Provider异常类别而改动评测器会超出已确认的22项审计范围，需另行确认。正式AI门槛仍未通过，隔离业务验收仍有3项intentional skip、状态incomplete；T12不能关闭，远端发布未授权。

2026-10-17候选 `97268ca67cdba7523de61be7e6acb95f17096410` 包含已完成的独立评测诊断改进 `0556c7e` 和S02别名修复。候选上 `./dev check` 全部通过；`./dev test all` 为1257 passed / 61 conditional skipped / 0 failed（总计1318，因skip为incomplete；run `20261017T092056Z-97268ca-test-all-38c6ab892758`）。数据库CI 5/5、development PostgreSQL 63/63、web 80/80、web-dev 1/1、renderer 2/2；provenance stable。S02定向回归此前为20 passed、3 subtests（run `20261017T091511Z-0556c7e-test-python-69525b84c9f0`）。

同候选 `97268ca` 的正式评测绑定数据hash `5ecab061588e5084ef1dd13c9d0a969d3c49f8d26bd7418b5341f427abedeafb`、RAG `audit-97268ca`、固定BGE revision `5617a9f61b028005a4858fdac845db406aefb181`，所有报告provenance stable。单轮 `20261017T093218Z-97268ca-single-turn-415beb8a73ca` 为28/29；S02在`query_understanding`失败，原因`PROVIDER_CALL_FAILED`，请求未到retrieval，因此未验证新别名的正式链路效果。经营分析 `20261017T094429Z-97268ca-business-analysis-1844097bd074` 为10/10，BA03通过。多轮 `20261017T094912Z-97268ca-multi-turn-1c312ded2342` 为6/7：`MT-FILTER-REPLACE`阶段一被`SQL_REJECTED`，阶段二因无前序session未运行；同一未修改案例的单例诊断 `20261017T095411Z-97268ca-multi-turn-2c41239efbf0` 为1/1通过，但不替代正式套件失败。官方 `./dev evaluate validate --report-dir reports/evaluation/audit-97268ca --expected-commit 97268ca67cdba7523de61be7e6acb95f17096410 --expected-rag-version audit-97268ca` 返回1（S02和`MT-FILTER-REPLACE`失败）。此前候选 `7ba52e1` 的首轮报告仍保留，未被覆盖。

候选 `97268ca` 的隔离容器验收首次因不完整BGE缓存及外部下载EOF未进入浏览器（run `20261017T095531Z-97268ca-business-acceptance-container-dev-de074096d92b`）；补齐固定revision私有缓存后，正式浏览器验收run `20261017T095656Z-97268ca-business-acceptance-container-dev-f4fe4aa726ef` 在重启阶段240秒未观察到执行终态。相同配置复跑 `20261017T101354Z-97268ca-business-acceptance-container-dev-23654bcf4e57` 显示首个请求200且执行成功，紧接的新请求被`503 SERVICE_NOT_READY`拒绝，随后验收等待执行终态超时；报告为1 passed / 1 failed / 1 skipped，后续阶段未运行。 readiness Contract要求未就绪时拒绝新工作；报告没有指出失败依赖，现有证据不足以判断应修复哪个组件或验收等待行为，不能通过绕过readiness修补。三次报告provenance stable；账号已禁用、活动session为0、精确Compose项目已删除、热更新源码SHA与备份完全相同，日常Compose未操作。完整报告保留于S02工作树的`reports/browser-real/`。

综合当前证据：S02确定性别名缺陷已纳入审计分支本地Commit `f67221b`，BA03在最近正式经营分析评测中通过；但S02正式单轮因模型提供方调用失败而未触达检索，多轮套件出现`SQL_REJECTED`，业务验收重复观察到`SERVICE_NOT_READY`。验收等待时序和错误捕获改进已纳入Commit `c345827`，等待clean candidate实测。验证器因此未通过，S02效果和readiness故障仍未闭环；AI/业务验收门槛以及61项条件skip仍未满足Done When。评测失败诊断改进已作为相关独立工作项完成，不改变案例、判分或门槛；本Ticket不据此宣称全部审计问题已完成。无新的范围或技术选择授权，不继续改变模型行为、readiness Contract或验收门槛；远端发布未授权。

容器复跑报告 `20261017T101354Z-97268ca-business-acceptance-container-dev-23654bcf4e57` 将 `SERVICE_NOT_READY` 限定在真实浏览器第二次提问：首个执行成功，下一次提交返回503；Playwright只等待终态GET，漏掉POST拒绝响应，错误地等待240秒。已有`operations.spec.ts`验证界面显示拒绝原因。针对该验收时序和诊断缺口，新增公开操作状态的有界恢复等待（75秒、需同时`status=ready`和`query_available=true`）与执行提交拒绝的即时捕获；不改变服务readiness或自动重试Contract。TDD红证据为上述真实UAT失败；定向浏览器用例10/10通过（run `20261017T104106Z-7ba52e1-test-web-a7625b7c2213`），完整Web 83/83通过（run `20261017T104315Z-7ba52e1-test-web-9ae68a228d49`，stable但运行时worktree dirty，仅作迭代验证）。干净候选的隔离容器业务验收尚未复跑，不能声称该问题已验证解决。

本轮只读实现Review：PASS，BASE `7ba52e1fcf9cc3140700982b77085dfabe1bacef`，范围为S02指标别名/源事实测试，以及容器验收readiness等待与503捕获辅助；未改查询、业务或readiness产品行为，未扩大评测阈值。定向Python 20 passed / 3 subtests、Web 83 passed、Python质量、文档链接和Shell语法检查通过；`git diff --check`通过。Clean candidate上的容器复验仍待执行；目前只提交本地，不Push/PR。

代码本地Commit：`f67221b fix(semantic): 修复订单明细行数指标识别`；`c345827 test(container): 修正真实验收就绪时序`。二者均通过相应定向回归、Review和Diff检查；c345827后的隔离容器实测尚未执行。

### 2026-10-17 `9b81160` clean UAT 与就绪轮询修正

clean candidate `9b81160498604a176d6693df98a1ad90345d9231` 的隔离业务验收 run `20261017T105025Z-9b81160-business-acceptance-container-dev-444bd63da584` provenance stable、`git_dirty=false`；prepare通过，browser-initial为1 passed / 1 failed / 1 skipped，后续restart与最终exports阶段未运行，cleanup通过。实际首次问数在所有六个业务执行阶段完成，返回成功快照；一次 XLSX 导出成功。随后验收轮询失败，安全错误为`应用在75000ms内未就绪（最近状态：http_401）`。失败点是验收helper误把需登录身份的`/api/v1/operations/status`用作公共就绪探针；该接口在`src/query_api/operations_api.py`明确执行只读身份认证。现有匿名`/ready`才是服务健康与就绪探针。证据支持测试等待目标错误，不支持将这次失败归因为问数业务缺陷。

失败报告中的验收账号已禁用、活动Session为0；容器、专用volume和network均按精确Compose项目身份移除；热更新源码恢复Hash与备份相同，日常Compose未操作。完整报告和产物保留于detached UAT工作树`/home/jojo/Projects/chatbi-engine-audit-remediation-uat-20261017/reports/browser-real/`及`reports/browser-real-artifacts/`。

已在审计分支修正测试代码：统一`frontend/tests/container-real.spec.ts`首次和追问前就绪检查，删除重复的身份态helper；`frontend/tests/helpers.ts`改为轮询匿名`/ready`，仅HTTP成功且`status=ready`时继续；`frontend/tests/operations.spec.ts`覆盖匿名状态从unknown/not_ready到ready恢复及超时。该修改不改产品接口、权限或readiness Contract。TDD红测报告`20261017T105827Z-9b81160-test-web-f3240f47153a`（2项预期失败，断言公开`/ready`时旧helper仍请求身份态接口）；修正后定向浏览器测试`20261017T105948Z-9b81160-test-web-0ad2ce348418` packaged 2/2、dev 1/1通过；完整Web `20261017T110059Z-9b81160-test-web-68bc922c0423` packaged 82/82、dev 1/1通过。上述是9b工作树上的实现迭代验证，provenance stable但`git_dirty=true`，不是clean候选门禁。`./dev check docs` PASS（run `20261017T110430Z-9b81160-check-docs-aeec5a7dfc31`），`git diff --check`通过；本次只读Code Review PASS，BASE `9b81160498604a176d6693df98a1ad90345d9231`，范围限于三项frontend测试文件。

下一步：本地提交该测试修正及记录，基于新clean HEAD再次运行隔离容器业务验收并保留新报告。Ticket 12仍为in-progress；正式AI评测仍绑定`97268ca`且单轮、多轮验证器未通过，61项条件性skip仍使全量软件结果为incomplete。不得绕过readiness、改模型参数或用此次helper修正宣称业务验收通过。

# Ticket 04：目标环境完整验收与交付证据

Status: done
Owner: 当前主Agent
Blocked by: 03
Result: clean runtime candidate `2b4a8c811713adb663d22cdac4108e13e731165f`，run `20261007T200251Z-e8ea09aa` 的正式完整隔离入口通过。Windows Edge 154.0.4258.53 真实业务、历史/成果、停止恢复、12份实际下载与独立解析、五项失败场景、Secret/挂载/资源隔离及清理通过；IDM临时PDF接管设置按用户授权调整并恢复。稳定API已upgrade到相同候选，数据指纹与PG/Qdrant资源不变，sandbox实测通过。正式Contract/Design/Acceptance/Runbook/产品范围/路线图已同步；CPU依赖的Evaluation复用适用性已说明，未重跑三套正式AI Evaluation。电脑或Docker重启维护步骤已记录，具体窗口待用户择时，未执行重启。PR60已合并（9a70601），运行候选身份未变；候选、报告及验证边界见 `docs/acceptance/local-deployment-v1.md`。
Comments: 本地实施授权于2026-10-07取得；发布授权于2026-10-08取得，PR60已合并并完成CI、复盘与分支清理。下文的验收失败与Review结论为当时的历史事实。


Change Profile: 本轮验收+持续维护文档入口 / 中 / 证据身份与清理影响风险 / 软件回归+真实浏览器+运行验收 / 本地Commit。
Owner: 当前主Agent；后续验收脚本与Runbook维护者。
Blocked by: Ticket 03。
What to build: 可重复隔离验收入口、完整业务与失败场景证据、目标机重启验收计划、正式Acceptance与文档状态收尾。前述Tickets的测试不推迟到本项。
Owned files: scripts/verify_local_deployment*、受影响tests、docs/specs/local-deployment-v1.md、docs/designs/local-deployment-v1.md、docs/acceptance/local-deployment-v1.md、docs/runbook.md、docs/product-scope.md、docs/roadmap.md及本目标scratch记录。
Acceptance Criteria:
- 同一最终clean候选完成空环境安装与Windows浏览器登录/问数/追问/经营分析/历史/保存成果/XLSX PNG PDF下载并独立检查内容。
- 停止/重启/手动恢复后账号、历史和成果可用，Seed不重播；电脑或Docker重启验证安排维护窗口，不擅自重启共享服务。
- 真实升级回滚与不兼容拒绝、配置/端口/索引/启动失败、资源隔离/安全日志均有证据；清理仅限身份已确认验收资源。
- 记录候选commit、dirty状态、镜像与模型/Seed/RAG身份，历史R1–R5报告保持原身份。根据最终Diff说明AI Evaluation复用适用性或重跑受影响正式套件。
Evidence: 最终受影响软件回归、容器集成、真实模型Windows浏览器/Business Acceptance、目标机运行证据及资源清理核对；报告绑定最终候选，无结果预填。
Migration / Rollback: 只在专用验收资源构造失败状态，不写开发数据；稳定环境重启需维护窗口。已有长期记录保留，验收结束只清理临时项目。
Done When: 正式Contract/Design/Runbook/Acceptance/产品范围/路线图全部一致，最终Code Review与Diff检查完成，未运行项与限制明确；产品/R6实时状态同步，无远端发布。发布另需明确授权。

Implementation review: PASS；基线 `995440b`，Scope为当前Ticket owned files与现有容器浏览器支持。检查Correctness / Comprehension / Consistency / Testability / Architecture / Security：运行资产API无源码或迁移身份；清理验证run ID / project / 卷 / 网络身份；Docker inspect敏感值仅内存核验；账号禁用并撤销Session、报告扫描已知凭据。定向软件66项、报告路径3项、TypeScript / Ruff / Markdown link / Diff检查通过。完整真实验收待clean candidate执行，尚未宣称通过。

## 历史：Ticket 04 验收与Review过程

2026-10-08 首次完整运行：clean候选 `e4f83aca437d1824db0f8c2045b33cae8231ed0e`，run `20261007T190056Z-9b5b8021`。空卷Seed / migration / 管理员 / RAG / 兼容前置与五项失败检查通过；Windows Edge真实问数和XLSX下载成功，随后PNG返回503，原浏览器用例等待不存在的下载导致180秒超时。诊断保存在ignored `.local/acceptance/<run>/`，未改称通过。专用账号已禁用、活跃Session为0；本次容器/卷/网络及Windows workspace已清理，临时配置凭据已删除。

根因与修复：稳定Compose遗漏R5 renderer所需seccomp配置，启用sandbox的Chromium namespace启动失败；相同固定镜像加入既有profile后sandbox启动实测通过。新增Compose security_opt回归先Red（缺少security_opt），修复后66项软件检查、类型/Ruff/Bash/链接/Diff检查通过。增加实际sandbox前置检查与浏览器导出非200快速失败；Review基线`e4f83ac`，PASS。下一步新clean候选完整复验。

2026-10-08 第二次正式验收：clean `9f01de2`，run `20261007T191015Z-8582c456`。sandbox、问数 / 追问 / 多指标 / XLSX / PNG及经营分析参考值通过；PDF浏览器204空响应使完整运行失败，后续重启及成果检查未执行。专用资源与凭据已清理，失败报告保留。

诊断run `20261007T191852Z-9ffb13b7` 的测试副本已修改，仅用于诊断：API导出200，Edge收到204；有效PDF最小对照Linux/Windows PowerShell200且78,427 bytes，Edge204且0 bytes。IDMan运行、advanced integration与PDF监控已核实；疑似下载接管，等待用户授权临时调整并恢复，未修改本机配置。下一步先完成暂停接管前后最小对照，再运行同一clean候选正式完整验收。正式结果仍为未完成。

2026-10-08 IDM对照与后续测试修复：用户确认临时调整并恢复后，通过原生IDM配置界面仅取消PDF文件类型接管；同一有效PDF由Edge204/0bytes恢复200/78,427bytes，根因确认。正式clean `1bebea5334596ac876d64b00fbb6b26d18f1b0f4`，run `20261007T194018Z-5cecc97d`，当前与历史分析PDF均下载成功；随后测试在打开保存成果请求尚未完成时立即读取旧URL，产生“成果URL缺少身份”的Red。现场记录显示读取期间UI仍busy，应用只有完成读取后才切换hash。修复测试改为等待saved URL与已保存成果标题，再读取ID / 导出；保持全部原业务断言，未修改应用行为。该run账号/资源已清理，IDM原配置已恢复；完整验收仍未完成，待新clean候选重跑。

等待修复Review：PASS，BASE `1bebea5`，仅container-real测试和本Ticket记录。用saved URL与成果专属标题观察完成状态，保留导出来源、内容与业务断言；不增加sleep或重试、不变更Domain/应用。TypeScript typecheck与Diff检查通过；历史/成果确定性回归在Windows Edge（临时frontend+隔离stub）3 passed。宿主Linux尝试因缺少Chrome及libnspr4无法启动，未计为通过；随后使用已确认目标浏览器完成回归。实际完整链Green仍待新clean候选复验。

2026-10-08 完整浏览器与恢复通过、解析环境修复：clean `7c5a5fa` run `20261007T194953Z-b342096a` 的Windows业务/成果/三格式导出、停止恢复、续聊/重查、执行unconfirmed恢复均通过；恢复前后2用户/5历史/8turn/2成果/1,166业务行与Seed v3一致。随后生产镜像admin工具执行独立文件解析时缺少dev group的openpyxl，故完整runner仍失败，保留原身份。相同12份文件随后由宿主锁定dev环境解析全部通过（补充证据，未冒称原runner通过）。修复将解析移到宿主解释器，并在任何Docker安装前检查openpyxl/pypdf；不向生产镜像安装测试依赖。资源及IDM原设置已恢复，待新clean候选完整复验。

解析环境修复Review：PASS，BASE `7c5a5fa`，Scope仅验收入口与本Ticket记录。使用入口的宿主sys.executable执行既有独立解析器，报告路径以argv传入；启动Docker资源前检查dev解析依赖，不改变API依赖或业务。Red为生产工具缺少dev依赖；同一12份真实下载文件在宿主解析Green。定向66项软件回归、Ruff与Diff检查通过；新候选完整复验待执行。

最终收尾Review：PASS，BASE `2b4a8c8`，Scope为本Ticket适用正式文档与长期记录。核对实际成功runner、候选 / image ID、浏览器 / 文件 / 失败 / 持久化 / 清理及IDM恢复，保留所有旧失败身份。稳定运行候选仍2b4a8c8；随后本地证据提交只有文档，不冒称新的运行验收身份。电脑重启与正式AI Evaluation未运行明确保留；远端发布授权未取得，R6工作项阶段为待发布授权。

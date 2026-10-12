# 当前文档整理实施草案

Status: 仅草案，尚未写入正式 issues/ Ticket；等待用户确认四项拆分与整体本地实施。
Canonical Source: [已确认 Spec](spec.md)；实施细化见 [设计](design.md)，审查见 [Design Review](design-review.md)。
Owner: 当前主 Agent；各项维护责任由后续实际修改者承接，无跨团队或运行资源交接。
交付: 一个目标、一个 branch / worktree；各切片验证、Review 后本地提交，最终一个候选。Push / PR 不在当前授权内。

## 01：当前功能行为形成唯一正式入口

Change Profile: 持续维护文档 / 中等跨文件迁移 / 行为依据丢失风险 / 链接检查与内容覆盖 Review / 本地候选。
Owner: 当前主 Agent。
Blocked by: None。

### What to build

- 核对现有正式 Spec 与已确认的检索、多轮、经营分析来源；按能力整理当前行为、边界与验收标准。
- 用当前统一检索 Contract 替换历史 online-retrieval 正文；多指标现行规则融入同一入口，旧规格和独有决定归对应历史记录。
- 将已交付经营分析未正式固化的规则集中落入当前 Spec；将短期多轮规则整合至当前 Query API 说明，明确与持久历史的适用边界。
- 清理全部现有正式 Spec 的旧发布状态、开发任务和阶段日志；不改变输入输出、失败、授权、兼容及 SQL Guard 规则。
- 将功能阶段多轮 ADR 的独有理由 / 取舍归入对应工作记录；按迁移顺序修复所有引用。
- 建立本工作项迁移台账，逐项记录当前规则去向、历史覆盖与保存位置。

### Acceptance criteria

1. 每个当前功能规则有正式位置；查询、检索、多轮和经营分析不再将历史规划视为当前唯一 Contract。
2. 实体 / 单指标 / 多指标使用已确认的一条检索链；指标数量、直接 FK→PK、LEFT JOIN 等边界不被历史描述覆盖。
3. 短期 API 会话与长期历史续聊的状态、失败与逐轮授权边界保持正确，不把历史 ADR 限制泛化到新历史能力。
4. 所有重写 / 移除文档具备台账覆盖证据；独有理由和历史候选结论可追溯。
5. 所有 Markdown 消费者的受影响链接修复，全库链接检查通过；当前重要规则逐项 Review 通过。

owned files: docs/specs/ 全部现有文件、按覆盖需要新增经营分析当前 Spec；docs/adr/0001-multi-turn-query-v1-boundaries.md；对应 .scratch 来源的历史用途 / 归档与受影响引用；migration-ledger.md。其他当前文档只做必要引用修复，主要内容由后续切片负责。

验证证据: `uv run --python 3.11 --locked python -m scripts.check_markdown_links`；`git diff --check`；以规划基线和后续已确认扩展为依据的章节 / 规则覆盖 Review，记录候选或未提交范围。

Migration / Rollback: 先保全独有内容再提供现行说明、修复消费者、移除旧入口；覆盖不明不删除。恢复文档须同时恢复对应链接，不 reset 用户修改或删掉唯一历史副本。

Done When: 当前规则统一、台账完整、引用与语义 Review 通过、本地候选证据记录；不以历史测试结果替代本次文档核对。

## 02：README、架构与实现说明形成连贯阅读路径

Change Profile: 持续维护导航与机制文档 / 中等批量迁移 / 导航与重要机制遗漏风险 / 阅读走查与引用 / 本地候选。
Owner: 当前主 Agent。
Blocked by: 01。

### What to build

- README 承接项目简介、开始入口、简短代码地图和当前文档导航，合并 project-guide 有效定位能力。
- 当前架构集中描述模块、依赖、链路、数据归属和关键约束；产品范围按能力描述支持与限制。
- 按处置清单逐份核对 15 份 Design；仅保留独有重要机制，重复说明引用正式 Spec，开发方案和历史结果归工作记录。
- 将历史检索设计、多指标独立设计和无独立价值的细碎说明归档；保留事务、worker / SSE、备份恢复、SQL Guard、Trace 与资产发布的必要当前机制。
- 原 guide 独立入口移除前提供完整替代导航，修复全库当前及历史消费者，更新台账。

### Acceptance criteria

1. README 直接定位当前产品、架构、主要模块、核心能力、运行和验证入口，没有独立 project-guide 阅读入口。
2. 架构和产品范围不重复功能细则和开发日志；系统定位、依赖方向、业务语义链路与支持边界完整。
3. 每个 Design 的保留 / 合并 / 归档都有内容依据；没有重要机制仅留在未说明用途的历史文件。
4. 所有当前内容层级连贯、章节具名引用；正文补充已融入相应主题，不在尾部堆阶段追加。
5. README → 能力 / 模块 → 当前规则 / 机制的阅读走查通过，全库链接检查通过。

owned files: README.md；docs/project-guide.md、architecture.md、product-scope.md；docs/designs/ 现有 15 份；必要受影响引用与所属 .scratch 归档；迁移台账。Spec 仅在核对中发现需要落位已有规则时做一致性补充并复核前项证据。

验证证据: 全库 Markdown 链接检查；`git diff --check`；导航与核心链路只读走查；当前重要机制覆盖 Review。代码入口以存在的路径和符号核对，不执行业务命令。

Migration / Rollback: 先提供新的当前入口与机制说明，再修复链接并移除旧稿；恢复时同时恢复当前 / 历史引用。无代码、模型、数据或运行资源迁移。

Done When: 导航唯一且可达、产品 / 架构职责清晰、15 份设计逐项核对完成、台账和验证更新。

## 03：操作手册清楚可用，历史验收回到工作记录

Change Profile: 持续维护运行文档与历史证据 / 中等批量迁移 / 操作前提或证据身份遗漏风险 / 命令核对与历史保全 Review / 本地候选。
Owner: 当前主 Agent。
Blocked by: 02。

### What to build

- 按开发初始化、日常开发、宿主调试、Stable、测试 / Evaluation、排障和恢复组织 Runbook，保留环境前提与数据操作影响。
- 替换章节符号和裸编号引用为具名链接，修复旧数字锚点的全部消费者。
- 将 16 份 Acceptance 逐份核对已有工作记录后归档；保留独有环境、候选、失败 / 复验、结论与限制，不移动原始报告。
- 现行验收标准指向 Spec，验证方法指向 Runbook，必要历史证据索引简短明确其适用候选。
- Roadmap 精简为当前阶段与已确认未来方向，历史推进归所属记录；不重新排优先级或生成新承诺。

### Acceptance criteria

1. 读者可从 Runbook 独立选择容器开发、宿主调试或 Stable 路径；不会把一个环境的命令用于另一环境。
2. 测试命令的 uv / Python 版本、锁定依赖、Origin 临时覆盖原因明确；纯软件、PG 集成与真实 LLM 证据边界完整。
3. 备份 / 恢复、资源隔离、迁移 / 重置、Secret、当前配置限制等必要前提仍在对应步骤附近。
4. 16 份历史验收均有完整覆盖或归档证明，日期、候选、报告位置、结论不被当前身份替换；现行文档不再堆历次结果。
5. Roadmap 只保留当前与未来方向；所有受影响引用修复，台账和全库链接检查通过。

owned files: docs/runbook.md、roadmap.md、acceptance/ 全部 16 份；README / 其他文档中相关引用与所属 .scratch 归档；迁移台账。

验证证据: 全库 Markdown 链接检查；`git diff --check`；按实际脚本 / CLI 和已确认运行 Contract 只读核对命令、配置名与环境路径；历史报告身份核对；阅读走查。不执行重置、部署、恢复或真实 LLM 调用来验证排版。

Migration / Rollback: 先保全证据再迁移当前说明；锚点含义逐项匹配，不能统一替换成含义不符的入口。候选不变、原始报告不移动；恢复时同批恢复引用和历史文件。

Done When: 操作路径连贯、必要前提完整、历史验收覆盖与身份证明完整、当前 / 历史索引可达、Roadmap 核对有记录。

## 04：维护规则、门禁与 Review 形成可验证闭环

Change Profile: 持续维护工程工具与项目规则 / 中等脚本、测试、CI 和文档变更 / 漏报与误报、协作保护丢失风险 / fixture 回归和最终迁移 Review / 本地候选。
Owner: 当前主 Agent。
Blocked by: 03。

### What to build

- 在 AGENTS.md 保留短强制入口，详细文档维护规范集中在 docs/agents/documentation.md。
- 精简 domain / issue-tracker / git-pr-workflow 的重复说明；原 agent-harness 中当前要求逐项分入正确位置，独有过程归档，修复全部引用。
- 更新现有 PR 模板与 Done When / Agent Review，记录当前文档更新、历史去向或不适用理由；保持现行授权、状态恢复、Auto-merge 与收尾规则。
- 保留原链接入口和 --root；新增组合文档检查入口，使用共享最小解析检查链接、当前文档标题跳级和正文章节符号引用。
- 基于临时 Git fixture 建立有意义的回归，验证文件发现、作用范围、代码示例过滤、ATX / Setext、行号及退出码。
- 现有 Deterministic tests job 调用组合入口，不更改 job 名称和远端 required checks 设置；Runbook 同步可复现的本地命令。
- 完成整目标台账、规则覆盖、阅读走查、验证 / Review 与本机状态记录。

### Acceptance criteria

1. 从 AGENTS 能找到文档归属、更新与检查规则；唯一详细规范可达，现行关键协作与安全保护未丢失。
2. 本地和 CI 使用同一组合入口；原链接入口仍兼容，全库历史记录继续受链接保护。
3. 正式文档的跳级和章节符号引用失败，定位准确；代码块 / 行内代码 / 历史目录不误报；缺少 Git 或读取失败非零退出。
4. 回归包含新违规 fixture、正常 fixture、历史和示例边界；现有链接测试通过，新增解析没有破坏旧锚点 / 链接行为。
5. 现有 Review 可追溯文档更新 / 不适用理由；不通过关键词推断业务矛盾、不新增用户审批或第三方依赖。
6. 全部迁移条目有当前规则 / 独有历史内容的处置证据；最终当前文档脱离历史唯一 Contract，导航和运行阅读走查通过。
7. 最终验证绑定本目标候选 / 基线；不把 CI 配置已改称为远端 required gate 已核实，也不把历史 AI 结果称为当前候选新结果。

owned files: AGENTS.md；docs/agents/ 现有文件与新 documentation.md；.github/pull_request_template.md；scripts/check_markdown_links.py、新 check_documentation.py 与按需要共享的 markdown_content.py；tests/scripts/test_check_markdown_links.py 与新 test_check_documentation.py；.github/workflows/ci.yml；Runbook 检查命令；受影响引用与本工作项证据。CONTEXT / CONTEXT-MAP 仅检查现行结构，领域定义不变。

验证证据:

- `CHATBI_WEB_ORIGIN=https://example.invalid uv run --python 3.11 --locked python -m pytest -q tests/scripts/test_check_markdown_links.py tests/scripts/test_check_documentation.py`
- `uv run --python 3.11 --locked python -m scripts.check_documentation`
- `uv run --python 3.11 --locked python -m scripts.check_module_boundaries`
- `bash scripts/check_python_quality.sh`，并以该脚本固定的 Ruff 版本补充检查受影响 scripts 文件（其现有全量范围是 src / evaluation / tests）。
- `uv run --python 3.11 --locked python -m scripts.check_harness_state` 与 `git diff --check`；说明属于本目标的 REVIEW。
- 工作流调用核对、当前文档语义 Review、全目标阅读走查与历史保全台账核对；无业务代码变更时不启动真实服务或 LLM。

Migration / Rollback: 先完成正式文档清理，再激活组合门禁。解析回归失败时固定坏例子后修复，不通过排除全部正式文档绕过；恢复时同时恢复工具、CI 调用和规范入口。用户改动保留，旧历史唯一副本不删除。

Done When: 规则可发现、确定性问题可拦截、语义 Review 可追溯、全目标迁移 / 阅读 / 验证通过、本地候选完成。发布授权仍是独立边界。

## 依赖与确认范围

直接依赖为 01 → 02 → 03 → 04，按同一 branch 顺序执行。各项交付自己的内容与引用修复，不留断链给最后一项兜底；最后一项承担完整工具和持续维护闭环。

本草案等待用户确认拆分及四项整体本地实施；确认后写入正式 Ticket 并连续完成，不逐项请求继续。该确认不包含 Push、PR、远端配置或运行资源操作。

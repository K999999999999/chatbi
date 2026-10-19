# Harness V1 Ticket 草案

本文件保留确认前的拆分草案。用户于 2026-10-19 确认 8 项粒度 / 依赖并授权整体本地实施；正式执行记录以 [issues/](issues/) 为准，草案中的状态描述仅反映起草时点。

## 共同约束

- Change Profile：长期维护的工程工具 / 项目适配；每项为一个可观察纵向行为，包含实现、确定性验证、文档和 Code Review。高风险点为状态 / 依据 / 授权 / 写入边界，无业务应用功能或真实数据库迁移。
- Owner：当前主 Agent；用户决定关键边界和额外授权。共享代码按同一仓库候选顺序集成，不启动独立 Agent，不产生逐Ticket PR。
- Canonical Source：需求以 Spec 为准，设计以 design.md 为准；长期草案不代替Git、远端或原始验证。ChatBI保存主记录，Plugin关联记录引用主记录且不扩大授权。
- Plugin通用实现候选位置为 `plugins/engineering-workflow/tools/harness.py`、`tools/harness_lib/`，测试为该Plugin的 `tests/`。ChatBI adapter为 `.harness/project.json` 及现有dev入口；路径是本拆分的owned-files规划，不要求为形式创建空文件。
- 不新增第三方依赖、服务、宿主运行时或付费模型；通用标准库Python测试在现有Python 3.11环境运行。ChatBI验证仍在容器内，不安装宿主依赖。
- 每项验证绑定仓库 / 基线 / 候选 / 覆盖 / 结果；测试计划不是运行证据。旧状态、旧检查行为和用户归档必须保留。
- 起草时 Result：各项尚未实施；实施结果、验证及授权边界以对应正式 Ticket 和 [验收记录](acceptance.md) 为准。无 Push / PR、安装同步、远端设置或实验授权。

## 01 — 查看工作状态并拒绝非法阶段转换

Change Profile: Plugin；长期工具，小到中型切片；风险为状态损坏 / 虚假推进；临时Git与文件故障回归；本地候选。
Owner: 当前主 Agent
Blocked by: None (can start immediately)

### What to build

提供可运行的标准库CLI，读取数据adapter及单一Markdown状态记录，展示生命周期 / 阶段 / 运行情况 / 下一步，执行经校验的显式阶段转换。覆盖版本化扩展、旧字段权威、预期文件摘要、互斥与原子保存；旧记录只读识别，显式迁移保留原件，不创造历史证据。依据先采用明确的类型化输入Contract，后续Ticket接入实际事实采集。

### Acceptance criteria

- 合法转换成功且得到可重读状态；跳过必要确认、缺必需依据、未知阶段 / 格式均非零拒绝且原文件不变。
- 旧顶层字段与扩展不重复定义同一事实；linked worktree正确使用Git公共目录，不假定.git为目录。
- 两个写入者、过期预期摘要、写入失败及遗留锁不会静默覆盖；恢复不删除归属未核实的锁 / 原件。
- 只读查询不写记录、不执行adapter任意代码、不读取.env、不访问网络；缺adapter显示未接入。

owned files: Plugin `tools/harness.py`、`tools/harness_lib/`状态/存储/CLI部分、`tests/test_harness_state.py`、Plugin README与必要工具文档。

Verification evidence: 标准库unittest；临时Git / linked worktree；转换矩阵正反例；故障写入、并发冲突、旧记录及Secret canary不输出。

Migration / Rollback: 按目标显式迁移并保留原状态；无历史批量更新，回退CLI不删除新扩展或证据。

Done When: 行为测试 / 文档 / Diff Review通过；单一当前权威与失败不改原状态可复现；候选身份明确。

## 02 — 查看本轮 / 累计 Diff 并核实候选依据

Change Profile: Plugin；长期事实采集，中型；风险为漏报改动 / 旧证据放行 / 内容泄漏；Git与报告合成回归；本地候选。
Owner: 当前主 Agent
Blocked by: 01

### What to build

采集任务起点、切片和当前commit/index/worktree身份；输出本轮及累计安全Diff清单。记录机器核实、人工声明、未验证的区别，核对报告 / Git / 远端安全快照身份，分离范围授权与具体候选批准，接入转换依据判断和敏感路径分类。

### Acceptance criteria

- 已提交、staged、unstaged和未跟踪变更均按边界列明，不能只统计commit；默认不输出敏感配置内容。
- 新增依赖、公共接口 / 权限 / 数据 / 验收敏感路径提示需Review；未知语义不能自动称安全，分类规则改动也被标明。
- 源码、base、报告 / 输入身份变化后，受影响依据失效或明确待复核；复用必须有来源、覆盖和理由，原报告身份不改。
- 人工声明不冒充机器核实；同范围CI修复保留范围授权但刷新候选依据，关键范围变化要求新决定。
- 不可读取Git / 报告或缺少实时核对不能产生完整通过。

owned files: Plugin工具事实采集/依据模块、CLI、`tests/test_harness_evidence.py`、工具使用文档。

Verification evidence: 临时Git提交与四类修改、合成报告 / 远端快照、base移动、相容 / 不相容证据、敏感路径与canary输出检查。

Migration / Rollback: 新证据增量登记，不将旧结果重标新候选；回退采集功能保留原报告和引用。

Done When: 正反例证明Diff边界和依据失效；风险限制说明与用户可读摘要完整，Review通过。

## 03 — 跨会话诊断预算与停止升级

Change Profile: Plugin；长期状态行为，中型；风险为无限诊断或误停止；可控时间 / 合成事件验证；本地候选。
Owner: 当前主 Agent
Blocked by: 02

### What to build

按问题ID记录原因假设、动作、结果、有效证据、无进展轮数及有界等待；提供预算查看、诊断推进和升级结果，触发后拒绝继续诊断转换，允许只读 / 证据保存 / 用户决定登记。

### Acceptance criteria

- 第3轮连续无进展或累计有效诊断时长1800秒任一触发；边界前不误触发。
- 重复证据、重复命令、问题改名、重开会话不会获得新预算；有实质证据的更新保留可核实来源。
- 正常等待 / 暂停有起止和理由，超时、时钟倒退或无法核实返回待核实，不能无限延长。
- 升级报告说明可靠候选、累计改动、失败、尝试、未知和下一步成本；不自动撤销改动或杀进程。

owned files: Plugin工具诊断/预算部分、CLI、`tests/test_harness_budget.py`、预算及交接文档。

Verification evidence: 可控时钟与边界值；跨进程重读、问题别名、坏时间区间、重复证据及重开记录回归；无真实30分钟等待。

Migration / Rollback: 缺失旧计时明确未知，不补造零预算；回退保留问题记录，不能用降级清零。

Done When: 所有预算与恢复边界测试通过，工具限制明确；阶段推进失败时状态一致。

## 04 — 动态文件收尾、恢复与 Harness 改进闭环

Change Profile: Plugin；长期生命周期闭环，中型；风险为假完成 / 证据丢失；合成项目文档和follow-up验证；本地候选。
Owner: 当前主 Agent
Blocked by: 02

### What to build

工具消费项目动态文件清单，登记适用 / 不适用、更新位置、核实版本和未决项；区分本地、远端和总体完成。恢复时核对主关联记录、候选及唯一证据。复用复盘/follow-up记录缺口分类、有效性证据和例外复查。

### Acceptance criteria

- 缺适用核对、未完成Ticket / 子工作项、未证实合并 / 复盘 / 清理时不能误标整体完成。
- 不适用必须有理由；工具校验结构与引用，语义Review独立声明，不声称能自动理解任意文档。
- 换worktree / 主记录不可用 / 记录损坏保留未知与原件，关联不继承授权；存在用户改动不清理。
- 缺口有归属、授权、验收、处置和实际效果证据；登记或多写一条规则不足以解决，旧机制退出有替代覆盖与历史去向。
- 本地目标未获发布授权可准确结束本地范围，包含交付的目标不因此被标done；唯一证据未处置前拒绝报告已安全清理。

owned files: Plugin工具收尾/恢复/维护部分、CLI、`tests/test_harness_closeout.py`、动态文件清单与复盘使用文档。

Verification evidence: 合成Spec/Ticket/文档/PR正文、缺引用/未完成/不适用/损坏状态、关联循环或缺失、效果未验证与退出覆盖回归。

Migration / Rollback: 不批量改旧done，不删除旧跟踪；恢复工具回退保留当前状态和原始证据。

Done When: 有效生命周期及拒绝假完成均可验证；语义与结构边界清楚，Review通过。

## 05 — 显式项目接入与 CI / 远端配置核验计划

Change Profile: Plugin；长期接入行为，中型；风险为覆盖用户配置 / 隐式远端写入；新旧项目fixture和远端安全快照验证；本地候选。
Owner: 当前主 Agent
Blocked by: 04

### What to build

提供只读发现、适配与差异计划、已确认文件的本地写入和接入核验。识别真实测试入口与CI覆盖，输出远端目标、检查来源、严格base等变化与回退计划。远端授权、应用、读回由阶段Skill协同现有工具，核心只读查询不执行远端修改。

### Acceptance criteria

- Plugin安装 / 只读检查不修改项目；新项目显式接入，已有项目复用规则并展示逐文件差异。
- 未确认文件、用户已有变动、路径越界、未知栈 / 测试命令、无权限或无法核验远端，均不覆盖、不生成空绿色job或报告完整接入。
- 本地应用前重新核对原文件身份；并发变化拒绝覆盖，重复应用安全且不会重复追加规则。
- GitHub快照区分实际required checks与其他成功job、来源、base策略及未验证项；真实应用需独立授权和读回。
- 其他托管平台 / 技术栈不虚构真实适配；输出待确认项目，而非硬编码ChatBI的8项检查。

owned files: Plugin工具接入部分、CLI、`tests/test_harness_onboarding.py`、接入 / CI配置文档；不改实际远端规则。

Verification evidence: 新旧项目fixture、冲突与重复应用、越界路径、缺命令、过期 / 错仓库快照；模拟应用前变化；全程无业务服务 / 真实远端写入。

Migration / Rollback: 写入前保留已核实原件与清单；只回退本次明确文件，不移除用户新增内容；远端回退仅计划，未经授权不执行。

Done When: 能生成具体接入Diff并证明拒绝路径；未知平台 / 权限限制可见，Review通过。

## 06 — 将控制工具接入通用阶段 Skills 与可复现验证

Change Profile: Plugin；长期规则集成，中型；风险为规则重复 / 自修改误判；真实CLI与临时工程流程走查；本地候选。
Owner: 当前主 Agent
Blocked by: 03, 05

### What to build

把状态查看、转换、Diff、预算、收尾和初始化接入现有阶段Skills，保持单一规则来源。增加通用工具标准库测试入口与Plugin仓库CI，使临时Git合成流程验证无需开发机缓存或业务项目。明确源版本、安装版本与会话加载的发现 / 同步流程，准备后续发布说明。

### Acceptance criteria

- 正常切片汇报后继续；关键变化/预算升级等待用户；Spec/Ticket确认不冒充实施或发布授权。
- 阶段Skills调用已定义CLI并读取项目adapter，不复制ChatBI命令 / 机器路径；工具不可达明确unavailable，不假装已执行。
- setup说明支持已确认的本地配置与另行授权远端协同，保持显式入口、安装不自动初始化。
- CI从Plugin仓库真实源码执行标准库回归；不连接LLM / 业务库，不依赖缓存或未跟踪文件；测试修改本身仍需Review。
- 文档 / 元数据版本相容；不手改安装缓存、不自动安装更新、不宣称源提交等于已加载。

owned files: Plugin现有各阶段 `skills/*/SKILL.md`、共享references、README、`.codex-plugin/plugin.json`、工具测试入口、Plugin仓库 `.github/workflows/harness-tests.yml`（若不存在则按真实仓库规则新增）。

Verification evidence: 全部标准库回归、临时项目生命周期CLI走查、Skill引用/命令校验、工具不可达、无网络测试；CI配置静态检查与后续实际run分开。

Migration / Rollback: 保留原阶段语义，替换重复规则时列明覆盖与引用；Plugin同步仅准备受支持步骤，未授权不执行；回退规则不删状态。

Done When: 通用工具与Skills形成一个候选，Review/文档通过；本地结果与托管CI未执行范围明确。

## 07 — ChatBI 容器适配与旧入口兼容

Change Profile: ChatBI；长期项目适配，中型；风险为运行路线变化 / 缺Plugin假通过；容器挂载和fixture回归；本地候选。
Owner: 当前主 Agent
Blocked by: 06

### What to build

在ChatBI登记项目阶段、路径 / 验证 / 风险 / 动态文件清单，扩展现有dev协作入口使用Plugin工具。只读与明确状态写入分开挂载，保留旧check命令的行为与覆盖；CI使用合成Plugin fixture验证adapter，不复制通用控制核心。

### Acceptance criteria

- 不要求宿主Python/uv/Node，不读.env、不挂Docker socket，不改业务应用或服务；容器挂载源码/工具只读，写权限限所需状态位置。
- 普通clone与linked worktree均可定位公共目录；缺工具/镜像/路径不自动联网安装、不回退后声称新版通过。
- 旧 `./dev harness check` 与 `python -m scripts.check_harness_state` 的既有检查行为保留；新能力显式接入并报告范围。
- 动态文件清单链接现有权威文档，当前未授权旧工作项/用户文件保留；当前目标不伪装成已由新工具管理的历史。
- CI / 本地使用仓库内可复现fixture验证调用和失败行为；fixture不冒充已安装Plugin真实运行。

owned files: ChatBI `.harness/project.json`、`dev`、`scripts/container_tasks.sh`、必要薄adapter、`tests/scripts/test_harness_adapter.py`、旧Harness测试（仅兼容扩展）、必要fixture及CI入口、AGENTS/文档规则/Runbook/模板。

Verification evidence: 容器定向adapter测试、只读/写挂载检查、无Plugin/坏路径、Git公共目录、旧状态检查回归、文档链接/结构与模块边界；无LLM。

Migration / Rollback: 不批量迁移54份历史记录；新profile仅对显式目标启用。入口回退保留旧工具及新数据，不清理唯一证据。

Done When: 容器内正常/失败路径通过，旧入口兼容，项目Diff和文档Review通过；远端与安装状态如实报告。

## 08 — 两仓候选验收、恢复走查与交付计划

Change Profile: 两仓总体验收；一次收尾并保留长期证据；风险为跨仓假完成 / 清理唯一证据；合成流程与安全只读核验；本地交付。
Owner: 当前主 Agent
Blocked by: 07

### What to build

用ChatBI adapter和已实现Plugin候选完成合成任务：查看、拒绝转换、Diff、预算升级、恢复、动态文档、follow-up与收尾；建立逐项Spec覆盖和两仓证据引用。准备各仓发布、安装同步、严格base远端配置以及无Secret隔离阻断实验的具体计划和回退说明。

### Acceptance criteria

- Spec适用行为都有对应实际软件证据；实际运行与Mock、旧报告、未执行CI / 安装 / 远端实验明确分开。
- 两仓候选/基线/范围、相关长期记录、主关联实时记录、未提交用户文件归属可核实；已有long-task-progress-clarity只在适用目标和实际效果核实后处置，不自动继承授权或提前关闭。
- 源变更与安装/会话生效分别说明；未授权发布或更新时保持本地完成，不写整个远端目标完成。
- 远端计划明确目标、当前配置、strict变化、检查来源、授权需求、步骤、失败处理和回退；隔离实验不向实际master注入失败。
- 当前过期文档事实按真实Git/PR修正，历史验收不重标；无相关内容变更的业务Spec明确不适用。

owned files: ChatBI本目标验收与过程文档、适用Roadmap/Runbook/Agent文档；Plugin工具文档/验证记录及本目标关联记录。仅为验收发现且在已确认范围内的修复返回所属Ticket，不夹带无关重构。

Verification evidence: 两仓实际定向/完整工具回归、ChatBI容器合成走查、文档/链接/边界检查、Diff Review；基于可得权限的只读远端核验。真正远端阻断实验另等明确授权。

Migration / Rollback: 仅清理已确认本目标临时测试资源；保留候选/报告身份与唯一证据；不动Plugin源用户7z归档、不直接写master；无远端写入就不执行远端回退。

Done When: 本地验收覆盖、证据、两仓Review与项目规定本地Commit完成；待发布/安装/远端实验明确列出，不因等待额外授权否定已完成的本地范围，也不冒充整体交付。

## 依赖与交付

直接依赖：01 → 02；02 → 03、04；04 → 05；03、05 → 06；06 → 07；07 → 08。按编号在各仓同一目标候选上推进；依赖不等于先创建远端PR。两仓各一个活动实现候选，Plugin源的既有用户归档保持原位。

用户确认拆分和本地实施授权后，依赖连续实施，不逐Ticket等待“继续”。如只确认粒度未授权实施，先一次确认范围。发布、安装、远端设置及实验授权不由此推定。

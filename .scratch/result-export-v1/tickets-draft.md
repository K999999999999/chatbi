# R5 实施 Ticket 草案

Status: 用户已确认四项拆分与整体连续本地实施（2026-10-06）；01 XLSX 候选 `111980d`、02 PNG 候选 `88f122c` 已完成；03 PDF 实施中，04 按依赖待开始。
Canonical Source: 已整体确认 [Spec](spec.md)，实施机制见 [Design](design.md)，[Design Review](design-review.md) PASS。
Owner: 当前主 Agent；不委派独立 Agent。全部本地切片按 01 → 02 → 03 → 04 执行。
Change Profile: 持续维护、中等规模、跨模块；身份 / 精度 / 外部渲染与资源清理风险较高；证据为独立文件解析、Application / PG / worker / 浏览器 / 真实 Compose；一个目标一个 branch / worktree，默认本地候选，远端发布另行授权。

## 01：成功快照 XLSX 导出闭环

Blocked by: None (can start immediately)
Owner: 当前主 Agent
Change Profile: 首个完整用例，中等规模，风险为 owner / 精度 / 权限裁决 / 并发与子进程生命周期。

### What to build

- 只读 ExportSource DTO / owner 限定来源投影，兼容历史与独立成果；取得历史 completed_at，旧成果缺完成时间如实说明。
- Export Application、FileGenerator Port、共享独立进程 runtime / 限额及清理；生成与交付前身份、当前权限 / 来源可用性和 hash 检查。
- 严格 POST 导出接口，先支持 XLSX，其他尚未实现格式受控拒绝；Cookie / CSRF、MIME / no-store / 安全文件名及错误映射。
- XlsxWriter 完整数据 / 说明、精度规则与特殊单元格原类型 / 值记录、危险文本和格式长度边界。
- 当前查询、查询历史、查询成果的网页 XLSX 下载入口和进度 / 错误；失败不修改既有状态或自动重试。

### Owned files

`src/query_api/export*`（新用例 / Contract / HTTP / runtime / XLSX Adapter）、`src/chatbi_control/history.py`（只读投影）、`src/query_api/app.py` / `src/bootstrap/`（装配与 shutdown）、`frontend/src/api.ts` / `Chat.tsx` / `HistoryPanel.tsx` 及新增导出 UI 模块、`pyproject.toml` / `uv.lock`；相关 Python / PG / 前端测试。同步正式 `docs/specs/result-export-v1.md` / Design、Web / Query API 说明、Product Scope / Architecture / Runbook、阶段证据和路线图（仅声明 XLSX 已完成）。不修改业务 Query / Analysis / SQL Guard 链路。

### Acceptance criteria / Evidence

- 三种查询来源正常 / 空结果 / 截断均可实际下载并由独立解析器还原原值；NULL / 空字符串 / 零、前导零编号、超长整数、高精度、真实标记同名字串、公式 / URL 文本不混淆、不执行。
- 跨 owner 与不可用记录统一拒绝；认证 / CSRF / 权限失败正确；生成期间删除 / 撤权在交付裁决前拒绝，裁决后按已开始下载规则；历史删除不影响独立成果下载。
- owner 1 / global 2、60 秒 watchdog、20 MiB、长文本等边界可测试；worker 子进程 / 慢下载 / 断连 / shutdown 全路径清理后额度可再使用。
- Application spy 证明无 LLM、业务查询与状态更新；PG 投影与既有历史 API 回归通过。
- 本地浏览器真实 HTTP 下载和文件解析 PASS；依赖锁 / lint / build / Diff / Code Review PASS。此阶段不冒称 PNG / PDF 或最终 Compose 验收通过。

Migration / Rollback: 无 migration；撤回新增端点、装配、UI 与依赖即可，无历史写入。只读 DTO 不改变旧 HTTP 响应。
Done When: 上述闭环、受影响回归、正式 Contract / 阶段文档、Review 与本地提交完成，Evidence 绑定候选身份。

## 02：完整 PNG 与离线容器渲染

Blocked by: 01
Owner: 当前主 Agent
Change Profile: 独立图形用例，中等规模；风险为完整性 / 语义漂移 / 字体 / Chromium 装配与清理。

### What to build

- 提取 / 复用共享图形与归因 pure plan / option，保留原网页语义，新增完整 export profile。
- PNG 当前图形类型 / product 选择验证与 UI 按图下载，覆盖 query 图、analysis 产品 / 因素图及已有可用 task 图。
- 离线 bundle、ready / coverage manifest、Playwright worker、本地字体与网络 / 数据隔离；复用 01 runtime，不能在 API 主进程渲染。
- 固定构建与版本 / hash；API 镜像离线资产、Chromium / 字体、开发只读源校验挂载，本地安装 / 重建与缺失诊断。

### Owned files

01 导出模块 / DTO 的 PNG 扩展；`frontend/src/Chart.tsx` / `chartPlan.ts` / `Analysis.tsx` / `echartsRuntime.ts` / `numberFormat.ts` 与专用 export 入口 / 构建配置；`frontend/package.json` / lock（如需）；`docker/python-dev.Dockerfile` / `docker-compose.dev.yml`、`pyproject.toml` / `uv.lock`，适用容器脚本；相关文件 / 图形 / 浏览器 / runtime 测试与 Contract / Design / Runbook / README / Acceptance / Roadmap。

### Acceptance criteria / Evidence

- 超过 15 个分类完整导出，legend / zoom / 页面折叠不隐藏数据；全部 series / 全长标签 / 标题 / 单位 / 时间与截断说明可核验。选中 factors 产品和 line / bar 正确，不合法选择拒绝。
- 无图 / 图形无法完整可读表达 / 40M 像素边界 / 字体缺失 / 未 ready / 图形 coverage 缺失均受控失败；已有 XLSX 保持可用。
- 构建产物 / font / browser 匹配当前锁与 source manifest，开发源变化未重建拒绝；API 无 Vite / CDN 时仍可生成。
- 危险 HTML / URL / 脚本文本不执行、不读取文件 / 网络，worker 不继承凭证；保持 sandbox 并实际核验容器支持，无法满足返回设计审查。
- 独立 PNG 解析、共享图形回归、浏览器实际下载、容器固定快照生成与进程清理 PASS；精度和文字内容通过图形计划 / coverage 与渲染结果交叉核对，不仅查看响应状态。

Migration / Rollback: 无数据迁移，退回 01 仅 XLSX 候选；依赖 / bundle / 镜像代码一起回退，网页既有图形保持回归。
Done When: PNG 三种适用来源和图形闭环、离线运行、阶段文档、Review、本地提交完成，不宣称 PDF / 最终真实模型闭环完成。

## 03：完整分析 PDF 下载

Blocked by: 02
Owner: 当前主 Agent
Change Profile: 独立报告用例，中等规模；风险为分页 / 图形与证据完整性。

### What to build

- 正式分析结果、历史、报告成果 PDF 入口；复用来源、权限、runtime 和离线 renderer。
- 专用可选取正文 HTML / PDF，完整正文、全部返回归因、产品因素明细、引用任务附录、受控失败 / 跳过与不完整 / 截断说明。
- A4、中文字体、重复表头、宽表分块、长文本分页和 coverage / overflow 校验；无需先保存成果，页面折叠 / product 选择不减少 PDF 内容。

### Owned files

导出 PDF Adapter 与专用 TypeScript 模板 / 样式；`frontend/src/Analysis.tsx` / `HistoryPanel.tsx` 及导出 UI；PDF 解析测试依赖 / lock、API / 文件 / 浏览器 / 渲染测试，Spec / Design / Web / Runbook / Acceptance / Roadmap 的 PDF 阶段更新。不改变报告模型结构或归因业务逻辑。

### Acceptance criteria / Evidence

- 带 / 不带归因、全部已返回产品 / 因素、引用任务与多页宽表完整导出；中文 / 标题 / 来源时间真实，旧成果没有原完成时间明确未知。
- 独立 PDF 解析可抽取正文 / 中文与附录完整内容，图形数量 / 分类与输入覆盖一致；人工检查分页与中文可读性并保留渲染证据，不只检查页数。
- 草稿 / 未确认 / 不支持格式拒绝；坏字形 / overflow / incomplete manifest / 超时超限不返回部分报告。
- SQL、内部日志、Prompt、私有 query_state、账号凭证不进入 PDF；原历史删除后报告成果仍可导出，撤权 / 删除交付竞态沿 01 验证。
- 当前 / 历史 / 成果浏览器 PDF 实际下载通过，01 / 02 受影响回归 PASS；阶段文档、Review / Diff 通过。

Migration / Rollback: 无迁移，退回 02 PNG / XLSX 候选，历史 / 结果不变。
Done When: PDF 完整用例和边界证据、文档、Review、本地提交完成；尚不能以固定输入证明最终真实链路验收。

## 04：真实闭环、最终候选与交付证据

Blocked by: 03
Owner: 当前主 Agent
Change Profile: 最终完整交付，中等规模；范围为真实环境验收、必要缺陷修复与文档收口，非新增功能 / 生产部署。

### What to build

- 扩展隔离 Compose 验收：真实登录、问数、追问 / 新结果、完成分析，分别从当前 / 重开历史 / 保存成果导出，再验证文件与已保存快照。
- 服务重启后历史 / 成果仍导出；撤权、删除、生成故障、断连、超时超限与 quota 回收，核验无孤儿进程 / 文件 / 临时凭证，日常开发资源不被清理。
- 实际候选 clean 身份、RAG / 模型 / 数据 / 依赖身份、文件 hash / 大小、实测生成时间、覆盖范围与结果记录；首次失败报告保留。
- 按 Spec 完成受影响回归 / build / security / 模块边界 / Review；记录 AI Evaluation 复用依据及基线差异，若模型 / 生成 / Retrieval / Guard 变化重跑适用检查。

### Owned files

`frontend/tests/container-real.spec.ts` / 适用真实浏览器与容器脚本、文件核验入口和相关回归；必要的已授权 R5 范围缺陷修复；`docs/acceptance/result-export-v1.md`、正式 Spec / Design、API / Web、Product Scope / Architecture / Runbook / README / Roadmap 和工作项长期结果。原始报告绑定候选放适用 ignored 目录，实时身份在 Git 公共目录，不改写历史成绩。

### Acceptance criteria / Evidence

- 01–03 所有成功、边界和失败标准都有可执行证据；clean 最终候选三种文件实际解析与浏览器 / 隔离真实闭环 PASS。
- 文件值 / 口径对照持久化快照，无导出引发的模型调用 / 业务重查，真实问数分析仅为验收创建来源；未修改正式业务 Evaluation 结果身份。
- 原历史删除后的独立成果、过期身份、跨 owner、截断 / 空 / 高精度、全部产品、宽表 / 长中文、服务重启等场景覆盖完整。
- 清理验证、运行依赖 / 锁 / manifest 可复现、适用回归与 Code Review PASS；未运行或未通过项不得以历史证据掩盖。
- 所有正式文档状态一致，Roadmap 标注本地验收完成且未发布，不宣称 R6 / R7 完成。

Migration / Rollback: 无数据迁移；整体回退新增文件能力，下载文件不撤回；无真实用户 rollout，不引入 Feature Flag / staged 发布门禁。Push / PR 明确授权后按目标仓库 Auto-merge 规则另行处理。
Done When: 本地 clean candidate、适用验收 / Regression、文档、Review 与 Commit 完整；输出提交 / 验证 / 剩余问题，不把本地完成等同于已发布。

## Scope / 升级与授权

共同非目标见 Spec Out of Scope。Owner 由当前 Agent 负责，Backup Owner 不适用；关键方案或边界无法满足时暂停对应切片并返回 Spec / Design Review，不能以临时绕过获得通过。各项同源且串行，shared owned files 没有并行 writer 冲突。

依赖与安装的确切兼容版本 / hash 由实施在已确认库与平台选择内锁定并验证，不更换库或取消隔离。每项测试与文档是自身 Done When；04 补真实整体验收，不代替前三项的验证。

用户于 2026-10-06 确认四项拆分、直接依赖及连续完成 01–04 的整体本地实施范围（编码、适用测试 / 真实验收、Review 与本地 Commit）。不授权 Push / PR / 部署。

# R1 实施 Ticket 草案

状态：用户于 2026-10-03 确认拆分并授权整个 R1 实施；本文保留原草案，正式进度见 issues/ 的五项 Ticket。

Canonical Source：[R1 Spec](r1-spec.md) 定义行为，[R1 Design](r1-design.md) 定义技术细化，[Design Review](r1-design-review.md) 已 PASS。实施时同步到正式 `docs/specs/` / `docs/designs/`；历史文件保留。

共同 Owner：当前主 Agent，后续维护者为本项目维护者。无并行 Agent 或独立团队。共同 Change Profile：长期维护的产品入口、单 Feature branch / 一个最终 candidate / 一个 PR；身份与状态风险较高，故按可验收的纵向切片推进。

共同非目标：手机、图表、长期历史、流式 / 取消 / 通用恢复、导出、公众注册、多租户 / 行列隔离、业务语义扩展及本次公网发布。

## 01. 浏览器登录与可运行网页入口

**Change Profile**：长期；中等跨模块切片；高身份风险；后端确定性 / 集成 + 桌面浏览器基础验证；本地逻辑 Commit。

**Blocked by**：None (can start immediately)。

### What to build

- 建立 `frontend/` React / TypeScript / Vite 与锁定 npm 依赖，网页提供登录、首次改密、退出与默认问数页面外壳。
- 新增 Design 的四个浏览器认证路由、业务 Cookie、精确 Origin / 自定义头 CSRF 门禁与 Cookie / Bearer 身份提取；旧 Bearer 路由保持兼容。
- 增加同源开发代理、显式网页 Origin / dist 配置和打包页面入口；保留 Streamlit。
- 统一身份清理、epoch / 请求编号、退出待确认 fragment、跨标签页通知；保护迟到响应和错账号发送。

### Acceptance criteria

- 新 clone 的 npm lock / 类型检查 / 构建可重现；登录 → 强制改密 → 重新登录 → 空白问数闭环可用，改密前业务访问拒绝。
- Cookie HttpOnly / SameSite / Secure / Path 属性正确；新浏览器 JSON 不含原始 Token；原 Bearer 登录响应及 SQLAdmin 兼容测试继续通过。
- 30 分钟 Idle、8 小时 Absolute、禁用 / 撤销 / 错误凭证均遵循原规则，无周期保活；错误 CSRF / Origin / 混合凭证 / 用户 ID 不匹配在业务前拒绝。
- 网页仅通过 HTTP，未知 API / 静态资源 404，缺失 dist / 非法配置按 Design 失败；API-only 不被新增前端要求破坏。
- 退出失败清空私有内容并保持待确认状态，刷新不自动进入；迟到响应 / 其他标签换号不能写回旧身份。

### Owned files 与证据

- `frontend/package.json` / lock / 配置 / 登录与状态基础组件 / CSS；`src/query_api/` 的浏览器 / 静态 Adapter 与装配 seam；`src/authorization/auth_service.py` 的身份 Adapter（必要部分）；`src/bootstrap/` 配置传递。
- `tests/query_api/`、`tests/authorization/`、前端基础检查；`.env.example`、README / Runbook 的新增开发入口、`docs/specs/web-dialogue-v1.md` / Query API 认证部分、`docs/designs/web-dialogue-v1.md`。
- CI 中增加 Node / npm lock / 类型 / 构建检查，沿用原 required check 名称；不修改远端 ruleset。
- 验证：现有认证 / 授权 / API 回归、浏览器认证 / CSRF / 配置 / 静态资源测试、npm ci / 类型 / 构建 / 依赖检查、真实 HTTP 基础登录与改密。

**Migration / Rollback**：Expand，新旧入口并存；无数据库迁移，回退新增 Adapter / 前端 / 对应依赖与配置即可，保留现有账号及审计。失败停止后续切片。

**Done When**：以上行为、兼容、验证和新增入口文档到位，Review 通过，本地 Commit；不声称 R1 查询已完成。

## 02. 问数、连续追问与查询失败恢复

**Change Profile**：长期；中等切片；状态 / 隐私风险；前端确定性 + API / 浏览器闭环；本地逻辑 Commit。

**Blocked by**：01。

### What to build

- 当前问数时间线、输入 / 发送 / 新对话、结果表格、SQL 展开、空结果 / null / 截断提示。
- 首轮和追问只提交现有问题 / 模式 / 会话编号；成功才更新会话，失败与澄清沿用原 Contract。
- 进行中操作限制、输入草稿与请求原问题分离、有限等待、响应形状校验与 query 结果未确认后的新对话提示。
- 刷新保持登录但问数展示 / 编号清空，页面说明阶段边界；无浏览器历史持久化。

### Acceptance criteria

- 登录后完整问题返回表格 / 经校验 SQL，追问使用服务端成功编号；前端不能直接提交语义状态 / SQL。
- 空输入不发送、空结果仍可继续追问；null / 0 / 空串分开，截断提示不误称完整数据。
- 受控失败 / 澄清不改变成功状态；会话不可用不自动把片段追问当首轮执行。
- 重复发送 / 模式切换 / 新对话在等待时禁用，草稿仍能编辑；网络失联 / 客户端超时 / 畸形响应显示结果未确认，不自动重发，不允许基于不确定状态继续追问。
- 退出 / 过期 / 账号变化后查询内容和迟到响应被清理；刷新进入空白问数。

### Owned files 与证据

- `frontend/` 查询 API 客户端、状态转换、问数 / 表格 / SQL 组件及对应检查；已存在的业务 API body / 结果语义不改变。
- `docs/specs/web-dialogue-v1.md` 查询章节、Runbook 查询示例；必要的 `tests/query_api/` 浏览器请求 seam。
- 验证：前端状态 / 请求形状 / 受控错误 / 超时测试，真实 HTTP 身份 + 假查询服务的桌面浏览器问数与追问；既有会话 / Query API 回归。

**Migration / Rollback**：Migrate 普通问数，Streamlit 保留；回退本切片不影响登录及后端状态 Contract，无数据迁移。

**Done When**：查询闭环与全部边界有可复现证据、文档同步、Review / 本地 Commit 完成；不加入图表或历史。

## 03. 经营分析与模式切换

**Change Profile**：长期；中等切片；任务重试 / 模式隔离风险；前端 / API / 桌面浏览器验证；本地逻辑 Commit。

**Blocked by**：02（在已有单请求状态机与聊天页面上接入模式切换）。

### What to build

- 同页问数 / 经营分析手动切换、独立输入草稿 / 展示记录；默认问数，切回保留原有效 query 编号。
- 自然语言分析输入、支持边界提示、报告 / 任务证据组件、原 UUID / 问题的手动重试。
- 分析 1200 秒有限等待及结果未确认提示；改变问题创建新 ID，重试不能静默新建 ID。

### Acceptance criteria

- 支持既有两个时期的人民币净销售额 / 毛利产品归因；不自动继承查询条件或增加区域 / 客户分析。
- analysis 请求不含 conversation_id；每个新问题独立 ID，重试同用户 / 原问题 / 原 ID，过期 / 不匹配显示受控拒绝。
- 报告及证据展示与返回内容一致，不补写原因、不重算指标，不执行模型输出 HTML。
- query → analysis → query 的记录和上下文不串用；等待时切换禁用；失败保留上一个 query 成功状态。
- 分析重试草稿编辑不改变原任务问题；新分析成功与旧任务重试结果按请求身份归属正确展示，迟到响应受 epoch 门禁保护。

### Owned files 与证据

- `frontend/` 模式 / 分析客户端、状态、报告 / 证据组件与对应检查；`tests/query_api/` 分析请求兼容 seam；正式 Web Spec / Design 的分析章节。
- 后端 `src/business_analysis/`、指标 / Prompt / Golden Cases 默认不改；发现核心问题应记录独立问题，不以 UI 接入改写业务事实。
- 验证：模式分离 / ID / 原问题锁定 / 重试 / 拒绝 / 安全展示检查、桌面浏览器确定性分析闭环、现有 analysis API 回归。

**Migration / Rollback**：Migrate 分析；不删除 checkpoint / run registry；回退本切片保留 query 和旧 Streamlit 分析入口。

**Done When**：经营分析和模式切换的正常 / 边界证据、文档、Review / 本地 Commit 完成。

## 04. 桌面浏览器验收与真实 AI 闭环

**Change Profile**：长期验证能力；中等切片；认证与真实外部资源风险；确定性 Chrome + 真实 AI / PostgreSQL；本地逻辑 Commit。

**Blocked by**：03。

### What to build

- Playwright 桌面 Chrome 验收，固定依赖 / browser channel 并记录实际版本；确定性 fixture 使用真实 HTTP / Session，fake 查询结果与真实 AI 报告分别记录。
- 将 R1 浏览器矩阵接入已有 CI 检查，覆盖登录 / 首次改密 / 刷新 / 双模式 / 等待 / 失败 / 失联 / 换号 / 迟到响应 / 跨标签 / CSRF。
- 用真实后端、模型 / RAG / PostgreSQL，经浏览器登录完成普通问数、连续追问与两期分析，核对结果与参考数据。
- 安全验收记录 / 可复现命令，禁用含真实凭证和业务内容的自动网络 Trace / 视频；不存在真实闭环资源时明确记录未完成，不用 fake 结果替代。

### Acceptance criteria

- 真实 `channel: chrome` 下 Spec 浏览器矩阵通过；报告包含提交、构建、浏览器 / OS 和范围，Chromium 不冒称 Chrome。
- 确定性失联 / 迟到响应 / CSRF 失败能重复触发并验证，不靠人为描述代替测试。
- 真实 AI 请求走生产同一授权 / SQL Guard / 只读执行链，普通问数 / 追问 / 经营分析结果和两期证据正确；不改变数据去迎合问题预设。
- 报告区分测试替身、真实 AI 与历史 Evaluation；最终真实验收须绑定 clean code candidate，后续行为变化重跑受影响场景。
- 既有必须检查继续有效，Node / 浏览器 / 依赖安装有明确版本及锁文件；不新增部署或公网发布。

### Owned files 与证据

- `frontend/` Playwright 配置 / 验收脚本 / fixture；`tests/` 必需的真实 HTTP 测试装配；`.github/workflows/ci.yml` 及确有需要的 real-e2e 入口；README / Runbook 验收步骤。
- `docs/acceptance/web-dialogue-v1-20261003.md`（实际执行日期变更时据实命名）与安全报告入口；真实原始报告保存在 ignored reports，文档说明复现步骤和实际验证提交。
- 受影响的认证 / API / 会话 / 分析回归、浏览器矩阵、依赖审计、真实 AI 闭环；正式 Evaluation 按最终 Diff / 证据适用性决定复用或重跑，不预填成绩。

**Migration / Rollback**：建立 Migrate 验收里程碑，仍保留 Streamlit；资源不具备或核心闭环失败时停止 05。安全 fixture / CI 可回退，不删除真实数据或弱化安全检查。

**Done When**：核心替换条件有真实证据，所有验收命令 / 适用范围 / 未验证项清楚，Review / 本地 Commit 完成。

## 05. 切换默认入口、移除 Streamlit 与完整 R1 收尾

**Change Profile**：长期入口替换；中等迁移闭包；旧入口删除 / CI / 配置风险；完整 smoke / 回归 / 文档证据；同一最终 candidate，等待单独发布授权。

**Blocked by**：04。

### What to build

- 切换 README / Runbook / 启动脚本至 Vite / 打包网页，CI application smoke 验证新默认入口 / 登录，不再依赖 Streamlit health。
- 删除 Streamlit 活动代码 / 专属测试 / Python 依赖与 lockfile 解析结果，更新模块检查及其测试，保留历史 Spec / Acceptance。
- 同步正式 Product Scope、Architecture、Query API / Web Spec、Design、Acceptance、Roadmap 与当前工作记录。
- 最终核对全部 R1 代码、依赖、运行和证据；文档 / 历史报告不互相竞争或伪称当前候选通过。

### Acceptance criteria

- 新默认入口在新 clone 安装 / 开发 / 打包运行链路可复现，API-only / Bearer / SQLAdmin 仍有效；回退不会要求重置数据库。
- 活动源码 / 依赖 / 启动脚本 / CI / 文档中无失效 Streamlit 用法；历史记录允许保留但不是当前启动入口。
- 模块门禁继续覆盖新 Adapter、查询及核心边界，删旧文件后不读取不存在路径，不降低既有边界约束。
- 最终 npm / Python lock、类型 / lint / 构建、软件 / 集成 / 浏览器 / startup smoke / 依赖与安全检查完成；删除引起的行为变化重跑受影响验收。
- 最终 clean candidate 的真实 HTTP / Chrome AI 闭环按最终风险重跑或明确证明代码证据可复用；报告仍绑定实际被验证的提交，不把早期 dirty 结果或历史基线移植到最终 HEAD。
- Roadmap 只标记已完成 R1 事实，不声称图表 / 历史 / 流式或 R6 / R7 已完成。

### Owned files 与证据

- 删除 `src/streamlit_app.py` / `tests/streamlit/`；`pyproject.toml` / `uv.lock`；`scripts/start-dev.ps1`、`scripts/check_module_boundaries.py` 及测试；`.github/workflows/ci.yml` smoke；正式文档与 `.scratch/chatbi-product-v1/` 完成记录。
- 首轮 rg 已发现的消费者及实现阶段全仓库再核对清单；必要时扩充清单但不清理无关文件。
- 证据：完整 Diff / Review、Markdown 链接 / 模块门禁、构建与新入口 smoke、受影响回归 / 最终真实闭环、删除闭包检查；记录每项提交身份与结果。

**Migration / Rollback**：Contract / Cleanup。失败时修复新入口或恢复迁移中的旧入口；发布回退整份 known-good 代码 / lock / 配置，不删除数据库数据。无 Feature Flag / 灰度上线，本次尚不发布真实用户流量；未来发布按目标仓库授权流程执行。

**Done When**：R1 的代码、正式事实源、验证、Review、适用本地 Commit 全部完成，形成可审查 candidate；Push / PR 仍须说明最终范围、证据、风险和 Auto-merge 后另行取得授权。

## 依赖与实施规则

`01 → 02 → 03 → 04 → 05`。单 branch / worktree，不为 Ticket 单独发布 PR；每项同步测试、文档和 Review。04 是跨功能浏览器 / 真实 AI 证据里程碑，不代替 01–03 的逐项测试。

用户确认拆分并授权整个 R1 实施范围后，主 Agent 按依赖连续完成全部切片，不逐项请求“继续”。本草案不授权 R2–R7 实施或 R1 Push / PR。

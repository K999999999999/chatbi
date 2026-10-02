# R1 Ticket Readiness Review

日期：2026-10-03。Owner：当前主 Agent；当前上下文只读检查，未启动独立 Agent。

Ticket Readiness: READY

Scope：[已确认 Spec](r1-spec.md)、[已审查 Design](r1-design.md)、[Design Review](r1-design-review.md) 与 [五项 Ticket 草案](r1-tickets-draft.md)。本结论不代表已经写入正式 Tickets 或开始实现。

Change Profile：长期维护的电脑端产品入口；五个可独立验证的纵向切片；身份 / 状态 / 删除旧入口风险；软件、集成、真实 Chrome 与 AI 闭环证据；单 branch / 最终 candidate / 一个 PR，远端发布尚未授权。

Owner：当前主 Agent 负责五项切片与交付；本项目维护者承担后续代码、文档、CI 与运行入口维护。暂无跨团队或 Backup Owner 要求。实施中若发现未获确认的 Contract / 范围变化，返回 Spec / Design，不自行扩张。

## Findings 与覆盖

- 无阻止实施拆分的剩余问题。01–03 各自包含界面、HTTP / 状态接入、软件验证与文档；04 增加跨流程 Chrome / 真实 AI 证据，不替代前面各切片验证；05 是新入口通过后的旧入口关闭与最终证据核对。
- Spec 作为行为权威，Design 固化 Edge 技术；正式 Spec / Design 的同步位置、长期记录与证据职责明确，不以 Ticket 反向改变领域事实。
- 依赖有实际启动依据且无环：02 依赖登录 / 状态外壳，03 依赖单请求聊天状态机，04 依赖双模式完整页面，05 依赖替换验收。每项只记一个直接前置，未把 R2–R7 作为 R1 阻塞。
- Cookie / Bearer / SQLAdmin 兼容、CSRF 来源拒绝、期待用户比对、单请求 / 成功状态、失联恢复、退出待确认 / 迟到响应、安全文本展示均有客观验收 seam。
- Scope 与 owned files 覆盖前端、浏览器 HTTP Adapter、装配、认证 Provider、CI、启动脚本、模块检查、Python / npm lock 与正式文档；不新增数据库历史或改动业务指标 / Prompt。
- Node / npm / React / Vite / TypeScript / plugin / Playwright 已查版本和声明兼容条件；精确 lock、peer dependency 解析、npm ci、构建和审计是 01 / 最终 Done When。查元数据不等于组合安装已通过；不兼容时停止并重新审查，不能自动跨大版本换栈。
- 验证区分真实 HTTP + fake 查询服务、真实 Chrome + AI / RAG / PostgreSQL、历史 Evaluation；证据记录实际提交 / 构建 / 浏览器 / 范围；没有资源时不以替身结果冒充真实验收。
- 每项 Review / 文档 / 验证 / 本地 Commit 条件明确；最终 R1 不承诺生产容量或历史 / 图表 / 流式。

Dependencies：01 → 02 → 03 → 04 → 05，仅直接前置，无循环；一条 Feature branch / 一个 worktree 连续推进。

Migration / Rollback：Expand → Migrate → Contract；已有 Streamlit 消费者闭包已检索，05 前再核对活动入口；旧入口仅在替换证据有效后删除。无数据库数据迁移，按完整代码 / lock / 配置版本回退，保留账号、审计、checkpoint；失败停止删除与后续交付。尚无真实用户流量发布，不强加 Feature Flag / 灰度流程。

Evidence：读取 Spec / Design / Review / 草案、AGENTS 及 issue / Git 工作流、Architecture / Product Scope / Query API Contract、AuthService / API / SQLAdmin、当前测试 / CI / 启动 / 模块检查消费者；核对已有 pytest 与 HTTP seam、Chrome 驱动及依赖元数据。此阶段只检查文档，不运行功能测试、浏览器或真实 AI。

Next：用户确认五项拆分并授权整个 R1 实施范围后，写入正式 Tickets 并连续实施；不逐项询问“继续”。R1 Push / PR 需候选形成后按仓库规则另行取得发布授权。

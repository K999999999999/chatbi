# 04. 桌面浏览器验收与真实 AI 闭环

Status: done
Owner: 当前主 Agent
Canonical Source: ../r1-spec.md、../r1-design.md、../r1-design-review.md、../r1-ticket-readiness.md


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


## Result

确定性与真实验收入口已完成。以下保留形成候选前的过程，最终真实结论见末尾。

- Chrome 154.0.8037.92：打包入口 16 项通过，Vite 开发代理 1 项通过；覆盖全部 Spec 桌面矩阵、原任务重试、断网 / 超时 / 畸形响应、换号 / 跨标签 / 迟到响应、CSRF、文本安全与归因展示。
- npm audit 0 漏洞；类型 / 构建、225 个 Python 文件格式、CI lint、模块边界、Markdown 链接与 diff 检查通过。
- 真实 harness 使用正式 runtime 与真实专用 analyst 账号，随机密码仅进程环境；停服禁用 / 撤销、保留审计，不修改已有账号或业务数据。独立只读参考查询 + 产品因素对账，禁用网络 Trace / 视频 / 截图，安全 reporter 不输出错误内容。真实报告 ignored，不混入 Commit。
- 当前上下文 Code Review：PASS（BASE 0800600，范围本切片 frontend 验收 / 身份小修、tests/browser_real_*、CI / Runbook / Design / ignore）。补查发现其他标签身份变更可使初始化留在 checking，已修复 ready 状态，身份矩阵通过。真实配置只在显式 opt-in 下创建隔离账号；不通过静态身份绕过认证。
- 全部软件回归：`uv run --locked python -m pytest -q` 639 passed、15 skipped、146 subtests（跳过依赖显式 opt-in 的外部集成）；独立业务参考查询成功。直接 pytest 入口曾因 sys.path 收集失败，按仓库 CI 的 python -m pytest 入口通过，无代码修复。
- 先形成 clean code candidate 后执行真实闭环，结果在后续 Result / Acceptance 回填，尚未允许删除 Streamlit。

## Comments

2026-10-03 用户确认五项拆分并授权完整 R1 实施；不包含 Push / PR 发布。


首次真实闭环：clean `2b182b5fc6e8e09ae2b3c4a1f00b1c7abe53519f` / Chrome154 通过；问数、追问、4个分析任务及程序产品归因与独立参考一致。发现 Playwright 默认 SIGKILL 导致 fixture finally 未运行；已仅禁用本次唯一归属账号并撤销 Session。验收关闭改用 SIGTERM / 30 秒，并生成不含凭证的账号清理证据；修复后需重跑真实验收。核心业务代码未变化。


最终切片结论：clean `c8fe37ed6be41e9d754fd82bfeb22685f4392fd2` 的真实 Chrome 闭环重跑 PASS，自动清理 disabled=true / active_sessions=0；Review 修复项复核 PASS。正式 Acceptance 已写入 `docs/acceptance/web-dialogue-v1-20261003.md`，包含提交 / 环境 / 参考值 / 证据适用性、首次关闭问题和修复证明。软件证据与历史 AI 基线明确分开；R1 业务语义未变，未冒称全量 Golden Set 新基线。可以进入 05 删除旧入口。

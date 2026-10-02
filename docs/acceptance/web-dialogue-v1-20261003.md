# Web Dialogue V1 电脑端验收

## 结论与适用范围

R1 登录 → 问数 → 连续追问 → 独立经营分析的浏览器核心替换条件通过。Ticket 04 证据绑定 clean code candidate `c8fe37ed6be41e9d754fd82bfeb22685f4392fd2`；Streamlit 删除与最终候选验证由 Ticket 05 继续，不将该候选冒称最终交付或生产部署证明。

Contract：[Web Spec](../specs/web-dialogue-v1.md)、[Web Design](../designs/web-dialogue-v1.md)。范围仅电脑端、指定账号、同步请求；图表、长期历史、流式、导出和生产运行验收仍按 R2–R7。

## 软件与浏览器证据

- `uv run --locked python -m pytest -q`：639 passed、15 skipped、146 subtests；适用实现至 `2b182b5`。`c8fe37e` 仅修正真实验收关闭和清理记录，业务 / API / 页面代码未变化，因此软件证据复用。
- `npm run build` / 类型检查、CI 选择的 Ruff 格式 / lint、模块边界、Markdown 链接、diff 空白检查通过。
- 打包网页 `npm test`：16 个 Chrome 用例通过；Vite 同源代理 `npm run test:dev`：1 个双模式用例通过。真实 HTTP / Session / RBAC，查询与分析服务为确定性替身，不能代替模型验证。
- 矩阵包含首次改密 / 重登、登录刷新、退出、问数 / 追问 / 澄清 / 空结果 / 截断、NULL / 零 / 空串、模式隔离 / 原 UUID 重试 / 拒绝、等待时按钮与草稿、断网 / 超时 / 畸形响应、退出失败刷新、跨标签换号、迟到响应、CSRF / 错账号和文本安全展示。
- Node 24.21.0 / npm 11.19.0；依赖由两个 lockfile 固定，npm audit 0 漏洞。CI 的 8 个 required check 名称保持不变，新增浏览器 / npm 验证尚未在远端执行。

## 真实业务闭环

环境：Linux / WSL，桌面 Chrome for Testing 154.0.8037.92，1440 × 1000；本地 PostgreSQL 16、Qdrant 1.18.3、现有模型 / BGE-M3 / RAG 资产。网页通过 Cookie 登录和正式 runtime，使用实际权限校验、SemanticQuery / Certified Mapping、SQL Guard 与业务只读执行，不使用静态身份替代真实认证。

执行命令：`cd frontend && npm run build && npm run test:real`。浏览器与库在用户 cache，使用 `CHATBI_CHROME_PATH` / `LD_LIBRARY_PATH` 指定，未修改系统或真实 `.env`。原始证据位于 ignored `reports/browser-real/2026-10-02T20-18-24-162Z-c8fe37e.json`，时间为 UTC，提交 / 浏览器 / 对照与结果均由运行写入。

| 场景 | 对照与结果 |
| --- | --- |
| 完整问数：2025 年 2 月已完成订单人民币净销售额 | 与独立业务只读 SQL 一致：171010.143550 |
| 连续追问：改成 2025 年 3 月 | 使用同一成功 conversation_id；与参考一致：209683.289100 |
| 两期人民币毛利 / 产品因素 | 比较期 90822.565882，当前期 109017.883677，变化 18195.317795；归因主要产品 / 每项因素与独立参考一致 |
| 任务证据 | 4 个任务均 completed / 未截断；两期整体各 1 行、产品证据各 8 行，网页可展开查看 |
| 退出 / 服务关闭 | 浏览器退出后返回登录；服务收到 SIGTERM，专用验收账号 disabled=true、active_sessions=0，清理 JSON 已核实 |

当前上下文核对真实报告：主要产品与变化方向符合参考；前端按后端报告原文和程序数值展示，未补写原因或重算。主要贡献列表只展开 3 个产品，明确另有 5 个未展开；完整产品任务证据可查看。模型文字带有英文内部术语和“未展开”表述，属于现有报告生成行为；本次不改 Prompt，丰富结果解释属于 R2 的后续需求细化。

首次真实运行 `2b182b5` 的业务闭环也通过，但默认 SIGKILL 未触发验收账号清理。已仅禁用该次唯一归属账号并撤销其会话，之后修正 Playwright 的关闭配置；`c8fe37e` 重跑业务闭环通过，自动清理记录确认成功。保留失败过程，不把首次未清理结果改称完整收尾成功。

## 证据边界与风险

- 三套正式 AI Evaluation 的历史 `6a5e6cc` 基线不改称本次结果。R1 未改变指标、语义、Prompt、模型配置、SQL Guard 或业务编排；历史报告仅说明核心覆盖，本次真实浏览器的三个场景说明新增入口实际闭环，不声称重新跑过全量 Golden Set。
- 真实随机密码只存在于进程环境；报告不记录密码、Cookie 或 Session Token，Trace / 视频 / 截图关闭。应用库保留验收账号、安全审计和分析记录；账号停用，不修改已有账号、销售数据或 RAG 资产。
- 非生产负载测试；未验收手机、其他浏览器、多实例、生产 HTTPS / 代理、容量、备份恢复与公网部署。
- 实现 Review 在当前主 Agent 上完成，无独立 Agent 或新增用户 Review 门禁；Ticket 05 还需检查删除闭包、最终软件 / 浏览器及真实候选证据。

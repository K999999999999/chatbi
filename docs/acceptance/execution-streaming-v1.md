# R4 执行状态与流式反馈验收

本文件是 R4 的正式验收入口，记录 Ticket 04 / 05 的历史证据与各阶段边界。R4 最终 clean 候选身份、三套正式 Evaluation、真实浏览器报告和门禁即时状态绑定本机候选，保存在 Git 公共目录 `work-items/execution-streaming-v1/status.md`；ignored 原始报告不随仓库发布。不得把此处历史候选重标为当前结果，也不得将本地验收解释为生产部署或远端发布。R4 行为 Contract 与设计分别见 [Spec](../specs/execution-streaming-v1.md) 和 [Design](../designs/execution-streaming-v1.md)。

## Ticket 04 状态与结果真实验收

### 结论与候选身份

Ticket 04 的 clean 候选真实验收通过。

- 候选：`d6478da957b7515ebb3f1387f123de8752c34192`，branch `feat/execution-streaming-v1`，`git_dirty=false`。
- 验收入口：`scripts/verify_container_dev.sh real`；目标为本机 Compose + Vite + FastAPI + PostgreSQL / Qdrant + 桌面 Chromium + 实际 LLM。
- 原始报告：本机 ignored 文件 `reports/browser-real/container-1791209719-real.json`，SHA256 `e22ce2e91b0140ff5041e33924eb5d6ea4308c22b4560bef733c7e5dfb37603a`。报告不进入 Git，新 clone 不会自动包含；报告身份和安全摘要保存在本机 Git 公共目录的 R4 工作状态中。
- 浏览器：Chromium `153.0.8010.12`。模型：`deepseek-flash`，Provider host `api.deepseek.com`，模型配置 SHA256 `26159e7ad065073448460117eb24b7a4572f6f4e78eadff65dc0a11c052449fa`。RAG manifest SHA256 `0fb107ab3a5fc9dca1f828625bd9b46d8f15fde8d5f2d15cb94dbbe04616a08e`；业务 Schema `mart_sales`。原始报告含完整模型 / 运行 / 独立 SQL 参考身份。

### 真实链路结果

| 验收 | 结果 |
| --- | --- |
| 问数与追问 | HTTP 200；真实 SSE 为 snapshot / progress / terminal，六个实际查询阶段均被观察到，最终 `succeeded`；单月、月度趋势及分类结果与独立只读 SQL 参考一致 |
| 经营分析 | HTTP 200；真实 SSE 为 snapshot / progress / terminal，六个分析阶段均被观察到，最终 `succeeded`；任务数值、归因方向与独立参考一致 |
| 刷新 / 多页 / 取消 | 刷新和第二标签页重连到同一 execution，业务操作只提交一次；取消状态为 running → stopping → cancelled，上一成功轮次保留；取消后新操作的续聊引用与上一成功上下文一致 |
| API 重启恢复 | 验收进程实际停止 API 容器后重启 Compose；遗留 execution 和 turn 均收敛为 `unconfirmed`，活动指针清除，未确认快照不存在，上一成功轮次保留；Control Schema v1–v5 标记完整 |
| 重启后持久化 | 历史快照重读、重新登录、续聊、显式重查及业务数据 / RAG 资产身份核对通过 |
| 清理 | 专用账号禁用、活跃 Session 为 0、临时凭证移除；既有用户、业务数据、开发数据卷和 RAG 资产保留；报告不含 Secret |

### 确定性验证与 Review

- `uv run --locked python scripts/run_database_tests.py --profile development`：42 passed。包含隔离 development PostgreSQL、迁移 / 重复迁移、execution / history 竞态与旧版保留数据兼容检查。
- `cd frontend && npm run build`：typecheck 与生产构建通过。
- 隔离 Docker Chromium 定向用例 `问数取消终态保留上一成功上下文并允许用户新建下一轮`：1 passed；覆盖刷新活动历史、取消及之后提交下一问题。
- `git diff --check`：通过；Ticket 04 实现与证据 Code Review：PASS。
- 有一次直接对日常 development PostgreSQL 启动子集测试的尝试，被仍运行的 API 按单进程 advisory lock 正确拒绝。随后改用上述仓库隔离 development 数据库入口，全套 42 项通过；该失败尝试生成的 21 个无引用测试占位账号已按固定前缀清理并核实归零，未留下业务记录。

### 范围边界

该阶段的证据只覆盖真实执行状态、结果、取消 / 重连及进程重启恢复，不覆盖分析报告文字增量、完整 R4 Regression、三套正式 Evaluation、生产容量或部署验收。Ticket 05 / 06 的后续阶段按已确认顺序分别记录于本文件；R4 发布仍未授权。

## Ticket 05 分析报告真实流式开发验收

### 结论与证据身份

Ticket 05 的实现与定向验证通过；真实模型增量证据来自 Ticket06 前的开发运行，不是 clean 最终候选验收。

- 开发运行基线：`e1f3f4dff8e5e2c14ee6e601a32a983151950ae4`，branch `feat/execution-streaming-v1`；当时 `git_dirty=true`，包含尚未提交的 Ticket05 实现。
- 验收入口：`CHATBI_CONTAINER_ALLOW_DIRTY=1 scripts/verify_container_dev.sh isolated`；Compose、浏览器与临时数据库均使用隔离资源。
- 原始报告：本机 ignored 文件 `reports/browser-real/container-1791214283-isolated.json`，SHA256 `a3eb24f278320d394fc8674f13760a17bbd90d99e0c8f682efc5a8e9d21489a4`。完整报告不进入 Git；此处只记录所需证据。
- 运行目标 `compose-vite-api`；模型 `deepseek-flash`，Provider host `api.deepseek.com`，CPU Embedding；模型配置 SHA256 `26159e7ad065073448460117eb24b7a4572f6f4e78eadff65dc0a11c052449fa`。

### 真实模型结果

| 验收 | 结果 |
| --- | --- |
| 模型报告增量 | HTTP 200；实际 SSE 含 `text_delta`；收到 804 个文字增量，首个增量序号 18，报告 `succeeded` 序号 823，证明完成前收到真实模型文字 |
| 分析闭环 | 4 个分析任务完成；报告方向、归因与独立业务参考匹配；产品 / 因素图表存在 |
| 阶段与终态 | 六个分析阶段均被观察到，终态 `succeeded` |
| 隔离与清理 | 临时账号已禁用、活跃 Session 为 0；isolated 网络与卷清理完成，既有开发数据与 RAG 资产保留 |

### 确定性验证与 Review

- Python 定向回归：`uv run --locked pytest -q tests/business_analysis tests/query_api/test_history_application.py tests/query_api/test_execution_events.py tests/query_api/test_execution_api.py tests/query_api/test_execution_application.py tests/query_api/test_analysis_mode.py`：99 passed。
- `cd frontend && npm run build`：TypeScript 类型检查与生产构建通过。
- Docker 浏览器 `execution.spec.ts`：10 passed；覆盖未校验草稿、retry generation 清理、断线快照重连及既有执行交互。
- Ticket05 触及的 12 个 Python 源码 / 测试文件 `ruff format --check` 通过；仓库 CI 选用的 Ruff `E4` / `E7` / `E9` / `F` 规则、模块边界、Ticket05 源码 Bandit 检查和 Markdown 本地链接检查通过；`git diff --check` 通过。
- Code Review：PASS。Review 中补齐了同步兼容 `invoke` 路径的原始 JSON 5 MiB 上限，并将草稿增量和快照大小计数改为线性累计；最终候选仍由 Ticket 06 检查。

### 范围边界

此证据证明真实模型报告文字增量先于执行成功事件，并证明该隔离运行的分析结果与独立业务参考一致。由于开发运行 `git_dirty=true`，它不证明最终 clean 候选、完整 R4 Regression 或三套正式 Evaluation；Ticket 06 的候选绑定结果单独记录在本机实时工作状态。


## Ticket 06 最终候选验收入口

Ticket 06 在全部实现、正式 Contract 与本文件维护提交后，于唯一 clean candidate 上执行适用门禁。确定性 Python 全量回归、隔离 development PostgreSQL、前端 `npm ci` / typecheck / build / Playwright、CI 锁文件 / Ruff / 模块边界 / 安全 / Markdown / Diff 检查按 [Runbook](../runbook.md) §8 和 CI 定义运行；真实 R4 浏览器、模型、RAG、业务 PostgreSQL 与独立参考使用 `scripts/verify_container_dev.sh isolated`。三套正式 single-turn / multi-turn / business-analysis Evaluation 与统一 report identity 检查、三次完整多轮诊断按 [Runbook §9.2](../runbook.md#92-正式三套基线与稳定性诊断) 执行。

这些报告必须指向同一个 clean commit，并满足案例全集、案例 Hash、RAG / 数据 / 模型身份及零 `FAIL` / 零 `INVALID_CASE`。精确命令退出状态、报告路径 / SHA256、实际模型与数据摘要、账号清理和未运行项由本机实时工作状态保存；本段提供可复现门槛，不预填本机结果。单机单进程验收不构成 R6 / R7 生产容量或部署验收。

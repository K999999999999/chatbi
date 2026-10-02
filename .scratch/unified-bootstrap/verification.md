# 初始化与资源装配验收证据

Date: 2026-10-02（Asia/Shanghai）
Baseline: `08c632e01baae62e161f3eec69993d56a3f441c3`
Candidate: 待本地提交后记录；测试期间为本目标未提交候选，不能描述为 clean commit AI Evaluation。
Product source SHA-256: `520e7e9063947f529a07958ca769aac695a9c0fc08e1e4bc9c6b6e28bb39ce5c`（按记录的源文件范围，候选提交后复算核对）
Scope: 三项正式 Tickets；已确认 Spec 与 design.md；运行资源、四类命令、旧入口删除、当前消费者迁移和受影响文档。

## 验证结果

| 检查 | 命令 / 范围 | 结果 |
| --- | --- | --- |
| TDD Red | 无配置导入测试 | 原实现因导入调用配置加载失败；修改后通过 |
| TDD Red | 经营分析 close | 原实现 run store close 失败后跳过 pool；修改后通过 |
| TDD Red | RAG 命令失败清理 | 原实现 close 异常覆盖构建异常；修改后保留构建原因 |
| 全量软件 | `uv run --locked --no-sync python -m pytest -q` | 604 PASS、15 SKIP、128 subtests PASS；外部环境集成按原 skip 条件处理 |
| 最后清理修订回归 | bootstrap、query_api、business_analysis、RAG Runtime、rag_offline、scripts 软件测试 | 240 PASS、14 subtests PASS；覆盖 RAG 意外异常、多个 client 清理与重复启动 |
| 最后所有权修订回归 | `tests/query_api/test_runtime_binding.py`、`tests/bootstrap/test_runtime.py` | 14 PASS；覆盖混用拒绝及启动 / 失败 / 关闭 |
| 隔离 development DB | `uv run --locked --no-sync python -m scripts.run_database_tests --profile development` | 19 PASS；最后行为修订后重跑通过；migration / checkpoint / grants、管理员、数据库摘要与完整 API startup smoke |
| 隔离 CI DB | `uv run --locked --no-sync python -m scripts.run_database_tests --profile ci` | 5 PASS；逐查询连接策略无后续改动，证据可复用 |
| 锁文件 | `uv lock --check` | PASS，无依赖版本变更 |
| 编译 | `python -m compileall -q src evaluation tests` | PASS |
| 格式与 Lint | CI 同版本 Ruff 0.16.8 format / E4,E7,E9,F | PASS |
| 模块边界 | `python -m scripts.check_module_boundaries` | PASS |
| 文档 | `python scripts/check_markdown_links.py` | PASS |
| Diff | `git diff --check` | PASS |
| 安全静态检查 | `uv run --locked --with bandit bandit -r src scripts -ll` | PASS，0 Medium / High；依照仓库 CI 阈值，现有 Low 不在此次门禁范围 |
| 实现 Review | 当前主 Agent 依据 Spec / Tickets 检查 | PASS，见 code-review.md |

## 边界与适用性

- 数据库验证使用本次 runner 创建的带运行身份标记的临时容器和随机端口；结束后仅清理该容器和数据卷，没有访问或重置日常开发数据库。
- API startup smoke 使用真实 PostgreSQL / Control DB、checkpoint、SQLAdmin、模型对象与应用装配；LLM 地址为测试地址，不发送模型请求。启动成功后健康接口、管理员匿名重定向及非法查询响应符合 Contract；结束后经营分析线程退出、服务绑定清空。
- 模型准备和 RAG 命令使用替身与已有 builder 软件测试，证明参数、固定 revision、退出码、发布规则及失败释放；没有实际下载模型或写入开发 Qdrant。
- 全量回归后只修改局部清理、CLI 帮助身份、资源 repr 和混用校验；分别执行受影响复验。未受影响全量 / CI DB 证据继续适用，不把更早的结果当作新运行。
- 未运行：真实 LLM Evaluation、真实 RAG 构建、外部真实查询 Real E2E、远端 CI。理由：本目标不改变 Prompt、Semantic、模型参数或查询业务链，已通过确定性完整装配及数据库验证；外部验证不隐式执行。本报告不声明当前 clean commit Evaluation 基线通过。
- 路线图已新增初始化 / 装配完成事实，保留原 Evaluation 待办与优先级。
- 正式入口更新位置：docs/specs/bootstrap.md、Query API / RAG Spec、Query API Design、Architecture、README、Runbook、两项 workflow 与相关 runner / reset 调用。
- 默认本地交付，没有 Push / PR 授权。

## 结果

三项 Tickets 的功能、适用文档、验证和 Review 完成。已确认的旧入口全部移除，仓库当前消费者已迁移；旧字符串仅保留在明确说明删除行为的文档、旧入口失败测试和历史证据中。

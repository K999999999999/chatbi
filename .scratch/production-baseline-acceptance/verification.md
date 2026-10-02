# 生产准备基线修复验证

Date: 2026-10-02（Asia/Shanghai）
Baseline: `76dddbdad8b8153e810f13ed5f81dd35de0b47ee`
Candidate: 包含本记录的本地修复提交；精确 SHA 与真实评测进度保存于 Git 公共目录 `harness/work-items/production-baseline-acceptance/status.md`。软件验证针对本提交形成前的对应 Diff，不声明为 clean commit AI Evaluation。

## 已完成证据

- Red：原验收器不支持预期身份和完整三套目录，新增公共 CLI 用例出现 23 个失败；此前对真实历史报告的只读复现返回通过。Green：修复后定向 Evaluation / 工作流测试 94 PASS、1 SKIP、22 subtests PASS；报告忽略修订后增加递归目录回归，95 PASS、1 SKIP、22 subtests PASS。
- 原始历史报告 `20260930T055904Z-5643432.json` 在预期 commit 为 `76dddbd` 时被明确拒绝：`metadata.git_commit: identity mismatch`。
- 验收测试覆盖正确三套、旧 / dirty / 缺失身份、错误套件 / 案例 Hash / RAG 版本、缺失 / 重复 / 失败案例、多轮缺失轮次、不同数据和模型、缺失元数据及非法 JSON；不同套件的 context / reference result Hash 允许不同。
- 工作流测试实际执行仓库中的 shell，用最小可执行 uv 替身隔离外部 LLM，验证任一正式套件失败仍运行其他套件和身份验收、验收失败返回非零、诊断失败继续三次且不替换正式结果。
- 隔离开发 DB：`python -m scripts.run_database_tests --profile development`，19 PASS；完整 Seed、运行角色、Control DB / checkpoint、授权与数据指纹在临时容器验证，不访问或重置日常开发库。
- YAML 解析与 10 个 run block 的 `bash -n` PASS；Markdown links、Stable module boundaries、uv lock、Ruff 0.16.8 format / E4,E7,E9,F、compile 与 diff --check PASS。
- 日常环境只读预检：Seed `chatbi-sales-mart-dev-v3`；数据 Hash `5ecab061588e5084ef1dd13c9d0a969d3c49f8d26bd7418b5341f427abedeafb`；Control DB / checkpoint Ready；RAG `provenance-20260929` 的来源指纹与实际 catalog 验证通过；必需 LLM 配置存在，不打印其值。

## 文档与范围

- Evaluation Spec 固化现有三套零失败门槛的完整身份验收与独立多轮诊断规则；Runbook 给出 clean commit 三套验收步骤、诊断与报告保留方式。
- 路线图记录验收工具完成事实，保留当前候选真实 Evaluation 待核验项；补充历史较新基线、模型波动、会话扩容 / readiness / 流量边界。优先顺序来自用户本轮批准的建议，不新增生产平台或容量承诺。
- 产品范围与架构同步历史基线身份。日期化历史 Acceptance 和原始失败报告未改写。
- 普通 CI 未改动 fixture；Real E2E 改用现有完整合成 Seed 以覆盖经营分析所需月份，并初始化 Control DB / checkpoint。

## 后续验证及限制

- 初始候选 `a8a5d9ad9df32184b31094d2ce974087613ef418` 首轮单轮 29/29 PASS、clean；多轮 6/7 Conversations / 14/15 turns，`MT-FAILURE-ISOLATION-T3` 返回意外 `CLARIFICATION_REQUIRED`，且报告为 dirty。原因：原 `.gitignore` 只忽略报告根目录，新分目录 JSON 使后续运行变脏。经营分析在发现此问题后中止；全部原始报告和日志保留于 ignored `reports/evaluation/baseline-20261002T133502Z-a8a5d9a/`，该次不能作为有效基线。
- 修复递归 JSON / Markdown 忽略规则，新增实际 Git check-ignore 回归；工具与查询业务代码未再次改变。原三套零失败和 clean commit 门槛不放宽；形成新 clean candidate 后重新运行三套与诊断。隔离 DB 19 PASS 证据继续适用。

- 真实三套与三次多轮诊断在最终 clean commit 后执行，绑定报告自身 commit、案例 Hash 和资源身份；实际结果仅在原始 ignored reports 与本机实时记录更新，避免追加文档提交使报告身份过期。
- 未运行 GitHub 远端 CI / 手动 Real E2E：未获得发布授权。actionlint 不可用，采用 YAML、shell 语法和实际 shell 行为验证；这不声明云端工作流已成功。
- 未运行生产容量、动态 readiness、备份恢复或多副本验收：这些需要另行确认生产目标和 Contract。本次只澄清现有运行限制。

## Harness 反馈

测试 / 反馈缺口：真实 E2E 曾只覆盖单轮且验收器只检查成绩，无法自动拒绝旧身份。修复沉淀于统一验收器、正式三套工作流、公共 CLI 回归和工作流失败行为测试，可持续发现漏套件和误用报告。没有新增当前范围之外的 Harness 改动。

上下文 / 测试缺口：本次初始 Review 漏查分目录产物与已有 ignore 模式的交互，真实运行的 dirty 检查揭示问题。通过 `tests/scripts/test_evaluation_report_ignore.py` 将根目录、正式 / 诊断分目录和汇总文件的 Git 忽略行为固化为回归；失败证据保留，后续不因输出组织变化重复污染验收身份。

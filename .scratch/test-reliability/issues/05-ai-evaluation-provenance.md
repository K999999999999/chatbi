# 05 四套 AI 评测统一追溯、防覆盖与正式验收

Status: in-progress
Canonical Source: [Spec](../spec.md)、[Design](../design.md)、[草案](../tickets-draft.md#05-四套-ai-评测统一追溯防覆盖与正式验收)
Owner: 当前主 Agent
Change Profile: 中等跨套件工具 / 报告改动；证据兼容风险中等；不改业务执行或评分。
Blocked by: None (can start immediately)

## What to build

建立标准库报告工具，四套评测都在开始加载 / 执行前采集身份，并在完成后核对。版本化 provenance，记录安全的起止 Git / 输入身份；补齐语义题集 / 模型有效配置与经营分析 Judge 配置；使用唯一 run ID 和排他写入 JSON / Markdown。新正式验收拒绝 changed / unverified / 缺少必要证明的报告，旧报告继续可读、旧基线比较继续有效。

Owned files: 新增 `scripts/verification_report.py`；`evaluation/__main__.py`、`evaluation/common/`、四套评测报告适配、`tests/scripts/` 与 `tests/evaluation/` 对应测试；Evaluation Spec / Design 和相关 Runbook。

Out of Scope: 改变题目、标准 SQL、评分阈值、模型行为或收费调用范围；回填 / 伪造历史报告元数据；在正式三套 JSON 目录增加旁路 summary 文件。

## Acceptance criteria

- 固定时间 / 提交下 run ID 仍唯一；重名时旧文件字节不变并返回失败；JSON 与 Markdown 属于同次运行，部分保存失败不报告成功。
- 四套报告都在执行前后采集；提交 / dirty / tracked 变更、输入身份变化或 Git 读取失败有清晰状态；正式验收只接受 stable 且身份完整的新报告。
- 修改题目内容或实际模型设置能改变指纹；不适用的数据库字段不造值；Judge 的有效 temperature 0 单独记录；报告不泄漏 Secret、完整端点或连接串。
- 历史报告读取与既有基线比较通过；不虚构历史证明；Evaluation 文档语义案例数修正为实际 7。
- 确定性报告 / 验收测试和完整 Evaluation 软件测试通过，不要求付费 LLM 复跑。

Migration / Rollback: 新报告增量写入，不改写历史；回退代码保留新产物原件，身份不足时可读但不能作为正式新验收。

## Result

Implemented versioned start/end provenance and content fingerprints for all four evaluation suites, safe effective model / Judge configuration fingerprints, unique Run IDs, and exclusive JSON / Markdown pair writes. Formal acceptance now rejects reports with missing, changed, or unverified provenance; historical report loading and baseline comparison remain compatible. Corrected the documented Query Understanding case count to 7. No evaluation data, scoring thresholds, or model behavior changed, and no paid LLM / database run was performed.

Review: PASS；基线 `9654f2d83a46b869c0f98a64f3f80e574cc1eb33`；范围为本 Ticket 的报告工具、四套入口与适配、验收测试和相关文档。What：统一运行身份、配置追溯与安全落盘；Why：避免测试中身份变化或报告覆盖造成证据不可信；Risk：新报告采用增量格式，缺少新 provenance 的历史报告不再满足新的正式验收，但仍可读取和比较；Verification：下列确定性测试、静态检查与文档检查通过。Findings：无。Review Dimensions：Correctness / Comprehension / Consistency / Testability / Architecture / Security 均通过。

Verification：`uv run --locked pytest -q tests/evaluation tests/scripts/test_verification_report.py`（103 passed、1 skipped、26 subtests passed）；`bash scripts/check_python_quality.sh`、`uv run --locked ruff format --check scripts/verification_report.py`、`uv run --locked ruff check --select E4,E7,E9,F scripts/verification_report.py`、`python3 -m scripts.check_documentation`、`git diff --check` 均通过。未运行 LLM、数据库、镜像构建或 CI。

Roadmap：不修改 `docs/roadmap.md`；Ticket 05 是已确认测试可靠性目标内的执行项，未改变已确认范围、依赖、验收或路线优先级。

Commit：本地提交待执行；没有 Push / PR。

## Comments

此 Ticket 提供 Ticket 06 复用的报告身份与安全写入工具。

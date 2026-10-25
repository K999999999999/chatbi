# Ticket 01 实现 Review

Review: PASS
Scope: base `64d2eae2b4004dc402d006a1a524ded71a9d7304`；PostgreSQL / renderer CI evidence checker、CI workflow、对应测试与 Runbook。

## Change Description

在既有 CI 中分别检查 PostgreSQL CI / development JUnit，并将 renderer 摘要、JUnit 和 CI 环境记录交叉核对。报告生成器 Contract 未改动。风险限于 PostgreSQL job 报告检查规则；证据缺失时 job 失败，原有 `always()` artifact 步骤继续上传可用报告。

## Findings

- 无未解决问题。
- PostgreSQL 报告要求 XML 可解析、计数非零、全部通过且零跳过。
- Renderer 报告要求摘要与 JUnit 计数一致、摘要状态通过、无缺失产物；源码提交、`uv.lock`摘要和 Python 测试镜像与 CI 环境记录匹配。
- Workflow 静态测试确认检查步骤在 renderer 后、artifact 上传前运行，并使用 `always()`。
- Runbook 已说明必需证据和失败行为。

## Review Dimensions

Correctness / Comprehension / Consistency / Testability / Architecture / Security：PASS。没有改变产品行为、评测 Contract、远端门禁或 `scripts.verification_report` 生成报告后的退出码。

## Tests

- TDD Red：18 个缺陷场景首先失败。
- Green（初次）：`tests/scripts/test_check_ci_test_evidence.py` 与 `tests/scripts/test_ci_verification_workflow.py`，35 passed。
- Ruff 0.16.8 对本 Ticket Python 文件执行 format check 与 `E4,E7,E9,F` lint，均通过。
- `scripts.check_documentation` 与 `git diff --check` 通过。
- 首次 Hosted run `40211914522` 的两个 PostgreSQL profile 和 renderer pytest 均通过；新增核验器仅因 `reports/ci/` 未忽略而读到 `git_dirty=true`。环境提交、锁文件、镜像及 tracked changes hash 均匹配。

## Hosted CI 根因修复复审

Review: PASS
Scope: base `d050cb074a8d6e0a5d71e50fe361aee9359f8b17`；仅新增 `reports/ci/` 忽略规则及其静态回归测试。

- 将 `reports/ci/` 与既有 `reports/tests/` 一并视作生成证据目录，避免报告文件自身污染源码身份。
- 未放宽核验器对源码 dirty 状态的要求；核验器仍会拒绝真实源码变化。
- TDD Red：新回归测试在缺少忽略规则时失败；Green：Ticket01定向测试36 passed，Ruff该测试文件通过。
- `git check-ignore -v reports/ci/environment.txt` 确认规则命中；Hosted 重新验证等待新 commit。

Review Dimensions: Correctness / Comprehension / Consistency / Testability / Architecture / Security：PASS。

Next: 推送修复提交，确认新 head 的 Hosted CI 完成后再收尾。

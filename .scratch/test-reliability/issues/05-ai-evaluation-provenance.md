# 05 四套 AI 评测统一追溯、防覆盖与正式验收

Status: open
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

Pending.

## Comments

此 Ticket 提供 Ticket 06 复用的报告身份与安全写入工具。

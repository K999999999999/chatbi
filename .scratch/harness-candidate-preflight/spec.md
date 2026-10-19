# Harness 候选发布前置验证提案

Status: 待用户确认；仅登记发现，不授权实施
Parent work item: `harness-task-control-v1`

## 观察到的问题

Harness Task Control V1 的 ChatBI PR #90 首次推送后，GitHub `Code quality` 检查因新增 `tests/scripts/test_harness_adapter.py` 未经过 Ruff 格式化而失败。发布前没有运行仓库已指定的 `bash scripts/check_python_quality.sh`。运行该脚本、格式化该测试文件并推送修复提交后，本地与托管质量检查通过。

## 目标

让 Agent 在发布候选前明确识别项目规定的阻塞检查及其本地前置命令，记录每项命令对应的候选 SHA、结果或未运行原因，降低“本地验证完成”但遗漏确定性质量门禁的概率。

## 建议范围

- 为 Harness 项目配置或发现提供 Presubmit 检查清单，关联 GitHub Required Check 与可本地运行的命令。
- 候选发布检查逐项汇总适用检查、命令、候选 SHA、结果和证据引用。
- 对可本地运行但缺少结果的阻塞检查，拒绝登记候选已就绪，或要求记录明确的未运行原因和替代方案。
- 保持 Hosted CI、AI Evaluation、Business Acceptance 和真实外部服务检查的证据类型区分，不把未运行结果标成通过。

## 验收建议

- 确定性测试证明：候选缺少适用本地质量命令结果时不能标记为发布就绪；补齐对应证据后才可继续。
- 检查清单覆盖来源可追溯到项目 Contract / workflow / GitHub 实时规则，不能凭工作流名称猜测命令。
- 记录绑定仓库、候选 HEAD、base、命令和结果；HEAD、base 或检查定义改变后旧证据显示需复核。
- 不能把非阻塞、不可本地运行或不适用的 Hosted / AI / Business 检查强行塞进 Presubmit。

## 不在范围内

- 自动跳过或绕过 GitHub Required Checks。
- 给 `agent-plugins` 配置额外 required-check 规则。
- 自动调用付费 API、真实模型、生产数据或用户服务。

## 授权状态

用户尚未确认本提案、实施范围、优先级或技术方案；不得开始实现。下一步为需求发现 / Spec 确认。

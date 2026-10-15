# 07 CI 接入关键数据库与 PDF 检查及证据

Status: done
Canonical Source: [Spec](../spec.md)、[Design](../design.md)、[草案](../tickets-draft.md#07-ci-接入关键数据库与-pdf-检查及证据)
Owner: 当前主 Agent
Change Profile: 小至中等 workflow 改动；自动门禁风险中等；复用现有 job 和本地软件套件。
Blocked by: 02, 06

Implementation baseline: `9f85b034bf996ee3c42786553cc96987c8484b34` on `refactor/test-reliability`; initial worktree clean.

## What to build

在现有 PostgreSQL integration job 内接入 development 数据库测试套件和真实 PDF renderer，共用开发测试环境并使用与本地一致的执行入口。失败非零；可获得的 JUnit / summary 在失败时仍上传。保留现有 job 名称、来源码 API smoke、前端 build 和其他检查。

Owned files: `.github/workflows/ci.yml`、如必需的 CI workflow 确定性测试、相关脚本适配及 Runbook。

Out of Scope: 新增必需 job 或修改远端保护规则；打包 / 上传业务 APP 镜像；调用真实 LLM 或访问日常环境。

## Acceptance criteria

- workflow 结构及本地等价命令证明真实执行 development 数据库测试与 renderer，不只是 collect 或默认 skip；失败会使 job 失败。
- 复用 CI 临时资源，不需要日常配置 / 模型密钥；依赖锁、固定工具版本与镜像身份可追溯。
- 成功 / 失败 / 未完成时上传可获得的证据；不可得计数不虚构，AI 报告目录不被软件产物污染。
- 既有 job 名称不变，无 APP 镜像发布；本地 workflow / 脚本 / 全量软件 / 文档检查通过。未获发布授权时远端 CI 明确未执行。

Migration / Rollback: 在既有 job 内增加步骤，不更改远端门禁身份；失败时不删除测试以换取通过。

## Result

在既有 `PostgreSQL integration` job 中接入 development PostgreSQL fixture / migration / 测试集，以及由 `docker/python-dev.Dockerfile` 构建并运行的真实 PDF renderer；保留 job 身份和其他 CI 检查，不构建或上传业务 APP 镜像。CI JUnit、实际环境身份和 renderer 本地 summary 分开放置，上传步骤在失败时仍尝试保存可获得的证据，不触碰 AI Evaluation 报告目录。

实施中修复并回归了复用 PostgreSQL 服务时的角色残留边界：CI fixture 创建的集群角色会在 development 初始化前随临时数据库一起重置，否则 development init 会重复创建 `chatbi_app` 而失败。最终本机同服务顺序验证 CI profile 5/5、development profile 56/56；`tests/scripts/test_ci_verification_workflow.py` 5 项通过。

本地 Verification：`./dev test all` 退出码 0，1206 total：1152 passed、54 skipped、0 failed、0 errors；报告 `reports/tests/20261015T154537Z-9f85b03-test-all-62eba8a46063.json` 将状态标记为 `incomplete`（如实反映 54 项 skipped），清理通过且源码起止 stable；Python 1019/1073、CI DB 5/5、development DB 56/56、packaged browser 69/69、development browser 1/1、renderer 2/2 均通过。`./dev check` 六步全过，报告 `20261015T155112Z-9f85b03-check-all-311da29766a0`。workflow YAML 解析、Ruff format / lint、文档与链接检查、`git diff --check` 通过。

托管验证：PR #86 的最终 CI run `38768884092` 中 8 项 required checks 全部通过；PR 于 `2026-10-15T16:28:38Z` 合并，merge commit 为 `f9f960797c5aef2d2d13779eca5677caa028a3d0`。初次 CI run `38767893615` 暴露 shallow checkout 缺少历史提交及不安全 XML 解析问题，已在 PR 内修复并由最终 run 验证。未运行真实 LLM 或业务验收。

Review：PASS；基线 `9f85b034bf996ee3c42786553cc96987c8484b34`；范围为既有 PostgreSQL CI job、development DB / renderer 接入、回归测试、Runbook 和全量验证中暴露的测试装配可靠性修正。What：保持 job 身份并补齐 development 数据库与真实 PDF 检查和失败证据上传；Why：普通 CI 覆盖本地关键软件套件且可追溯；Risk：复用 PostgreSQL 服务需显式清除先前 profile 留下的测试角色，已由顺序验证覆盖；Failure behavior：pytest、migration、renderer 或 image build 失败均保持非零，后置 artifact 仍尝试上传。最终审查无遗留发现；Correctness / Comprehension / Consistency / Testability / Architecture / Security 均通过。

Roadmap：形成原 candidate 时未修改 `docs/roadmap.md`；合并复盘发现目标仍被标记为“当前实施”，现由[路线图收尾 Spec](../../test-reliability-roadmap-closeout/spec.md)跟进更正。该目标未改变其他路线优先级。原 Ticket Commit：`a022faf0cbc78c14e053ce2728646092f08c6787`；汇总交付见 [PR #86](https://github.com/K999999999999/chatbi/pull/86)。

## Comments

依赖 Ticket 02 的数据库并发测试修复和 Ticket 06 的统一软件运行证据。

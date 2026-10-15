# 07 CI 接入关键数据库与 PDF 检查及证据

Status: open
Canonical Source: [Spec](../spec.md)、[Design](../design.md)、[草案](../tickets-draft.md#07-ci-接入关键数据库与-pdf-检查及证据)
Owner: 当前主 Agent
Change Profile: 小至中等 workflow 改动；自动门禁风险中等；复用现有 job 和本地软件套件。
Blocked by: 02, 06

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

Pending.

## Comments

依赖 Ticket 02 的数据库并发测试修复和 Ticket 06 的统一软件运行证据。

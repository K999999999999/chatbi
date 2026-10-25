# 删除未使用的根目录入口

## 目标与授权
用户明确要求先删除 config/ 示例和 .devcontainer/，该指令构成本小范围改动的实施授权；不含 Push / PR。基线：0e8a198，初始工作区干净。

## 范围与预期结果
- 删除 config/authorization-policy.example.json 和 .devcontainer/ 两个文件。
- 删除基础 Compose 中仅供该编辑器入口使用的 devcontainer 服务；保留 PostgreSQL、Qdrant、卷、端口及两个 Compose 文件。
- 删除退役入口的专用测试，保留同文件中的数据库 LF 换行检查；同步正式 Spec、Runbook 与项目讲解。
- 保留静态授权实现、测试注入方式及宿主路径映射兼容，不扩展成授权或开发脚本重构。
- Compose 是否合并仅提供研究建议，本次不合并。

## 验收与验证
- 两个目录及编辑器服务移除；既有开发启动及基础设施定义保持。
- 运行相关容器配置、开发入口、数据库脚本测试，文档检查与 Python 质量检查；执行当前上下文 Code Review 和 git diff --check。
- 不改变业务链路，无需真实 LLM 评测或业务验收。

## 文档与历史
当前事实同步 docs/specs/container-dev-environment.md、docs/runbook.md、docs/project-explained.md；历史 .scratch 结论保持，仅将两个历史文档内指向已删除文件的链接改为基线提交与退役说明，原文件可从 0e8a198 恢复。Roadmap 不涉及产品能力、优先级或里程碑变化，无需更新。其他动态文件的触发条件不适用。

## 已确认的 CI 修复范围
用户在依赖告警说明后确认将 Vite 8.3.2 升级至审计建议的 8.3.5，更新必要的前端依赖锁文件并纳入同一 PR #98。此确认覆盖实现、验证及同 PR 发布跟进；不修改其他直接依赖，不关闭或弱化安全门禁。验收增加 npm audit 无告警、前端与导出构建以及相关浏览器软件回归；初始候选 CI 7/8 通过，唯一失败为既有 Vite 依赖审计。

## 已确认的 Python 依赖修复范围
用户在六项 Python 依赖告警及兼容性说明后要求“那还是先处理这个吧”，确认先修复这些告警并完成 #98，不加入其他新改动。按审计建议更新 certifi 2026.10.19、filelock 4.2.1、langgraph-checkpoint-postgres 3.1.3、opentelemetry-api 1.45.1、pypdf 6.21.2、setuptools 84.1.0，并允许必要的 OpenTelemetry 配套依赖和 langgraph-checkpoint 4.3.0 升级。直接依赖提高安全版本下限，其他业务实现 / Contract 不变。验收增加 Python 依赖审计、状态持久化 / PostgreSQL、追踪与 PDF 相关回归；运行项目适用软件检查，AI Evaluation 与真实 LLM 业务验收不适用，因为未改模型、Prompt 或业务行为。

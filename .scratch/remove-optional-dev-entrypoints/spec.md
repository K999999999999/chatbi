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

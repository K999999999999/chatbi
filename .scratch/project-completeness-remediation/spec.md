# 当前项目运行与收尾修复

## 目标

修复全仓完整性检查发现的四项问题，使当前 `master` 候选能够在本机正确运行、诊断结果可信、交付状态文档一致，并以当前提交和资产身份完成适用验证。

## 范围

1. 将本机开发环境从已清理的旧审计 worktree 挂载切回当前仓库，重建 API 服务并确认业务数据卷保留。
2. 从当前已确认的 Semantic 与结构事实重建并发布 RAG 资产，确认 readiness 来源指纹匹配。
3. 修正 `doctor` 的 Web 探针目标 / Host 行为；添加回归测试，覆盖 Vite 拒绝内部 `web` Host 的现实场景。
4. 对齐 `docs/roadmap.md`、项目审计修复 Spec 和 Ticket 12 的当前完成状态，保留适用历史及其原候选绑定。
5. 运行完整 `./dev check`、`./dev test all`、Harness / 文档检查；在当前实现提交上运行三套 AI Evaluation、官方报告验收和隔离业务验收，记录费用、报告身份、清理与限制。

## 边界

- 不改变产品能力、公开行为 Contract、授权 / 数据 / 安全边界、评测案例或通过阈值。
- 本机服务恢复只使用当前 `chatbi-engine` Compose 项目；保留现有 PostgreSQL 数据及账号。仅在 `./dev build-rag` 的既有原子发布语义下更新索引。
- 远端 Push / PR / 合并未获授权；只做本地改动和 Commit。
- AI Evaluation 与隔离业务验收使用现有固定合成数据、模型参数与隔离资源；不清理日常业务资源。

## 验收

- API、Web、数据库、Qdrant、模型与匹配 RAG 索引均 ready；主机 API / Web 健康探测成功；旧 worktree 不再是当前 API 挂载来源。
- `doctor` 在开发 Compose 网络内将正常 Vite 服务判为 ready；不可达服务仍判为 not_ready。
- Roadmap、审计修复 Spec、Ticket 12、PR #88 实时状态与验收证据相符；文档链接检查通过。
- 完整质量检查和软件测试通过；三套 AI Evaluation 的当前 SHA / RAG 身份一致且官方验收通过；隔离业务验收无意外 skip，清理验证通过。
- 相关验证报告、最终 Review、Diff 检查和本地 Commit 完成。真实外部 Trace 收件如无法确认，明确保留为未知。

## 授权

用户在 2026-10-20 明确同意按完整项目检查提出的四项方案执行，包括本机 API / RAG 恢复、`doctor` 代码与测试修复、完成状态文档对齐，以及真实 AI Evaluation 和隔离业务验收。真实模型调用费用已在方案中说明。仅本地 Commit；无 Push / PR 授权。

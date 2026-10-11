# Design Review：ChatBI 新人项目导航

Date: 2026-10-11
Review target: `.scratch/project-navigation/spec.md`
Verdict: PASS WITH MINOR FIXES

## Findings

### 1. 新人理解程度缺少可复核的走查方式

- Evidence: Spec 验收条件原先要求新人理解用途、边界、功能、架构和链路，但没有定义如何观察或记录结果。
- Impact: 文档作者容易把自己的讲解补充当成导航本身完整，无法复核新人是否能独立找到入口。
- Recommendation / disposition: 增加由非导航文档作者独立执行并留存结果的走查清单，明确需要定位和说明的内容，不依赖口头补充。已写入验收条件 1。

### 2. Spec 阶段状态与已发生进度不一致

- Evidence: 用户已确认完整 Spec，设计审查正在进行，但文件头仍标记“待 Spec 确认及 Design Review”。
- Impact: 后续执行者会误判授权和工作阶段。
- Recommendation / disposition: 更新 Spec 状态并记录本审查结论。已完成。

## Review basis

- 导航以已存在的 Architecture、Product Scope、Specs、Designs、Acceptance、Runbook 和 Roadmap 为权威事实源，不复制完整 Contract。
- 新 clone 的启动 / 健康 / 确定性测试路径与现有 Runbook 可衔接；以隔离环境验证，保护 Stable 与用户数据。
- 文档移动受职责与证据约束，明确排除业务源码、运行资产、数据、模型、报告和日期化 Acceptance，风险和回滚范围可控。
- 功能与工程子系统的全量覆盖可在实施时通过源码、产品边界和事实文档盘点形成核对矩阵；没有未决架构、业务 Contract、权限或状态决策。

## Evidence sources

- `AGENTS.md`
- `docs/architecture.md`
- `docs/product-scope.md`
- `docs/runbook.md`
- `docs/roadmap.md`
- `.scratch/project-navigation/spec.md`
- 实际源码入口及 Markdown 本地链接检查结果（改动前通过）

## Next

Design Review 完成。进入 Ticket 草案和当前上下文 Ticket Readiness；不创建正式 Ticket，待用户确认拆分。

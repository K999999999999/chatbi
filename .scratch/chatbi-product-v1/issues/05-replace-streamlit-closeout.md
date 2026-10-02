# 05. 切换默认入口、移除 Streamlit 与完整 R1 收尾

Status: open
Owner: 当前主 Agent
Canonical Source: ../r1-spec.md、../r1-design.md、../r1-design-review.md、../r1-ticket-readiness.md


**Change Profile**：长期入口替换；中等迁移闭包；旧入口删除 / CI / 配置风险；完整 smoke / 回归 / 文档证据；同一最终 candidate，等待单独发布授权。

**Blocked by**：04。

### What to build

- 切换 README / Runbook / 启动脚本至 Vite / 打包网页，CI application smoke 验证新默认入口 / 登录，不再依赖 Streamlit health。
- 删除 Streamlit 活动代码 / 专属测试 / Python 依赖与 lockfile 解析结果，更新模块检查及其测试，保留历史 Spec / Acceptance。
- 同步正式 Product Scope、Architecture、Query API / Web Spec、Design、Acceptance、Roadmap 与当前工作记录。
- 最终核对全部 R1 代码、依赖、运行和证据；文档 / 历史报告不互相竞争或伪称当前候选通过。

### Acceptance criteria

- 新默认入口在新 clone 安装 / 开发 / 打包运行链路可复现，API-only / Bearer / SQLAdmin 仍有效；回退不会要求重置数据库。
- 活动源码 / 依赖 / 启动脚本 / CI / 文档中无失效 Streamlit 用法；历史记录允许保留但不是当前启动入口。
- 模块门禁继续覆盖新 Adapter、查询及核心边界，删旧文件后不读取不存在路径，不降低既有边界约束。
- 最终 npm / Python lock、类型 / lint / 构建、软件 / 集成 / 浏览器 / startup smoke / 依赖与安全检查完成；删除引起的行为变化重跑受影响验收。
- 最终 clean candidate 的真实 HTTP / Chrome AI 闭环按最终风险重跑或明确证明代码证据可复用；报告仍绑定实际被验证的提交，不把早期 dirty 结果或历史基线移植到最终 HEAD。
- Roadmap 只标记已完成 R1 事实，不声称图表 / 历史 / 流式或 R6 / R7 已完成。

### Owned files 与证据

- 删除 `src/streamlit_app.py` / `tests/streamlit/`；`pyproject.toml` / `uv.lock`；`scripts/start-dev.ps1`、`scripts/check_module_boundaries.py` 及测试；`.github/workflows/ci.yml` smoke；正式文档与 `.scratch/chatbi-product-v1/` 完成记录。
- 首轮 rg 已发现的消费者及实现阶段全仓库再核对清单；必要时扩充清单但不清理无关文件。
- 证据：完整 Diff / Review、Markdown 链接 / 模块门禁、构建与新入口 smoke、受影响回归 / 最终真实闭环、删除闭包检查；记录每项提交身份与结果。

**Migration / Rollback**：Contract / Cleanup。失败时修复新入口或恢复迁移中的旧入口；发布回退整份 known-good 代码 / lock / 配置，不删除数据库数据。无 Feature Flag / 灰度上线，本次尚不发布真实用户流量；未来发布按目标仓库授权流程执行。

**Done When**：R1 的代码、正式事实源、验证、Review、适用本地 Commit 全部完成，形成可审查 candidate；Push / PR 仍须说明最终范围、证据、风险和 Auto-merge 后另行取得授权。

## Result

尚未实施。

## Comments

2026-10-03 用户确认五项拆分并授权完整 R1 实施；不包含 Push / PR 发布。

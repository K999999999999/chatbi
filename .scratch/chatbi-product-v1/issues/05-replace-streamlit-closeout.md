# 05. 切换默认入口、移除 Streamlit 与完整 R1 收尾

Status: in-progress
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

默认入口切换与旧入口删除已实现，当前进行最终 candidate 验证 / 收尾。

- Streamlit 源码 / 专属测试 / Python 依赖及其独有传递包已移除；SQLAdmin 的 itsdangerous 显式锁定原 2.2.0。Vite 开发与打包网页的 README / Runbook / PowerShell / Dev Container 端口 / CI 同步；没有数据迁移或删除真实数据。
- 保留请求 / 链路编号展示，Cookie 查询的 CSRF 拒绝仍遵守既有 Trace / request_id Contract；新增 RED 证据为丢失编号，修复后相关 API / 观测 / 模块 30 项通过。非法 Origin 端口 / 空白 4 条 RED 后 GREEN。模块门禁移除旧路径读取并覆盖新增浏览器 Adapter，新增依赖拒绝 RED 后 GREEN。
- 默认全量软件 `python -m pytest`：617 passed / 15 skipped /139 subtests；移除的旧 Streamlit 测试由真实桌面 Chrome 行为用例与现有 API 测试覆盖，不降低业务校验。
- Chrome 打包17项、Vite代理1项通过；类型 / build、lock、格式 / CI lint、模块 / links / diff检查通过。最终表格形状补查和真实安全 reporter 清理核验加入后再跑最终浏览器矩阵。
- npm audit0 / pip-audit无已知漏洞；Bandit src / scripts中高风险0。CI required names保持8项，未Push，远端CI未执行。
- 隔离临时 PostgreSQL 的 CI profile5项、development profile19项通过；额外从干净数据库 migration → 首个管理员 → 正式 runtime → 打包网页 / Cookie登录 / 首次改密 / 重登 / 退出真实HTTP smoke通过，使用 scripts.smoke_web，与 CI 新入口一致。测试容器标签归属核实后清理；真实开发数据库未修改。
- Owned files 闭包补充：scripts/smoke_web.py、.devcontainer 5173端口、前端观测编号客户端与验收报告 build Hash / 账号清理核验，以及发现的 Observability / ADR / 多指标文档消费者。均为替换兼容和验证闭包，无新增产品需求。
- Source of Truth同步 Architecture / Product Scope / Query API / Web Spec / Design / Runbook及适用观测文档；历史 Acceptance / ADR过去决定保留，ADR新增当前入口迁移补记。
- Code Review将在最终Diff和验证完整后回填，真实候选复验 / R1完成状态尚未回填。

## Comments

2026-10-03 用户确认五项拆分并授权完整 R1 实施；不包含 Push / PR 发布。


最终本地 Code Review：PASS；Scope 为 BASE 1517189 至本切片完整 Diff，结合 d790317 至 R1 全部已提交实现复核。What：新网页默认入口替换与兼容 / 验证闭包；Why：R1 核心验收已通过，不长期维护双入口；Risk：身份、CSRF、单请求状态、旧入口删除、锁解析和运行脚本。Findings：旧 CSRF 拒绝丢失 request_id / Trace、非法 Origin 端口未失败、删除后的硬编码边界检查和签名传递依赖均已处理，相关验证通过。检查正确性 / 可读性 / 一致性 / 测试能力 / 依赖方向 / Secret与安全；没有未解决的实施问题。最终 browser17 + Vite1及 npm audit再次通过。剩余门禁为形成 clean candidate 后真实闭环复验与事实回填；本地发布授权不包含 Push / PR。

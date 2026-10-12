# 浏览器身份与状态隔离：整理前的过程记录

来源：`docs/designs/web-dialogue-v1.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# R1 实现设计

依据：[已确认 R1 Spec](../../../docs/specs/web-dialogue-v1.md)。状态：已确认设计，实现 / 入口替换与最终本地验收已完成（证据见 [Acceptance](../../chatbi-product-v1/history/acceptance--web-dialogue-v1-20261003.md)）；审查见 [Design Review](../../chatbi-product-v1/r1-design-review.md)。Owner：当前主 Agent。

## 1. 最小结构与运行入口

- `frontend/` 保存 React + TypeScript 页面、原生 CSS、原生 `fetch`、Vite 配置及 npm lockfile。R1 不增加路由框架、全局状态平台、图表库或 Markdown / HTML 渲染依赖。
- 前端分为浏览器 API 客户端、页面状态转换、登录 / 改密视图、问数 / 分析视图与结果展示。划分按知识职责，不能建立只透传调用的多层 Service。
- FastAPI 只新增浏览器身份 / CSRF Adapter 和打包文件入口；复用 `AuthService`、现有 `AuthorizedQueryService`、Conversation Store 与 Business Analysis。Domain 不新增前端依赖。
- 开发：Vite 监听 `127.0.0.1:5173`，将 `/api`、`/auth`、`/health` 代理到回环 FastAPI。浏览器始终使用相对 URL；Vite 不改写真实 `Origin` 来绕过来源校验。
- 打包：Vite 生成 `frontend/dist`；FastAPI 提供 `/` 与 `/assets`，只有配置目录中的构建文件可被读取，不能暴露源码、`.env` 或任意路径。
- API / 认证 / 管理后台 / health 路由优先，未知 API 和未知静态资源保持 404，不将 API 错误改成 HTML。R1 仅一个聊天页面，不需要全局 SPA fallback。
- 显式 `CHATBI_WEB_DIST_DIR` 配置构建目录；未配置则保留 API-only 能力，配置但没有有效构建时启动报错，避免把缺失前端当成功应用启动。
- 单实例单 worker 运行；前端打包入口不宣称已经完成 R6 的公网 HTTPS / 升级 / 回滚验收。

## 5. 有限等待与错误分类

- 客户端等待：认证 / 改密 / 退出 30 秒，普通问数 180 秒，经营分析 1200 秒；使用 AbortController，结束后根据已确认恢复规则处理。
- 预算依据是现有单次 LLM 最多 30 秒、Qdrant 默认 30 秒、四个顺序查询 Task 及既有重试。它是有限客户端等待选择，不是形式化服务器上限或生产 SLA；多个检索 / 本地处理 / 不同配置仍可能超预算。
- 后端合法成功 / 受控失败按原 Contract 显示；没有合法受控结果、网络错误或客户端超时均视为结果未确认。HTML 代理报错、畸形 JSON、错误模式结果、错误 ID、列 / 行形状不匹配不能当成成功。
- Cookie CSRF / 身份错误不做匿名回退；401 清理私有状态，403 显示拒绝并停止本次发送。不存在自动业务重发。
- 不增加后台轮询、保活、任务查询、取消协议或服务器总运行时限；这些改变需回到对应需求。

## 6. 工具与验证

本机已核实 Node `24.21.0` / npm `11.19.0`。npm 元数据核实的实施候选：React / React DOM `19.3.0`、Vite `8.3.2`、TypeScript `7.0.2`、`@vitejs/plugin-react` `6.1.1`、`@playwright/test` `1.63.0`。新依赖在实施时精确锁定，包含 plugin peer dependency 解析；如不兼容不得自动跨大版本升级，先重新审查。组合已按 lockfile 安装，类型检查、Vite 构建及桌面 Chrome 确定性用例通过；版本以 frontend/package-lock.json 为准。

- `package-lock.json` + `npm ci` 作为可复现入口；Node 使用 24 系列，CI 固定实际兼容版本。Vite 的 Node 要求已经核对。[Vite 官方文档](https://vite.dev/guide/)。
- TypeScript 类型检查、Vite 构建、前端状态 / 客户端确定性检查；后端现有 pytest seam 验证 Cookie / Bearer / CSRF / 配置 / 静态入口。
- Playwright 驱动桌面浏览器；最终 Chrome 验收必须使用 `channel: chrome`，不能把默认 Chromium 结果改称 Chrome。记录浏览器实际版本、OS、提交与构建身份。[Playwright 官方浏览器说明](https://playwright.dev/docs/browsers)。
- 确定性浏览器检查使用真实 HTTP / 账号 Session 和假的查询服务；真实 AI 浏览器验收使用同一页面与真实模型 / RAG / PostgreSQL，两者报告明确区分。
- 在现有 CI 的必需检查中加入 npm lock / 类型 / 构建 / 依赖审计 / 浏览器链路，保留既有 required check 名称，不调整远端 ruleset。现有 Python 和 Secret / Security 检查继续运行。
- 真正高风险的身份 / 查询 / 分析 HTTP 路径需真实闭环证据；正式 AI Evaluation 是否重跑按最终 Diff 与仓库基线规则判断，不继承新提交通过身份。
- 浏览器报告默认不保存带真实登录凭证、问题或结果的网络 Trace / 视频；验收记录只保留安全字段，真实业务截图另按数据范围确认。

## 7. Streamlit 替换闭包与回滚

Owner 为同一主 Agent。Expand：新增 Cookie 支持和网页，保留 Streamlit / Bearer；Migrate：查询 / 分析及浏览器验收覆盖旧核心入口；Contract：新入口 smoke 通过后删除 Streamlit。

已查到的消费者：`src/streamlit_app.py`、`tests/streamlit/`、`pyproject.toml` / `uv.lock`、README、Runbook、Architecture、Product Scope、Query API 文档、`.github/workflows/ci.yml`、`scripts/start-dev.ps1`、`scripts/check_module_boundaries.py` 及其测试。实施时再用 rg 核对全仓库，区分历史记录 / 验收与活动入口，不删除历史 Spec 或证据。

- 启动脚本与文档切换至 Vite / FastAPI；CI smoke 切换至构建后的网页 / API，并添加浏览器登录闭环，不仅验证 `/health`。
- 更新模块检查以覆盖新增 HTTP Adapter，并移除对被删除 Streamlit 文件的硬编码读取；不能为删旧文件而削弱查询 / Domain 依赖门禁。
- CI / 文档禁止新增 Streamlit 活动入口；历史文件允许注明“历史入口”。
- 无数据库业务数据迁移。Cookie / 页面层新增能力可回滚；完整发布回退到 known-good 版本及对应 lockfile / 启动入口，不删除数据库 volume / 账号 / 审计 / checkpoint。
- 删除阶段若新入口或兼容测试失败，停止删除 / 交付，修复新入口或恢复仍在迁移中的旧入口；不把带缺陷的替换标记为完成。

Revisit Trigger：真实需求要求跨站部署、多实例、移动端、历史续聊、通用恢复或更高访问规模时重新审查对应设计；不能直接加 worker 或拉长 TTL 代替新 Contract。


## 实施收尾核对

- Streamlit 已从活动源码 / 专属测试 / 依赖中移除，开发改用 Vite；打包入口和登录 smoke 已接入 CI，8 个 required check 名称保持不变。
- SQLAdmin 所需签名依赖 `itsdangerous` 显式声明，保留原 lockfile 的 2.2.0，不依赖 Streamlit 的传递依赖。
- 请求诊断保存 Header Trace ID 和 JSON request_id 于页面内存，展开显示；Cookie 查询的 CSRF 拒绝在既有 HTTP Trace 中返回，不进入业务链路。
- 非法 Origin 端口 / 空白启动失败；模块门禁覆盖 browser Adapter，继续禁止直接依赖查询 runtime / 数据库 / Provider。
- 真实验收每次先重新构建，报告记录构建文件 SHA-256；测试服务使用 SIGTERM，安全 reporter 在关闭后强制核对专用账号已禁用且无活动 Session，缺少清理证据即失败。

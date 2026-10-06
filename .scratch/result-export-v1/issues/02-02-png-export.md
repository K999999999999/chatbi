# 完整 PNG 导出与离线渲染

Status: completed; local candidate `88f122c`
Owner: 当前主 Agent
Blocked by: None; 01-xlsx-export completed at `111980d`

## What to build

从当前结果、历史和成果完整下载图表 PNG，使用与网页一致的认证图形事实。

## Acceptance criteria

共享纯 chart plan / renderer options；支持全部类目、图表类型、产品 / 因素与查询任务图；离线 bundle、manifest、本地字体、Playwright + Chromium 隔离；容器装配与开发源 hash 检查。

## Verification

- `uv run --group dev pytest tests/query_api -q`：176 passed、14 subtests；`uv run --locked python scripts/run_database_tests.py --profile development`：43 passed。导出 Runtime / 来源 / worker 和 PostgreSQL owner 投影回归通过。
- `npm run typecheck`、图表 / 来源 / 选择 / NULL 逻辑 7 tests、`npm run build` 与 `npm run build:export` 通过；`uv lock --check`、导出模块定向 Ruff、`git diff --check` 通过。受影响测试文件中既有 Decimal / import-order / unused-variable / exec lint 项单独排除，新增行无告警。
- 固定 Playwright 1.63 / Chromium 镜像使用 `--network none`、非 root `1000:1000` 与随仓库 seccomp profile 启动。通过真实 UI 登录 / 历史选择 / PNG 按钮 / HTTP 导出下载：1600×2203、192,473 bytes；独立检查所有 PNG chunk CRC 与完整解压像素流，18 个类别完整可见，中文、导出时间和表格可读。11 个浏览器请求全部本机，恶意 HTML / file / URL 标签未触发外部请求；成功下载后临时根仅余 `.runtime.lock`。
- 在同一受限 renderer 中分别完成 products、factors（所选 product_index）和已完成 task 图形的 PNG 生成与独立 chunk CRC / 尺寸检查。Manifest / 源码指纹覆盖 `frontend/src`、导出入口、Vite / TypeScript 配置及依赖清单；Docker Compose 只读挂载与最终构建 bundle 指纹一致。
- 视觉检查确认全部图形与说明表未被视口裁切。宿主完整前端 browser suite 因缺 Chromium / `libnspr4` 未通过；实际 UI→API→PNG 下载链路已在带完整依赖的隔离 API 镜像内真实执行并通过。数据库与浏览器测试使用独立环境，未停止或重建日常开发容器。
- Dockerfile 成功构建的验证镜像使用本机缓存基础镜像 `chatbi-python-dev:local`；默认 pinned Python base 的大 Torch wheel 下载遇 TLS 解密错误，未完成 clean-base 构建。项目依赖仍由 `uv.lock` 锁定；此环境差异不作为 clean pinned-base 构建通过的证据。

## Result

Implementation 和 Review PASS：PNG 根据 owner 当前可读的成功快照生成，完整复用共享 ChartPlan / 展示规则；外部网络和不完整图形 fail closed。修正了 worker `RLIMIT_NOFILE=64` 导致 Chromium network service 崩溃（上限改为 256）、PNG 页脚导出时间来源、网页 profile 轴选项回归、安全标题文件名及离线 bundle 未纳入 TypeScript 配置指纹的问题。Ticket 02 本地候选提交待本记录随后的状态提交补入；PDF / 隔离真实 Compose 仍未完成。

## Comments

本 Ticket owns vertical PNG slice of tickets-draft.md §02. Canonical Contract: ../spec.md; mechanism: ../design.md. User-confirmed XlsxWriter / Playwright + Chromium direction; use assets offline.

Migration / Rollback: 无数据迁移。依赖资源缺失时 PNG fail closed、01 XLSX 保持有效。若 Chrome sandbox / offline asset constraints infeasible，返回 Design Review，不禁用 sandbox 绕过。

# R5 成果导出阶段验收

Status: Ticket 01–03 的本地实现证据已记录；Ticket 04 隔离真实闭环尚未完成，R5 整体未验收。

本文件只记录 R5 各阶段可核验的候选和结果。上一 clean candidate `89bc7a6` 的真实浏览器流程通过，但独立 PDF 文本解析发现 Noto 将“民”“长”映射为部首码位，因此该候选没有通过完整验收。用户确认仅修正 PDF 字体；Ticket 04 完成后记录新的 clean candidate 身份及完整业务闭环。此前证据不代表发布或生产部署。

## Ticket 01–02：XLSX 与 PNG

- XLSX 候选 `111980d`：独立 XLSX 解析、Query API / Runtime / PostgreSQL owner 投影及隔离 Chromium 浏览器下载通过，详见本地工作项 `.scratch/result-export-v1/issues/01-01-xlsx-export.md`。
- PNG 候选 `88f122c`：完整 API / Runtime 回归、受限 Chromium 下载、PNG CRC / 像素完整性及视觉检查通过，详见本地工作项 `.scratch/result-export-v1/issues/02-02-png-export.md`。
- 两项结果绑定各自提交；不是后续 PDF 候选或最终 R5 候选的验证身份。

## Ticket 03：PDF renderer 与独立解析

上一 PDF Noto 候选的独立文本层缺陷已导致最终 Compose 验收失败；以下是本次字体修正的证据。最终 clean candidate 和全链路验收待补。

- 查询 API 回归：`uv run --locked pytest tests/query_api -q`，180 passed、2 skipped、14 subtests passed。宿主环境跳过的两项浏览器 renderer 用例在下述固定镜像内单独通过。
- 代码检查 / 构建：定向 Ruff、`uv lock --check`、`git diff --check`、`npm run typecheck`、`npm run build`、`npm run build:export` 均通过。两个 Vite build 报告既有 ECharts chunk 大于 500 KB 的提示。
- 隔离 renderer：镜像 `chatbi-result-export-t3:local`，image ID `sha256:47cf68a371143b19612aa5b76f3b01f0b51422f7290597054456744f9b2cc1eb`；以 `--network none`、非 root `1000:1000`、Chromium sandbox 和仓库 seccomp profile 运行 PDF renderer API 测试，2 passed。覆盖含 / 不含归因、100 行宽表、多页中文、空 / 失败 / 跳过 / 截断任务、非可信 HTML / file URL 作为文本及私有运行 ID 不进入文件。
- 独立 `pypdf` 解析：示例 PDF 为 16 页、292,045 bytes，SHA-256 `4f31becd445d195c9e892cfcca1b4fa71d9563a2d2bd9d6907af27f3b7077df9`。可抽取中文正文、完整归因产品 / 因素、宽表末列与末行、证据限制；私有 request / analysis ID 未出现。
- 人工检查了封面、归因页、证据表页和末页。页面预览及解析样本仅保存在本机忽略目录 `reports/browser-real-artifacts/result-export-v1/pdf-render-t3/`，不会进入 Git。
- 此阶段证据未覆盖真实用户会话下的 Web 按钮下载、Compose 持久化业务链路、重启及清理；这些留给 Ticket 04，不能据此宣称 R5 完成。

## 最终 R5 验收

待 Ticket 04 在 clean 本地候选上完成。需要记录浏览器登录、真实问数 / 追问 / 经营分析、三种文件的独立内容核验、重启后的历史 / 成果访问、权限 / 删除边界、资源回收、模型 / 数据 / RAG 身份和隔离资源清理。正式 AI Evaluation 是否复用按 R5 Spec 记录理由；导出不变更生成 / Retrieval / SQL Guard 行为时，不把历史报告改称为当前候选结果。

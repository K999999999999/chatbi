# R5 成果导出验收

Status: Ticket 01–04 与 R5 本地候选完整验收通过；最终 clean candidate 为 `71d72d2585306dc50a0b9ecca9ac1679d7ab45ff`；[PR56](https://github.com/K999999999999/chatbi/pull/56) 已合并（merge commit `367a42adf0043356463dce98f6d4976340b0df6f`），required CI 全部通过。生产部署和目标环境运行验收未包含。

本文件记录各阶段候选及最终真实闭环。历史候选证据仍绑定各自提交，不替代最终候选结果；生产部署与 R6 / R7 运行保障不属于此次完成范围。

## Ticket 01–02：XLSX 与 PNG

- XLSX 候选 `111980d`：独立 XLSX 解析、Query API / Runtime / PostgreSQL owner 投影及隔离 Chromium 浏览器下载通过，详见 `.scratch/result-export-v1/issues/01-01-xlsx-export.md`。
- PNG 候选 `88f122c`：完整 API / Runtime 回归、受限 Chromium 下载、PNG CRC / 像素完整性及视觉检查通过，详见 `.scratch/result-export-v1/issues/02-02-png-export.md`。
- 两项阶段结果绑定各自提交；最终候选 `71d72d2` 上再次通过了真实 XLSX / PNG 下载及独立内容解析，见 Ticket 04。

## Ticket 03：PDF 中文文本与渲染

- Noto PDF 的独立文本提取曾把“民”“长”映射为部首码位。用户确认只调整 PDF 正文字体；PNG 仍用 Noto Sans CJK SC，PDF 使用 WenQuanYi Zen Hei。
- Debian Bookworm 包固定为 Noto `fonts-noto-cjk=1:20220127+repack1-1` 和 WenQuanYi `fonts-wqy-zenhei=0.9.45-8`。PDF 字体包许可证为 GPL-2 with Font embedding exception 和 M+ FONTS License；镜像保留 Debian copyright 文件。来源见 [Debian fonts-wqy-zenhei](https://packages.debian.org/bookworm/fonts-wqy-zenhei) 与 [版权文件](https://metadata.ftp-master.debian.org/changelogs//main/f/fonts-wqy-zenhei/fonts-wqy-zenhei_0.9.45-8_copyright)。
- 运行 manifest 按图形 / PDF 角色记录字体包版本、精确 fontconfig 匹配路径及文件 SHA-256；运行时核验 family、版本、路径与 hash。最终 API 镜像记录 Noto SHA-256 `b76b0433203017ca80401b2ee0dd69350349871c4b19d504c34dbdd80541690a`，WenQuanYi SHA-256 `79c18ebe7b811951e8311bad7103ebeae8c337ed9988ea69e8a78a66cfe029b9`。
- `uv run --locked pytest tests/query_api -q`：181 passed、2 skipped、14 subtests passed。隔离 Chromium PDF renderer：2 passed，回归样例包含“居民消费和民生数据”。`uv run --locked ruff check ...`、`git diff --check`、`npm run typecheck` 与 API 镜像构建通过。完整 Review PASS。

## Ticket 04：最终 clean candidate 真实闭环

- Candidate：`71d72d2585306dc50a0b9ecca9ac1679d7ab45ff`，`git_dirty=false`；Playwright / Chromium `153.0.8010.12`。隔离 Compose 项目 `chatbi-verify-1791304486-55124` 完成真实登录、问数、同一会话追问、经营分析、文件下载、API/Web 重启及重启后历史 / 成果恢复。
- 浏览器捕获并通过独立 XLSX / PNG / PDF 解析共 12 个文件；导出期间触发的 execution POST 为 0。PDF 共 5 份，每份 6 页；`pypdf` 均能抽取“民”和“长”，不包含错误映射码位 U+2EA0 / U+2ED3。PNG CRC / 解码及 XLSX 内容检查也全部通过。
- 最终运行身份：API 镜像 `sha256:719bfd377591f6afd5256c28dda332353e1380335cae611f2459a3750b345df4`；Web 镜像 `sha256:2e71969a5e7b5f1a838985f0d97a033680dd611532063623a5e12d854aed763d`；数据库 Schema `mart_sales`；RAG current manifest SHA-256 `b3275830e77c04a9c47d38cf6e40f4a87ed6c459320212e0290f4544b114dced`。运行配置记录模型 `deepseek-flash`、Provider hostname `api.deepseek.com`、模型配置 SHA-256 `26159e7ad065073448460117eb24b7a4572f6f4e78eadff65dc0a11c052449fa`。
- 清理检查通过：临时账号已禁用、活跃 Session 为 0、导出临时根只保留权限为 `0600` 的锁文件、没有残留 worker；隔离容器、卷和网络已移除。原日常 API / Web 镜像 ID 未改变，服务保持 healthy。
- 原始机器报告和文件保存在 ignored 目录 `reports/browser-real-artifacts/result-export-v1/compose-1791305520/`；以下 SHA-256 / 大小来自独立 verifier 报告：

| 文件 | 来源 | 大小（bytes） | SHA-256 |
| --- | --- | ---: | --- |
| `r5-current-query.xlsx` | 当前历史轮次 | 6317 | `262fad2ee1a1e3d1bdc9542c37dbda7170fba7c7324eefaf67a6275ec16e84a3` |
| `r5-current-query-chart.png` | 当前历史轮次 | 117650 | `16107e47e5800ec81ab1c9c115eb484977e1e3c1080af43a6932e117c1051dde` |
| `r5-current-analysis.pdf` | 当前历史轮次 | 78427 | `2cf08fc46380dfefa25e8361cc4f562f3fc9b4bbbb87eb121d3e5a60636c3f76` |
| `r5-history-analysis.pdf` | 历史轮次 | 78426 | `09b4f7045214ed1d0a34ca31bbf7ac5d92093a82cd404af9e8e4169061ddeb19` |
| `r5-saved-analysis.pdf` | 保存成果 | 78478 | `b523b2304cb297a52382f2ef556f60a5a0be696e720a13b5a8166c7e011aa0c7` |
| `r5-saved-query.xlsx` | 保存成果 | 6685 | `4be6984d49fa22b4a61b875e375ac1174d7280dea20f992db4098730a02a272f` |
| `r5-saved-query-chart.png` | 保存成果 | 74577 | `09f93b2bc6cef3f95440922999cd36c4d399d113d65e8f1ba56a15f678907f6b` |
| `r5-restarted-history-query.xlsx` | 重启后的历史轮次 | 6441 | `f106b77f54a0bfe9a0ba4ec117134335324681daf61b62d23d49b45d263ecbaf` |
| `r5-restarted-history-analysis.pdf` | 重启后的历史轮次 | 78431 | `273b10e6c86defe040f6361698ed31b9f232320c10a2262831640b1ef34e54c3` |
| `r5-restarted-saved-analysis.pdf` | 重启后的保存成果 | 78484 | `a67191e4ccf797141efafa0e04fe2b97adf0caadf6c0db2bcd3095f0979e8e4a` |
| `r5-restarted-saved-query.xlsx` | 重启后的保存成果 | 6688 | `8d547d2ec1b6f3fec0994a6341df16ddd307b63091659c968ca041cf5f179f4a` |
| `r5-restarted-saved-query-chart.png` | 重启后的保存成果 | 74508 | `90c12919f28ee8463207f7d8359a3ecb1844dc00723590e70f69c97f0a08fead` |

## Evaluation 与发布范围

未重跑 AI Evaluation：R5 只从已提交快照导出，不更改模型生成、Retrieval 或 SQL Guard 行为；本次真实问数仅用于端到端验收。历史 Evaluation 仍绑定其原报告候选，不迁移为 `71d72d2` 的新结果。R5 本地候选实现和验收完成后，经 PR56 合并至 `master`；这不构成生产部署或目标环境验收。

## Linux Chromium 文件名补充核验（2026-10-10）

隔离浏览器运行 `20261009T170425Z-444d837d` 使用 Chromium `153.0.8010.12`；12 次 Blob 下载的 `suggested_filename` 均为 `download`，但文件内容与格式解析通过。对照实验发现浏览器容器未设置 `LANG` / `LC_ALL` 时中文保存名会退化；同一 Chromium 在设置 UTF-8 locale 后，Blob `download` 属性和 HTTP `Content-Disposition` 的 UTF-8 `filename*` 均保留中文名。前后端导出实现已经提供并解析 UTF-8 文件名，因此根因是浏览器验收环境，不是 R5 文件内容或导出功能。

修复在 `docker/node-dev.Dockerfile` 的 browser 阶段设置 `LANG=C.UTF-8`、`LC_ALL=C.UTF-8`，并由 `scripts/verify_container_dev.sh` 显式传给浏览器容器。构建后的 Chromium `153.0.8010.12` 报告 locale charmap `UTF-8`；Blob XLSX 与 UTF-8 `filename*` PNG 的隔离下载探针均得到完整中文 `suggestedFilename`。既有运行报告仍保留原始结果，不改称在该 locale 下验收通过；本补充不改变 R5 产品 Contract 或 PR56 的历史身份。

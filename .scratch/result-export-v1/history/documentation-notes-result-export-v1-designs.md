# 导出精度、渲染隔离与回收：整理前的过程记录

来源：`docs/designs/result-export-v1.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# R5 成果导出实现设计

Status: 基于已整体确认 Spec 的实现设计；Design Review PASS；Ticket 01–04 与最终 clean candidate `71d72d2` 的实现 / Review / 验收均已完成；[PR56](https://github.com/K999999999999/chatbi/pull/56) 已合并（`367a42a`），required CI 全部通过。生产部署未包含。
Baseline: `ee92acaa7998749d46b57d85611ec69ab14948b1`
Authority: [Spec](../../../docs/specs/result-export-v1.md)。本设计落实 Contract 内的机制，不扩大格式、数据范围、部署形态或业务边界。

## 1. 用例与依赖

Export Application 位于既有 `query_api` Application 边界：认证授权、选择持久化成功来源、确定性校验格式 / 图形选择、获取额度、调用文件生成 Port、交付前重新检查来源与身份。HTTP Adapter 只负责 DTO、CSRF、响应与断连通知。Control DB Adapter 提供 owner 限定的只读来源投影，文件 Adapter 隐藏 XlsxWriter、Playwright、进程和临时文件。Domain / Online Query 不依赖导出 SDK，不触发 query / analysis execution。

当前 XLSX Port 为 `generate(owner, document, cancelled) -> ExportArtifact` 加 runtime 生命周期；Document 是只含公开快照与导出时间的纯 JSON 数据，Artifact 只暴露受控临时文件路径、大小和单调时钟 deadline。子进程句柄、Request 和数据库对象不跨文件 Adapter 边界。后续格式复用该 Port 和 Runtime，不为每一种格式增加 Service / Manager / Repository。App lifespan 装配与启动 Runtime，shutdown 时终止活动进程并回收任务目录。

不新增持久化导出任务、队列、数据库表或 migration。不修改 R4 execution 状态 / 额度。若实施发现此假设不成立，先回到设计审查。

## 8. 替代方案、验证与回滚

比较：浏览器生成文件减少服务端依赖，但无法独立证明当前权限与资源额度，不满足已确认服务端生成；Python 重建全部图形 / PDF 可减少浏览器运行成本，但复制 ECharts / 归因规则，增加语义漂移与验证范围。选择已确认的服务端 Chromium + 共享纯展示规则，独立进程只为确定性终止外部运行依赖，不新增任务基础设施。

无迁移，撤回新增路由 / UI / Adapter 并回退构建依赖即可回到既有代码；已下载文件无需处理，历史 / 成果无变更。负责人为当前实施 Agent，未来因运行资源成本、中文 / 图形正确性或部署平台变化而复查技术决策。

验证 seam：Application 注入 fake SourceReader / FileGenerator / 当前身份回调和时钟；runtime 用可控子进程故障验证进程组 / 超时；Control DB owner 投影独立 PG 集成；共享 option 两种 profile 与 manifest 固定输入测试；独立文件解析器检查原值 / 中文 / 全部分类 / 页数和引用；Playwright 浏览器实际下载；真实 Compose 检查 sandbox / 字体 / 资产与断连 / 重启清理。最终 Acceptance 按 Spec 覆盖正常 / 边界 / 失败和未运行项。

Reference: [XlsxWriter Worksheet](https://xlsxwriter.readthedocs.io/worksheet.html)、[Workbook](https://xlsxwriter.readthedocs.io/workbook.html)、[Microsoft Excel 规格与限制](https://support.microsoft.com/en-us/excel/excel-specifications-and-limits)、[Playwright Page](https://playwright.dev/python/docs/api/class-page)、[Noto 使用说明](https://notofonts.github.io/noto-docs/website/use/)、[Debian fonts-wqy-zenhei](https://packages.debian.org/bookworm/fonts-wqy-zenhei)、[WenQuanYi Debian copyright](https://metadata.ftp-master.debian.org/changelogs//main/f/fonts-wqy-zenhei/fonts-wqy-zenhei_0.9.45-8_copyright)。文档能力不冒称当前候选运行已验证。

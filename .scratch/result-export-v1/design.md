# R5 成果导出实现设计

Status: 基于已整体确认 Spec 的实现设计；Design Review PASS；Ticket 01–04 已在最终 clean candidate `71d72d2` 完成实现、Review 与验收；未授权远端发布 / 部署。
Baseline: `ee92acaa7998749d46b57d85611ec69ab14948b1`
Authority: [Spec](spec.md)。本设计落实 Contract 内的机制，不扩大格式、数据范围、部署形态或业务边界。

## 1. 用例与依赖

Export Application 位于既有 `query_api` Application 边界：认证授权、选择持久化成功来源、确定性校验格式 / 图形选择、获取额度、调用文件生成 Port、交付前重新检查来源与身份。HTTP Adapter 只负责 DTO、CSRF、响应与断连通知。Control DB Adapter 提供 owner 限定的只读来源投影，文件 Adapter 隐藏 XlsxWriter、Playwright、进程和临时文件。Domain / Online Query 不依赖导出 SDK，不触发 query / analysis execution。

当前 XLSX Port 为 `generate(owner, document, cancelled) -> ExportArtifact` 加 runtime 生命周期；Document 是只含公开快照与导出时间的纯 JSON 数据，Artifact 只暴露受控临时文件路径、大小和单调时钟 deadline。子进程句柄、Request 和数据库对象不跨文件 Adapter 边界。后续格式复用该 Port 和 Runtime，不为每一种格式增加 Service / Manager / Repository。App lifespan 装配与启动 Runtime，shutdown 时终止活动进程并回收任务目录。

不新增持久化导出任务、队列、数据库表或 migration。不修改 R4 execution 状态 / 额度。若实施发现此假设不成立，先回到设计审查。

## 2. HTTP 与来源

POST `/api/v1/result-exports`，同源 Cookie 写请求检查现有 CSRF；新能力仅服务已有本地账号和 owner 隔离的历史 / 成果，旧同步 Query API 不迁移。

严格 request body，拒绝未知字段：

- `source` 判别联合：`history_turn` 带 history_id / turn_id；`saved_result` 带 saved_result_id。编号采用 UUID，不能提供 owner、SQL、原始值、HTML、URL、文件路径。
- `format` 为 xlsx / png / pdf；xlsx 只接受查询快照，pdf 只接受完成分析快照，png 接受合法图形。
- PNG 的选择为确定性 `chart_id`、适用 line / bar 类型、因素图 product_index；查询 chart_id 对应共享 ChartPlan 生成身份，分析图为 products / factors / task:<task_id>:<chart_id>。索引 / 图形身份从服务端快照派生的图形集合核验，不能直接接受客户端 option。任务图仅在已有 R2 展示规则支持时可用。
- 非 PNG 请求禁止图形选择字段。默认文件名由服务端安全地生成，采用短标题 / 固定类型与导出时间；剔除路径与控制字符，响应使用规范的 UTF-8 Content-Disposition。

成功响应为一种完整文件，不提前发送文件头 / 文件字节。Content-Type 按格式、`Cache-Control: no-store`、`X-Content-Type-Options: nosniff`。失败使用既有 request_id / error_code / error_message JSON：认证 401、权限 403、不可用来源 404（隐藏不存在 / 他人 / 删除差异）、选择或不支持格式 422、超额 429、文件超限 413、生成超时 504、依赖 / 存储不可用 503；不暴露原异常 / 路径。

SourceReader 复用 HistoryStore 的 owner 查找语义，用纯 DTO 提供 kind、成功状态、快照、原问题、源时间、标题和稳定源指纹。历史查询以所选 turn 的 snapshot / question 为准；分析以 envelope.original_question 为准；成果以其独立 envelope.source_question / original_question 为准。旧查询成果缺 source_question 时用明确的来源问题未知，不依赖原历史或 title 推断问题。

HistoryTurn.completed_at 在只读导出投影从底层列取得，不改变既有公共历史 DTO。旧成果没有原完成时间时写“原结果完成时间未保存”，另列成果保存时间，禁止把 created_at 替代原结果时间。历史删除后独立成果继续读取自身。新导出不修改已存 envelope 或业务口径。

## 3. 权限与竞态裁决

受理时 authenticate → 当前查询权限 authorize → owner 限定读取 → snapshot 版本 / 成功与选择校验 → 导出额度；任何步骤失败不进入 renderer。运行开始固定源内容及 hash，重命名或新成功轮次不改变本次内容。

生成完成后、发送第一个响应字节前重新 authenticate / authorize，重新用原来源身份查 owner 可读性与源快照 hash。失败时丢弃文件；不能只用受理时 AuthContext。新结果追加不否定旧成功 turn；成果重命名不否定固定快照；源被删或身份失效则拒绝交付。

最后一次成功重鉴权和重新读源组成文件交付的可观察裁决点：裁决前已生效的删除 / 撤权必须拒绝，裁决之后的删除 / 撤权与已开始下载等价，不追溯撤回字节。不得声称能原子锁住所有认证状态与网络交付；不持有数据库事务跨渲染 / 下载。测试以受控同步点验证裁决前后的行为。生成期间若客户端断连立即终止任务，避免等待后交付；不自动重试。

## 4. XLSX 保真

两个工作表固定为“原始数据”和“结果说明”。原始数据保留全部列 / 行及顺序；可信名称优先，不保证名称唯一，说明表按列序号绑定原始字段。

- JSON bool 显式 boolean；JSON int / float 仅在有限、最多 15 位有效数字且落在 Excel 普通单元格数值范围（零或绝对值 `2.2251E-308` 至 `9.99999999999999E+307`）时写 number，否则按原值文本写入并在说明表记录原类型 / 值。精度判定使用 `Decimal(str(value))`，不先经二进制浮点舍入再计数。
- 原始字符串默认 write_string，不根据数字外观推断类型；已认证 metric 的十进制字符串只有通过相同精度规则才可写 number，并在说明表保留该单元格原字符串和 JSON 类型。高精度 / 长整数 / dimension 编号保持文本，不能浮点预处理后再决定。
- NULL 与空字符串分别在数据表显示 `〈NULL〉` / `〈空字符串〉`，说明表为每个特殊单元格记录坐标、原 JSON 类型和值；真实同名字串记录 string 类型，避免标记冲突。JSON 零保持数字 0。所有发生文本 / 数字转换的单元格同样记录原类型及原词法值；从文件可确定性还原 JSON 单元格。
- Workbook 禁用 strings_to_formulas / strings_to_urls / strings_to_numbers；只显式调用类型 writer，不允许客户端公式。数字格式只控制显示，原值保真信息不舍入。
- UTF-16 单元格长度、行列上限、非法字符与库返回错误逐项检查；说明表自身也受检查。过长文本无法完整写入时返回格式无法完整表达，不利用库自动截断。zip 完整性、关键工作表及行列数量验证后交付；OOXML 使用 `defusedxml` 严格拒绝 DTD、实体与外部引用，非法或危险 XML fail closed；内存外临时文件仍遵守清理。

精度、NULL 与冲突标记的验证用独立 XLSX 解析器读取类型与说明表还原原值，禁止只复用 writer 内部判断作为 oracle。

## 5. 共享图形与文件模板

既有 ChartPlan、resultMetadata、numberFormat 与归因图形事实保留为可信快照到展示的规则。提取现有图形 option 生成与归因 plan 为无 React 生命周期的纯函数，提供 web / export 展示配置；网页既有行为回归不变。Export bundle 使用相同 TypeScript 模块与 ECharts，独立入口，不读取 App / Cookie / API，不复制 Python 图形语义。

导出 profile 禁用 dataZoom / scroll legend / animation；所有 series 可见，分类全部包含，长标签按测量换行。单图按完整数据计算画布和说明块，保持图表类型 / factors 产品选择。PNG 标准宽度 1600 CSS px、scale 1；图高动态，像素总量以 4000 万为渲染保护上限；若完整可读图形无法在此上限表达，则明确图形超出导出资源限制，不删除标签 / 分类。缺失时段和 NULL 仍使用既有安全规则。

PDF 使用专用 HTML，A4 自动分页、正文可选取、标题与页码、重复表头；不截屏整页当作 PDF。宽表按列拆分为带原行号 / 列号的连续表块，长单元格可换行 / 分页，不能 CSS overflow 裁切。产品和因素图按可读分组分页，重复上下文 / 范围说明，组合后包含全部已返回归因；仍不获取未返回产品。引用任务附录按引用身份固定排序，failed / skipped 保留适用限制，不冒充有结果。

模板在 document.fonts.ready、全部图形 finished、尺寸 / overflow 检查完成后才发布 ready manifest。Manifest 记录输入 hash、所有应展示 block / chart / row 标识及数量；Application / Adapter 校验预期 coverage 再截图 / PDF。任何异常、未 ready 或不满足完整性均失败。最终格式头 / zip / PNG 尺寸 / PDF 可打开检查是必要检查，不能以 manifest 替代独立内容验收。

PNG 图形继续使用 Noto Sans CJK SC；PDF 正文改用随应用安装的 WenQuanYi Zen Hei。独立 PDF 文本解析在 Noto 输出中发现“民”“长”被映射为部首码位，用户确认只为 PDF 修正字体，以保持可读且可搜索 / 复制的中文文本。Debian Bookworm 锁定 `fonts-noto-cjk=1:20220127+repack1-1` 与 `fonts-wqy-zenhei=0.9.45-8`；Debian copyright 记载 WenQuanYi Zen Hei 使用 GPL-2 with Font embedding exception 和 M+ FONTS License，保留镜像内版权文件。运行 manifest 分角色记录字体包版本、fontconfig 匹配路径和 SHA-256，并在导出时校验路径与 hash；任一字体缺失 / 不匹配时视觉导出受控不可用，不依赖外部网络或静默替代。版本信息见 [Debian Bookworm fonts-noto-cjk](https://packages.debian.org/bookworm/fonts/fonts-noto-cjk)、[fonts-wqy-zenhei](https://packages.debian.org/bookworm/fonts/fonts-wqy-zenhei) 与 [WenQuanYi Debian copyright](https://metadata.ftp-master.debian.org/changelogs//main/f/fonts-wqy-zenhei/fonts-wqy-zenhei_0.9.45-8_copyright)。

## 6. 进程、额度与清理

ExportRuntime 在 API 进程内以线程安全 / async 安全原子计数维护 owner 1、global 2，无队列。获取额度后开始 60 秒 wall-clock 总预算，包含启动、生成和交付前检查；超额不启动 worker。

所有格式都运行于单独 OS 子进程及进程组，由父进程 watchdog 管理。只传经过剥离的公开 Document / Selection 与受控资源位置，清理 env（无 .env、账号 Cookie、Token、数据库密码或 LLM Key），不继承连接句柄。子进程以非 root 运行，禁 shell 参数拼接，使用 argv；任务目录 0700、文件 0600，位于应用专用临时根。

Playwright 创建全新 context，不保存登录 / storage_state，加载父进程提供的固定模板 / bundle / 字体；仅内存映射固定内部 origin 资源，不启真实监听端口。route handler 默认拒绝所有 URL，仅固定资源精确白名单由 fulfill 提供；禁 service worker、downloads、WebSocket、弹窗及 file 导航。数据通过固定函数参数传入，以 textContent / React 文本节点写出；禁止输入控制 markup / style / option callback，CSP 只允许应用固定资源。隔离目标是确定性数据渲染和凭证隔离，不把 route 拦截声称为 OS sandbox；保留 Chromium sandbox，具体 Linux 支持在安装和真实容器验收核验，禁止靠 --no-sandbox 绕过未满足的安全条件。

文件输出在任务目录内，父进程验证路径 / 普通文件 / 大小，不允许 symlink 或调用方路径。设置进程文件大小保护和父进程大小检测，输入最多 5 MiB、输出最多 20 MiB、PNG 像素上限和 DOM / 图表数量由源范围控制；不等待无限 stdout，工作进程只输出有界状态 / manifest，不输出业务值或原异常。

正常完成先关闭 context / browser、等待进程退出。超时 / 断连 / shutdown 由 watchdog 终止整个进程组，必要时强制 kill 并 wait；不能仅取消 await 或释放 semaphore。额度 lease 保留至 worker 确认退出且文件发送 / 失败清理结束，慢下载期间仍占额度，避免已生成文件无限堆积；父进程监听断连并显式关闭响应文件和删除目录，不仅依赖正常发送后的后台回调。活动输出文件总量因而最多 2 × 20 MiB，不计尚在生成过程的有界临时开销。生成 60 秒预算不当作客户端网络性能承诺。当前无持久任务，重启不恢复导出。

Runtime startup 通过单进程服务约束取得临时根清理所有权；只清理本应用专用根中的已退出旧实例目录，不扫描 / 清理 /tmp 其他文件。worker 对父进程退出做 liveness watchdog，父进程意外死亡仍终止 renderer；正常 shutdown 显式 wait。真实验收须证明无孤儿进程 / 文件 / 永久额度，不能仅推断 init:true 已解决。

## 7. 构建与运行装配

Python dependencies 新增 XlsxWriter / Playwright / `defusedxml`，dev verification 使用独立 XLSX / PDF / PNG 解析工具，uv.lock 固化；Chromium build 与 Playwright 版本配套。

单独 Vite export build 将 HTML / JS / CSS 打包为自包含 / 静态已知资源 bundle，manifest 绑定源码 / 依赖 hash。不新增运行时 Node 服务。Python 开发镜像增加 Node 构建 stage，COPY bundle 到 `/opt/chatbi-export/assets`，安装浏览器到固定只读位置，并按锁定版本安装 Noto 与 WenQuanYi：前者供 PNG 图形使用，后者供 PDF 正文使用；现有源码挂载不能遮盖这些资产。

本地开发增加显式生成 export bundle / 安装 browser 与字体步骤。改共享图形规则后必须重建；manifest 比对失败时只拒绝导出，保留既有 query / history 服务，不能偷偷使用旧图形资产。开发 Compose 给 API 增加 export build 源文件（frontend/src、相关构建配置与 package lock）只读挂载到专用校验位置；运行时 hash 与 bundle manifest 比对，用于检测热更新代码和镜像内资产不一致，不服务这些源码，也不在请求期间运行 npm。非开发装配使用同一打包资产 manifest。当前 XLSX runtime 在 startup 检查私有根和单进程锁；检查失败时记录导出不可用，Query API 仍启动，导出请求受控返回 503 并 fail closed。Runbook 描述新依赖、构建、重建、缺失资源诊断和 rollback。

不使用运行中 Vite 服务器、public Web URL 或 CDN。这满足 Compose 中 API 不挂 frontend 且 CHATBI_WEB_DIST_DIR 为空的事实；R6 正式生产镜像仍不在本目标范围。

## 8. 替代方案、验证与回滚

比较：浏览器生成文件减少服务端依赖，但无法独立证明当前权限与资源额度，不满足已确认服务端生成；Python 重建全部图形 / PDF 可减少浏览器运行成本，但复制 ECharts / 归因规则，增加语义漂移与验证范围。选择已确认的服务端 Chromium + 共享纯展示规则，独立进程只为确定性终止外部运行依赖，不新增任务基础设施。

无迁移，撤回新增路由 / UI / Adapter 并回退构建依赖即可回到既有代码；已下载文件无需处理，历史 / 成果无变更。负责人为当前实施 Agent，未来因运行资源成本、中文 / 图形正确性或部署平台变化而复查技术决策。

验证 seam：Application 注入 fake SourceReader / FileGenerator / 当前身份回调和时钟；runtime 用可控子进程故障验证进程组 / 超时；Control DB owner 投影独立 PG 集成；共享 option 两种 profile 与 manifest 固定输入测试；独立文件解析器检查原值 / 中文 / 全部分类 / 页数和引用；Playwright 浏览器实际下载；真实 Compose 检查 sandbox / 字体 / 资产与断连 / 重启清理。最终 Acceptance 按 Spec 覆盖正常 / 边界 / 失败和未运行项。

Reference: [XlsxWriter Worksheet](https://xlsxwriter.readthedocs.io/worksheet.html)、[Workbook](https://xlsxwriter.readthedocs.io/workbook.html)、[Microsoft Excel 规格与限制](https://support.microsoft.com/en-us/excel/excel-specifications-and-limits)、[Playwright Page](https://playwright.dev/python/docs/api/class-page)、[Noto 使用说明](https://notofonts.github.io/noto-docs/website/use/)、[Debian fonts-wqy-zenhei](https://packages.debian.org/bookworm/fonts-wqy-zenhei)、[WenQuanYi Debian copyright](https://metadata.ftp-master.debian.org/changelogs//main/f/fonts-wqy-zenhei/fonts-wqy-zenhei_0.9.45-8_copyright)。文档能力不冒称当前候选运行已验证。

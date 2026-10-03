# R2 结果解释与可视化验收（2026-10-04）

## 结论与候选身份

本地R2完整范围已通过适用验收和当前上下文Code Review。未发布PR，不代表生产部署或全套AI Evaluation完成。

- 基线：`f182cf369217e7775c756101f45baff0ec301f44`。
- 最终代码候选：`64f29a99a9c0187a767e28e8f8cf72cd3988375e`，branch `feat/result-visualization-v1`。
- 正式真实容器报告：`commit=64f29a99a9c0187a767e28e8f8cf72cd3988375e`、`git_dirty=false`、`status=passed`、`suite_status=passed`；开始时间UTC `2026-10-03T18:20:00.506Z`。
- 原始证据本机ignored路径：`reports/browser-real/result-visualization-v1-64f29a9.json`；SHA256 `275ad6615df6091b8514b365a70f057038dc2eb05f465e8385e4d210d695c209`。含业务结果的原始报告不进入Git，新clone不自动具备；本文公开安全摘要。
- 后续收尾提交只修改验收/roadmap/工作记录；没有代码、Contract、资源或依赖变化时复用以上候选证据，不把报告重标成收尾HEAD。

## 覆盖与结果

| 层级 | 命令/范围 | 结果 |
| --- | --- | --- |
| 软件 | `uv run --locked python -m pytest -q` | 641 passed，15 skipped，139 subtests passed；后续只补网页舍入提示，Python未变，证据仍适用 |
| 默认Playwright | `npm run build`后`npx playwright test --reporter=line`，Chrome桌面1440×1000 | 33 passed：24项浏览器行为/故障注入，9项格式/解码/图计划纯函数 |
| 开发代理 | `npm run test:dev` | 1 passed；登录、问数、分析、退出经实际Vite同源代理 |
| 实际容器 | `scripts/verify_container_dev.sh real`，显式真实LLM/业务只读数据/RAG | 2项真实容器测试通过：源码挂载热更新，以及完整业务闭环；脚本退出0 |
| 构建与静态 | npm typecheck/build，uv lock，compileall，Ruff format/check，Markdown链接，模块边界，bash语法，Diff检查 | PASS；ECharts动态模块约580kB，build有大小提示，非构建失败 |
| 依赖与安全 | `npm audit --audit-level=low`、pip-audit、`bandit -r src scripts -ll` | npm/Python均0已知漏洞；Bandit medium/high为0，59条low属现有不阻断层级 |
| Code Review | [记录](../../.scratch/result-visualization-v1/code-review.md) | PASS；无独立Agent、无新增用户Review阶段 |

15个跳过项沿用环境显式开关，包含独立PostgreSQL开发/数据库指纹/数据库及模型服务集成入口；未将跳过计为通过。真实Compose/PostgreSQL/RAG/模型链路由本次专用验收覆盖，不能替代所有可选Integration或Golden Evaluation。

### 确定性边界

实际查询服务证明：公式及固定条件认证，不信别名；误导别名保持未知；年月是一个逻辑分组而列分别为年份/月；完成日期连接角色校验；缺年份不猜时间；隐藏分组不能显示总体卡；局部未知、损坏展示属性局部降级；HAVING范围partial；额外JOIN谓词仍由既有Guard拒绝且不访问数据库；快照不能被调用者修改。

API旧响应不多出null字段，可选说明兼容；Task执行/API/实际JsonPlusSerializer与旧字段集合Checkpoint恢复兼容；新增说明不进入报告模型提示。

网页覆盖：高精度字符串金额、千分位/元/百分比/计数，编号不格式化，NULL/零/空字符串，原值及极小非零舍入提示；图表/表格同显与独立收起、切图不请求；时间排序而表格不改序、缺月/NULL断点、单点、不安全坐标、重复分组、复杂维度、未知说明与空结果降级；100行截断图表/表格共同提示；图形模块失败保留表格；恶意文本不执行；产品选择不重查、成本负贡献、无变化/新增/退出/缺因素/省略产品及证据不完整提示；R1登录/CSRF/过期/换号/迟到响应/两模式/失败恢复继续验证。

### 正式真实业务结果

1. 2025年2月人民币净销售额问数与独立只读SQL一致；同一会话追问2025年3月一致，可信单位CNY和实际月份范围正确。
2. 2025年按月净销售额、毛利、毛利率共12行，与独立SQL逐行逐指标一致；说明complete，两个图单位CNY/ratio，其中CNY图含两个系列；图表、表格和类型切换有效。
3. 2025年按产品线净销售额与成本共4行，与独立SQL一致；说明complete，CNY同图两个系列。
4. 2025年3月对2月毛利分析与独立SQL任务证据及既有确定性归因参考一致，变化方向increase；4任务完成且未截断，4份说明均complete；产品/因素图、贡献表和任务证据有效。
5. Python重载/Vite热更新通过。热更新阶段单独记录`experiment_dirty=true`，结束恢复原文件；正式启动及结束工作区clean，未将实验修改混入候选。
6. 停止并重启后业务参考和RAG身份保持；现有业务数据、用户、持久卷与模型资产保留。

## 运行资源与清理

- 目标：本机Compose Vite→FastAPI→PostgreSQL/Qdrant，Chrome `153.0.8010.12`。
- 模型：`deepseek-flash`，provider host `api.deepseek.com`；Embedding CPU。
- 模型config SHA256：`26159e7ad065073448460117eb24b7a4572f6f4e78eadff65dc0a11c052449fa`。
- RAG current manifest SHA256：`0fb107ab3a5fc9dca1f828625bd9b46d8f15fde8d5f2d15cb94dbbe04616a08e`；Schema `mart_sales`。
- API image ID：`sha256:f782c2e08af701cd854ec0a3205dc775e67de8ad8ad2ae632d160292e03778d1`。
- Web image ID：`sha256:72844b8e4ca7d172bacece8e027eaf34a20b79e20204c841bf1dcf9bfdb046df`。
- Browser image ID：`sha256:034d766e7e6a327eeaec0e3787012cc73828739abde37768c58ffe2adbd7b694`，正式结束后本机核实。
- 专用验收账号`disabled=true`、`active_sessions=0`，临时`credentials.env`已移除；原账号不变。应用与基础设施结束恢复健康，网页 `http://127.0.0.1:5173`。

## 历史诊断、未运行项与风险

初次dirty容器诊断的时间/分类与热更新通过，分析对照误要求前端未保留的`reconciliation_passed`字段，因而失败；修正对照字段后ada51d0 clean全链通过。收尾再补微小贡献舍入提示，最终64f29a9重新clean全链通过。正式依据为最终报告，历史dirty或旧提交不冒称新候选通过。

未运行全套AI Evaluation：本次不修改查询理解、Prompt、Retrieval决策、SQL Guard政策、业务公式或归因算法；已执行小范围真实链路，既有Evaluation成绩仍只属于原报告候选。未运行完整Gitleaks Secret scan，本机无该CLI；本Diff人工检查未发现真实Secret，CI Secret scan仍由远端真实流程执行。未运行生产部署、容量或R6/R7验收。

保守认证只支持可证明的简单投影、标准时间配方和实际绑定；复杂SQL或未知语义保留表格。图形坐标为有限近似，原始返回值和格式化文本保留；不承诺恢复传输前已丢失精度。R2不扩展历史、导出、全量分页或自动聚合。

## Done When与Harness反馈

正式[R2 Spec](../specs/result-visualization-v1.md)、[Design](../designs/result-visualization-v1.md)、Query API/Web Spec、Product Scope、README/Runbook、roadmap及四个Ticket已同步。无DB迁移或RAG重建；Architecture一级边界/职责/依赖方向和Evaluation Contract未变，无需改写这些事实源。PR发布另需授权。

观察到一个工具缓存缺口：仅网页源码改变，`docker/node-dev.Dockerfile`的browser阶段仍继承已COPY源码的dev阶段，实际多次重装Playwright OS/浏览器依赖，单次约数分钟。建议后续将稳定依赖安装置于不依赖业务源码COPY的阶段，并验证改源码后的缓存命中；可减少后续真实验收等待。当前不修改该Harness、不新增实施承诺，优先级待用户决定。

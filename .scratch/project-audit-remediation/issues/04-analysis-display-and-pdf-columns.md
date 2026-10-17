# 归因分类与PDF证据列的一致展示


- Change Profile: 中高风险；页面/快照/文件结果表达；寿命/交付见共同规则。
- Owner: 当前主Agent；维护归属见共同规则。
- AUD: AUD007、AUD008。
- Blocked by: None (can start immediately)
- owned files: frontend/src/Analysis.tsx；frontend/src/export/pdfReport.tsx；frontend/src/（必要的轻量共用分类函数）；frontend/tests/result-export.spec.ts；frontend/tests/history.spec.ts；tests/query_api/test_result_export_pdf.py；tests/query_api/test_result_export_pdf_renderer.py；相关fixture；docs/specs/result-visualization-v1.md；docs/specs/result-export-v1.md。同目录其他文件仅在同一行为确有调用点时扩展并记录，不覆盖用户修改。

### What to build

页面和PDF识别后端真实新增/退出产品分类及旧兼容值；PDF分块按同一源列取得名称、索引和值。

### Acceptance criteria

1. continuing/new_product/exited_product可在首次结果、历史重开、归因图表和PDF正常展示；旧new/discontinued仍识别，未知值不猜语义。
2. 归因金额/方向/因素与后端一致，不重算业务公式。
3. 8列、奇数列、空行、长中文名称与多分块的标题/序号/值精确对应；实际PDF文本可核验，coverage检查不能仅证明数量。

### 验证证据

确定性浏览器从真实后端payload形状渲染；解析实际PDF的分块文本与原值，运行web及renderer相关测试。

### Migration / Rollback

不引入Schema或公开协议迁移。局部修复通过相关本地Commit回退；回退会重新暴露原缺陷，不能当作验收通过。测试资源仅按本次准确身份清理；已按现有Contract删除的过期checkpoint不可还原，不能以回滚代码承诺数据恢复；真实LLM费用不可撤回。无生产发布，不新增Feature Flag或部署回滚平台。

### Done When

对应Acceptance criteria及定向回归成立；适用正式文档更新或记录不适用理由；当前切片Code Review、Diff检查通过；结果记录命令/计数/候选基线及未验证范围，不把其他Ticket和整体目标标完成。最终Ticket还须满足Spec的全部候选、评测和隔离验收条件。

### Result / Comments

Status: completed
Result: 页面与PDF统一识别 `continuing`、`new_product`、`exited_product`，兼容旧 `new`、`discontinued`；未知分类保留为“分类未确认”。PDF证据表修复奇数列末块取错原列的问题，并在成功就绪前逐项校验分块标题、源列索引、行号和单元格文本。
Comments:
- TDD Red：`20261016T181903Z-3d566d6-test-web-43d229733465` 暴露后端新分类无法通过页面解析；`20261016T183337Z-3d566d6-test-web-1dee232b5a14` 的2项失败暴露未知分类应显示未确认而非拒绝整份分析。修复后定向 Web 为 `20261016T183427Z-3d566d6-test-web-2d0251744c2c`，9/9 passed，报告 provenance stable。
- 只读 Code Review：PASS。白名单归一化拒绝原型属性伪值；未知值不猜语义；PDF奇数列以 `slice(start, start + 2)` 绑定原列名、序号和值；coverage 增加逐项内容核对。Review 后无未解决问题。
- 候选 `0b3755c`：`./dev build` 成功并刷新导出镜像；`./dev test web` 71/71 passed（`20261016T183628Z-0b3755c-test-web-c2ae9ae720f9`）；`./dev test renderer` 2/2 passed（`20261016T183817Z-0b3755c-test-renderer-759f41e475fb`）；`./dev check python` 307 files / all checks passed（`20261016T183835Z-0b3755c-check-python-4a1b2cdf5d09`）；`./dev check docs` PASS（`20261016T183853Z-0b3755c-check-docs-1d8d592af71c`）；四份报告均为 stable provenance。`git diff --check` PASS。
- PDF renderer 实际下载并解析输出文本，覆盖多分块、八列、奇数列、长中文列名、空结果、分类新旧别名与未知分类。未运行全项目数据库回归、真实LLM评测或隔离Compose业务验收；由对应后续Ticket负责。

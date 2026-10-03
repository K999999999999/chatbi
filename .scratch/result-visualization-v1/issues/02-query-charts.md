# 02 问数趋势与分类图表

Change Profile: 持续维护 /中 /依赖与绘图解释中高风险；Evidence为锁依赖、纯图表计划、Chrome及容器页面；Owner当前主Agent。
Blocked by: 01

### What to build

- 锁定ECharts6.1.0与npm lock，按需SVG渲染、安全tooltip /aria /实例生命周期，局部加载 /绘制失败隔离；不安装新表格库或React包装依赖，不升级现有框架。
- 扩展01认证支持当前月份 /季度 /年份与分类物理输出的可靠绑定及time_axis，单一逻辑时间可能对应多个物理列；无新语义 /SQL决策。
- 实现time /category图表计划、同单位series /不同单位拆图；与表格同显、分别收起，适用类型切换不重查。
- 时间排序只作用图形；NULL与缺失时段断点，单点无趋势暗示，重复键 /多业务维度 /不可安全绘图数值降级。长标签及最多100行有可读布局，截断明确部分结果。

### Owned files

frontend package /lock、图表计划 /React图形边界 /查询展示 /样式 /results解码、02需要的后端元数据时间 /分组认证增量；相关纯函数 /online_query /Chrome用例、正式R2设计 /Contract /运行说明与工作记录。

### Acceptance / 验证

1. 同一结果同时用于图表 /表格，分类与时间显示类型正确；同单位对比、不同单位分图，未认证单位不误合轴。
2. 表格顺序保留，时间图升序；同一分组重复 /OR复杂范围未知 /缺失年份身份等保守降级，不求和、不填零。
3. 100行 /跨度大缺失时段 /长标签 /恶意标签 /绘图失败可重复测试，不丢数据、不生成无限空位、不执行HTML，原始表格保持。
4. 追问后图 /表 /单位 /范围同步，退出 /换号 /迟到响应 /刷新仍符合R1。
5. npm ci、typecheck、build、audit及锁来源验证通过；桌面Chrome开发与打包入口、容器启动 /热更新适用检查通过。

### Migration / Rollback / Done When

新增Web依赖，无数据库迁移 /平台发布。依赖兼容失败须定位；若需版本 /技术改变则返回设计或用户决定，不私自升级。受影响回归、安全检查、Code Review、正式Contract /设计文档及逻辑本地提交完成；保留数据卷与资产。


Status: in-progress
Canonical Source: ../spec.md、../design.md
Authorization: 用户已确认四项拆分及全目标本地实现、验证、Review和Commit；未授权发布

## Result

实现与确定性验证完成，Code Review PASS；待本地代码候选及04实际容器clean验收绑定。

证据：软件641 passed /15 skipped /139 subtests，Chrome32 passed / Vite1 passed；R2公共Contract、Design、Query API、Runbook、README及roadmap已同步。

## Comments

按01→02→03→04连续完成。

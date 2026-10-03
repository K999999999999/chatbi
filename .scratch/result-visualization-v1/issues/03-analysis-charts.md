# 03 经营分析贡献图与任务证据

Change Profile: 持续维护 /中 /经营方向与恢复兼容风险；Evidence为确定性归因 /旧Checkpoint兼容 /Chrome；Owner当前主Agent。
Blocked by: 02（复用已完成的格式与图表边界；不重复列传递依赖01）

### What to build

- 两期金额 /差额、主要产品正负条形图、选择产品看已有因素，沿用后端effect_on_metric /分类 /对账，不重算归因。
- 省略产品明确计数，不填其他贡献或计算全量占比；new/discontinued不补造价格 /成本因素。
- 分析汇总传递查询结果可选metadata至task_results证据；不暴露SQL /内部状态，旧Checkpoint和无字段结果仍保留表格。
- 任务完成 /失败 /跳过及不完整证据提示保留；缺归因保留报告，无效 /未对账归因保持既有校验拒绝。

### Owned files

frontend Analysis /共享图形 /证据展示、business_analysis现有任务结果Contract与序列化 /checkpoint兼容传递、相关API /Business Analysis与Chrome测试，正式分析响应 /R2行为说明及本工作记录。

### Acceptance / 验证

1. 增加 /降低 /无变化方向与金额、因素和分类匹配后端；成本上升不被当毛利正贡献。
2. 产品选择不重查 /不改分析ID，省略产品 /新进入 /退出 /缺因素 /缺归因 /不完整证据用固定案例覆盖。
3. 原任务重试 /24小时Checkpoint语义不变，旧保存结果不因新增metadata失效；无额外模型调用或业务数据访问。
4. 恶意产品 /因素文本安全展示，指标 /原值格式与02一致，缺图不丢报告。

### Migration / Rollback / Done When

无DB或Checkpoint Schema迁移，新增可忽略字段且可读取旧payload。归因逻辑不变，不删历史checkpoint回滚。适用分析回归 /旧payload兼容 /Chrome、安全Review与正式响应说明完成并形成本地逻辑提交。


Status: in-progress
Canonical Source: ../spec.md、../design.md
Authorization: 用户已确认四项拆分及全目标本地实现、验证、Review和Commit；未授权发布

## Result

实现与确定性验证完成，Code Review PASS；待本地代码候选及04实际容器clean验收绑定。

证据：软件641 passed /15 skipped /139 subtests，Chrome32 passed / Vite1 passed；R2公共Contract、Design、Query API、Runbook、README及roadmap已同步。

## Comments

按01→02→03→04连续完成。

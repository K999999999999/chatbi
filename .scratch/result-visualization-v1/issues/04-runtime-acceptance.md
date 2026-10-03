# 04 完整容器验收与候选交付证据

Change Profile: 持续维护 /中 /真实费用与账号清理较高风险；Evidence为最终clean代码候选、独立SQL /归因参考和资源身份；Owner当前主Agent。
Blocked by: 03

### What to build

- 扩展现有外部实际容器浏览器验收，覆盖时间 /分类 /同单位及混单位多指标问数、同会话追问、两期分析，核对元数据与图形 /表格一致。
- 使用专用验收账号，凭证不入报告；结束禁用 /撤销Session，保留原有用户、开发数据与RAG。独立SQL与既有归因参考做对照，不用LLM生成参考答案。
- 补最终受影响确定性、API /集成、浏览器、容器开发与打包检查、依赖 /安全门禁及Code Review；无新业务生成行为时明确不重跑全套Evaluation理由。
- 回填正式Spec /API /Design /Runbook /README适用变化、日期Acceptance /roadmap和工作状态，绑定clean candidate与运行资源，不覆盖旧证据身份。

### Owned files

frontend/tests容器真实用例及必要Playwright配置 /安全reporter、tests容器支持 /独立参考、scripts/verify_container_dev.sh适用扩展；docs/specs /designs /acceptance、Runbook /README /roadmap与本工作项证据。真实用例保持显式入口，与默认确定性回归隔离。

### Acceptance / 验证

1. 实际Compose网页 /API完成授权范围真实链路，图 /表 /单位 /范围及贡献对照一致；报告记录commit、git_dirty=false、模型 /数据 /RAG /镜像身份、安全结果。
2. 声明实际覆盖场景及每项结果；低概率边界由确定性故障注入证明，不以模型偶然输出替代测试。
3. 账号disabled=true /active_sessions=0、凭证移除、仅清理经标签核实的临时资源；已有资源保留。
4. 全部适用验证 /Review /Diff与事实源Done When完成；未运行项目明确列出，不声称R6 /R7或全套Evaluation完成。

### Migration / Rollback / Done When

真实资源缺失 /失败保留诊断并修复，不能换假模型宣称通过；不提高成本范围或删除既有资产。代码candidate与文档回填可分本地提交；最终工作区clean且所有Ticket完成。当前只允许本地交付，Push /PR发布独立确认。


Status: done
Canonical Source: ../spec.md、../design.md
Authorization: 用户已确认四项拆分及全目标本地实现、验证、Review和Commit；未授权发布

## Result

实际容器验收已扩展：真实问数/追问、时间同/混单位多指标、分类同单位多指标及经营分析，独立SQL与归因参考、安全错误位置与账号清理。最终代码候选64f29a9的clean真实容器全链通过（脚本退出0）；问数/追问、12月三指标混单位、4产品线同单位两指标、分析4任务与归因参考一致，说明均complete，图/表/贡献有效。账号disabled=true/active_sessions=0，凭证移除；重启持久性PASS。正式Acceptance、roadmap和适用事实源均回填；Code Review PASS。全套Evaluation/Gitleaks未运行并说明原因，未发布PR。

## Comments

按01→02→03→04连续完成。

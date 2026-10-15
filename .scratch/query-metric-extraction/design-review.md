# 设计审查

Review: PASS

Review Target: [已确认 Spec](spec.md)及[实施设计](design.md)；基线 `a247096`。只读审查，未运行业务测试或模型评测。

## 发现与设计核对

### 1. 历史修订不能按原始指标文字判断身份变化

- Signal：别名提取改变字符串，但不一定改变指标身份；检索前直接比较会放大为排序 / 聚合条件错误。
- Evidence：`src/query_api/semantic_revision.py` 的历史修订在合并后检查排序与聚合目标是否属于 `merged.metrics`；`src/online_query/semantic_state.py` 会将 metrics 规范化，却要求条件目标已经是规范名。
- Impact：同指标更换别名可能被错误澄清；若仅改提示词，排名及历史查询可能认证失败，或被错误映射为技术故障。
- Recommendation：依赖权威身份的检查放在已有检索后的认证边界；同时认证指标及条件引用；真实指标替换仍维持原澄清规则。设计已明确处理顺序、所选指标范围及业务 / 技术失败分类，符合 Spec，无需改变产品决定。

### 2. 已有辅助评测不能直接承载全部新验收场景

- Signal：当前辅助语义评测只接受单轮六字段候选，不能把澄清或多轮结果混进现有格式后直接运行。
- Evidence：`evaluation/suites/query_understanding/semantic_evaluation.py` 的 Case 及比较逻辑使用普通候选；`tests/evaluation/query_understanding/test_semantic_evaluation.py` 验证对应格式；历史 profile 含独立 conditions / 修订操作。
- Impact：只跑原六例无法证明歧义、多轮和历史引用正确；直接替换格式可能破坏旧入口。
- Recommendation：评测兼容旧案例默认行为，按需扩展受控 outcome / revision 案例；历史条件走正式 profile。设计与 Ticket 草案据此分别安排软件证据和真实模型 / 网页证据，禁止把模拟解析成功当成模型准确率。

## 其他审查结论

- 权威来源：候选保留原话，认证依据本轮已发布资产及已选 Metric；不让词汇表、SQL 或模型决定业务真相。
- 边界与复杂度：沿用 Online Query / Retrieval / History，未新增 Service、Port、Provider、状态表或指标目录；对比了仅改 Prompt、提前额外匹配及复用既有认证三种方案。
- 失败与状态：METRIC 检索失败继续关闭；原修订业务歧义继续澄清；技术认证故障仍报技术错误；失败及澄清不提交成功状态。
- 兼容：既有状态格式及规范身份不变，无历史迁移；解析和衔接作为单一候选交付及回滚。
- 旧候选：`fix/full-validation-findings` 的规范名评测期望与本目标冲突，保留原分支；不作为本次证据或盲目整合。

Reference: 已读取 Architecture Knowledge Core，主要应用章节 2（变更放大）、4（依赖方向）、5（可观察行为）、7（失败与状态）、8（备选方案与兼容）、9（避免过度设计）。

Evidence Sources: Spec、实施设计、`docs/architecture.md`、`docs/product-scope.md`、`docs/roadmap.md`、在线查询 / 检索 / 查询恢复 Contract、查询理解及执行 / 认证代码、HistoryApplication / semantic_revision、相关软件测试和现有评测入口。证据为只读代码核对，不代表候选已实现或验证通过。

Next: `workflow-to-tickets` 形成一个完整纵向实施项草案，执行当前上下文的 Ticket Readiness Review，再请用户确认拆分及实施范围。

# S02 订单明细行数口语别名

## 目标

修复正式单轮案例 S02 在 Query Understanding 保留原始指标说法后，被在线指标检索以 `AMBIGUOUS` 拒绝的问题。把明确的“已完成订单明细有多少行”登记为既有“已完成订单明细行数”指标的精确别名。

## 范围与不变量

- 只扩展 `src/semantic/metrics.json` 中现有 `COUNT(*)` 指标的别名。
- 不修改公式、过滤条件、日期口径、Seed、案例、模型配置、检索阈值或失败关闭策略。
- 多个近似检索命中仍不按分数排名猜测；只有精确规范名或精确登记别名才能认证指标身份。

## 验收

1. 使用真实指标词汇构造的 S02 语义说法，在包含相近订单指标的候选中唯一映射到“已完成订单明细行数”。
2. 源事实测试确认新别名仅属于该指标且原公式保持 `COUNT(*)`。
3. 相关确定性回归、AI 评测测试、Python 检查和新的正式单轮 / 经营分析评测通过身份校验；旧正式失败报告保留。

## 验证结果

- 别名映射与源事实定向回归：20 passed、3 subtests（run `20261017T102743Z-7ba52e1-test-python-ba73e0829689`）。
- `./dev check python`：309 files already formatted、all checks passed（run `20261017T102800Z-7ba52e1-check-python-df4a91d17d6d`）；`./dev check docs`：PASS（run `20261017T102816Z-7ba52e1-check-docs-1645f7897471`）。
- Clean candidate `97268ca` 完整 `./dev check` 通过、`./dev test all` 为1257 passed / 61 conditional skipped / 0 failed；报告因skip为incomplete。
- 正式单轮 `20261017T093218Z-97268ca-single-turn-415beb8a73ca` 的S02在 Query Understanding 阶段以 `PROVIDER_CALL_FAILED` 失败，没有到达检索，故验收条件3中的别名正式链路效果未验证。正式经营分析 `20261017T094429Z-97268ca-business-analysis-1844097bd074` 为10/10；整体验收仍被S02、多轮 `MT-FILTER-REPLACE` 与隔离容器验收阻断。所有正式失败报告保留。

## Review

Review: PASS。以审计分支基线 `7ba52e1fcf9cc3140700982b77085dfabe1bacef` 检查`src/semantic/metrics.json`和两项事实 / 规划回归：变更只登记与正式S02说法完全匹配的指标别名，保持`COUNT(*)`、过滤条件及fail-closed检索不变；测试从事实源加载词汇，并在相近订单指标候选中验证唯一映射。`git diff --check`通过。别名代码已纳入审计分支待提交差异；正式模型请求失败仍未证明在线S02链路通过。

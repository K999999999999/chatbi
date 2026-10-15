# Design Review

Review: PASS WITH MINOR FIXES → PASS（修订逐项核对完成）

Review Target: 用户已明确确认的 [Spec](spec.md)，基线 `47a9dc8cee10298504d9daec6be79712a5bf194d`。

## Findings

1. Signal: APP 退役有误删旧资源拒绝保护的风险。Evidence: `scripts/dev_compose.py` dev 分支拒绝旧应用 Compose；恢复入口与 AuthService 校验环境。Impact: 删除正向支持时若取消校验，会弱化安全边界。Recommendation: 删除 app 正向支持，保留旧资源拒绝测试。落实：Spec 运行边界与 Design 第 1 节明确保护，历史审计不迁移。
2. Signal: 最终报告与运行中状态写入混在一起。Evidence: `tests/container_dev_support.py`、`container-real.spec.ts` 和 safe-reporter 在重启 / 清理后更新同份记录。Impact: 机械禁止一切重写会破坏业务验收，放任重写又可能覆盖跨次证据。Recommendation: 独立 run 私有状态可变，最终发布不可覆盖。落实：Spec 与 Design 第 5 节划清边界，部分保存失败非零，不将辅助 JSON 放进正式三套目录。
3. Signal: 报告字段和兼容策略尚需固定。Evidence: 语义报告与其他三套不同，正式验收器目前只有起点旧字段检查，软件测试多为控制台输出。Impact: 可能出现多个不兼容采集器或把未知历史身份升级成正式通过。Recommendation: 只增加最小版本化 provenance 与命令级 summary，保留原报告可读性，新正式验收拒绝缺失 / changed / unverified 身份。落实：Design 第 5 节明确字段、适用性、旧报告边界与 Secret 白名单。
4. Signal: 完整数值配对可能被实现成指数级回溯。Evidence: 现有无序贪心匹配有容差重叠反例，结果行数有界但可接近百行。Impact: 全排列使评测耗时不可预测。Recommendation: 逐列原规则建立匹配关系，增广路径判断完整一一配对。落实：Design 第 4 节采用多项式算法，保留原容差及有序语义。

## Review Dimensions

- Business / Architecture: 不改变核心业务链、模块一级职责、依赖方向、数据权限和 SQL Guard；移除的是已获用户确认的独立运行路线。
- Repository / Runtime: 已核对 dev / container_tasks / dev_compose / doctor、恢复环境校验、Python / Node 开发 Dockerfile、浏览器 fixture 与配置、CI / Real E2E、四套评测入口和报告消费者。
- State / Security: 隔离测试资源、失败先释放锁、无生产测试后门、Secret 不进入报告、旧 APP 容器拒绝保护、历史证据不改写。
- Simplicity: 复用 pytest JUnit、Playwright 与既有 CI artifact；只引入标准库小工具，不新增依赖、业务层或测试平台。比较仅隐藏 help、保留别名、完整退役，以及新平台与最小报告适配的成本。
- Testability: 通过 CLI / 文件结果 / 真实隔离库 / 浏览器观察行为；报告采用确定性注入与无付费调用验证；超时故障有进程级上限。

## Reference 与 Evidence

已完整读取 workflow-design-review 的 Architecture Knowledge Core，重点使用复杂度、Contract、依赖方向、Failure / State、Migration 与 Overengineering 原则；并读取 workflow-to-tickets 的 Migration and Large-Scale Change。

证据为仓库当前代码、Architecture、Product Scope、Roadmap、Evaluation / 容器 / 恢复 Contract、已记录基线调查与本轮只读核对；本阶段没有运行新软件 / 模型验收，不把设计审查当测试结果。

Next: Ticket Readiness 已通过，七项拆分与本地实施、验证、Commit 已由用户另行确认。此 Design Review 本身不构成实施、Commit、Push 或 PR 授权。

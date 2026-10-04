# R3 Implementation Code Review

结果：**PASS**。审查范围是相对基线 `afad5ac18452566199bfcfdcceb1585115576a77` 的 R3 代码与文档 Diff，依据为已确认的 `spec.md`、`restoration-semantics.md`、`design.md`、`docs/specs/history-results-v1.md`、`docs/designs/history-results-v1.md` 与 `docs/designs/history-query-restoration.md`。Review 只判断实现是否遵守已确认 Contract；clean candidate 的真实验收与 AI Evaluation 仍待提交后执行。

重点检查了持久化受理 / 原子完成、运行 epoch 与 generation fencing、跨账号隔离和 Cookie / CSRF、快照白名单 / 大小边界、当前业务认证闭包、SQL Guard、查询追问条件合并、历史与成果独立生命周期，以及前端刷新 / 身份变化 / 断连处理。

审查过程中关闭了以下问题，并补上回归证据：

- JSON 往返会把 Join 来源元组变成列表，导致合法历史条件误报不兼容；现在来源指纹统一序列化为列表，并覆盖 round-trip。
- 未映射业务字段错误分支缺少 `sha256` 导入；补回依赖并验证拒绝路径。
- 结果已执行完成后，短时历史管理事务的 `NOWAIT` 竞争可能令完成失败；finish 改为等待该短事务，并用真实 PG 锁等待测试覆盖。
- finish 提交失败不可被当作业务执行失败再次写入；失败映射为结果未确认，测试证明不会第二次调用 finish。
- 没有显式排名依据的 Top-N 曾可能复用展示排序；现在理解阶段澄清，展示与平局顺序仅在 SQL 校验阶段派生，完整条件不写入隐式排序。
- 从某个成功轮次或另存成果重查时，结果条件可能来自该轮，但新记录文本可能取对话第一问 / 成果标题；快照现在私有保存轮次来源问题，历史来源取选中轮次，成果保留用户命名作为显示标题，旧 v1 快照缺少来源问题时仍可展示并用中性提示重查。

未发现剩余的 Spec / Contract 偏差或阻止本地 candidate 的代码问题。最近提交前验证：`pytest -q` 685 passed / 29 skipped / 139 subtests；隔离 PG 33 passed；Playwright 36 passed；`npm run build` 与 TypeScript、Ruff、`uv lock --check`、模块边界、Markdown 本地链接、`compileall`、`git diff --check` 通过。Vite 的 ECharts chunk >500 kB 是现有打包尺寸提示，不影响构建通过。

最终 R3 Compose 真实闭环、三套正式 AI Evaluation、统一身份验收及三次多轮诊断不是此代码 Review 的替代项；结果与候选 SHA 记录在 Git 公共目录本机实时工作状态。

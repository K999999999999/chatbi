# Ticket 05：分析文字真实流式、草稿重置与最终校验

ID: execution-streaming-v1/05
Status: complete
Authorization: 用户于 2026-10-05 确认六项拆分及连续完成整个 R4 的本地实施，包含编码、适用测试与真实验收、Review 和本地 Commit；不含远端发布。

Change Profile: 持续维护 /中偏大 /高风险模型不可信输出 /纯decoder+软件+浏览器 /本地candidate。
Owner: 当前主Agent。
Blocked by: 04

### What to build / Scope

- summarizer可选R4 observer路径调用锁定SDK stream，六类报告文字增量严格解码 /公开；原invoke路径和最终结构 /引用校验复用，不伪造打字。
- 草稿generation /field /index /offset、snapshot /delta /reset处理；原JSON与草稿5MiB限制，escape /Unicode /重复key等异常受控失败，不公开JSON /任意对象路径。
- 同execution /deadline最多一次Provider异常内部重试，清旧draft；取消 /超时 /授权失效不重试，校验失败不自动重试。
- UI生成中不可另存，成功校验保存后替换成正式报告，数值 /图表 /证据此时展示；非成功清草稿、断连保留提示 /重连取当前generation。

Out of Scope: 新模型 /依赖 /业务指标、改变report结构、伪流式降级、token前公开数值图表。

Owned files: `src/business_analysis/reporting.py` /contracts.py /application.py /runtime.py及单一增量JSON decoder；execution runtime /event DTO /API的文字映射；`frontend/src/execution.ts` /executionStream.ts /Analysis.tsx /Chat.tsx /style.css；analysis /decoder /event /reducer /浏览器tests；正式R4 /Web /Analysis文档。

### Acceptance criteria / Evidence

1. 六类文字来自实际stream，合法chunk分割、CRLF /多行data、转义 /surrogate /空列表均得到正确纯文本；未知字段不任意写路径，重复key /不安全结构不制造草稿与最终结果分歧。
2. Provider异常重试保留execution /deadline、draft_reset正确；旧generation /重复offset /序号缺口 /多页 /重连不拼接两次输出；不可安全解析的内容不自动重试 /回放invoke。
3. 成功报告沿原结构 /引用 /业务校验及快照保存门槛，失败 /取消 /超时 /撤权无成功提交或可保存draft；既有成功结果保留。
4. 无observer的旧同步API /分析Evaluation正常行为兼容；停止信号在stream /retry /graph路径不被吞，Provider不支持stream给受控错误。
5. targeted software /浏览器通过且至少一次实际模型有完成前文字增量的开发证据；正式clean真实stream验收仍由06统一完成，不冒称样例为全套基线。

验证：单一decoder纯函数边界与生成器stop、Runtime /PG提交行为、HTTP/Cookie浏览器草稿测试；frontend types /build /静态 /文档链接；原analysis /query受影响回归，新增bad case加入regression。
Migration / Rollback: 无新SDK /存储选择，保持现有model /endpoint /temperature /max_tokens /max_retries=0；依赖无需升级，若确需新版本先回设计。
Done When: 1–5及Review PASS、本地Commit完成，可形成完整R4最终候选。
Result: 本地提交完成。Python 定向回归 99 passed；Docker Chromium `execution.spec.ts` 10 passed；前端 typecheck/build、Ticket05 Python 文件格式、仓库 CI Ruff 规则、模块边界、源码 Bandit、Markdown 本地链接和 Diff 检查通过。开发态 isolated Compose 实际模型报告 `reports/browser-real/container-1791214283-isolated.json` SHA256 `a3eb24f278320d394fc8674f13760a17bbd90d99e0c8f682efc5a8e9d21489a4`：804 个 `text_delta`，首个序号 18、`succeeded` 序号 823，4 个分析任务与独立业务参考匹配，临时账号禁用 / 活跃 Session 0。此报告 `git_dirty=true`，不是最终候选验收；Ticket06 对最终 clean candidate 重跑完整验收。
Review: PASS；BASE `e1f3f4dff8e5e2c14ee6e601a32a983151950ae4`；commit包含同步 `invoke` 原始 JSON 5MiB 上限、草稿累计线性化，以及成功终态清除未校验草稿。
Comments: 不能以完成报告字符分割或HTTP chunk数充当真实模型流式证明；实际模型验收以SSE中的模型文字增量先于成功终态为准。

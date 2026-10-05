# Ticket 03：主动取消、总时限与授权失效停止

ID: execution-streaming-v1/03
Status: open
Authorization: 用户于 2026-10-05 确认六项拆分及连续完成整个 R4 的本地实施，包含编码、适用测试与真实验收、Review 和本地 Commit；不含远端发布。

Change Profile: 持续维护 /中偏大 /高风险竞态 /软件+真实PG+浏览器 /本地candidate。
Owner: 当前主Agent。
Blocked by: 02

### What to build / Scope

- POST取消 /网页按钮、stopping /cancelled /timed_out /授权失败状态、stop signal与1秒monitor，query180s /analysis1200s，共享deadline /quota。
- 全业务边界 /retry /stream前后识别专门停止信号，防broad catch吞掉；SQL Adapter best-effort cancel、模型停止边界，实际函数结束才释放。
- request_stop /finish_success同PG裁决；取消分析同事务封锁原run，旧API /checkpoint不能复活已取消运行；checkpoint完成不是网页成功。
- 原登录失效 /禁用 /撤权后台检测，不依赖SSE在线；成功提交前再鉴权；故障 /unconfirmed /restart与原TTL恢复规则一致。

Out of Scope: 改成立即强杀 /多进程、导出、文字流式；不延长checkpoint TTL。

Owned files: execution API /Application /runtime、History Application /Store /reconcile；`src/authorization/auth_service.py` /必要策略绑定；`src/online_query/contracts.py` /service.py /service_execution.py /llm.py /query_understanding_llm.py /database.py及实际下游停止传播；`src/business_analysis/application.py` /execution.py /run_store.py /run_execution.py /reporting.py /decomposer.py；bootstrap资源关闭；frontend execution /Chat /状态解码；对应软件 /真实PG /浏览器tests，R4 /Web /History恢复文档。

### Acceptance criteria / Evidence

1. 取消请求ACK之后不能成功回写；成功已提交之后取消读到成功。双连接 /可控barrier覆盖两种先后与重复取消 /超时竞争，历史snapshot /指针不被取消更新。
2. 停止中quota /run lease保留，迟到调用返回仍不继续或提交；真正结束才显示终态 /释放一次；超时重试不重置计时，不以Future.cancel或PG cancel回执证明停止。
3. 无业务帧期间撤权 /过期 /账号禁用也能停止后续步骤；同一原Session校验不续期，权限恢复不自动续跑；授权依赖不可用fail closed。
4. 未进入graph的取消、graph执行中、checkpoint completed但history未提交的取消都封锁原run；旧API /R3恢复路径不可重新claim；已完成正式结果不被取消撤销。
5. 服务重启未完成标unconfirmed、旧epoch /generation迟到写拒绝，问数按上一成功续聊、分析有效期内显式恢复，cancelled原run拒绝；存储失效 /关闭流程没有隐式接管或提前释放。

验证：全风险控制的确定性回归、真实PG stop/commit /registry /TTL，浏览器取消 /超时 /撤权。实际Provider不能立刻中断的限制准确报告。用户已确认的手动重试 /新任务行为须有浏览器证据。
Migration / Rollback: 使用01最小execution状态，cancelled run写旧版可识别expired；停止旧worker后回滚，不通过删数据解锁。
Done When: 1–5通过、Code Review PASS、相关安全 /状态Contract同步、本地Commit完成，可进入状态阶段真实验收。
Result: 尚未实施。
Comments: 验收deadline用可控clock与barrier，不长时间真实sleep。

# 宿主无新依赖及调度细化 Design Review

Mode: Main Agent / 当前上下文只读；Status: PASS。

依据Spec宿主无新依赖：将文件/JSON/来源处理移到固定工具，宿主Bash只捕获受限元数据并解析已知image ID/revision；无Docker socket、host新包或业务API Secret权限变化。Raw capture只清理本次目录，identity最后原子发布；失效/陌生source拒绝。

observed_at是live socket响应证据，不冒称dependency ready；HTTP状态/权限/30秒stale完全不变。调度clock、持久失败冷却、成功后retention与API生命周期解耦符合确认Contract。

剩余验收：真实ChatBI资源的跨版本升级前门禁及恢复/回退/最终运行矩阵归05/07，不能以synthetic PG与shell编排证据替代。无需新用户决定，未扩张Spec或授权。

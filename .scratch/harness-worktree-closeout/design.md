# 实现设计

已确认范围见 [Spec](spec.md)。只扩展现有本机检查器和容器 adapter，不建立新的任务平台。

- `scripts/check_harness_state.py` 复用现有字段解析和 Git 查询，增加 worktree 枚举、结构化归属、显式 checkout / cleanup 检查。检查结果按现有 INFO / REVIEW / ERROR 协议输出，原入口语义保留。
- 新增 `scripts/harness_control.py` 作为容器内薄入口：state 记录查询可跨 checkout，但不匹配时剥离 candidate 派生结论；其他带工作项的候选操作先核验归属再调用原 Plugin CLI。输出错误时不修改状态、不迁移历史记录。
- `scripts/harness_container_adapter.sh` 保持镜像、网络隔离、只读项目 / Plugin / Git、单工作项可写挂载，只将容器入口改为项目 preflight。已有缺镜像 / 缺包失败行为保留。
- 源 bind mount 改用 Docker 原生 `--mount type=bind,...,readonly`，并在调用前核验宿主源存在。真实 smoke 发现本机 Docker Desktop 对 `--mount` 也会创建缺失源，因此不能只信任 daemon 行为。宿主映射在当前调用环境不可验证时明确失败，要求从可验证宿主路径的环境调用，不假装缺失源已通过。
- Plugin 兼容通过官方重新安装已发布 master 版本解决；无需修改另一个源码仓库或绕过加载边界。
- 新记录绑定 active checkout；候选离开主目录等待授权时标 parked。完成的临时工作树标 removed，必须验证实际目录和登记均消失；需保留的主目录标 retained 并写明原因。
- Ticket 从所属 worktree / parked 分支 / 已确认 Merge commit 读取。严格收尾在发生时核对返回 master；普通历史检查允许后续已登记任务正常复用主目录，避免每次新开发都让旧 done 记录重新失败。

替代方案：强制所有任务共用当前 checkout 会打断未发布工作；批量迁移旧记录会制造历史证据。采用当前任务显式绑定、旧记录只读发现与本机确定性门禁，保留既有阶段与授权边界。

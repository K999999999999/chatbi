# 01 — 查看工作状态并拒绝非法阶段转换

Status: done
Ticket Readiness: READY


Change Profile: Plugin；长期工具，小到中型切片；风险为状态损坏 / 虚假推进；临时Git与文件故障回归；本地候选。
Owner: 当前主 Agent
Blocked by: None (can start immediately)

### What to build

提供可运行的标准库CLI，读取数据adapter及单一Markdown状态记录，展示生命周期 / 阶段 / 运行情况 / 下一步，执行经校验的显式阶段转换。覆盖版本化扩展、旧字段权威、预期文件摘要、互斥与原子保存；旧记录只读识别，显式迁移保留原件，不创造历史证据。依据先采用明确的类型化输入Contract，后续Ticket接入实际事实采集。

### Acceptance criteria

- 合法转换成功且得到可重读状态；跳过必要确认、缺必需依据、未知阶段 / 格式均非零拒绝且原文件不变。
- 旧顶层字段与扩展不重复定义同一事实；linked worktree正确使用Git公共目录，不假定.git为目录。
- 两个写入者、过期预期摘要、写入失败及遗留锁不会静默覆盖；恢复不删除归属未核实的锁 / 原件。
- 只读查询不写记录、不执行adapter任意代码、不读取.env、不访问网络；缺adapter显示未接入。

owned files: Plugin `tools/harness.py`、`tools/harness_lib/`状态/存储/CLI部分、`tests/test_harness_state.py`、Plugin README与必要工具文档。

Verification evidence: 标准库unittest；临时Git / linked worktree；转换矩阵正反例；故障写入、并发冲突、旧记录及Secret canary不输出。

Migration / Rollback: 按目标显式迁移并保留原状态；无历史批量更新，回退CLI不删除新扩展或证据。

Done When: 行为测试 / 文档 / Diff Review通过；单一当前权威与失败不改原状态可复现；候选身份明确。

Result: Done。交付标准库 CLI、JSON adapter 校验、Markdown 旧状态只读识别、显式迁移备份、阶段 / 运行状态更新、类型化依据、SHA-256 乐观并发检查、独占锁及同目录原子替换。验证：Python 3.11.16 ChatBI 容器中 `python -m unittest discover -s tests -p test_harness_state.py -v` 10 项通过；Python 3.14.4 定向测试 10 项通过；`py_compile` 与 `git diff --check` 通过。手工声明不能伪装机器验证；容器以只读方式挂载Plugin候选，测试仅在临时Git仓库操作。
Comments: 用户于 2026-10-19 确认 8 项拆分并授权整体本地实施、验证、Review 和 Commit；不含 Push / PR、Plugin 安装更新、远端设置或实验。

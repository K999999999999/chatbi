# 常驻容器自动恢复验证

## 对象与范围

BASE：`38e1302ce33d999dc908419067bc5d39195f86cf`；分支`fix/container-auto-restart`。以下检查针对本次Compose、开发API启动入口与相关测试的工作树实现；本地候选保留同一实现。原始安全摘要与源文件指纹保存在本机ignored `.local/container-auto-restart/`，不包含凭据。

## 验证结果

| 检查 | 结果与覆盖 |
| --- | --- |
| Compose实际解析及开发入口 | 11 PASS；开发四服务和标准三服务`unless-stopped`，一次性工具`no`，停止保留卷、初始化权限与回环边界 |
| 启动等待TDD Red | 3个预期行为失败：控制库由不可用变可用、超时安全提示、就绪后启动热重载；失败来自占位行为，无导入或环境错误 |
| 定向软件回归 | `./dev test python tests/scripts/test_start_dev_api.py tests/scripts/test_container_dev.py tests/scripts/test_container_application.py tests/bootstrap/test_operations.py tests/bootstrap/test_runtime.py`：34 PASS，17.16秒 |
| Docker策略隔离验证 | 临时无网络、无凭据容器正常退出后自动重启（RestartCount=1）；手动stop后观察15秒仍停止；按本次标签和容器ID核对后清理 |
| 实际延后启动Red | 开发API先启动、PostgreSQL延后20秒；旧热重载父进程仍running、RestartCount=0，但子进程startup failed，依赖恢复后未自行恢复 |
| 实际延后启动Green | 加入控制库等待后重复同一20秒场景，API自行恢复HTTP存活，无startup failed标记；无需修改源码触发重载 |
| 当前开发服务 | 最终API / Web / PostgreSQL / Qdrant均running且实际restart策略为unless-stopped；`/ready` HTTP 200 / status=ready，Web5173 HTTP 200 |
| 组合质量 | `./dev check` PASS：锁文件、文档/链接、模块边界、Python格式/lint、网页typecheck/build、export build；保留既有大chunk提示 |
| CI同入口Python质量 | 在容器执行`bash scripts/check_python_quality.sh`，Ruff固定0.16.8，全src/evaluation/tests格式与lint PASS；新增启动脚本另做定向format/lint PASS |
| 最终文档与Diff | 更新README、Runbook、Product Scope、两份正式容器Spec；文档组合检查与`git diff --check` PASS |

## 环境处置与失败保留

- 原开发RAG资产Embedding记录devices=null，当前容器固定CPU，导致来源指纹不匹配并返回503；显式`./dev build-rag`重建，最终发布`20261014T103325Z-66fde892ef79`，7/69/7份文档、9条关系，failure_count=0。旧资产保留；只读探测四项依赖均ready。
- 首次索引重建尚未完成时误开始停止验证，Qdrant停机造成该构建VECTOR_STORE失败，published=false；恢复基础设施后串行重建成功，失败不算通过证据。
- 首次CI同入口质量检查因只读源码挂载下Ruff缓存不可写而未完成；改用容器内临时RUFF_CACHE_DIR后重新执行通过，不改变质量规则。
- 所有Docker资源操作限当前开发四服务和本次隔离探针；未操作旧Stable/Restore，不删除开发数据卷，不迁移账号/历史。

## 文档、路线图与未执行范围

已核对`docs/roadmap.md`的当前阶段和后续方向：本次是已确认的小范围容器启动行为调整，不改变V1能力、目标优先级、依赖、里程碑或既有验收身份，因此路线图不追加完成过程。旧部署/运行证据保持历史身份，现行自动恢复Contract归入正式容器Spec。

未执行整机/Docker daemon重启，未修改Docker Desktop登录自动启动设置；没有把延迟启动或退出重启验证冒称整机恢复验收。未运行真实LLM业务、完整AI Evaluation、真实浏览器登录/问数、标准app完整空卷验收或远端CI；本次不改变相应业务链路，标准app覆盖实际配置解析，开发环境有本次真实生命周期证据。

Harness检查无ERROR；OPEN_WORK_ITEM与DIRTY_WORKTREE REVIEW均归属于本工作项的本地实施。未观察到符合门槛的Harness缺口；已发现的冷启动问题在本次启动边界修复，不扩展协作规则。

## PR #83 安全扫描复验

首次托管CI其余八项通过，Static security scan将容器内部0.0.0.0监听标为B104。Compose实际配置与回归已验证宿主仅发布127.0.0.1；容器内部监听是既有Web代理/网络调用必需行为。对该行增加精确B104说明，不改变监听或宿主暴露范围、不关闭整个扫描。按当前候选补跑启动/Compose回归与相同Bandit命令，并以新head重新执行托管CI。

复验：启动/Compose等原34项回归PASS（22.27秒）；uv run --locked --with bandit bandit -r src scripts -ll退出0，Medium/High=0。新增行只有静态扫描说明，无运行代码变化，既有Docker/延后依赖与全量质量证据继续适用。

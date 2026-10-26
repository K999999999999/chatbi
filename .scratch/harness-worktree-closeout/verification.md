# 验证记录

## 候选与适用范围

基线为 `master@6ca342c1bb61d0d8018bb165f733b9104c5e342f`；验证对应本目标提交前的代码 / Contract 改动，最终候选提交、源码摘要及原始报告保存在本机实时记录。提交仅改变 Git 记录身份时，源码与 Contract 摘要不变的测试证据继续适用。

范围：检查器、Plugin adapter / preflight、容器挂载入口及相关规则；产品代码、业务 Spec、数据库、模型与依赖锁文件均未改变。

## 软件验证

- Red：真实 Git fixture 的三个回归在旧实现上失败，分别为漏查另一 worktree 修改、漏查无归属 worktree、done 但仍 active 未被拒绝；报告 `20261026T090036Z-6ca342c-test-python-da139cfe0266.json`。
- `./dev test python tests/scripts -q`：268 / 268，通过，0 skipped；报告 `20261026T094703Z-6ca342c-test-python-70d27b38c883.json`。覆盖 Git / worktree、原有脚本入口、容器配置、维护与资源边界。
- 最后补充 legacy state 不得冒充新版 closeout 后，`./dev test python tests/scripts/test_harness_control.py -q`：9 / 9，通过，0 skipped；同模块原证据由本轮定向结果更新。
- `UV_NO_SYNC=true UV_OFFLINE=true bash scripts/check_python_quality.sh`：固定 Ruff `0.16.8`，341 个 Python 文件格式检查与既有 lint 规则全部通过。使用已安装工具缓存，不同步未改动的项目依赖。
- 容器质量检查的初次环境同步因镜像内 pypdf 与锁文件所需状态不同且目录无写权限失败；随后运行同一规范脚本的固定 Ruff 完成全量检查。一次工具包重新下载等待已停止，未把环境失败报告为产品回归或检查通过。
- 组合文档 / 链接检查、模块边界检查、`git diff --check`、全部受影响 shell 的 `bash -n`：通过；本机记录保留实际命令与最新报告。

## 真实工具与环境

- 两个工作目录初始均无未提交修改。CI 目录 5 份测试报告归档后逐文件 SHA256 一致，存于 `<git-common-dir>/harness/archives/ci-merge-gate-hardening/20261026T165046+0800/`；临时目录已移除，文档候选 e598533 保留。
- 真实容器入口读取合成仓库的两个 worktree，成功发现另一目录的未跟踪文件；验证前后文件内容一致。
- 真实 Docker Desktop smoke 发现单独使用 `--mount` 仍会生成缺失源；增加调用前校验后，缺失宿主映射退出 2，目录未创建。失败 smoke 产生的空测试目录已清理。
- 正确任务 state 返回匹配 candidate；未绑定取消记录和 parked 文档任务只返回 record-only；文档任务的错误 checkout diff 在调用 Plugin 前退出 2，记录未写入。
- 通过 `codex plugin add engineering-workflow@harness-task-control-v1 --json` 刷新真实安装包。与已发布源码 `681f8cd` 的 48 个受跟踪包文件逐一摘要比较，0 差异；之前失败的取消记录读取成功。版本号相同不代表内容一致，本次已核验实际文件；当前会话重新加载未验证。
- PR #100 正文原快照已保存，纠正 Roadmap 事实与复盘后完整读回，`gap-found` 与本后续项身份一致；最终本机清理 / 字段一致性在收尾时再次读回核对。原 8 项 required checks 的成功证据保持其原 run 身份。

## 事实源复核

| 事实源 | 处置 |
| --- | --- |
| AGENTS、issue-tracker、git-pr-workflow、Runbook | 更新任务归属、跨目录记录查询、严格本机收尾和缺失源失败规则。 |
| documentation | 明确文档事实绑定实际 worktree / branch / commit；错误纠正保存前后快照。 |
| Roadmap、产品范围、架构、业务 Spec | 复核无变化；本目标不改变产品里程碑或业务边界，也不混入待发布文档删除目标。 |
| `.harness/project.json` | 阶段图、授权和证据种类不变；增加的是项目执行前核验，原 Plugin 门禁保留。 |
| `.harness/dynamic-files.json` | 文件归属和触发条件不变，已逐项复核；不为本次改动修改其他工作项的通用清单。 |
| 本目标 Spec / Design / Tickets / Review | 保留当前决定及验证，实际运行原始产物归档于本机 Git common-dir。 |

## PR #101 托管 CI 与兼容性修正

- 首轮 required check 中 7 项通过；`Deterministic tests` 为 1182 passed、61 skipped、155 subtests passed、1 failed。失败用例 `test_compose_config_excludes_secrets_and_migration_identity_from_api` 直接索引规范化 Compose 输出的 `create_host_path` 字段；GitHub Compose 将默认 false 省略，触发 `KeyError`。配置源仍显式声明 `create_host_path: false`，不是运行行为失败。
- 将断言改为 `v.get("bind", {}).get("create_host_path", False) is False`，适配规范化输出省略默认值的行为。本机 Docker Compose v5.1.4 下定向用例通过，报告 `20261026T102903Z-b605a5a-test-python-390717497b39.json`。
- 修正已更新到 PR 后，全部 required checks 将针对新 head 重跑；在重跑完成前不把 PR 标为可合并。

## 未执行与交付边界

未运行付费 AI Evaluation、真实业务端到端或生产运行验收；本目标无相应业务行为变化。历史审计目录的具体创建命令仍未确认，本次验证解决已复现的缺失源重建机制。

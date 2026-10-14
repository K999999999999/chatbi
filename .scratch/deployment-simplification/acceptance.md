# Deployment Simplification 验收

Status: 本地实现、验收与Code Review完成；运行候选40b7749；无发布授权。

## 候选与证据适用性

- BASE: f4d0693f76b47f5f8a7a54de4309adea1025da1a；branch: refactor/deployment-simplification。
- 下列验证针对本目标实现并对应运行候选40b7749；后续提交仅维护验收记录。本机运行源码指纹在ignored `reports/deployment-simplification/source-sha256.json`，提交前核对实际源码与证据对应，不把历史候选重标为新结果。
- 镜像本机构建，无镜像上传。标准app完整业务验收使用初版成功构建镜像6b76e5；最终9ce998仅增加配置门禁和机械格式，新增门禁有Red/Green及最终镜像只读positive verification，核心运行与合格初始化输入不变，原业务证据仍适用。

## 验证结果

| 检查 | 结果与覆盖 |
| --- | --- |
| Python全量 | 最终921 PASS、44 SKIP、142 subtests PASS，90.94秒 |
| 条件SKIP补测 | 36个development PG、5个基础PG、2个renderer、1个真实LLM均通过下列独立运行覆盖；未静默跳过 |
| 隔离数据库 | CI profile 5 PASS；development profile 46 PASS；权限、migration、checkpoint、history、execution与指纹 |
| 确定性浏览器 | 打包mock API 67 PASS；Vite同源1 PASS |
| 实际PDF renderer | 2 PASS，真实Chromium/CJK与完整证据/归因解析 |
| 原生真实LLM软件测试 | ServiceIntegrationTest 1 PASS，7.77秒；相同认证指标只读SQL参考 |
| 构建 | 根Dockerfile api/database、python-dev、node-dev dev/browser targets成功；浏览器依赖父target随构建验证 |
| 静态/质量 | dev check通过：锁文件、文档/链接、模块边界、全量Python格式/lint、前端typecheck/build/export build |
| CI固定Ruff | 0.16.8 lint PASS、298文件format PASS；容器内执行 |
| 安全 | Gitleaks v8.30.1当前Git跟踪及非忽略新文件快照无泄漏；Bandit src/scripts中高风险0（-ll与CI相同，低风险81非阻断） |
| 初始化verify | 标准空卷通过；最终镜像以只读方式检查现有开发资源通过，未迁移或写数据；弱签名Key/缺配置/缺资产有安全失败验证 |
| 端口保护 | 真实TCP占用软件回归Red→Green；不启动新服务、不停止占用进程；通用loopback四项与入口回归通过 |
| 删除闭包 | 当前src/scripts/CI无Stable发布、升级回滚、备份恢复、运维socket消费者；最终app镜像无release/compatibility文件或local_release脚本 |

## 两种容器首次部署与业务闭环

### 标准应用Compose

资源 `chatbi-app-verify-1791938714-9946`：独立空卷Sales Mart与Control DB初始化、migration、pty隐藏密码管理员、固定BGE-M3缓存离线准备、真实Qdrant/RAG构建、verify、/health与/ready均通过。

打包网页真实问数、追问、多维度/排序、经营分析、私人历史/成果、取消、重启后未完成执行unconfirmed、重新登录/续聊/重查/持久性通过；12份XLSX/PNG/PDF独立内容校验通过。model缓存从原固定版本只读复制后通过prepare-model复用，不声称重新从网络下载。

原始安全报告：ignored `reports/deployment-simplification/chatbi-app-verify-1791938714-9946/`。账号已禁用，active_sessions=0；本次新建PG/Qdrant/model/RAG卷、网络和容器已按project标签清理。

### dev源码挂载环境

资源 `chatbi-verify-1791939451-11655`：独立空卷初始化、管理员、实际CPU索引构建（83秒）、热更新、就绪/回环启动、完整真实业务闭环、重启持久性与未确认执行恢复通过；12份导出独立解析通过。

原始安全报告：ignored `reports/browser-real-artifacts/result-export-v1/compose-1791940082/`。账号禁用、Session归零；临时资源按标签清理，热更新实验恢复原始源码。

## 失败历史与处置

- TDD预期Red：backup字段/socket三项；新dev test入口两项；verify命令一项；端口占用一项；弱签名配置一项。相应Green及回归已通过。
- 首轮旧开发镜像缺defusedxml、导出字体manifest不匹配，引发全量collection、XLSX与renderer失败；按当前锁文件重建后921/浏览器/renderer通过，未删除或放宽断言。
- 早期容器fixture HTTP服务名违反回环安全规则，改为共用网络命名空间；Vite配置/Playwright输出权限问题通过runner loader和可写报告子目录修复，未关闭应用sandbox。
- 首轮隔离数据库清理将同名network误识别为container，修复为container专用inspect；成功/失败清理复验，进一步核验网络标签。
- 首次标准验收运行期间修改Bash脚本导致命令截断（127）；冻结脚本后重跑成功，失败资源已清理。
- 开发真实验收首次在热重载后立即提交返回SERVICE_NOT_READY；增加只读真实ready等待，重跑完整业务及恢复通过。
- 标准业务首轮取消后追问得到SQL_REJECTED；保留失败证据，未改SQL Guard/Prompt/核心链路，后续相同业务闭环重跑通过。真实模型候选仍可能被拒绝，不将一次通过解释为模型无条件正确。
- 校验中发现端口探测接入错分支，行为测试Red揭示后修正为仅up调用，并完成14项软件与实际dev首次/重启验证。

## 边界、文档与未执行检查

- database SQL、核心AI/权限/控制数据/离线RAG模块、pyproject/uv.lock和evaluation案例均无Diff。唯一API例外为已确认details.backup删除。
- README/Runbook、Architecture/Product Scope/Roadmap、Bootstrap/Container Dev、Query API/Execution/Observability同步；应用保护归入application-readiness，标准运行归入container-deployment。
- 旧R6/R7 Spec/Design与旧Runbook完整归档到本目标history；全仓当前和历史链接修复，不改写原验收候选/结果。
- 旧开发/Stable/restore容器ID、运行状态与卷名保持；未替换或删除旧配置、密钥、备份、数据或模型。仅日常PG/Qdrant原本运行，API/Web保持原先停止状态。
- 未运行远端GitHub CI、依赖审计、四套完整AI Evaluation、OTLP云接入和整机/Docker重启；未Push/PR。无依赖/AI行为变更，正式AI评测只保留原基线适用性，不声称本候选取得新评分；真实浏览器与原生LLM验证已另列。
- 企业生产、升级回滚、备份恢复、镜像仓库发布不在本目标支持范围。

## 本机镜像身份

```text
chatbi-app:local sha256:9ce998871992b7de1e502615cee2ec3c895ac6832664ad64ec67466d5d3928ea
chatbi-demo-postgres:local sha256:9026a6af01945a6d915aa13a5c2f8821fa1a519c58af5cf8ea7891c3592482e9
chatbi-python-dev:local sha256:9b97fe16497e74f35d170816a05a5e4eb36b7c51481bb58de0e1896f77721217
chatbi-node-dev:local sha256:af5d96836e58f052d22aa1d6acdee29f04e6eaf91d97fd150f91c090a9664bc2
chatbi-browser-dev:local sha256:e451ac01fdf15e1f701cd1cdda13ad0a687492f3b6c43423595d1b594e1362cd
```

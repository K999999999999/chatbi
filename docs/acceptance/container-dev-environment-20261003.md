# 本地容器开发验收（2026-10-03）

状态：三项本地实施、Code Review和最终clean候选验收通过；未Push / PR。

## 入口与覆盖

正式行为见[开发运行Spec](../specs/container-dev-environment.md)，命令见[Runbook](../runbook.md)。宿主仅需WSL / Linux、Git、Bash、Docker；隔离验收需Compose≥2.24.4，使用[官方override规则](https://docs.docker.com/reference/compose-file/merge/)避免占用现有Qdrant端口。

```bash
scripts/verify_container_dev.sh isolated
scripts/verify_container_dev.sh real
```

`isolated`使用独立项目、空数据库 / Qdrant卷与独立端口，显式migration、真实TTY管理员创建、CPU索引构建后验证实际Compose网页。`real`复用现有开发资源，只创建专用验收账号。两个模式均检查热更新、真实问数 / 同一会话追问、停止重启和数据 / 资产身份，最后禁用专用账号并撤销Session。

正式验收要求clean candidate。开发诊断可显式设置`CHATBI_CONTAINER_ALLOW_DIRTY=1`，报告必须保留`git_dirty=true`。源码热更新是临时实验，独立记录`experiment_dirty=true`并安全恢复；真实问数阶段在恢复后的源码运行。失败报告保留，不能以假模型替代真实通过。

原始浏览器报告写ignored `reports/browser-real/`；临时0600凭证文件清理后删除。报告记录commit、镜像IDs、模型 / 资产身份和账号清理，不保存API Key、密码或完整连接串。隔离资源按本次项目标签核实后清理，不操作日常项目卷。

## 已核实的第一轮结果

- 软件624 passed、15 skipped、139 subtests passed；CLI / Compose边界7项通过。
- 前端类型 / build、Chrome打包17项、宿主Vite代理1项通过；静态、模块、Markdown、Shell与Diff检查通过。
- 隔离空卷初始化、checkpoint / 权限、交互管理员、CPU索引构建约45秒、热更新、真实两轮、持久性通过。
- 已有模型和旧索引复用通过；首次固定模型容器路径引起503，已只调整映射保留既有绝对路径身份，原manifest和业务校验未修改。
- 依赖不可连接时启动返回非零且不报告成功，修复后plain `./dev up`恢复。
- 专用账号disabled=true、active_sessions=0；独立临时卷清理，现有开发资源保留。

第一轮基于`8c506fa`上的未提交目标Diff，保留为诊断记录。最终clean候选成绩见下节。

## 最终clean代码候选

候选：`38602d9c1864add83528ff78de65d1f217907222`。两种模式均PASS，`git_dirty=false`；热更新实验独立标记`experiment_dirty=true`，恢复源码后真实查询匹配独立SQL参考，追问沿用同一conversation_id。后续提交仅回填文档，代码 / Contract不变，软件624 / 15 / 139及既有浏览器17+1证据继续适用，不将其改称重跑结果。

| 模式 | 原始本机记录 | 结果 |
| --- | --- | --- |
| 现有资源real | `/tmp/chatbi-container-verify.jff6gE/report`；`/tmp/chatbi-final-real.log` | 旧模型 / 索引复用，热更新，两轮真实查询，重启持久性通过 |
| 空卷isolated | `/tmp/chatbi-container-verify.b8RhtK/report`；`/tmp/chatbi-final-isolated.log` | migration / checkpoint、交互管理员、CPU索引37秒、热更新、两轮查询、持久性通过 |

两轮账号清理均disabled=true / active_sessions=0，临时凭证已删除；隔离容器 / 网络 / 两个卷按本次项目标签核实后清理。日常开发卷、原有用户、模型和RAG资产保留。源码恢复后工作区clean。测试报告另存ignored `reports/browser-real/`，临时路径仅为本机证据，不是可移植事实源。

实际LLM：`deepseek-flash`，Provider `api.deepseek.com`；Embedding CPU，模型config SHA256：`26159e7ad065073448460117eb24b7a4572f6f4e78eadff65dc0a11c052449fa`。

- real API镜像：`sha256:c0c09d6b9b6b20ffc4e6fbe3e48ad8348f98a254bdb2e5e2d03abf34df15d245`；Web：`sha256:df3981a9c256d36852a3335db73ab4417f9972e35594e52bf64619562b11951d`。
- isolated API镜像：`sha256:77c067976a1090059c53012f816ec6d668324cd8325414b4292fe5ab219ae8d3`；Web：`sha256:4d8d52135e217b15c3b272ba491fc792935cf78433a7b6d19caeb7640a316b68`。

本地Code Review PASS；正式Spec / Runbook / README / 环境模板及路线图已同步。无新增Harness缺口，下一需求为R2细化；本次没有远端CI / 发布授权。

## 限制

默认Embedding为CPU，但锁文件安装的PyTorch含CUDA依赖；首次Python镜像约12GB，Node开发镜像约462MB。首次构建较慢，日常up使用已有镜像，依赖变化显式build。本机网络限制时使用同版本 / digest的镜像地址覆盖，不关闭TLS；此次不改系统配置。

未重跑全套AI Evaluation；未验收GPU、Dev Container构建、Windows原生 / macOS、生产镜像 / HTTPS / 升级回滚或容量。历史Evaluation身份不改写；本项不代表R6 / R7完成。

# 开发容器验证记录

Base：`8c506fab07868c851d2ec8e5f8ed1b0b4fe0c295`。本记录第一轮对应该base上的本目标未提交Diff，不声称已是clean candidate。

## 实现与验证

| 范围 | 证据 / 结果 |
| --- | --- |
| 命令TDD | 初始3 FAIL / 1 PASS；实现后确定性命令 / Compose边界7 PASS，含停止保留卷、错误码传播、未知命令、缺配置、migration失败不等待完整healthy、管理员终端要求、API凭据 / 挂载 / 路径身份 |
| 默认软件回归 | `uv run --locked python -m pytest -q`：624 passed、15 skipped、139 subtests passed；日志 `/tmp/chatbi-final-software.log`。跳过项不宣称通过 |
| 静态 / 文档 | Ruff格式 / CI lint、模块边界、Markdown本地链接、Shell语法、`git diff --check`通过 |
| 前端 | 类型检查 / build通过；既有Chrome打包17项、宿主Vite代理1项通过；本机Chrome需已有用户cache中的运行库，通过本次进程LD_LIBRARY_PATH提供，不改系统配置 |
| 构建 | Python3.11.16 / uv0.12.2、Node24.21.0，固定基础digest；镜像内锁文件依赖与宿主隔离；Python镜像约12GB（锁文件含Torch / CUDA包），Node约462MB，验收浏览器约1.94GB；日常up复用镜像 |
| 模型入口 | `./dev prepare-model`：固定BGE-M3 revision缓存复用，ready=true，无重新下载完整权重；日志 `/tmp/chatbi-model-prepare.log` |
| 空卷初始化 | 独立project完成基础初始化、migration / checkpoint、真实TTY管理员创建、CPU索引构建45秒、实际API / Vite / Cookie和两轮真实查询；报告 `/tmp/chatbi-container-verify.pCztwp/report` |
| 热更新 / 持久性 | 实际浏览器验证Python重载与Vite CSS HMR；实验临时修改原样恢复，单列experiment_dirty；停止重启后的业务结果和RAG current身份保持 |
| 现有资产复用 | 固定模型目标导致旧manifest路径校验503，失败报告保留于 `/tmp/chatbi-container-verify.gpJVaD/report`；设计复核后只改运行挂载目标，原资产 / Guard不变。修订后真实复用通过，报告 `/tmp/chatbi-container-verify.fs0dRX/report`，第一轮仍git_dirty=true |
| 故障 | API依赖URL指向不可连接地址时`up`返回1且不报告成功；恢复原配置后plain `./dev up`成功；日志 `/tmp/chatbi-dependency-fault.log`、`/tmp/chatbi-recovered-up.log` |
| 资源清理 | 隔离project及两个临时volume按标签核实后清理；实际专用测试账号全部disabled=true / active_sessions=0，保留审计。现有开发卷、用户和`.env`保留 |

## 证据边界与失败闭环

- `uv run pytest`直接launcher的首次全量收集缺项目import路径；使用仓库规定的`python -m pytest`后通过，不改测试断言。
- 初次Docker Hub元数据请求TLS证书错误；本机Node构建使用相同digest的镜像地址覆盖，默认官方配置保留，不改系统证书 / TLS策略。
- Chromium系统依赖一次502，配置apt重试后构建通过；只作用于验收镜像。
- 首次API缺`scripts/metadata`、独立migration缺SQL目录挂载，补只读挂载后通过；工具profile需显式用于Compose配置解析，已修复并回归。
- 正式全套AI Evaluation、GPU、Dev Container构建、Windows原生 / macOS、生产部署 / HTTPS / 容量验收未运行，不属于本次承诺。
- Blueprint与真实运行证据已覆盖当前行为；最后需在本地代码candidate提交后执行正式clean容器链路，回填适用commit与资源身份。原始报告留ignored目录，不把第一轮脏状态或旧Evaluation改称最终候选通过。

## 正式事实源

新增 `docs/specs/container-dev-environment.md`，同步README、Runbook、环境模板、roadmap。Bootstrap / Web业务Contract保持，只新增运行入口与代理适配，正式开发Spec引用其语义；Architecture / 领域对象不变，无需新增ADR或业务Spec。

## Harness反馈

未观察到符合门槛的Harness缺口。路径身份与遗漏挂载属于本目标已修复的运行实现 / 设计问题；不扩大为持久规则或Plugin修改。

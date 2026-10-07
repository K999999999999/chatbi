# R6 编码前 Design Review

Review: PASS
Review Target: 已整体确认的[Spec](spec.md)与[实现设计](design.md)
Owner: 当前主Agent；当前上下文只读审查，无独立Agent，无实现Diff。

## 审查依据

已读取Architecture、产品范围、bootstrap/RAG/开发环境Contract、Runbook、现有Compose、Dockerfiles、.dockerignore、BrowserSettings、bootstrap runtime/readiness/control、数据库初始化/healthcheck及Control schema校验、R5 ExportRuntime和既有测试入口。

Reference: Architecture Knowledge Core；重点使用复杂度、依赖方向、可观察Contract、失败/状态/测试、替代方案及迁移章节。

## Findings 与处理核对

### 本机HTTP与production门禁

Signal: HTTP入口与production配置不能混用。
Evidence: BrowserSettings仅development/dev/test/testing放行回环HTTP；production启动另有RAG/secret门禁。
Impact: 直接标production会阻断登录；简单改development又可能跳过资产启动校验。
Recommendation: 使用显式development的本地交付配置，入口额外复用既有RAG/catalog检查并检查secret/静态身份，保留production和Cookie安全规则。
核对: Design已落实；不新增环境枚举，不改变默认开发入口与业务Contract。

### 开发Compose不能作为固定交付

Signal: overlay继承隐含源码/端口/重启策略。
Evidence: dev挂src/scripts/frontend，基础Compose固定Qdrant宿主端口并unless-stopped。
Impact: 版本身份不稳、资源冲突或重启行为与Spec不符。
Recommendation: 独立local Compose与完整镜像，仅API回环端口；数据/工具身份分离、全部显式启动。
核对: Design已落实；前端用现有FastAPI静态Adapter，不引入额外服务/通信层。

### marker不等于回滚兼容

Signal: 只检查旧marker会低估未知迁移或快照变化。
Evidence: schema_migrations加法记录，v2/v3等可并存；现有Runbook只承诺已验证兼容旧版。
Impact: 可能把无法安全读取数据的旧镜像启动成功当作回滚完成。
Recommendation: 发布声明已验证状态并与catalog/checkpoint/快照/RAG输入对照，未知状态拒绝；只读检查、无downgrade。
核对: Design已落实；初始状态来自权威DDL/锁文件，不以当前观测自动放行；真实release版本对与隔离不兼容场景有验证计划。

### 发布失败状态与目标机重启

Signal: 元数据可能残留旧active；全机重启影响其他项目。
Evidence: 本机还有开发服务，upgrade停止后可能失败。
Impact: 操作者误判服务实际状态或验收影响其他工作。
Recommendation: 分开记录最后成功版本与实际服务/失败阶段；目标机重启安排维护窗口，不自动执行全局重启。
核对: Design已落实；不增加R7自动恢复/监控承诺。

## 总体判断

用例、状态、授权与SQL Safety继承已有Contract；部署边界是Infrastructure/装配，不移动Domain，不新增Port/Service层。替代方案已比较，独立Compose和保守兼容声明的复杂度与当前风险匹配。所有正常/边界/失败行为具备确定性、集成或业务验收seam。

无未解决阻塞项。PASS仅说明方案可进入Ticket规划，不证明镜像已构建、验证已通过或实施已获授权。
Next: workflow-to-tickets，再由当前主Agent执行workflow-ticket-readiness。

### CPU运行时与依赖来源（实施中新证据，定向复审）

Signal: 初次按锁文件构建，CPU镜像开始安装PyTorch 2.14.0及数个CUDA/NVIDIA组件（多个wheel单项达数百MB），违背CPU/FP32目标并显著增加镜像获取时间/体积。
Evidence: 原uv.lock将torch解析自PyPI，依赖含CUDA toolkit、NVIDIA libraries、Triton；目标镜像执行`uv sync --no-dev`时显式下载这些包。PyTorch官方提供CPU安装平台；uv依赖来源可精确绑定且explicit限制索引范围。
Impact: 首次安装耗时与存储上升，交付范围无必要附带GPU运行时；改锁可改变模型运行依赖，必须锁定并回归实际Embedding链路。
Recommendation: 将torch作为明确运行依赖绑定官方CPU索引，explicit=true，更新仓库uv.lock；不单独做仅镜像的未锁pip覆盖。
处理与复审: 已将此决定纳入已确认CPU Contract的具体锁定实现，PyPI其他包来源不变。`uv lock --upgrade-package torch`移除CUDA/Triton依赖并锁定CPU wheels，`uv lock --check`待最终确认；定向Design Review PASS。继续构建并运行RAG资产/检索和适用Evaluation回归；若任一模型行为或可重复安装失败，返回设计门禁，不猜测接受。来源：[PyTorch安装选择器](https://pytorch.org/get-started/locally/)、[uv依赖来源](https://docs.astral.sh/uv/concepts/dependencies/)。

Ticket 01实现核对：固定版本构建与资产生成直接调用`/opt/venv/bin/`，避免`uv run`二次同步开发组；当前镜像smoke确认pytest/ruff未安装。此选择已在Design显式记录，属于锁定运行环境行为，不改变Contract。

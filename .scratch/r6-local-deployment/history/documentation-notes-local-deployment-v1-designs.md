# 固定版本部署与兼容切换：整理前的过程记录

来源：`docs/designs/local-deployment-v1.md`，基线 `c7f7e74`；以下为历史内容，不定义当前行为。

## 整理前入口说明

# R6 本地稳定交付实现设计

Status: 基于2026-10-07已确认[R6 Spec](../spec.md)；Design Review PASS。Ticket 01–04本地实施与适用验收完成；最终运行候选与限制见 [Acceptance](acceptance--local-deployment-v1.md)。
Owner: 当前主Agent；后续维护由交付配置、bootstrap和所属模块维护者承接。

## 事实与方案选择

- `src/query_api/browser.py:BrowserSettings.from_environment`仅对development/dev/test/testing放行回环HTTP，production/staging均要求Secure Cookie / HTTPS。首版本地交付显式设置development，固定构建与隔离通过交付入口保障；不放宽production或浏览器安全Contract，不增加新环境枚举。
- development不触发`src/bootstrap/readiness.py`的production RAG来源检查。交付入口必须额外显式调用既有`RagRuntime.verify_production_ready`和catalog检查，强制启用RAG并校验管理员密钥至少32字符及拒绝旧静态身份配置；作为交付前置检查，不改变默认开发入口。每次启动/升级/回滚都执行，检查成功不代表动态readiness。
- `docker-compose.yml`与dev overlay有源码bind、固定Qdrant端口和unless-stopped。新增独立`docker-compose.local.yml`，不叠加开发Compose：api、postgres、qdrant常驻，tools/migrator使用profiles。所有服务restart=no，手动完整启动；仅API发布回环端口，数据库与Qdrant只在项目私有网络可达。
- 数据库账号沿用既有固定角色名，但在独立PostgreSQL实例/独立凭据下创建，不修改Sales Mart grants。两套数据库仍在同一独立PostgreSQL服务中。项目资源由Compose项目名/labels和显式数据路径归属，不使用开发卷或默认全局资源名。

替代方案：复用dev overlay后逐项覆盖挂载和端口，虽然文件少但易残留源码、凭据或端口继承；独立Compose成本局部且隔离可直接核对。production + 新增HTTP例外会改变安全边界，因此不采用。

## 验证与切片

每个切片包含软件/集成检查和相应文档，不把测试全部留到最后。最终在隔离验收项目以clean candidate验证，指定Windows浏览器完成核心链路；重启验收在目标机安排明确维护窗口，不擅自重启整个Docker/电脑影响其他项目。

兼容升级/回滚使用本目标两个真实clean release提交构建的镜像（例如安装闭环候选与后续版本管理候选），保持同一业务Schema；记录其具体SHA。它证明已声明状态的兼容升级，不等于新增Schema migration跨版本能力。额外不兼容状态在隔离验收实例构造，只读拒绝后证明数据未改。

## 边界与重新审查触发

Domain/Application业务行为不变；部署脚本复用bootstrap、catalog及RAG既有边界。不得把发布兼容逻辑塞入Domain或新增业务Service层。若必须改变Cookie规则、production启动策略、migration语义、manifest格式或新增依赖，返回Spec/Design审查。预期维护寿命为持续维护的本地交付入口。

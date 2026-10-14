# Deployment Simplification 规划与交付记录

- 工作项ID：deployment-simplification；branch：refactor/deployment-simplification；BASE：f4d0693。
- 用户已确认完整Spec、四项拆分、完整本地实施/验证/相关Commit；无Push/PR或旧真实资源操作授权。
- 四项正式Tickets已完成；[Design Review](design-review.md) PASS、[Readiness](ticket-readiness.md) READY、[Code Review](code-review.md) PASS。
- [验收](acceptance.md)：最终Python921/142 subtests通过，44条件跳过均补测；数据库、浏览器、renderer、构建、两种首次部署和真实业务/重启/导出验证通过。
- 本地运行候选Commit：`40b7749f540d89a852eb091d60023311c089f230`；源码指纹与实际验收范围一致。后续仅提交交付记录，实时状态见Git公共目录harness/work-items/deployment-simplification/status.md。
- 下一步：本地交付完成；若发布，先取得另行授权。

## 历史规划与实施过程

# Deployment Simplification 规划记录

- 工作项 ID：`deployment-simplification`；审查基线：`master@f4d0693`。
- 已完成仓库 Stable 入口与依赖只读审查，输出删除 / 保留清单与风险。
- 用户确认统一 `./dev` 容器开发，取消宿主 `uv run` 教程；保留容器和 CI 内 uv / 依赖锁文件。不维护镜像发布体系。
- 用户确认删除运维状态 API 的 `details.backup` 和网页备份提示；其他业务 Contract 不变。
- 用户已确认[完整 Spec](spec.md)。[实现设计](design.md)已完成，[Design Review](design-review.md)为PASS。
- [四项 Ticket 草案](tickets-draft.md)经当前主Agent[Readiness](ticket-readiness.md)为READY；尚无实现、Commit或发布授权，没有正式Tickets。
- 实时阶段与授权以 Git 公共目录 `harness/work-items/deployment-simplification/status.md` 为准。
- 下一步：用户确认四项拆分及完整本地实施/验证/Commit范围；随后正式写入Tickets并连续实施。
- Roadmap已读取，本阶段只形成计划，尚未修改正式产品文档；实施交付时同步已确认部署边界与实际完成事实。

## 实施进度

- 四项正式Tickets已按用户确认写入issues；refactor/deployment-simplification从fetch核实同步的master f4d0693开始。
- 01 TDD Red为备份字段和运维socket三个预期失败，Green定向61项通过；operations浏览器7项通过，最终回归待汇总。
- 02入口TDD Red两项预期失败，Green软件8项通过；隔离PG CI 5项/development 46项通过，标签清理已修复并复验。
- 03标准api/database/browser镜像构建成功；空卷迁移、隐藏密码管理员、固定模型缓存和真实RAG构建成功。首轮脚本运行期间更新引起命令截断，临时资源已清理，冻结脚本重跑。
- 首轮全量/浏览器/renderer发现旧开发镜像缺defusedxml及字体manifest不匹配，按当前锁文件重建后复验；不得作为产品通过证据。
- 04文档/历史链接更新进行中；未观察数据库SQL/评测案例/核心业务模块改动。

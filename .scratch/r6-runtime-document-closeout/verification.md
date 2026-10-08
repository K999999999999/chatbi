# R6 稳定恢复与文档收尾验证

基线：master `9a706016504be6145e7a702536d858b2d641d957`；文档候选位于 `fix/r6-runtime-document-closeout`。运行证据绑定既有clean runtime `2b4a8c811713adb663d22cdac4108e13e731165f`，不冒称文档候选取得新的完整业务验收身份。

## 服务恢复结果（2026-10-08）

- `./local up`：退出0；镜像身份、管理员、网页 / 导出资产、Control / checkpoint migration、历史快照版本、Seed / catalog与固定来源RAG只读兼容校验通过。
- API仍为2b4a8c8，API / PostgreSQL healthy，Qdrant running；`curl --noproxy '*' http://127.0.0.1:8080/health`返回ok，网页HTTP200；部署状态running/succeeded。
- PostgreSQL由Compose按发布记录重建，镜像从733b074切换为2b4a8c8；原数据库卷保持。Qdrant镜像 / 容器 / 卷和API镜像身份未变。
- 只读查询4账号 / 3历史 / 3turn / 0成果；以历史相同的PostgreSQL jsonb聚合排序和SHA-256算法核验，四表完整行指纹均匹配此前stable-upgrade.json的after。Seed为chatbi-sales-mart-dev-v3，业务表1,166行。
- 两个稳定持久卷与其他项目的容器身份、镜像、状态、启动时间和卷保持。原始证据保存于ignored `reports/browser-real-artifacts/r6-runtime-recovery-20261008/{before,after,verification}.json`，不含原始账号或业务行。
- 初次以postgres角色读取失败（不存在该role），改用容器配置的migrator角色只读核验；首次JSON指纹编码不同无法比较，找到历史只读算法后全部匹配。失败不作为通过证据。

## 文档范围与剩余边界

补齐正式Acceptance、roadmap、R6完整Spec、Ticket04与产品V1工作记录中的当前授权 / 交付状态；原阶段记录保留为历史。核对product-scope、正式Contract、Design和Runbook现有范围仍正确，不改变业务行为或路线优先级。

未运行：整机 / Docker重启、登录 / 问数 / 导出完整浏览器重验、三套正式AI Evaluation。停止原因未确认；不改变手动启停Contract、IDM配置或R7范围。此恢复不构成重启恢复验收通过。

Harness：产品V1仍待R7；presubmit-coverage仍是未授权发现项，两者不阻碍当前任务。此前文档更新遗漏本次已补齐，遵循现有事实源同步规则，不新增持久工作流规则。

## 文档验证与Review

`python3 -m scripts.check_markdown_links`：PASS；`git diff --check`：PASS。当前上下文执行workflow-code-review，BASE 9a70601、范围为本Spec声明的文档：PASS。核对PR60真实MERGED、候选与运行身份、重建PG事实、持久指纹、授权和未运行限制；不触及代码、Domain、权限或公共Contract。纯文档变更无需软件测试。

本地candidate已准备，尚未Push或创建本次新PR；整个交付生命周期保持待发布授权，关联本机记录保留可发现的下一步。

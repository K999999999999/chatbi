# 03 完整运行验收与交付证据

Status: done
Owner: 当前主 Agent
Canonical Source: ../spec.md、../design.md
Authorization: 用户已确认三项拆分并授权整体本地实施；不含发布

### Change Profile / Owner

Lifetime：持续维护的验收入口及日期化证据；Size：中；Risk：较高，涉及真实API费用、账号和测试清理；Evidence：隔离新环境、真实Compose浏览器、独立SQL参考、运行资源身份。Owner：当前主 Agent。

### Blocked by

02，实际四服务与统一入口已完成；不重复列传递依赖01。

### What to build

- 建立可重复的开发运行验收入口，独立project / volume / 端口验证首次准备、状态、故障与持久性；无宿主Python / Node依赖。
- 为实际Compose网页 / API建立外部服务模式的浏览器配置与两轮真实问数验证，复用已有安全reporter、账号与参考值逻辑。不能让webServer另起宿主替身取代被验收目标。
- 真实调用少量已获授权；只创建 / 禁用专用验收账号并撤销Session，保留审计，不变更已有用户。
- 完成最终candidate的针对性软件回归、CPU / 模型与索引命令验证、运行检查、Code Review、正式Contract / Runbook / README / Acceptance及roadmap完成事实。

### Owned files

`scripts/verify_container_dev.sh`（新，或同等单一入口）、`frontend/playwright.container.config.ts`（新）、`frontend/tests/container-real.spec.ts`（新）、必要的`tests/browser_*`验收支持和`tests/scripts/test_container_dev.py`；`docs/acceptance/`的本目标记录、README / Runbook / 正式开发Spec、`docs/roadmap.md`、本项工作记录。测试工具和临时支持不得进入常驻API；原始报告写ignored目录。准确路径在实施中按最小复用决定，不扩展产品功能。

### Acceptance criteria

1. 隔离空数据卷首次准备至浏览器登录可复现；临时项目清理只作用于经标签 / 身份核实的本次资源。
2. 模型准备 / RAG构建的容器入口可用，固定模型身份和既有资产复用得到核实；实际CPU构建耗时记录，不预设性能承诺。
3. 实际Compose链路完成登录→问数→同一对话追问，匹配只读账号的独立SQL参考；浏览器报告记录candidate、镜像、模型、RAG和数据范围，凭证不入报告。
4. 热更新证据单列临时实验Diff；恢复后在clean candidate执行最终真实链路，不把脏状态改称clean。
5. 正常停止重启持久数据 / 模型 / 索引身份保持，故障和配置缺失证据齐全；账号disabled与活跃Session为0有安全核对。
6. 全部适用软件 / 浏览器 / 运行检查及Review通过；未执行项如实列出，不重跑或声明新的全套AI Evaluation基线。
7. 正式事实源可供新clone使用，roadmap只标本地开发准备完成并返回R2，R6生产部署仍待验收。

### 验证证据 / Done When

执行并记录Spec验收表全部适用场景；记录无关 / 可复用证据理由，发现真实失败补回归并修复。验证与Review绑定最终candidate，文档 / Diff检查完成、工作项状态准确，形成本地交付报告与Commit。Push / PR发布授权独立取得，当前Ticket不包含远端动作。

### Migration / Rollback

验收失败保留诊断和持久开发数据，不降低通过条件。撤销本次账号会话、禁用专用账号，清理经核实的临时容器卷；无生产发布、Feature Flag或线上回滚要求。外部资源不可用如实阻塞，不替换为假模型宣称真实通过。

## Result

运行验收入口、正式事实源与最终clean candidate验收完成。代码候选38602d9；real和isolated均PASS，账号禁用 / Session清零 / 临时卷清理已核实。证据见[verification](../verification.md)及[正式验收记录](../../../docs/acceptance/container-dev-environment-20261003.md)。仅本地交付，未Push / PR。

## Comments

拆分与整体实施已获本轮确认，按01→02→03连续推进。

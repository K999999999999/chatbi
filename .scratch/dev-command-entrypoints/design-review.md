# Design Review

Review: PASS
Review Target: [已确认 Spec](spec.md)、[实现设计](design.md)
Reviewer: 当前主 Agent，只读审查；未启动独立 Agent。审查与方案写作分步进行；本文件记录结论，不改变 Contract。
Baseline: master@38e1302；只审查方案，不表示实现已验证。

## Findings

### 1. 恢复配置与应用配置耦合已在设计中处理

- Signal: 完整应用配置可能使紧急恢复依赖无关Secret和资产。
- Evidence: docker-compose.app.yml x-runtime对LLM_API_KEY、CHATBI_ADMIN_SECRET_KEY、QDRANT_API_KEY强制插值，tools继承该配置；设计第5节改为同一文件集未插值结构、最小服务和已运行PG namespace。
- Impact: 若直接compose run tools，API停机且无LLM配置时无法恢复，违反已确认边界。
- Recommendation: 按最小服务实现，并用真实Compose测试缺少LLM/Qdrant/管理员Key仍可恢复；未知配置形状须拒绝。已纳入设计与T06验收，无待定权限决定。

### 2. 账号状态、并发及强制审计已形成完整事务方案

- Signal: 复用普通重置并在CLI外判断admin会出现状态竞争及无审计成功。
- Evidence: AuthService.reset_password使用session.get；_write_security_audit在Sink=None时直接返回；login/change_password已有User锁。SQLAdmin只有部分修改锁User，set_user_roles缺少User锁。PersistentAuditSink.write向调用方事务追加AuditEvent。
- Impact: 可能恢复已经撤权的账号或允许未记录的密码变更；旧Session竞争难以验证。
- Recommendation: 专用恢复事务、 mandatory write、User锁后重新校验；所有相关已有写路径统一User先锁，不改变其权限规则。设计已明确锁顺序和真实PG并发验收；审计提交失败回滚为T06阻断项。

### 3. 统一入口的复杂度与迁移范围受控

- Signal: 将全部脚本变成独立命令，或直接删除旧runner，会放大维护成本或丢失断言。
- Evidence: inventory覆盖24/24文件；dev已有container_tasks路由；real.spec.ts有独立SQL真值和真实业务断言；linked worktree的.git为文件。
- Impact: 包装链过多、消费者和测试身份不明，会使单一入口仅是表面整理。
- Recommendation: 保留现有执行器、一个共享目标辅助文件；内部分别保留，旧入口按Expand→Migrate→Contract证明覆盖后处理；Git以真实common-dir装配。设计和T01/T02/T03/T07覆盖，无通用命令框架。

## 检查结论

用例、八类命令、退出码、隔离项目、host/container职责、受限恢复、事务和失败边界可实施。重置不可逆性及真实管理员不操作已明确。新增能力没有Domain→Bootstrap/Docker反向依赖，不引入数据库或身份平台。相关普通认证写路径仅调整锁与刷新，范围服务于恢复竞争保护。

Reference: 已完整读取Architecture Knowledge Core；重点为职责/依赖、深模块、Observable Behavior、安全可测试性、Design Twice及Deprecation。另读取Migration and Large-Scale Change。
Evidence Sources: AGENTS规则、docs/agents/issue-tracker.md、docs/agents/domain.md、docs/architecture.md、docs/product-scope.md、docs/roadmap.md、docs/specs/bootstrap.md、docs/specs/container-dev-environment.md；dev、container_tasks.sh、Compose、Bootstrap命令、AuthService、账号管理、事务审计及对应测试位置。既有完整盘点与只读Compose结构解析证据沿用，未运行产品测试。
Next: workflow-to-tickets；PASS不代表代码实施或远端发布授权。

# R7 首轮 Design Review

Review: NEED FIX
Review Target: 用户已整体确认的 spec.md；baseline0c77d80。当前主Agent只读执行，未修改目标Spec/代码/测试/配置。

## Findings

1. Signal: 恢复切换缺少明确资源绑定与中断恢复机制。
   Evidence: local固定chatbi-stable项目；docker-compose.local.yml固定两个卷名与.local/rag；Spec要求先隔离恢复、显式切换并保留原数据。
   Impact: 切换可能误用原卷、两个PG同时挂同一卷、配置/资源指针中断后不一致。
   Recommendation: 在既有工具边界明确版本化resource binding、切换journal、候选停机与单写者、验证和回退顺序；原配置与卷不覆盖删除。
2. Signal: 加密产物有效性校验与公钥加密职责未落实。
   Evidence: age加密仅需公钥，完整解密/有效性校验需私钥；Spec要求校验成功才登记/清理。
   Impact: 仅加密退出0不足以证明可恢复；秘钥挂载范围可能被误扩大到业务API。
   Recommendation: 工具独占受限key，备份用公钥，工具内私钥解密校验；保护临时文件和已知副本目录，清理在最终成功登记之后。
3. Signal: 同步入口与后台额度的现有租约边界不一致。
   Evidence: ExecutionRuntime.reserve需要history_id并取得history/analysis租约；同步/api/v1/query直接调用授权服务，无持久history execution。
   Impact: 用伪history_id接入会改变同步行为或重复取analysis lease；外层超时可能释放仍运行的工作。
   Recommendation: 从现有runtime抽出仅负责owner/API额度的同一计数/租约机制，后台组合history/analysis租约，同步只取额度并复用原analysis guard；停止生命周期保持真实结束后释放。
4. Signal: 状态接口、只读认证和后台Trace生命周期须落到设计。
   Evidence: BrowserIdentityProvider.authenticate_readonly已经存在；默认authenticate会滑动TTL；TraceRecorder根作用域在HTTP结束后失效；Spec要求无保活/覆盖后台任务。
   Impact: 状态轮询改变登录期限，异步Trace丢失/伪关联，60秒目标无法客观验收。
   Recommendation: 明确最小状态DTO与readonly认证、轮询/检查/过期预算，以及独立worker trace与安全关联，不复用已关闭根作用域。

Reference: Architecture Knowledge Core第2–9节（复杂度、依赖、Contract、状态/可测试性、Design Twice）。
Evidence Sources: local、compose.local、ExecutionRuntime、同步query路由、BrowserIdentityProvider/AuthService、OTel TraceRecorder、R4/R5/Web/Observability Contract、PostgreSQL16 pg_dump及age官方资料。
Next: 返回实现设计阶段，在已确认Contract内补齐上述机制，复审后才拆Ticket。

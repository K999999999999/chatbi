namespace ChatBI.PlatformIntegration;


/**
 * Enterprise AI Platform（企业 AI 平台）
 * 认证后的用户主体标识。
 */
scalar PrincipalId extends string;


/**
 * 企业租户标识。
 */
scalar TenantId extends string;


/**
 * Product Conversation（产品会话）标识。
 */
scalar ConversationId extends string;


/**
 * Platform Message（平台消息）标识。
 */
scalar MessageId extends string;


/**
 * 一次 ChatBI Run（执行实例）的唯一标识。
 */
scalar RunId extends string;


/**
 * ChatBI Domain State（领域状态）的不透明引用。
 *
 * Platform 可以保存并回传该值，
 * 但不得解释其内部含义。
 */
scalar StateReference extends string;


/**
 * ChatBI 业务结果的稳定引用。
 */
scalar ResultReference extends string;


/**
 * Platform Authentication（平台认证）后
 * 传递给 ChatBI 的主体上下文。
 *
 * 这些信息只是 Domain Authorization（领域授权）的输入，
 * 不直接代表最终业务数据权限。
 */
model PrincipalContext {

  /**
   * 当前用户或调用主体的唯一标识。
   */
  subjectId: PrincipalId;

  /**
   * 所属企业或租户。
   */
  tenantId?: TenantId;

  /**
   * Platform 提供的角色信息。
   */
  roles?: string[];

  /**
   * Platform 提供的其他身份属性。
   *
   * 可以作为 Domain Authorization（领域授权）输入，
   * 但不能直接代表最终 Data Scope（数据范围）。
   */
  attributes?: Record<unknown>;
}


/**
 * Platform Product Conversation（产品会话）上下文。
 */
model ConversationContext {

  /**
   * Platform 管理的产品会话标识。
   */
  conversationId?: ConversationId;

  /**
   * 当前 Platform Message（消息）标识。
   */
  messageId?: MessageId;

  /**
   * 上一次 ChatBI 返回的
   * Domain State（领域状态）引用。
   */
  stateRef?: StateReference;
}


/**
 * 启动一次 ChatBI Run（执行实例）所需输入。
 */
model RunRequest {

  /**
   * 用户当前提交给 ChatBI 的自然语言输入。
   */
  input: string;

  /**
   * Platform 已确认的主体上下文。
   *
   * ChatBI 仍需根据领域规则执行
   * Domain Authorization（领域授权）。
   */
  principal: PrincipalContext;

  /**
   * 连续业务任务需要的会话上下文。
   */
  conversation?: ConversationContext;
}


/**
 * 查询结果字段定义。
 */
model QueryColumn {

  /**
   * 字段名称。
   */
  name: string;

  /**
   * 字段的数据类型描述。
   */
  type: string;
}


/**
 * 指向可信结果或分析依据的
 * Evidence（证据）引用。
 */
model EvidenceReference {

  /**
   * Evidence 的稳定引用。
   */
  reference: string;

  /**
   * 面向展示的可选说明。
   */
  label?: string;
}


/**
 * Natural Language Query（自然语言查询）
 * 成功后的业务结果。
 */
model QueryResult {

  /**
   * 查询结果稳定引用。
   */
  resultRef: ResultReference;

  /**
   * 查询结果字段。
   */
  columns: QueryColumn[];

  /**
   * 查询结果数据行。
   *
   * 不同业务查询具有不同字段结构，
   * 因此保持动态对象结构。
   */
  rows: Record<unknown>[];

  /**
   * 返回的数据行数。
   */
  rowCount: int32;

  /**
   * 支撑结果的 Evidence（证据）。
   */
  evidence?: EvidenceReference[];
}


/**
 * Business Analysis（经营分析）
 * 成功后的业务结果。
 */
model AnalysisResult {

  /**
   * 分析结果稳定引用。
   */
  resultRef: ResultReference;

  /**
   * 基于可信业务数据形成的分析内容。
   */
  content: string;

  /**
   * 支撑分析结论的 Evidence（证据）。
   */
  evidence: EvidenceReference[];
}


/**
 * 当前输入不足以确定唯一业务语义。
 */
model Clarification {

  /**
   * ChatBI 需要用户补充回答的问题。
   */
  question: string;

  /**
   * 如果存在明确候选项，
   * 可以由 Platform 展示给用户。
   */
  options?: string[];
}


/**
 * 请求超出 ChatBI 当前支持的
 * Product / Domain（产品 / 领域）范围。
 */
model UnsupportedRequest {

  /**
   * 当前请求无法处理的业务原因。
   */
  reason: string;
}


/**
 * 一次 Run 的正常 Business Outcome（业务结果）。
 *
 * 使用 kind 区分具体结果类型。
 */
@discriminated(#{
  envelope: "none"
})
union RunOutcome {
  query_result: QueryResult,
  analysis_result: AnalysisResult,
  clarification: Clarification,
  unsupported_request: UnsupportedRequest,
}


/**
 * 一次 ChatBI Run（执行实例）的最终正常响应。
 */
model RunResponse {

  /**
   * 当前 Run 标识。
   */
  runId: RunId;

  /**
   * 当前 Run 的业务结果。
   */
  outcome: RunOutcome;

  /**
   * 最新 Domain State（领域状态）引用。
   *
   * Platform 可以保存并在后续请求中原样回传。
   */
  stateRef?: StateReference;
}


/**
 * System Error（系统错误）分类。
 */
enum ErrorCode {
  InvalidRequest: "invalid_request",
  Unauthenticated: "unauthenticated",
  Forbidden: "forbidden",
  Timeout: "timeout",
  DependencyUnavailable: "dependency_unavailable",
  InternalError: "internal_error",
}


/**
 * ChatBI Platform API 标准系统错误。
 */
@error
model ErrorResponse {

  /**
   * 稳定错误编码。
   */
  code: ErrorCode;

  /**
   * 面向调用方的错误说明。
   */
  message: string;

  /**
   * 如果已经创建 Run，
   * 返回对应 Run Id。
   */
  runId?: RunId;

  /**
   * 当前请求是否可以安全重试。
   */
  retryable: boolean;
}


/* =========================================================
 * SSE Streaming Contract（SSE 流式契约）
 * ========================================================= */




/**
 * SSE 连接建立后，
 * ChatBI 首先返回当前 Run 的标识。
 */
model RunStartedEvent {

  /**
   * 当前 Run 标识。
   */
  runId: RunId;
}


/**
 * Run 执行期间允许实时展示的增量内容。
 *
 * 这里只允许发送已经允许对外展示的内容，
 * 不得发送未经权限或安全校验的数据。
 */
model RunDeltaEvent {

  /**
   * 当前 Run 标识。
   */
  runId: RunId;

  /**
   * 当前新增的展示内容。
   */
  delta: string;
}


/**
 * Run 正常结束事件。
 *
 * 最终结果仍以完整 RunResponse 为准。
 */
model RunCompletedEvent {

  /**
   * 最终完整业务响应。
   */
  response: RunResponse;
}


/**
 * SSE 已经建立以后发生的执行错误。
 *
 * 因为 HTTP Response 已经开始，
 * 此时通过 SSE Terminal Event（终止事件）
 * 表达失败。
 */
model RunFailedEvent {

  /**
   * 当前 Run 标识。
   */
  runId: RunId;

  /**
   * 当前错误。
   */
  error: ErrorResponse;
}


/**
 * ChatBI Run 的 SSE Event Set（事件集合）。
 *
 * named union variant（具名联合成员）
 * 对应 SSE event 类型。
 */
@TypeSpec.Events.events
union RunStreamEvents {

  /**
   * Run 已创建。
   */
  started: RunStartedEvent,

  /**
   * 新的流式输出内容。
   */
  delta: RunDeltaEvent,

  /**
   * Run 正常完成。
   *
   * 客户端收到该事件后结束 SSE 连接。
   */
  @TypeSpec.SSE.terminalEvent
  completed: RunCompletedEvent,

  /**
   * SSE 建立后 Run 执行失败。
   *
   * 客户端收到该事件后结束 SSE 连接。
   */
  @TypeSpec.SSE.terminalEvent
  failed: RunFailedEvent,
}

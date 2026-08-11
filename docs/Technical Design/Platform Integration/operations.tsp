using Http;

namespace ChatBI.PlatformIntegration;


/**
 * ChatBI Platform API 的公共请求参数。
 */
model ApiVersionParameter {

  /**
   * 调用方希望使用的 ChatBI API Version（接口版本）。
   *
   * 例如：
   * 2026-08-12
   */
  @query("api-version")
  apiVersion: string;
}


/**
 * ChatBI Run API（执行接口）。
 *
 * Enterprise AI Platform（企业 AI 平台）
 * 通过该接口调用 ChatBI 领域能力。
 *
 * 当前支持：
 *
 * - Blocking（阻塞执行）
 * - SSE Streaming（SSE 流式执行）
 */
@route("/runs")
interface Runs {

  /**
   * 创建并执行一次 Blocking Run（阻塞执行实例）。
   *
   * 请求保持连接，
   * 直到得到最终 Business Outcome（业务结果）
   * 或 System Error（系统错误）。
   */
  @post
  op create(
    ...ApiVersionParameter,
    @body request: RunRequest
  ):

    /**
     * Run 得到正常 Business Outcome（业务结果）。
     */
    | {
        @statusCode statusCode: 200;
        @body body: RunResponse;
      }

    /**
     * 请求结构或参数无效。
     */
    | {
        @statusCode statusCode: 400;
        @body body: ErrorResponse;
      }

    /**
     * Authentication（身份认证）失败。
     */
    | {
        @statusCode statusCode: 401;
        @body body: ErrorResponse;
      }

    /**
     * Domain Authorization（领域授权）拒绝。
     */
    | {
        @statusCode statusCode: 403;
        @body body: ErrorResponse;
      }

    /**
     * ChatBI 内部发生未预期错误。
     */
    | {
        @statusCode statusCode: 500;
        @body body: ErrorResponse;
      }

    /**
     * ChatBI 依赖的外部服务不可用。
     *
     * 例如：
     *
     * - Model Service（模型服务）
     * - Business Data Source（业务数据源）
     */
    | {
        @statusCode statusCode: 503;
        @body body: ErrorResponse;
      }

    /**
     * Run 执行超时。
     */
    | {
        @statusCode statusCode: 504;
        @body body: ErrorResponse;
      };


  /**
   * 创建并执行一次 SSE Streaming Run（SSE 流式执行实例）。
   *
   * 成功建立连接后，
   * Server 通过 text/event-stream
   * 持续返回 RunStreamEvents。
   */
  @route("/stream")
  @post
  op stream(
    ...ApiVersionParameter,
    @body request: RunRequest
  ):

    /**
     * SSE Streaming 正常建立。
     *
     * 流中的最终结果由：
     *
     * - completed
     * - failed
     *
     * Terminal Event（终止事件）结束。
     */
     | TypeSpec.SSE.SSEStream<RunStreamEvents>

    /**
     * SSE 建立之前发现请求无效。
     */
    | {
        @statusCode statusCode: 400;
        @body body: ErrorResponse;
      }

    /**
     * SSE 建立之前 Authentication（身份认证）失败。
     */
    | {
        @statusCode statusCode: 401;
        @body body: ErrorResponse;
      }

    /**
     * SSE 建立之前 Domain Authorization（领域授权）失败。
     */
    | {
        @statusCode statusCode: 403;
        @body body: ErrorResponse;
      }

    /**
     * SSE 建立之前发生内部错误。
     */
    | {
        @statusCode statusCode: 500;
        @body body: ErrorResponse;
      }

    /**
     * SSE 建立之前发现外部依赖不可用。
     */
    | {
        @statusCode statusCode: 503;
        @body body: ErrorResponse;
      }

    /**
     * SSE 建立之前发生请求超时。
     */
    | {
        @statusCode statusCode: 504;
        @body body: ErrorResponse;
      };
}

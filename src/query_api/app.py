"""FastAPI HTTP 适配层。"""

import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, NoReturn, Protocol
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictStr

from src.authorization.contracts import (
    AuditSink,
    AuthContext,
    AuthenticationRequired,
    AuthorizationPolicyStore,
    AuthorizationPolicyUnavailable,
    IdentityProviderAdapter,
    IdentityProviderUnavailable,
)
from src.authorization.query_entry import (
    AuthorizedQueryService,
)
from src.observability.contracts import QuerySource, TraceRecorder
from src.observability.tracing import create_trace_recorder
from src.online_query.contracts import (
    QueryErrorCode,
    QueryFailure,
    QueryRequest,
    QueryResult,
    QuerySuccess,
)

from .conversation import (
    ConversationConflictError,
    ConversationLease,
    ConversationStore,
    ConversationUnavailableError,
    InMemoryConversationStore,
)
from .semantic_revision import SemanticRevisionError, revise_semantic_query

_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_LOGGER = logging.getLogger(__name__)


_HTTP_STATUS_BY_ERROR = {
    QueryErrorCode.INVALID_REQUEST: 400,
    QueryErrorCode.AUTHENTICATION_REQUIRED: 401,
    QueryErrorCode.AUTHORIZATION_DENIED: 403,
    QueryErrorCode.AUTHENTICATION_UNAVAILABLE: 503,
    QueryErrorCode.CANNOT_ANSWER: 422,
    QueryErrorCode.SQL_REJECTED: 422,
    QueryErrorCode.LLM_ERROR: 502,
    QueryErrorCode.CONTEXT_ERROR: 503,
    QueryErrorCode.DATABASE_ERROR: 503,
    QueryErrorCode.QUERY_TIMEOUT: 504,
    QueryErrorCode.CONVERSATION_UNAVAILABLE: 404,
    QueryErrorCode.CLARIFICATION_REQUIRED: 422,
    QueryErrorCode.UNSUPPORTED_ANALYSIS: 422,
    QueryErrorCode.CONVERSATION_CONFLICT: 409,
}


class QueryService(Protocol):
    """API Adapter 依赖的最小下游执行接口。"""

    def execute(self, request: QueryRequest) -> QueryResult:
        """执行一次已经通过授权的在线查询。"""


class QueryBody(BaseModel):
    """HTTP 查询请求体。"""

    model_config = ConfigDict(extra="forbid")

    question: StrictStr
    conversation_id: StrictStr | None = None


class QuerySuccessResponse(BaseModel):
    """HTTP 查询成功响应。"""

    request_id: str
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    conversation_id: str


class QueryFailureResponse(BaseModel):
    """HTTP 查询失败响应。"""

    request_id: str
    error_code: QueryErrorCode
    error_message: str


class _MissingIdentityProvider:
    """没有配置 Provider 时的安全默认值。"""

    identity_provider = "missing"

    def authenticate(self, provider_input: object | None = None) -> AuthContext:
        del provider_input
        raise AuthenticationRequired("未配置身份 Provider")


class _UnavailablePolicyStore:
    """没有配置策略时的安全默认值。"""

    def authorize(
        self,
        auth_context: AuthContext,
        *,
        resource: str,
        action: str,
        mode: str,
    ) -> NoReturn:
        del auth_context, resource, action, mode
        raise AuthorizationPolicyUnavailable("未配置授权策略")


def create_app(
    service: QueryService,
    trace_recorder: TraceRecorder | None = None,
    *,
    audit_sink: AuditSink | None = None,
    identity_provider: IdentityProviderAdapter | None = None,
    policy_store: AuthorizationPolicyStore | None = None,
    conversation_store: ConversationStore | None = None,
    query_understanding: object | None = None,
) -> FastAPI:
    """创建绑定查询服务的 FastAPI 应用。"""

    provider = identity_provider or _MissingIdentityProvider()
    authorization_store = policy_store or _UnavailablePolicyStore()
    active_conversation_store = (
        conversation_store
        if conversation_store is not None
        else InMemoryConversationStore()
    )
    authorized_service = AuthorizedQueryService(
        service,
        authorization_store,
        audit_sink=audit_sink,
    )
    recorder = trace_recorder or getattr(service, "_trace_recorder", None)
    if recorder is None:
        try:
            recorder = create_trace_recorder()
        except Exception:
            recorder = None

    app = FastAPI(
        title="ChatBI Query API",
        version="0.1.0",
    )
    app.state.query_service = authorized_service
    app.state.identity_provider = provider
    app.state.authorization_policy_store = authorization_store
    app.state.audit_sink = audit_sink
    app.state.trace_recorder = recorder
    app.state.conversation_store = active_conversation_store
    app.state.query_understanding = query_understanding

    @app.middleware("http")
    async def observability_middleware(
        request: Request,
        call_next: Any,
    ) -> JSONResponse:
        if request.url.path != "/api/v1/query":
            return await call_next(request)
        request_id = _request_id_from_header(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        with _http_trace_scope(recorder, request_id) as trace_scope:
            response = await call_next(request)
            response.headers["X-Trace-ID"] = trace_scope.trace_id
            return response

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(RequestValidationError)
    def request_validation_error(
        request: Request,
        _: RequestValidationError,
    ) -> JSONResponse:
        result = QueryFailure(
            request_id=_request_id_from_state(request),
            error_code=QueryErrorCode.INVALID_REQUEST,
            error_message="查询问题不能为空或格式错误",
            failure_stage="request_validation",
            internal_reason="INVALID_REQUEST_BODY",
        )
        return _result_response(result, trace_recorder=recorder)

    @app.post(
        "/api/v1/query",
        response_model=QuerySuccessResponse,
        responses={
            400: {"model": QueryFailureResponse},
            401: {"model": QueryFailureResponse},
            403: {"model": QueryFailureResponse},
            404: {"model": QueryFailureResponse},
            422: {"model": QueryFailureResponse},
            409: {"model": QueryFailureResponse},
            502: {"model": QueryFailureResponse},
            503: {"model": QueryFailureResponse},
            504: {"model": QueryFailureResponse},
        },
    )
    def query(
        request: Request,
        body: QueryBody,
    ) -> JSONResponse:
        result = _authorized_query(
            request,
            question=body.question,
            conversation_id=body.conversation_id,
            identity_provider=provider,
            query_service=authorized_service,
            conversation_store=active_conversation_store,
            query_understanding=query_understanding,
        )
        query_result, response_conversation_id = result
        return _result_response(
            query_result,
            conversation_id=response_conversation_id,
            trace_recorder=recorder,
        )

    return app


def _authorized_query(
    request: Request,
    *,
    question: str,
    conversation_id: str | None,
    identity_provider: IdentityProviderAdapter,
    query_service: AuthorizedQueryService,
    conversation_store: ConversationStore,
    query_understanding: object | None,
) -> tuple[QueryResult, str | None]:
    request_id = _request_id_from_state(request)
    try:
        auth_context = identity_provider.authenticate(request)
    except AuthenticationRequired:
        return (
            query_service.authentication_failure(
                request_id,
                error_code=QueryErrorCode.AUTHENTICATION_REQUIRED,
                internal_reason="AUTHENTICATION_REQUIRED",
                identity_provider=_provider_name(identity_provider),
            ),
            None,
        )
    except IdentityProviderUnavailable:
        return (
            query_service.authentication_failure(
                request_id,
                error_code=QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
                internal_reason="IDENTITY_PROVIDER_UNAVAILABLE",
                identity_provider=_provider_name(identity_provider),
            ),
            None,
        )
    except Exception as exc:  # noqa: BLE001 - authentication must Fail Closed
        _LOGGER.warning(
            "Identity Provider failure: error_type=%s",
            type(exc).__name__,
        )
        return (
            query_service.authentication_failure(
                request_id,
                error_code=QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
                internal_reason="IDENTITY_PROVIDER_FAILURE",
                identity_provider=_provider_name(identity_provider),
            ),
            None,
        )

    if not isinstance(auth_context, AuthContext):
        _LOGGER.warning(
            "Identity Provider returned invalid context: value_type=%s",
            type(auth_context).__name__,
        )
        return (
            query_service.authentication_failure(
                request_id,
                error_code=QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
                internal_reason="INVALID_AUTH_CONTEXT",
                identity_provider=_provider_name(identity_provider),
            ),
            None,
        )

    lease: ConversationLease | None = None
    if conversation_id is not None:
        try:
            lease = conversation_store.acquire(
                conversation_id,
                subject_id=auth_context.subject_id,
            )
        except ConversationUnavailableError:
            return (
                _conversation_failure(
                    request_id,
                    QueryErrorCode.CONVERSATION_UNAVAILABLE,
                ),
                None,
            )
        except ConversationConflictError:
            return (
                _conversation_failure(
                    request_id,
                    QueryErrorCode.CONVERSATION_CONFLICT,
                ),
                None,
            )

    request = QueryRequest(
        question=question,
        request_id=request_id,
    )
    try:
        authorization_result = query_service.authorize(
            request,
            auth_context=auth_context,
        )
        if authorization_result is not None:
            if lease is not None:
                conversation_store.abort(lease)
            return authorization_result, None

        effective_request = request
        if lease is not None:
            try:
                revised_state = revise_semantic_query(
                    lease.record.structured_query_state,
                    question,
                    query_understanding=query_understanding,
                )
            except SemanticRevisionError as exc:
                conversation_store.abort(lease)
                return _semantic_revision_failure(request_id, exc), None
            effective_request = QueryRequest(
                question=question,
                request_id=request_id,
                semantic_query=revised_state,
            )
        result = query_service.execute_authorized(effective_request)
    except Exception:
        if lease is not None:
            conversation_store.abort(lease)
        raise

    if isinstance(result, QuerySuccess):
        if lease is None:
            state = result.semantic_query
            response_conversation_id = conversation_store.create(
                subject_id=auth_context.subject_id,
                structured_query_state=state,
            ).conversation_id
        else:
            try:
                state = result.semantic_query or effective_request.semantic_query
                conversation_store.commit(
                    lease,
                    structured_query_state=state,
                )
            except Exception:
                conversation_store.abort(lease)
                raise
            response_conversation_id = lease.record.conversation_id
        return result, response_conversation_id

    if lease is not None:
        conversation_store.abort(lease)
    return result, None


def _conversation_failure(
    request_id: str,
    error_code: QueryErrorCode,
) -> QueryFailure:
    messages = {
        QueryErrorCode.CONVERSATION_UNAVAILABLE: "当前会话不可用，请重新开始查询",
        QueryErrorCode.CONVERSATION_CONFLICT: "当前会话已有进行中的查询，请稍后重试",
    }
    return QueryFailure(
        request_id=request_id,
        error_code=error_code,
        error_message=messages[error_code],
        failure_stage="conversation",
        internal_reason=error_code.value,
    )


def _semantic_revision_failure(
    request_id: str,
    error: SemanticRevisionError,
) -> QueryFailure:
    messages = {
        QueryErrorCode.INVALID_REQUEST: "查询问题不能为空或格式错误",
        QueryErrorCode.CONVERSATION_UNAVAILABLE: "当前会话不可用，请重新开始查询",
        QueryErrorCode.CLARIFICATION_REQUIRED: "请明确需要新增或修改的查询条件",
        QueryErrorCode.UNSUPPORTED_ANALYSIS: "当前问题超出单条查询修订范围",
        QueryErrorCode.LLM_ERROR: "暂时无法理解这个查询，请稍后重试",
    }
    return QueryFailure(
        request_id=request_id,
        error_code=error.error_code,
        error_message=messages.get(error.error_code, "暂时无法处理当前查询"),
        failure_stage="semantic_revision",
        internal_reason=error.reason,
    )


def _provider_name(identity_provider: IdentityProviderAdapter) -> str:
    try:
        value = identity_provider.identity_provider
    except Exception:  # noqa: BLE001 - provider identity name must Fail Closed
        return "unknown"
    return value.strip() if isinstance(value, str) and value.strip() else "unknown"


def _result_response(
    result: QueryResult,
    *,
    conversation_id: str | None = None,
    trace_recorder: TraceRecorder | None = None,
) -> JSONResponse:
    with _safe_span(trace_recorder, "response.serialize"):
        if isinstance(result, QuerySuccess):
            if not isinstance(conversation_id, str) or not conversation_id:
                raise RuntimeError("成功查询缺少会话编号")
            return JSONResponse(
                status_code=200,
                content=QuerySuccessResponse(
                    request_id=result.request_id,
                    sql=result.sql,
                    columns=list(result.columns),
                    rows=[list(row) for row in result.rows],
                    row_count=result.row_count,
                    truncated=result.truncated,
                    conversation_id=conversation_id,
                ).model_dump(mode="json"),
            )
        if isinstance(result, QueryFailure):
            return JSONResponse(
                status_code=_HTTP_STATUS_BY_ERROR[result.error_code],
                content=QueryFailureResponse(
                    request_id=result.request_id,
                    error_code=result.error_code,
                    error_message=result.error_message,
                ).model_dump(mode="json"),
            )
        raise RuntimeError("查询服务返回未知结果")


class _FallbackScope:
    def __init__(self, trace_id: str | None = None) -> None:
        self.trace_id = (
            trace_id if _TRACE_ID_RE.fullmatch(trace_id or "") else uuid4().hex
        )

    def __enter__(self) -> "_FallbackScope":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        return False


@contextmanager
def _http_trace_scope(
    recorder: TraceRecorder | None,
    request_id: str,
) -> Iterator[Any]:
    scope: Any = _FallbackScope()
    if recorder is not None:
        try:
            scope = recorder.query_trace(
                QuerySource.HTTP,
                attributes={"chatbi.request.id": request_id},
            )
        except Exception:
            scope = _FallbackScope()
    try:
        scope.__enter__()
    except Exception:
        scope = _FallbackScope()
        scope.__enter__()
    try:
        yield scope
    finally:
        try:
            scope.__exit__(None, None, None)
        except Exception:
            pass


@contextmanager
def _safe_span(
    recorder: TraceRecorder | None,
    name: str,
) -> Iterator[None]:
    if recorder is None:
        yield
        return
    try:
        scope = recorder.span(name)
        scope.__enter__()
    except Exception:
        yield
        return
    try:
        yield
    finally:
        try:
            scope.__exit__(None, None, None)
        except Exception:
            pass


def _request_id_from_header(value: str | None) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return str(uuid4())


def _request_id_from_state(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return (
        value
        if isinstance(value, str) and value.strip()
        else _request_id_from_header(request.headers.get("X-Request-ID"))
    )

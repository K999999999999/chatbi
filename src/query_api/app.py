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
    AuthContext,
    AuthenticationRequired,
    AuthorizationPolicyStore,
    AuthorizationPolicyUnavailable,
    IdentityProviderAdapter,
    IdentityProviderUnavailable,
)
from src.authorization.query_entry import (
    AuthorizedQueryService,
    authorization_failure,
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
}


class QueryService(Protocol):
    """API Adapter 依赖的最小查询服务接口。"""

    def query(self, request: QueryRequest) -> QueryResult:
        """执行一次在线查询。"""


class QueryBody(BaseModel):
    """HTTP 查询请求体。"""

    model_config = ConfigDict(extra="forbid")

    question: StrictStr


class QuerySuccessResponse(BaseModel):
    """HTTP 查询成功响应。"""

    request_id: str
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool


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
    identity_provider: IdentityProviderAdapter | None = None,
    policy_store: AuthorizationPolicyStore | None = None,
) -> FastAPI:
    """创建绑定查询服务的 FastAPI 应用。"""

    provider = identity_provider or _MissingIdentityProvider()
    authorization_store = policy_store or _UnavailablePolicyStore()
    authorized_service = AuthorizedQueryService(service, authorization_store)
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
    app.state.trace_recorder = recorder

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
            422: {"model": QueryFailureResponse},
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
            identity_provider=provider,
            query_service=authorized_service,
        )
        return _result_response(result, trace_recorder=recorder)

    return app


def _authorized_query(
    request: Request,
    *,
    question: str,
    identity_provider: IdentityProviderAdapter,
    query_service: AuthorizedQueryService,
) -> QueryResult:
    request_id = _request_id_from_state(request)
    try:
        auth_context = identity_provider.authenticate(request)
    except AuthenticationRequired:
        return authorization_failure(
            request_id,
            QueryErrorCode.AUTHENTICATION_REQUIRED,
            internal_reason="AUTHENTICATION_REQUIRED",
        )
    except IdentityProviderUnavailable:
        return authorization_failure(
            request_id,
            QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
            internal_reason="IDENTITY_PROVIDER_UNAVAILABLE",
        )
    except Exception as exc:  # noqa: BLE001 - authentication must Fail Closed
        _LOGGER.warning(
            "Identity Provider failure: error_type=%s",
            type(exc).__name__,
        )
        return authorization_failure(
            request_id,
            QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
            internal_reason="IDENTITY_PROVIDER_FAILURE",
        )

    if not isinstance(auth_context, AuthContext):
        _LOGGER.warning(
            "Identity Provider returned invalid context: value_type=%s",
            type(auth_context).__name__,
        )
        return authorization_failure(
            request_id,
            QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
            internal_reason="INVALID_AUTH_CONTEXT",
        )

    return query_service.query(
        QueryRequest(
            question=question,
            request_id=request_id,
        ),
        auth_context=auth_context,
    )


def _result_response(
    result: QueryResult,
    *,
    trace_recorder: TraceRecorder | None = None,
) -> JSONResponse:
    with _safe_span(trace_recorder, "response.serialize"):
        if isinstance(result, QuerySuccess):
            return JSONResponse(
                status_code=200,
                content=QuerySuccessResponse(
                    request_id=result.request_id,
                    sql=result.sql,
                    columns=list(result.columns),
                    rows=[list(row) for row in result.rows],
                    row_count=result.row_count,
                    truncated=result.truncated,
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

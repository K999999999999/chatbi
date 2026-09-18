"""带身份与数据授权门禁的 Application-level Query Entry。"""

import logging
from typing import Protocol
from uuid import uuid4

from src.online_query.contracts import (
    QueryErrorCode,
    QueryFailure,
    QueryRequest,
    QueryResult,
)

from .contracts import (
    AUTHORIZED_RESOURCE,
    QUERY_ACTION,
    READ_ONLY_MODE,
    AuthContext,
    AuthorizationDecision,
    AuthorizationPolicyStore,
    AuthorizationPolicyUnavailable,
)

_LOGGER = logging.getLogger(__name__)


class QueryService(Protocol):
    """授权入口依赖的最小下游查询接口。"""

    def query(self, request: QueryRequest) -> QueryResult:
        """执行已经通过授权的在线查询。"""


class AuthorizedQueryService:
    """在正式 Online Query 之前执行确定性身份与数据授权。"""

    def __init__(
        self,
        query_service: QueryService,
        policy_store: AuthorizationPolicyStore,
        *,
        resource: str = AUTHORIZED_RESOURCE,
        action: str = QUERY_ACTION,
        mode: str = READ_ONLY_MODE,
    ) -> None:
        self._query_service = query_service
        self._policy_store = policy_store
        self._resource = resource
        self._action = action
        self._mode = mode

    def query(
        self,
        request: QueryRequest,
        *,
        auth_context: AuthContext | None,
    ) -> QueryResult:
        request_id = _request_id(request.request_id)
        if auth_context is None:
            return authorization_failure(
                request_id,
                QueryErrorCode.AUTHENTICATION_REQUIRED,
                internal_reason="AUTH_CONTEXT_MISSING",
            )

        try:
            decision = self._policy_store.authorize(
                auth_context,
                resource=self._resource,
                action=self._action,
                mode=self._mode,
            )
        except AuthorizationPolicyUnavailable:
            return authorization_failure(
                request_id,
                QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
                internal_reason="POLICY_STORE_UNAVAILABLE",
            )
        except Exception as exc:  # noqa: BLE001 - authorization must Fail Closed
            _LOGGER.warning(
                "Authorization policy failure: error_type=%s",
                type(exc).__name__,
            )
            return authorization_failure(
                request_id,
                QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
                internal_reason="POLICY_STORE_FAILURE",
            )

        if not isinstance(decision, AuthorizationDecision):
            _LOGGER.warning(
                "Authorization policy returned invalid decision: value_type=%s",
                type(decision).__name__,
            )
            return authorization_failure(
                request_id,
                QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
                internal_reason="INVALID_POLICY_DECISION",
            )

        if not decision.allowed:
            return authorization_failure(
                request_id,
                QueryErrorCode.AUTHORIZATION_DENIED,
                internal_reason=decision.reason_code,
            )

        return self._query_service.query(request)


def _request_id(request_id: str | None) -> str:
    if isinstance(request_id, str) and request_id.strip():
        return request_id.strip()
    return str(uuid4())


def authorization_failure(
    request_id: str,
    error_code: QueryErrorCode,
    *,
    internal_reason: str,
) -> QueryFailure:
    messages = {
        QueryErrorCode.AUTHENTICATION_REQUIRED: "需要有效的身份认证",
        QueryErrorCode.AUTHORIZATION_DENIED: "当前用户没有该数据资源的访问权限",
        QueryErrorCode.AUTHENTICATION_UNAVAILABLE: "身份认证服务暂时不可用",
    }
    return QueryFailure(
        request_id=request_id,
        error_code=error_code,
        error_message=messages[error_code],
        failure_stage="authorization",
        internal_reason=internal_reason,
    )

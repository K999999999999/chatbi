"""带身份与数据授权门禁的 Application-level Query Entry。"""

import logging
from datetime import UTC, datetime
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
    UNKNOWN_AUDIT_PROVIDER,
    UNKNOWN_AUDIT_SUBJECT,
    UNKNOWN_POLICY_VERSION,
    AuditDecision,
    AuditSink,
    AuditSinkUnavailable,
    AuthContext,
    AuthorizationAuditEvent,
    AuthorizationDecision,
    AuthorizationPolicyStore,
    AuthorizationPolicyUnavailable,
)

_LOGGER = logging.getLogger(__name__)


class _UnavailableAuditSink:
    def emit(self, event: AuthorizationAuditEvent) -> None:
        del event
        raise AuditSinkUnavailable("未配置授权审计 Sink")


class QueryService(Protocol):
    """授权入口依赖的最小下游执行接口。"""

    def execute(self, request: QueryRequest) -> QueryResult:
        """执行已经通过授权的在线查询。"""


class AuthorizedQueryService:
    """在正式 Online Query 之前执行确定性身份与数据授权。"""

    def __init__(
        self,
        query_service: QueryService,
        policy_store: AuthorizationPolicyStore,
        *,
        audit_sink: AuditSink | None = None,
        resource: str = AUTHORIZED_RESOURCE,
        action: str = QUERY_ACTION,
        mode: str = READ_ONLY_MODE,
    ) -> None:
        self._query_service = query_service
        self._policy_store = policy_store
        self._audit_sink = _UnavailableAuditSink() if audit_sink is None else audit_sink
        self._resource = resource
        self._action = action
        self._mode = mode

    def query(
        self,
        request: QueryRequest,
        *,
        auth_context: AuthContext | None,
    ) -> QueryResult:
        authorization_result = self.authorize(
            request,
            auth_context=auth_context,
        )
        if authorization_result is not None:
            return authorization_result
        return self.execute_authorized(request)

    def authorize(
        self,
        request: QueryRequest,
        *,
        auth_context: AuthContext | None,
    ) -> QueryResult | None:
        """执行一次身份、策略和允许审计；允许时不进入下游查询。"""

        request_id = _request_id(request.request_id)
        if auth_context is None:
            result = authorization_failure(
                request_id,
                QueryErrorCode.AUTHENTICATION_REQUIRED,
                internal_reason="AUTH_CONTEXT_MISSING",
            )
            return self._audited_failure(
                result,
                request_id=request_id,
                auth_context=None,
                reason_code="AUTH_CONTEXT_MISSING",
                policy_version=UNKNOWN_POLICY_VERSION,
            )

        try:
            decision = self._policy_store.authorize(
                auth_context,
                resource=self._resource,
                action=self._action,
                mode=self._mode,
            )
        except AuthorizationPolicyUnavailable:
            result = authorization_failure(
                request_id,
                QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
                internal_reason="POLICY_STORE_UNAVAILABLE",
            )
            return self._audited_failure(
                result,
                request_id=request_id,
                auth_context=auth_context,
                reason_code="POLICY_STORE_UNAVAILABLE",
                policy_version=UNKNOWN_POLICY_VERSION,
            )
        except Exception as exc:  # noqa: BLE001 - authorization must Fail Closed
            _LOGGER.warning(
                "Authorization policy failure: error_type=%s",
                type(exc).__name__,
            )
            result = authorization_failure(
                request_id,
                QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
                internal_reason="POLICY_STORE_FAILURE",
            )
            return self._audited_failure(
                result,
                request_id=request_id,
                auth_context=auth_context,
                reason_code="POLICY_STORE_FAILURE",
                policy_version=UNKNOWN_POLICY_VERSION,
            )

        if not isinstance(decision, AuthorizationDecision):
            _LOGGER.warning(
                "Authorization policy returned invalid decision: value_type=%s",
                type(decision).__name__,
            )
            result = authorization_failure(
                request_id,
                QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
                internal_reason="INVALID_POLICY_DECISION",
            )
            return self._audited_failure(
                result,
                request_id=request_id,
                auth_context=auth_context,
                reason_code="INVALID_POLICY_DECISION",
                policy_version=UNKNOWN_POLICY_VERSION,
            )

        if not decision.allowed:
            result = authorization_failure(
                request_id,
                QueryErrorCode.AUTHORIZATION_DENIED,
                internal_reason=decision.reason_code,
            )
            return self._audited_failure(
                result,
                request_id=request_id,
                auth_context=auth_context,
                reason_code=decision.reason_code,
                policy_version=decision.policy_version,
            )

        audit_failure = self._emit_audit(
            request_id=request_id,
            auth_context=auth_context,
            decision=AuditDecision.ALLOW,
            reason_code=decision.reason_code,
            policy_version=decision.policy_version,
        )
        if audit_failure:
            return authorization_failure(
                request_id,
                QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
                internal_reason="AUDIT_SINK_UNAVAILABLE",
            )

        return None

    def execute_authorized(self, request: QueryRequest) -> QueryResult:
        """执行已经通过本轮授权的单条查询。"""

        return self._query_service.execute(request)

    def authentication_failure(
        self,
        request_id: str,
        *,
        error_code: QueryErrorCode,
        internal_reason: str,
        identity_provider: str = UNKNOWN_AUDIT_PROVIDER,
    ) -> QueryResult:
        """记录 Provider 失败并返回受控认证错误。"""

        request_id = _request_id(request_id)
        result = authorization_failure(
            request_id,
            error_code,
            internal_reason=internal_reason,
        )
        return self._audited_failure(
            result,
            request_id=request_id,
            auth_context=None,
            identity_provider=identity_provider,
            reason_code=internal_reason,
            policy_version=UNKNOWN_POLICY_VERSION,
        )

    def _audited_failure(
        self,
        result: QueryResult,
        *,
        request_id: str,
        auth_context: AuthContext | None,
        reason_code: str,
        policy_version: str,
        identity_provider: str | None = None,
    ) -> QueryResult:
        if self._emit_audit(
            request_id=request_id,
            auth_context=auth_context,
            identity_provider=identity_provider,
            decision=AuditDecision.DENY,
            reason_code=reason_code,
            policy_version=policy_version,
        ):
            return authorization_failure(
                request_id,
                QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
                internal_reason="AUDIT_SINK_UNAVAILABLE",
            )
        return result

    def _emit_audit(
        self,
        *,
        request_id: str,
        auth_context: AuthContext | None,
        decision: AuditDecision,
        reason_code: str,
        policy_version: str,
        identity_provider: str | None = None,
    ) -> bool:
        try:
            event = AuthorizationAuditEvent(
                request_id=request_id,
                subject_id=(
                    auth_context.subject_id
                    if auth_context is not None
                    else UNKNOWN_AUDIT_SUBJECT
                ),
                identity_provider=(
                    auth_context.identity_provider
                    if auth_context is not None
                    else identity_provider or UNKNOWN_AUDIT_PROVIDER
                ),
                resource=self._resource,
                action=self._action,
                decision=decision,
                reason_code=reason_code,
                policy_version=policy_version,
                timestamp=datetime.now(UTC),
            )
            self._audit_sink.emit(event)
        except Exception as exc:  # noqa: BLE001 - audit failure must Fail Closed
            _LOGGER.warning(
                "Authorization audit failure: error_type=%s",
                type(exc).__name__,
            )
            return True
        return False

    def bind(self, auth_context: AuthContext) -> "BoundAuthorizedQueryService":
        """将显式身份绑定为供内部调用方复用的授权入口。"""

        return BoundAuthorizedQueryService(self, auth_context)


class BoundAuthorizedQueryService:
    """复用 AuthorizedQueryService 的固定身份内部查询入口。"""

    def __init__(
        self,
        authorized_query_service: AuthorizedQueryService,
        auth_context: AuthContext,
    ) -> None:
        self._authorized_query_service = authorized_query_service
        self._auth_context = auth_context

    def query(self, request: QueryRequest) -> QueryResult:
        return self._authorized_query_service.query(
            request,
            auth_context=self._auth_context,
        )


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

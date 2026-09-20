"""ChatBI 身份与数据授权核心。"""

from .audit import InMemoryAuditSink
from .auth_service import (
    AuthenticationFailed,
    AuthService,
    SessionExpired,
)
from .contracts import (
    UNKNOWN_AUDIT_PROVIDER,
    UNKNOWN_AUDIT_SUBJECT,
    UNKNOWN_POLICY_VERSION,
    AuditDecision,
    AuditSink,
    AuditSinkUnavailable,
    AuthContext,
    AuthenticationRequired,
    AuthorizationAuditEvent,
    AuthorizationDecision,
    AuthorizationDecisionCode,
    AuthorizationPolicyStore,
    AuthorizationPolicyUnavailable,
    IdentityProviderAdapter,
    IdentityProviderUnavailable,
    StaticAuthorizationPolicyStore,
    StaticIdentityProviderAdapter,
)
from .passwords import hash_password, validate_password, verify_password
from .query_entry import (
    AuthorizedQueryService,
    BoundAuthorizedQueryService,
    authorization_failure,
)

__all__ = [
    "UNKNOWN_AUDIT_PROVIDER",
    "UNKNOWN_AUDIT_SUBJECT",
    "UNKNOWN_POLICY_VERSION",
    "AuditDecision",
    "AuditSink",
    "AuditSinkUnavailable",
    "AuthContext",
    "AuthService",
    "AuthenticationFailed",
    "AuthenticationRequired",
    "AuthorizationAuditEvent",
    "AuthorizationDecision",
    "AuthorizationDecisionCode",
    "AuthorizationPolicyStore",
    "AuthorizationPolicyUnavailable",
    "AuthorizedQueryService",
    "BoundAuthorizedQueryService",
    "IdentityProviderAdapter",
    "IdentityProviderUnavailable",
    "InMemoryAuditSink",
    "SessionExpired",
    "StaticAuthorizationPolicyStore",
    "StaticIdentityProviderAdapter",
    "authorization_failure",
    "hash_password",
    "validate_password",
    "verify_password",
]

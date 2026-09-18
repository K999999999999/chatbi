"""ChatBI 身份与数据授权核心。"""

from .audit import InMemoryAuditSink
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
from .query_entry import (
    AuthorizedQueryService,
    BoundAuthorizedQueryService,
    authorization_failure,
)

__all__ = [
    "AuthContext",
    "AuditDecision",
    "AuditSink",
    "AuditSinkUnavailable",
    "AuthenticationRequired",
    "AuthorizationDecision",
    "AuthorizationDecisionCode",
    "AuthorizationAuditEvent",
    "AuthorizationPolicyStore",
    "AuthorizationPolicyUnavailable",
    "AuthorizedQueryService",
    "BoundAuthorizedQueryService",
    "IdentityProviderUnavailable",
    "InMemoryAuditSink",
    "IdentityProviderAdapter",
    "StaticAuthorizationPolicyStore",
    "StaticIdentityProviderAdapter",
    "UNKNOWN_AUDIT_PROVIDER",
    "UNKNOWN_AUDIT_SUBJECT",
    "UNKNOWN_POLICY_VERSION",
    "authorization_failure",
]

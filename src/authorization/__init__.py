"""ChatBI 身份与数据授权核心。"""

from .audit import InMemoryAuditSink
from .audit_service import AuditRecord, AuditUnavailable, PersistentAuditSink
from .auth_service import (
    AuthenticationFailed,
    AuthService,
    LocalSessionIdentityProvider,
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
from .rbac import RoleAuthorizationPolicyStore

__all__ = [
    "UNKNOWN_AUDIT_PROVIDER",
    "UNKNOWN_AUDIT_SUBJECT",
    "UNKNOWN_POLICY_VERSION",
    "AuditDecision",
    "AuditRecord",
    "AuditSink",
    "AuditSinkUnavailable",
    "AuditUnavailable",
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
    "LocalSessionIdentityProvider",
    "RoleAuthorizationPolicyStore",
    "PersistentAuditSink",
    "SessionExpired",
    "StaticAuthorizationPolicyStore",
    "StaticIdentityProviderAdapter",
    "authorization_failure",
    "hash_password",
    "validate_password",
    "verify_password",
]
